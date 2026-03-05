#!/usr/bin/env bash

##############################################################################
# Deploy-v2 Deployment Script
# Manages deployment operations for production and staging environments
#
# Usage:
#   ./scripts/deploy.sh <command> [--env production|staging]
#
# Commands:
#   init      - Initial setup (first time deployment)
#   update    - Update existing deployment
#   restart   - Restart all services
#   stop      - Stop all services
#   logs      - View logs
#   status    - Check service status
##############################################################################

set -euo pipefail

# Script directory and imports
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_ROOT="$(dirname "$SCRIPT_DIR")"

# Source common libraries
source "$SCRIPT_DIR/common/common.sh"
source "$SCRIPT_DIR/common/validation.sh"
source "$SCRIPT_DIR/common/template-engine.sh"

# Default values
COMMAND=""
ENVIRONMENT="production"

# Parse arguments
parse_arguments() {
    if [[ $# -eq 0 ]]; then
        show_usage
        exit 1
    fi

    COMMAND="$1"
    shift

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
                print_error "Unknown option: $1"
                show_usage
                exit 1
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
Deploy-v2 Deployment Script

Usage: $0 <command> [--env production|staging]

Commands:
  init      - Initial setup (first time deployment)
  update    - Update existing deployment (pull, build, migrate, restart)
  restart   - Restart all services
  stop      - Stop all services
  logs      - View logs (follow mode)
  status    - Check service status and health

Options:
  --env ENV     Environment to deploy (production or staging, default: production)
  -h, --help    Show this help message

Examples:
  $0 init --env production        # Initial production deployment
  $0 update --env staging           # Update staging environment
  $0 logs --env production        # View production logs
  $0 status --env staging           # Check staging status

EOF
}

# Generate Redis password configuration
generate_redis_password_config() {
    print_info "Generating Redis password configuration..."

    if [[ -z "${REDIS_PASSWORD:-}" ]]; then
        print_error "REDIS_PASSWORD is not set in .env.${ENVIRONMENT}"
        exit 1
    fi

    local redis_conf_dir="$DEPLOY_ROOT/generated/redis"
    mkdir -p "$redis_conf_dir"

    # Generate redis-password.conf
    cat > "$redis_conf_dir/redis-password.conf" << EOF
# Redis Password Configuration (auto-generated - DO NOT COMMIT)
requirepass ${REDIS_PASSWORD}
EOF

    chmod 600 "$redis_conf_dir/redis-password.conf"
    print_success "Redis password configuration generated"
}

# Check prerequisites
check_prerequisites() {
    print_info "Checking prerequisites..."

    # Check Docker
    if ! command_exists docker; then
        print_error "Docker is not installed"
        print_info "Install from: https://docs.docker.com/get-docker/"
        exit 1
    fi

    # Check Docker daemon
    if ! docker info &>/dev/null; then
        print_error "Docker daemon is not running"
        print_info "Start Docker and try again"
        exit 1
    fi

    # Check Docker Compose and set command
    if ! validate_docker_compose; then
        print_error "Docker Compose is not installed"
        print_info "Install from: https://docs.docker.com/compose/install/"
        exit 1
    fi

    # Set compose command
    COMPOSE="$(get_docker_compose_cmd)"

    # Check environment file
    local env_file="$DEPLOY_ROOT/.env.${ENVIRONMENT}"
    if [[ ! -f "$env_file" ]]; then
        print_error ".env.${ENVIRONMENT} not found"
        print_info "Run: ./scripts/setup.sh --force"
        exit 1
    fi

    # Load environment variables
    print_info "Loading environment variables..."
    set -a
    source "$env_file"
    set +a

    # Load config for PROJECT_PREFIX
    if [[ -f "$DEPLOY_ROOT/config.env" ]]; then
        source "$DEPLOY_ROOT/config.env"
        derive_config_values "$ENVIRONMENT"
    else
        print_error "config.env not found"
        exit 1
    fi

    # Validate critical variables
    local critical_vars=("REDIS_PASSWORD" "POSTGRES_PASSWORD" "SECRET_KEY")
    for var in "${critical_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            print_error "$var is not set in .env.${ENVIRONMENT}"
            exit 1
        fi
    done

    # Generate Redis password config
    generate_redis_password_config

    # Set compose file path
    COMPOSE_FILE="$DEPLOY_ROOT/generated/docker-compose.${ENVIRONMENT}.yml"
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        print_error "Docker Compose file not found: $COMPOSE_FILE"
        print_info "Run: ./scripts/setup.sh --force"
        exit 1
    fi

    print_success "Prerequisites check passed"
}

# Initial setup (first time deployment)
initial_setup() {
    print_header "Initial Deployment - ${ENVIRONMENT}"

    check_prerequisites

    # Load config for domains
    source "$DEPLOY_ROOT/config.env"
    local api_domain="${API_SUBDOMAIN}.${BASE_DOMAIN}"
    local flower_domain="${FLOWER_SUBDOMAIN}.${BASE_DOMAIN}"

    # Check if domains are pointed to server
    print_separator
    print_warning "DNS Configuration Required:"
    echo "  • $api_domain → Server IP"
    echo "  • $flower_domain → Server IP"
    echo ""

    if ! confirm_action "Have you configured DNS records?"; then
        print_error "Please configure DNS records before proceeding"
        exit 1
    fi

    # Create necessary directories
    print_info "Creating directories..."
    mkdir -p "$DEPLOY_ROOT/certbot/conf"
    mkdir -p "$DEPLOY_ROOT/certbot/www"
    mkdir -p "$DEPLOY_ROOT/ssl"
    mkdir -p "$DEPLOY_ROOT/generated/nginx"
    mkdir -p "$DEPLOY_ROOT/generated/redis"
    print_success "Directories created"

    # Pull latest images
    print_info "Pulling Docker images..."
    $COMPOSE -f "$COMPOSE_FILE" pull

    # Build application images
    print_info "Building application images..."
    $COMPOSE -f "$COMPOSE_FILE" build --no-cache

    # Start services (without nginx initially for SSL setup)
    print_info "Starting services..."

    if [[ "$ENVIRONMENT" == "staging" ]]; then
        # Staging: start with containerized PostgreSQL
        $COMPOSE -f "$COMPOSE_FILE" up -d postgres redis
        print_info "Waiting for database to be ready..."
        sleep 15
        $COMPOSE -f "$COMPOSE_FILE" up -d api celery_worker celery_beat flower
        sleep 10
        # Start monitoring stack
        print_info "Starting monitoring services..."
        $COMPOSE -f "$COMPOSE_FILE" up -d prometheus grafana
    else
        # Production: no containerized PostgreSQL
        $COMPOSE -f "$COMPOSE_FILE" up -d redis api celery_worker celery_beat flower
        sleep 10
        # Start monitoring stack
        print_info "Starting monitoring services..."
        $COMPOSE -f "$COMPOSE_FILE" up -d prometheus grafana
    fi

    # Wait for services to be healthy
    print_info "Waiting for services to be healthy..."
    sleep 30

    # Run database migrations
    print_info "Running database migrations..."
    $COMPOSE -f "$COMPOSE_FILE" exec -T api alembic upgrade head || {
        print_warning "Migration failed, trying with run instead of exec..."
        $COMPOSE -f "$COMPOSE_FILE" run --rm api alembic upgrade head
    }

    # Check health
    print_info "Service status:"
    $COMPOSE -f "$COMPOSE_FILE" ps

    print_separator
    print_success "Initial setup completed!"
    echo ""
    print_warning "Next steps:"
    echo "  1. Setup SSL: ./scripts/ssl.sh setup --env ${ENVIRONMENT}"
    echo "  2. Start nginx: $COMPOSE -f $COMPOSE_FILE up -d nginx"
    echo "  3. Monitor logs: ./scripts/deploy.sh logs --env ${ENVIRONMENT}"
    echo "  4. Check status: ./scripts/deploy.sh status --env ${ENVIRONMENT}"
    echo ""
}

# Update existing deployment
update_deployment() {
    print_header "Updating Deployment - ${ENVIRONMENT}"

    check_prerequisites

    # Pull latest code changes
    print_info "Pulling latest changes from git..."
    cd "$DEPLOY_ROOT/.."
    local current_branch=$(git branch --show-current)
    print_info "Current branch: $current_branch"
    git pull origin "$current_branch"

    # Backup database
    if [[ -f "$SCRIPT_DIR/backup.sh" ]]; then
        print_info "Creating backup..."
        "$SCRIPT_DIR/backup.sh" db --env "$ENVIRONMENT" || print_warning "Backup script not ready yet"
    fi

    # Pull latest images
    print_info "Pulling latest Docker images..."
    $COMPOSE -f "$COMPOSE_FILE" pull

    # Build updated images
    print_info "Building updated images..."
    $COMPOSE -f "$COMPOSE_FILE" build

    # Run database migrations
    print_info "Running database migrations..."
    $COMPOSE -f "$COMPOSE_FILE" exec -T api alembic upgrade head || {
        print_warning "Migration failed with exec, trying run..."
        $COMPOSE -f "$COMPOSE_FILE" run --rm api alembic upgrade head
    }

    # Restart services with zero-downtime (rolling update)
    print_info "Restarting services (zero-downtime)..."

    # Restart background workers first
    print_info "Restarting Celery workers..."
    $COMPOSE -f "$COMPOSE_FILE" up -d --force-recreate --no-deps celery_worker celery_beat
    sleep 5

    # Restart monitoring
    print_info "Restarting Flower..."
    $COMPOSE -f "$COMPOSE_FILE" up -d --force-recreate --no-deps flower
    sleep 3

    # Restart API (critical - do last)
    print_info "Restarting API..."
    $COMPOSE -f "$COMPOSE_FILE" up -d --force-recreate --no-deps api
    sleep 5

    # Restart nginx
    print_info "Restarting nginx..."
    $COMPOSE -f "$COMPOSE_FILE" up -d --force-recreate --no-deps nginx

    # Restart monitoring stack
    print_info "Restarting monitoring services..."
    $COMPOSE -f "$COMPOSE_FILE" up -d --force-recreate --no-deps prometheus grafana

    # Clean up old images
    print_info "Cleaning up old Docker images..."
    docker image prune -f

    print_separator
    print_success "Deployment updated successfully!"
    echo ""
    print_info "Service status:"
    $COMPOSE -f "$COMPOSE_FILE" ps
}

# Restart all services
restart_services() {
    print_header "Restarting Services - ${ENVIRONMENT}"

    check_prerequisites

    print_info "Restarting all services..."
    $COMPOSE -f "$COMPOSE_FILE" restart

    print_separator
    print_success "Services restarted!"
    echo ""
    $COMPOSE -f "$COMPOSE_FILE" ps
}

# Stop all services
stop_services() {
    print_header "Stopping Services - ${ENVIRONMENT}"

    check_prerequisites

    print_info "Stopping all services..."
    $COMPOSE -f "$COMPOSE_FILE" down

    print_separator
    print_success "Services stopped!"
}

# View logs
view_logs() {
    print_header "Viewing Logs - ${ENVIRONMENT}"

    check_prerequisites

    print_info "Viewing logs (Ctrl+C to exit)..."
    $COMPOSE -f "$COMPOSE_FILE" logs -f --tail=100
}

# Check status
check_status() {
    print_header "Service Status - ${ENVIRONMENT}"

    check_prerequisites

    # Service status
    print_info "Docker Compose services:"
    $COMPOSE -f "$COMPOSE_FILE" ps
    echo ""

    # Container health
    print_info "Container health:"
    docker ps --filter "name=${CONTAINER_PREFIX}_" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" || {
        print_warning "No containers found with prefix: ${CONTAINER_PREFIX}_"
        docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    }
    echo ""

    # Network info
    print_info "Network:"
    docker network ls --filter "name=${PROJECT_PREFIX}" --format "table {{.Name}}\t{{.Driver}}\t{{.Scope}}" || true
    echo ""

    # Volume info
    print_info "Volumes:"
    docker volume ls --filter "name=${PROJECT_PREFIX}" --format "table {{.Name}}\t{{.Driver}}" || true
    echo ""

    # Disk usage
    print_info "System disk usage:"
    df -h | grep -E '^Filesystem|/$' || df -h
    echo ""

    print_info "Docker disk usage:"
    docker system df
}

# Main execution
main() {
    parse_arguments "$@"

    case "$COMMAND" in
        init)
            initial_setup
            ;;
        update)
            update_deployment
            ;;
        restart)
            restart_services
            ;;
        stop)
            stop_services
            ;;
        logs)
            view_logs
            ;;
        status)
            check_status
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
