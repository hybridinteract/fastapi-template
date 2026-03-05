#!/usr/bin/env bash

##############################################################################
# Deploy-v2 Setup Script
# Complete initial setup: system checks, configuration, and generation
#
# Usage: ./scripts/setup.sh [--force]
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
FORCE_REGENERATE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            FORCE_REGENERATE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--force]"
            echo ""
            echo "Complete setup wizard for deploy-v2:"
            echo "  • System prerequisite checks (Docker, ports, etc.)"
            echo "  • Interactive configuration collection"
            echo "  • Automatic template generation"
            echo ""
            echo "Options:"
            echo "  --force       Force regenerate even if config exists"
            echo "  -h, --help    Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# ==================== SYSTEM CHECKS ====================

check_system_prerequisites() {
    print_header "System Prerequisites Check"

    local errors=0
    local warnings=0

    # Check Docker
    print_info "Checking Docker..."
    if command_exists docker; then
        local docker_version=$(docker --version | cut -d' ' -f3 | tr -d ',')
        print_success "Docker installed: $docker_version"

        # Check if Docker daemon is running
        if docker info &>/dev/null; then
            print_success "Docker daemon is running"
        else
            print_error "Docker daemon is not running"
            print_info "Start Docker and try again"
            ((errors++))
        fi
    else
        print_error "Docker is not installed"
        print_info "Install from: https://docs.docker.com/get-docker/"
        ((errors++))
    fi

    # Check Docker Compose
    print_info "Checking Docker Compose..."
    if docker compose version &>/dev/null; then
        local compose_version=$(docker compose version --short 2>/dev/null || docker compose version | grep -oP 'v?\K[0-9.]+' | head -1)
        print_success "Docker Compose (V2) installed: $compose_version"
    elif command_exists docker-compose; then
        local compose_version=$(docker-compose --version | grep -oP 'v?\K[0-9.]+' | head -1)
        print_success "Docker Compose (V1) installed: $compose_version"
        print_warning "Consider upgrading to Docker Compose V2"
        ((warnings++))
    else
        print_error "Docker Compose is not installed"
        print_info "Install from: https://docs.docker.com/compose/install/"
        ((errors++))
    fi

    # Check required tools
    print_info "Checking required tools..."

    if command_exists openssl; then
        print_success "OpenSSL installed"
    else
        print_error "OpenSSL not found (required for generating secrets)"
        ((errors++))
    fi

    if command_exists git; then
        print_success "Git installed"
    else
        print_warning "Git not found (recommended but not required)"
        ((warnings++))
    fi

    # Check port availability
    print_info "Checking port availability..."
    local ports=(80 443)
    for port in "${ports[@]}"; do
        if command_exists netstat; then
            if netstat -tuln 2>/dev/null | grep -q ":$port "; then
                print_warning "Port $port is already in use"
                print_info "This may cause issues during deployment"
                ((warnings++))
            else
                print_success "Port $port is available"
            fi
        elif command_exists ss; then
            if ss -tuln 2>/dev/null | grep -q ":$port "; then
                print_warning "Port $port is already in use"
                print_info "This may cause issues during deployment"
                ((warnings++))
            else
                print_success "Port $port is available"
            fi
        else
            print_warning "Cannot check port availability (netstat/ss not found)"
            ((warnings++))
            break
        fi
    done

    # Check disk space
    print_info "Checking disk space..."
    local available_gb
    if [[ "$OSTYPE" == "darwin"* ]]; then
        available_gb=$(df -g . | tail -1 | awk '{print $4}')
    else
        available_gb=$(df -BG . | tail -1 | awk '{print $4}' | tr -d 'G')
    fi

    if [[ $available_gb -ge 10 ]]; then
        print_success "Disk space available: ${available_gb}GB"
    elif [[ $available_gb -ge 5 ]]; then
        print_warning "Low disk space: ${available_gb}GB (recommended: 10GB+)"
        ((warnings++))
    else
        print_error "Very low disk space: ${available_gb}GB (minimum: 5GB)"
        ((errors++))
    fi

    # Summary
    print_separator
    if [[ $errors -gt 0 ]]; then
        print_error "System prerequisites check failed with $errors error(s) and $warnings warning(s)"
        print_info "Please fix the errors above before proceeding"
        return 1
    elif [[ $warnings -gt 0 ]]; then
        print_warning "System prerequisites check passed with $warnings warning(s)"
        print_info "You can proceed, but consider addressing the warnings"
        return 0
    else
        print_success "All system prerequisites met!"
        return 0
    fi
}

