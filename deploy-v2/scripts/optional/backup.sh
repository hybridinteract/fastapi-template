#!/usr/bin/env bash

##############################################################################
# Backup and Restore Script
# Backs up PostgreSQL database, Redis data, logs, and configuration
#
# Usage:
#   ./scripts/backup.sh <command> [--env production|staging] [backup_file]
#
# Commands:
#   full       - Create full backup (database + redis + logs + config)
#   db         - Backup database only
#   restore    - Restore from backup file
##############################################################################

set -euo pipefail

# Script directory and imports
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPTS_ROOT="$(dirname "$SCRIPT_DIR")"
readonly DEPLOY_ROOT="$(dirname "$SCRIPTS_ROOT")"

# Source common libraries
source "$SCRIPTS_ROOT/common/common.sh"
source "$SCRIPTS_ROOT/common/validation.sh"
source "$SCRIPTS_ROOT/common/template-engine.sh"

# Default values
COMMAND="full"
ENVIRONMENT="production"
RESTORE_FILE=""

# Timestamp for backup files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Parse arguments
parse_arguments() {
    if [[ $# -gt 0 ]]; then
        COMMAND="$1"
        shift
    fi

    while [[ $# -gt 0 ]]; do
        case $1 in
            --env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            *)
                # Assume it's a restore file
                RESTORE_FILE="$1"
                shift
                ;;
        esac
    done

    # Validate environment
    if [[ "$ENVIRONMENT" != "production" && "$ENVIRONMENT" != "staging" ]]; then
        print_error "Invalid environment: $ENVIRONMENT"
        print_info "Must be 'production' or 'staging'"
        exit 1
    fi
}

show_usage() {
    cat << EOF
Backup and Restore Script

Usage: $0 <command> [--env production|staging] [backup_file]

Commands:
  full       - Create full backup (database, redis, logs, config)
  db         - Backup database only
  restore    - Restore from backup file

Options:
  --env ENV     Environment to backup (production or staging, default: production)
  -h, --help    Show this help message

Examples:
  $0 full --env production                        # Full production backup
  $0 db --env staging                                # Staging database backup only
  $0 restore --env production backups/backup.tar.gz  # Restore from file

Notes:
  • Backups are stored in: deploy-v2/backups/
  • Old backups are automatically cleaned up (keeps last 7)
  • Database backups use pg_dump for PostgreSQL
  • Redis backups use RDB file copy

EOF
}

# Load configuration
load_backup_config() {
    # Check Docker Compose
    if ! validate_docker_compose; then
        print_error "Docker Compose not available"
        exit 1
    fi
    COMPOSE="$(get_docker_compose_cmd)"

    # Load config.env
    if [[ ! -f "$DEPLOY_ROOT/config.env" ]]; then
        print_error "config.env not found"
        exit 1
    fi

    set -a
    source "$DEPLOY_ROOT/config.env"
    set +a

    # Load environment file
    local env_file="$DEPLOY_ROOT/.env.${ENVIRONMENT}"
    if [[ ! -f "$env_file" ]]; then
        print_error ".env.${ENVIRONMENT} not found"
        exit 1
    fi

    set -a
    source "$env_file"
    set +a

    # Derive configuration values
    derive_config_values "$ENVIRONMENT"

    # Set compose file
    COMPOSE_FILE="$DEPLOY_ROOT/generated/docker-compose.${ENVIRONMENT}.yml"

    # Set backup directory and name
    BACKUP_DIR="$DEPLOY_ROOT/backups"
    BACKUP_NAME="${PROJECT_PREFIX}_${ENVIRONMENT}_backup_${TIMESTAMP}"
}

# Create backup directory
create_backup_dir() {
    mkdir -p "$BACKUP_DIR/$BACKUP_NAME"
    print_info "Backup directory created: $BACKUP_DIR/$BACKUP_NAME"
}

# Backup PostgreSQL database
backup_database() {
    print_info "Backing up PostgreSQL database..."

    # Check required variables
    if [[ -z "${POSTGRES_HOST:-}" ]] || [[ -z "${POSTGRES_DB:-}" ]] || [[ -z "${POSTGRES_USER:-}" ]]; then
        print_error "Database credentials not configured"
        exit 1
    fi

    local port="${POSTGRES_PORT:-5432}"

    # Create custom format dump (for pg_restore)
    print_info "Creating database dump (custom format)..."
    PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
        -h "$POSTGRES_HOST" \
        -p "$port" \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        -F c \
        -f "$BACKUP_DIR/$BACKUP_NAME/database.dump" || {
        print_error "Database backup failed"
        return 1
    }

    # Create SQL dump (for inspection/editing)
    print_info "Creating database dump (SQL format)..."
    PGPASSWORD="$POSTGRES_PASSWORD" pg_dump \
        -h "$POSTGRES_HOST" \
        -p "$port" \
        -U "$POSTGRES_USER" \
        -d "$POSTGRES_DB" \
        --clean \
        --if-exists \
        -f "$BACKUP_DIR/$BACKUP_NAME/database.sql" || {
        print_warning "SQL dump failed (custom dump succeeded)"
    }

    print_success "Database backup completed"
}

# Backup Redis data
backup_redis() {
    print_info "Backing up Redis data..."

    local redis_container="${CONTAINER_PREFIX}_redis"

    # Check if Redis container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${redis_container}$"; then
        print_warning "Redis container not running, skipping Redis backup"
        return 0
    fi

    # Trigger Redis save
    docker exec "$redis_container" redis-cli -a "$REDIS_PASSWORD" SAVE 2>/dev/null || {
        print_warning "Could not trigger Redis save"
    }

    # Copy RDB file
    docker cp "${redis_container}:/data/dump.rdb" "$BACKUP_DIR/$BACKUP_NAME/redis.rdb" 2>/dev/null || {
        print_warning "Redis backup failed or no data to backup"
        return 0
    }

    print_success "Redis backup completed"
}

# Backup application logs
backup_logs() {
    print_info "Backing up application logs..."

    # Check for logs in project root
    local logs_dir
    for possible_dir in "$DEPLOY_ROOT/../logs" "$DEPLOY_ROOT/logs"; do
        if [[ -d "$possible_dir" ]]; then
            logs_dir="$possible_dir"
            break
        fi
    done

    if [[ -n "${logs_dir:-}" ]]; then
        cp -r "$logs_dir" "$BACKUP_DIR/$BACKUP_NAME/" 2>/dev/null || {
            print_warning "Could not copy all logs"
        }
        print_success "Logs backup completed"
    else
        print_warning "No logs directory found, skipping"
    fi
}

# Backup configuration files
backup_config() {
    print_info "Backing up configuration files..."

    # Backup environment file
    cp "$DEPLOY_ROOT/.env.${ENVIRONMENT}" "$BACKUP_DIR/$BACKUP_NAME/env.${ENVIRONMENT}.backup"

    # Backup config.env (sanitized - remove passwords)
    grep -v "PASSWORD" "$DEPLOY_ROOT/config.env" > "$BACKUP_DIR/$BACKUP_NAME/config.env.backup" 2>/dev/null || {
        cp "$DEPLOY_ROOT/config.env" "$BACKUP_DIR/$BACKUP_NAME/config.env.backup"
    }

    # Create metadata file
    cat > "$BACKUP_DIR/$BACKUP_NAME/backup_info.txt" <<EOF
Backup Information
==================
Timestamp: $(date)
Environment: $ENVIRONMENT
Project: $PROJECT_PREFIX
Hostname: $(hostname)
Git Branch: $(cd "$DEPLOY_ROOT/.." && git branch --show-current 2>/dev/null || echo "N/A")
Git Commit: $(cd "$DEPLOY_ROOT/.." && git rev-parse --short HEAD 2>/dev/null || echo "N/A")
Database: $POSTGRES_DB
Database Host: $POSTGRES_HOST
EOF

    print_success "Configuration backup completed"
}

# Compress backup
compress_backup() {
    print_info "Compressing backup..."

    cd "$BACKUP_DIR"
    tar -czf "$BACKUP_NAME.tar.gz" "$BACKUP_NAME"
    rm -rf "$BACKUP_NAME"

    local size=$(du -h "$BACKUP_NAME.tar.gz" | cut -f1)
    print_success "Backup compressed: $BACKUP_DIR/$BACKUP_NAME.tar.gz"
    print_info "Backup size: $size"
}

# Cleanup old backups
cleanup_old_backups() {
    print_info "Cleaning up old backups (keeping last 7)..."

    cd "$BACKUP_DIR"

    # Clean up backups for this environment
    local pattern="${PROJECT_PREFIX}_${ENVIRONMENT}_backup_*.tar.gz"
    local count=$(ls -t $pattern 2>/dev/null | wc -l)

    if [[ $count -gt 7 ]]; then
        ls -t $pattern | tail -n +8 | xargs rm -f
        print_success "Old backups cleaned up"
    else
        print_info "No old backups to clean up"
    fi
}

# Full backup
full_backup() {
    print_header "Full Backup - ${ENVIRONMENT}"

    load_backup_config

    print_info "Creating backup: $BACKUP_NAME"
    echo ""

    create_backup_dir
    backup_database
    backup_redis
    backup_logs
    backup_config
    compress_backup
    cleanup_old_backups

    print_separator
    print_success "Full backup completed successfully!"
    echo ""
    print_info "Backup location: $BACKUP_DIR/$BACKUP_NAME.tar.gz"
    echo ""
}

# Database-only backup
database_only_backup() {
    print_header "Database Backup - ${ENVIRONMENT}"

    load_backup_config

    print_info "Creating database backup: $BACKUP_NAME"
    echo ""

    create_backup_dir
    backup_database
    backup_config  # Include config for restore context
    compress_backup

    print_separator
    print_success "Database backup completed successfully!"
    echo ""
    print_info "Backup location: $BACKUP_DIR/$BACKUP_NAME.tar.gz"
    echo ""
}

# Restore from backup
restore_backup() {
    print_header "Restore from Backup - ${ENVIRONMENT}"

    if [[ -z "$RESTORE_FILE" ]]; then
        print_error "Please specify backup file to restore"
        echo ""
        print_info "Usage: $0 restore --env $ENVIRONMENT <backup_file.tar.gz>"
        echo ""
        print_info "Available backups:"
        ls -lh "$DEPLOY_ROOT/backups"/*.tar.gz 2>/dev/null || echo "  No backups found"
        exit 1
    fi

    if [[ ! -f "$RESTORE_FILE" ]]; then
        print_error "Backup file not found: $RESTORE_FILE"
        exit 1
    fi

    load_backup_config

    print_warning "DANGER: This will restore data from backup"
    echo ""
    echo "  Source: $RESTORE_FILE"
    echo "  Target Environment: $ENVIRONMENT"
    echo "  Target Database: $POSTGRES_DB @ $POSTGRES_HOST"
    echo ""
    print_warning "This will OVERWRITE current data!"
    echo ""

    if ! confirm_action "Are you absolutely sure you want to continue?"; then
        print_info "Restore cancelled"
        exit 0
    fi

    # Extract backup
    print_separator
    print_info "Extracting backup..."
    local restore_dir="$BACKUP_DIR/restore_$(date +%s)"
    mkdir -p "$restore_dir"
    tar -xzf "$RESTORE_FILE" -C "$restore_dir"

    local backup_name=$(basename "$RESTORE_FILE" .tar.gz)
    local backup_path="$restore_dir/$backup_name"

    # Show backup info
    if [[ -f "$backup_path/backup_info.txt" ]]; then
        print_separator
        print_info "Backup information:"
        cat "$backup_path/backup_info.txt"
    fi

    print_separator

    # Restore database
    if [[ -f "$backup_path/database.dump" ]]; then
        print_info "Restoring database..."
        print_warning "Stopping API and Celery services..."

        $COMPOSE -f "$COMPOSE_FILE" stop api celery_worker celery_beat 2>/dev/null || {
            print_warning "Could not stop services (may not be running)"
        }

        sleep 3

        print_info "Running pg_restore..."
        PGPASSWORD="$POSTGRES_PASSWORD" pg_restore \
            -h "$POSTGRES_HOST" \
            -p "${POSTGRES_PORT:-5432}" \
            -U "$POSTGRES_USER" \
            -d "$POSTGRES_DB" \
            --clean \
            --if-exists \
            --no-owner \
            --no-acl \
            "$backup_path/database.dump" || {
            print_error "Database restore failed"
            exit 1
        }

        print_success "Database restored"
    else
        print_warning "No database backup found in archive"
    fi

    # Restore Redis
    if [[ -f "$backup_path/redis.rdb" ]]; then
        print_info "Restoring Redis data..."

        local redis_container="${CONTAINER_PREFIX}_redis"

        $COMPOSE -f "$COMPOSE_FILE" stop redis 2>/dev/null || true
        sleep 2

        docker cp "$backup_path/redis.rdb" "${redis_container}:/data/dump.rdb" 2>/dev/null || {
            print_warning "Could not copy Redis data"
        }

        $COMPOSE -f "$COMPOSE_FILE" start redis
        sleep 3

        print_success "Redis data restored"
    else
        print_warning "No Redis backup found in archive"
    fi

    # Restart services
    print_separator
    print_info "Restarting services..."
    $COMPOSE -f "$COMPOSE_FILE" start api celery_worker celery_beat 2>/dev/null || {
        print_warning "Could not start all services"
    }

    # Cleanup
    rm -rf "$restore_dir"

    print_separator
    print_success "Restore completed successfully!"
    echo ""
    print_info "Next steps:"
    echo "  • Check service status: ./scripts/deploy.sh status --env $ENVIRONMENT"
    echo "  • View logs: ./scripts/deploy.sh logs --env $ENVIRONMENT"
    echo ""
}

# Main execution
main() {
    parse_arguments "$@"

    case "$COMMAND" in
        full)
            full_backup
            ;;
        db|database)
            database_only_backup
            ;;
        restore)
            restore_backup
            ;;
        *)
            print_error "Unknown command: $COMMAND"
            show_usage
            exit 1
            ;;
    esac
}

# Run main
main "$@"