# ==================== CONFIGURATION ====================

collect_configuration() {
    print_header "Configuration Collection"

    # Check if config.env already exists
    if [[ -f "$DEPLOY_ROOT/config.env" && "$FORCE_REGENERATE" != "true" ]]; then
        print_warning "config.env already exists"
        if ! confirm_action "Do you want to reinitialize? (This will backup existing config)"; then
            print_info "Using existing configuration"
            return 0
        fi
        # Backup existing config
        local backup="$DEPLOY_ROOT/config.env.backup.$(date +%Y%m%d_%H%M%S)"
        cp "$DEPLOY_ROOT/config.env" "$backup"
        print_success "Existing config backed up to: $(basename $backup)"
    fi

    # Ask which environment to configure
    print_separator
    echo "Which environment(s) do you want to configure?"
    echo ""
    echo "  1) Production only"
    echo "  2) Staging only"
    echo "  3) Both Production and Staging"
    echo ""

    local env_choice
    while true; do
        read -p "Enter your choice (1-3): " env_choice
        if [[ "$env_choice" =~ ^[1-3]$ ]]; then
            break
        fi
        print_error "Invalid choice. Please enter 1, 2, or 3."
    done

    local setup_production=false
    local setup_staging=false

    case $env_choice in
        1)
            setup_production=true
            print_success "Selected: Production only"
            ;;
        2)
            setup_staging=true
            print_success "Selected: Staging only"
            ;;
        3)
            setup_production=true
            setup_staging=true
            print_success "Selected: Both Production and Staging"
            ;;
    esac

    # Collect configuration
    print_separator
    echo "Please provide your project configuration:"
    echo ""

    # Project name
    local project_name
    while true; do
        read -p "Project name (e.g., myhotel, bookingapp): " project_name
        if validate_project_name "$project_name"; then
            break
        fi
    done

    # Base domain
    local base_domain
    while true; do
        read -p "Base domain (e.g., example.com): " base_domain
        if validate_domain_format "$base_domain"; then
            break
        fi
    done

    # API subdomain
    read -p "API subdomain [api]: " api_subdomain
    api_subdomain=${api_subdomain:-api}
    if ! validate_subdomain_format "$api_subdomain"; then
        print_error "Invalid subdomain format"
        exit 1
    fi

    # Flower subdomain
    read -p "Flower subdomain [flower]: " flower_subdomain
    flower_subdomain=${flower_subdomain:-flower}
    if ! validate_subdomain_format "$flower_subdomain"; then
        print_error "Invalid subdomain format"
        exit 1
    fi

    # Admin email
    local admin_email
    while true; do
        read -p "Admin email (for SSL certificates): " admin_email
        if validate_email_format "$admin_email"; then
            break
        fi
    done

    # Production configuration (conditional)
    local prod_workers prod_celery prod_db_host prod_db_port prod_db_name prod_db_user prod_db_password
    if [[ "$setup_production" == "true" ]]; then
        print_separator
        echo "Production Configuration:"
        echo ""

        read -p "Production API workers [4]: " prod_workers
        prod_workers=${prod_workers:-4}

        read -p "Production Celery workers [4]: " prod_celery
        prod_celery=${prod_celery:-4}

        read -p "Production PostgreSQL host: " prod_db_host
        read -p "Production PostgreSQL port [25060]: " prod_db_port
        prod_db_port=${prod_db_port:-25060}

        read -p "Production PostgreSQL database: " prod_db_name
        read -p "Production PostgreSQL user: " prod_db_user
        read -s -p "Production PostgreSQL password: " prod_db_password
        echo ""
    else
        # Set defaults for production (not used but needed for config.env template)
        prod_workers=4
        prod_celery=4
        prod_db_host="your-db-host.db.ondigitalocean.com"
        prod_db_port=25060
        prod_db_name="defaultdb"
        prod_db_user="doadmin"
        prod_db_password="CHANGE_THIS_PRODUCTION_PASSWORD"
    fi

    # Staging configuration (conditional)
    local staging_workers staging_celery staging_db_name staging_db_user staging_db_password
    if [[ "$setup_staging" == "true" ]]; then
        print_separator
        echo "Staging Configuration (uses containerized PostgreSQL):"
        echo ""

        read -p "Staging API workers [2]: " staging_workers
        staging_workers=${staging_workers:-2}

        read -p "Staging Celery workers [2]: " staging_celery
        staging_celery=${staging_celery:-2}

        read -p "Staging PostgreSQL database [staging_db]: " staging_db_name
        staging_db_name=${staging_db_name:-staging_db}

        read -p "Staging PostgreSQL user [staging_user]: " staging_db_user
        staging_db_user=${staging_db_user:-staging_user}

        read -s -p "Staging PostgreSQL password: " staging_db_password
        echo ""
    else
        # Set defaults for staging (not used but needed for config.env template)
        staging_workers=2
        staging_celery=2
        staging_db_name="staging_db"
        staging_db_user="staging_user"
        staging_db_password="CHANGE_THIS_STAGING_PASSWORD"
    fi

    # Flower credentials
    print_separator
    read -p "Flower username [admin]: " flower_user
    flower_user=${flower_user:-admin}

    read -s -p "Flower password: " flower_password
    echo ""

    # Write config.env
    print_separator
    print_info "Writing configuration file..."

    cat > "$DEPLOY_ROOT/config.env" << EOF
# ==================== Project Identity ====================
PROJECT_NAME=$project_name
BASE_DOMAIN=$base_domain

# ==================== Domain Configuration ====================
API_SUBDOMAIN=$api_subdomain
FLOWER_SUBDOMAIN=$flower_subdomain

# ==================== Contact Email ====================
ACME_EMAIL=$admin_email

# ==================== Production Configuration ====================
PRODUCTION_API_WORKERS=$prod_workers
PRODUCTION_CELERY_WORKERS=$prod_celery
PRODUCTION_POSTGRES_HOST=$prod_db_host
PRODUCTION_POSTGRES_PORT=$prod_db_port
PRODUCTION_POSTGRES_DB=$prod_db_name
PRODUCTION_POSTGRES_USER=$prod_db_user
PRODUCTION_POSTGRES_PASSWORD=$prod_db_password
PRODUCTION_DB_SSL_MODE=require

# ==================== Staging Configuration ====================
STAGING_API_WORKERS=$staging_workers
STAGING_CELERY_WORKERS=$staging_celery
STAGING_POSTGRES_HOST=postgres
STAGING_POSTGRES_PORT=5432
STAGING_POSTGRES_DB=$staging_db_name
STAGING_POSTGRES_USER=$staging_db_user
STAGING_POSTGRES_PASSWORD=$staging_db_password
STAGING_DB_SSL_MODE=disable

# ==================== Flower Monitoring ====================
FLOWER_USERNAME=$flower_user
FLOWER_PASSWORD=$flower_password
EOF

    chmod 600 "$DEPLOY_ROOT/config.env"
    print_success "Configuration file created: config.env"

    # Store environment choices for generation phase
    export SETUP_PRODUCTION=$setup_production
    export SETUP_STAGING=$setup_staging
}

# ==================== TEMPLATE GENERATION ====================

generate_configurations() {
    print_header "Configuration Generation"

    # Load configuration
    if ! load_config "$DEPLOY_ROOT"; then
        exit 1
    fi

    # Determine which environments to generate
    local environments=()
    if [[ "${SETUP_PRODUCTION:-false}" == "true" ]]; then
        environments+=("production")
    fi
    if [[ "${SETUP_STAGING:-false}" == "true" ]]; then
        environments+=("staging")
    fi

    # If called with existing config.env, ask which to generate
    if [[ ${#environments[@]} -eq 0 ]]; then
        print_info "Which environment do you want to generate?"
        echo "  1) Production"
        echo "  2) Staging"
        echo "  3) Both"
        echo ""
        read -p "Enter your choice (1-3): " gen_choice
        case $gen_choice in
            1) environments=("production") ;;
            2) environments=("staging") ;;
            3) environments=("production" "staging") ;;
            *) print_error "Invalid choice"; exit 1 ;;
        esac
    fi

    # Create directory structure
    print_info "Creating directory structure..."
    mkdir -p "$DEPLOY_ROOT/generated/nginx"
    mkdir -p "$DEPLOY_ROOT/generated/redis"
    mkdir -p "$DEPLOY_ROOT/generated/prometheus"
    mkdir -p "$DEPLOY_ROOT/generated/grafana/provisioning/datasources"
    mkdir -p "$DEPLOY_ROOT/certbot/conf"
    mkdir -p "$DEPLOY_ROOT/certbot/www"
    mkdir -p "$DEPLOY_ROOT/ssl"
    print_success "Directory structure created"

    # Generate for each environment
    for env in "${environments[@]}"; do
        print_separator
        print_info "Generating configurations for: $env"

        # Derive configuration values
        derive_config_values "$env"

        # Check if files exist
        local env_file="$DEPLOY_ROOT/.env.${env}"
        if [[ -f "$env_file" && "$FORCE_REGENERATE" != "true" ]]; then
            print_warning ".env.${env} already exists"
            if ! confirm_action "Overwrite existing configuration?"; then
                print_info "Skipping $env generation"
                continue
            fi
        fi

        # Generate secrets
        generate_secrets "$env"

        # Process environment template
        print_info "Generating environment file..."
        local env_template="$DEPLOY_ROOT/templates/env/${env}.env.template"
        if ! process_template_file "$env_template" "$env_file"; then
            print_error "Failed to generate .env.${env}"
            exit 1
        fi

        # Process Docker Compose template
        print_info "Generating Docker Compose file..."
        local compose_template="$DEPLOY_ROOT/templates/docker/${env}.compose.yml.template"
        local compose_output="$DEPLOY_ROOT/generated/docker-compose.${env}.yml"
        if ! process_template_file "$compose_template" "$compose_output"; then
            print_error "Failed to generate docker-compose.${env}.yml"
            exit 1
        fi

        # Process nginx templates
        print_info "Generating nginx configurations..."
        for template in "$DEPLOY_ROOT/templates/nginx"/*.template; do
            local filename=$(basename "$template" .template)
            local output="$DEPLOY_ROOT/generated/nginx/$filename"
            if ! process_template_file "$template" "$output"; then
                print_error "Failed to generate nginx/$filename"
                exit 1
            fi
        done

        # Disable Flower for staging (save resources on 2GB droplet) or if not configured
        if [[ "$env" == "staging" ]] || [[ -z "${FLOWER_SUBDOMAIN:-}" ]]; then
            if [[ -f "$DEPLOY_ROOT/generated/nginx/flower.conf" ]]; then
                mv "$DEPLOY_ROOT/generated/nginx/flower.conf" "$DEPLOY_ROOT/generated/nginx/flower.conf.disabled"
                if [[ -z "${FLOWER_SUBDOMAIN:-}" ]]; then
                    print_info "Flower disabled (FLOWER_SUBDOMAIN not configured)"
                else
                    print_info "Flower disabled for staging (uncomment in docker-compose to enable)"
                fi
            fi
        fi

        # Copy redis config
        print_info "Copying redis configuration..."
        cp "$DEPLOY_ROOT/templates/redis/redis.conf.template" "$DEPLOY_ROOT/generated/redis/redis.conf"

        # Generate redis password config
        print_info "Generating redis password configuration..."
        local redis_password_file="$DEPLOY_ROOT/generated/redis/redis-password.conf"
        echo "requirepass ${REDIS_PASSWORD}" > "$redis_password_file"
        chmod 600 "$redis_password_file"

        # Process Prometheus config template
        print_info "Generating Prometheus configuration..."
        local prom_template="$DEPLOY_ROOT/templates/prometheus/prometheus.yml.template"
        local prom_output="$DEPLOY_ROOT/generated/prometheus/prometheus.yml"
        if [[ -f "$prom_template" ]]; then
            if ! process_template_file "$prom_template" "$prom_output"; then
                print_error "Failed to generate prometheus/prometheus.yml"
                exit 1
            fi
        fi

        # Copy Grafana provisioning configs
        print_info "Copying Grafana provisioning configuration..."
        if [[ -d "$DEPLOY_ROOT/templates/grafana" ]]; then
            cp -r "$DEPLOY_ROOT/templates/grafana/provisioning/" "$DEPLOY_ROOT/generated/grafana/provisioning/"
            print_success "Grafana provisioning copied"
        fi

        print_success "Configuration generated for: $env"
    done
}

# Generate secrets
generate_secrets() {
    local env="$1"
    print_info "Generating secrets for $env..."

    # SECRET_KEY
    if [[ -z "${SECRET_KEY:-}" ]] || [[ "$SECRET_KEY" == *"CHANGE_THIS"* ]]; then
        export SECRET_KEY=$(generate_secret 64)
        print_success "Generated SECRET_KEY"
    fi

    # JWT_SECRET_KEY
    if [[ -z "${JWT_SECRET_KEY:-}" ]] || [[ "$JWT_SECRET_KEY" == *"CHANGE_THIS"* ]]; then
        export JWT_SECRET_KEY=$(generate_secret 64)
        print_success "Generated JWT_SECRET_KEY"
    fi

    # REDIS_PASSWORD
    if [[ -z "${REDIS_PASSWORD:-}" ]] || [[ "$REDIS_PASSWORD" == *"CHANGE_THIS"* ]]; then
        export REDIS_PASSWORD=$(generate_secret 32)
        print_success "Generated REDIS_PASSWORD"
    fi

    # FLOWER_PASSWORD from config
    if [[ -z "${FLOWER_PASSWORD:-}" ]] || [[ "$FLOWER_PASSWORD" == *"CHANGE_THIS"* ]]; then
        export FLOWER_PASSWORD=$(generate_secret 24)
        print_success "Generated FLOWER_PASSWORD"
    fi

    # FLOWER_USERNAME
    if [[ -z "${FLOWER_USERNAME:-}" ]]; then
        export FLOWER_USERNAME="admin"
    fi

    # GRAFANA_PASSWORD
    if [[ -z "${GRAFANA_PASSWORD:-}" ]] || [[ "$GRAFANA_PASSWORD" == *"CHANGE_THIS"* ]]; then
        export GRAFANA_PASSWORD=$(generate_secret 24)
        print_success "Generated GRAFANA_PASSWORD"
    fi

    # Database credentials (environment-specific)
    if [[ "$env" == "production" ]]; then
        export POSTGRES_HOST="${PRODUCTION_POSTGRES_HOST}"
        export POSTGRES_PORT="${PRODUCTION_POSTGRES_PORT:-25060}"
        export POSTGRES_DB="${PRODUCTION_POSTGRES_DB:-defaultdb}"
        export POSTGRES_USER="${PRODUCTION_POSTGRES_USER:-doadmin}"
        export POSTGRES_PASSWORD="${PRODUCTION_POSTGRES_PASSWORD:-CHANGE_THIS_DB_PASSWORD}"
    else
        export POSTGRES_HOST="${STAGING_POSTGRES_HOST:-postgres}"
        export POSTGRES_PORT="${STAGING_POSTGRES_PORT:-5432}"
        export POSTGRES_DB="${STAGING_POSTGRES_DB:-staging_db}"
        export POSTGRES_USER="${STAGING_POSTGRES_USER:-staging_user}"
        export POSTGRES_PASSWORD="${STAGING_POSTGRES_PASSWORD:-CHANGE_THIS_STAGING_DB_PASSWORD}"
    fi
}

# ==================== MAIN ====================

main() {
    print_header "Deploy-v2 Complete Setup"

    echo ""
    print_info "This setup wizard will:"
    echo "  • Check system prerequisites (Docker, ports, disk space)"
    echo "  • Collect your project configuration"
    echo "  • Generate all required configuration files"
    echo ""

    # Step 1: System checks
    if ! check_system_prerequisites; then
        exit 1
    fi

    print_separator
    sleep 1

    # Step 2: Collect configuration
    collect_configuration

    print_separator
    sleep 1

    # Step 3: Generate configurations
    generate_configurations

    # Final instructions
    print_separator
    print_success "Setup Complete!"
    echo ""
    print_info "Your deployment is ready. Next steps:"
    echo ""
    echo "  1. Review configurations:"
    for env_file in "$DEPLOY_ROOT"/.env.*; do
        if [[ -f "$env_file" ]]; then
            local env_name=$(basename "$env_file" | sed 's/^\.env\.//')
            echo "     - .env.${env_name}"
        fi
    done
    echo ""
    echo "  2. Add your API keys (Fast2SMS, Sentry, DO Spaces, etc.)"
    echo ""
    echo "  3. Validate configuration:"
    echo "     ./scripts/validate.sh --env production"
    echo "     ./scripts/validate.sh --env staging"
    echo ""
    echo "  4. Deploy:"
    echo "     ./scripts/deploy.sh init --env production"
    echo "     ./scripts/deploy.sh init --env staging"
    echo ""
    echo "  5. Setup SSL certificates:"
    echo "     ./scripts/ssl.sh setup --env production"
    echo "     ./scripts/ssl.sh setup --env staging"
    echo ""

    # Show generated URLs
    source "$DEPLOY_ROOT/config.env"
    if [[ -f "$DEPLOY_ROOT/.env.production" ]]; then
        echo "  Production URLs:"
        echo "    - API: https://${API_SUBDOMAIN}.${BASE_DOMAIN}"
        echo "    - Flower: https://${FLOWER_SUBDOMAIN}.${BASE_DOMAIN}"
        echo ""
    fi
    if [[ -f "$DEPLOY_ROOT/.env.staging" ]]; then
        echo "  Staging URLs:"
        echo "    - API: https://${API_SUBDOMAIN}.${BASE_DOMAIN}"
        echo "    - Flower: https://${FLOWER_SUBDOMAIN}.${BASE_DOMAIN}"
        echo ""
    fi
}

# Run main
main
