#!/usr/bin/env bash

##############################################################################
# Deployment Configuration Validation
# Validates generated configuration before deployment
#
# Usage: ./scripts/validate.sh [--env production|staging]
##############################################################################

set -euo pipefail

# Script directory and imports
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DEPLOY_ROOT="$(dirname "$SCRIPT_DIR")"

# Source common libraries
source "$SCRIPT_DIR/common/common.sh"
source "$SCRIPT_DIR/common/validation.sh"

# Default values
ENVIRONMENT="production"
ERRORS=0
WARNINGS=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [--env production|staging]"
            echo ""
            echo "Options:"
            echo "  --env ENV     Environment to validate (production or staging, default: production)"
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

# Validate environment
if [[ "$ENVIRONMENT" != "production" && "$ENVIRONMENT" != "staging" ]]; then
    print_error "Invalid environment: $ENVIRONMENT"
    print_info "Must be 'production' or 'staging'"
    exit 1
fi

# Track errors and warnings
count_error() {
    ((ERRORS++))
}

count_warning() {
    ((WARNINGS++))
}

# Override print functions to count
print_error() {
    echo -e "${RED}✗${NC} $1"
    count_error
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    count_warning
}

print_ok() {
    echo -e "${GREEN}✓${NC} $1"
}

# Check config.env exists
check_config_env() {
    print_header "Base Configuration"

    if [[ ! -f "$DEPLOY_ROOT/config.env" ]]; then
        print_error "config.env not found"
        print_error "Run: ./scripts/setup.sh"
        return 1
    fi
    print_ok "config.env exists"

    # Check permissions
    local perms
    if [[ "$OSTYPE" == "darwin"* ]]; then
        perms=$(stat -f %A "$DEPLOY_ROOT/config.env" 2>/dev/null || echo "unknown")
    else
        perms=$(stat -c %a "$DEPLOY_ROOT/config.env" 2>/dev/null || echo "unknown")
    fi

    if [[ "$perms" != "600" && "$perms" != "unknown" ]]; then
        print_warning "config.env permissions are $perms (should be 600)"
        print_warning "Run: chmod 600 config.env"
    else
        print_ok "config.env has correct permissions"
    fi
}

# Check environment file
check_environment_file() {
    print_header "Environment Configuration ($ENVIRONMENT)"

    local env_file="$DEPLOY_ROOT/.env.${ENVIRONMENT}"

    if [[ ! -f "$env_file" ]]; then
        print_error ".env.${ENVIRONMENT} not found"
        print_error "Run: ./scripts/setup.sh --force"
        return 1
    fi
    print_ok ".env.${ENVIRONMENT} exists"

    # Check permissions
    local perms
    if [[ "$OSTYPE" == "darwin"* ]]; then
        perms=$(stat -f %A "$env_file" 2>/dev/null || echo "unknown")
    else
        perms=$(stat -c %a "$env_file" 2>/dev/null || echo "unknown")
    fi

    if [[ "$perms" != "600" && "$perms" != "unknown" ]]; then
        print_warning ".env.${ENVIRONMENT} permissions are $perms (should be 600)"
        print_warning "Run: chmod 600 .env.${ENVIRONMENT}"
    else
        print_ok ".env.${ENVIRONMENT} has correct permissions"
    fi

    # Source environment
    set -a
    source "$env_file"
    set +a

    # Check for unresolved template placeholders
    if grep -q "{{" "$env_file" 2>/dev/null; then
        print_error ".env.${ENVIRONMENT} contains unresolved template placeholders"
        print_error "Regenerate with: ./scripts/setup.sh --force"
        return 1
    fi
    print_ok "No template placeholders found"

    # Check critical variables
    local required_vars=(
        "SECRET_KEY"
        "JWT_SECRET_KEY"
        "POSTGRES_HOST"
        "POSTGRES_PASSWORD"
        "REDIS_PASSWORD"
        "FLOWER_PASSWORD"
    )

    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            print_error "$var is not set in .env.${ENVIRONMENT}"
        else
            # Check if it's a placeholder
            if echo "${!var}" | grep -Eqi "CHANGE_THIS|your-|generate|REPLACE"; then
                print_error "$var contains placeholder value: ${!var}"
            else
                print_ok "$var is configured"
            fi
        fi
    done

    # Check key lengths
    if [[ -n "${SECRET_KEY:-}" ]] && [[ ${#SECRET_KEY} -lt 32 ]]; then
        print_error "SECRET_KEY is too short (${#SECRET_KEY} chars, minimum 32)"
    fi

    if [[ -n "${JWT_SECRET_KEY:-}" ]] && [[ ${#JWT_SECRET_KEY} -lt 32 ]]; then
        print_error "JWT_SECRET_KEY is too short (${#JWT_SECRET_KEY} chars, minimum 32)"
    fi

    if [[ -n "${REDIS_PASSWORD:-}" ]] && [[ ${#REDIS_PASSWORD} -lt 16 ]]; then
        print_warning "REDIS_PASSWORD is short (${#REDIS_PASSWORD} chars, recommended 32+)"
    fi

    # Check optional services
    if [[ -z "${SENTRY_DSN:-}" ]]; then
        print_warning "SENTRY_DSN not configured (error tracking disabled)"
    else
        print_ok "Sentry error tracking configured"
    fi

    # Check environment settings
    if [[ "${ENVIRONMENT:-}" != "$ENVIRONMENT" ]]; then
        print_warning "ENVIRONMENT variable is '${ENVIRONMENT:-}' (expected '$ENVIRONMENT')"
    fi

    if [[ "$ENVIRONMENT" == "production" && "${DEBUG:-false}" != "false" ]]; then
        print_error "DEBUG is '${DEBUG}' (should be 'false' in production)"
    fi
}

# Check Docker Compose file
check_docker_compose() {
    print_header "Docker Compose Configuration"

    local compose_file="$DEPLOY_ROOT/generated/docker-compose.${ENVIRONMENT}.yml"

    if [[ ! -f "$compose_file" ]]; then
        print_error "docker-compose.${ENVIRONMENT}.yml not found in generated/"
        print_error "Run: ./scripts/setup.sh --force"
        return 1
    fi
    print_ok "docker-compose.${ENVIRONMENT}.yml exists"

    # Check for unresolved template placeholders
    if grep -q "{{" "$compose_file" 2>/dev/null; then
        print_error "Docker Compose file contains unresolved template placeholders"
        return 1
    fi
    print_ok "No template placeholders in Docker Compose file"

    # Validate YAML syntax with Docker Compose
    if validate_docker_compose; then
        local compose_cmd="$DOCKER_COMPOSE_CMD"
        if $compose_cmd -f "$compose_file" config > /dev/null 2>&1; then
            print_ok "Docker Compose file syntax is valid"
        else
            print_error "Docker Compose file has syntax errors:"
            $compose_cmd -f "$compose_file" config 2>&1 | head -10
        fi
    else
        print_warning "Docker Compose not available, cannot validate syntax"
    fi
}

# Check Nginx configuration
check_nginx_config() {
    print_header "Nginx Configuration"

    # Check main config
    if [[ ! -f "$DEPLOY_ROOT/generated/nginx/nginx.conf" ]]; then
        print_error "nginx.conf not found in generated/"
    else
        print_ok "nginx.conf exists"

        # Check for template placeholders
        if grep -q "{{" "$DEPLOY_ROOT/generated/nginx/nginx.conf" 2>/dev/null; then
            print_error "nginx.conf contains unresolved template placeholders"
        fi
    fi

    # Check site configs
    local nginx_configs=("api.conf")

    # For production, check flower.conf; for staging, check flower.conf.disabled
    if [[ "$ENVIRONMENT" == "staging" ]]; then
        nginx_configs+=("flower.conf.disabled")
    else
        nginx_configs+=("flower.conf")
    fi

    for config in "${nginx_configs[@]}"; do
        local config_path="$DEPLOY_ROOT/generated/nginx/$config"
        if [[ ! -f "$config_path" ]]; then
            print_error "$config not found in generated/nginx/"
        else
            print_ok "$config exists"

            # Check for template placeholders
            if grep -q "{{" "$config_path" 2>/dev/null; then
                print_error "$config contains unresolved template placeholders"
            fi
        fi
    done

    # Check for common nginx mistakes
    if grep -q "more_clear_headers" "$DEPLOY_ROOT/generated/nginx/nginx.conf" 2>/dev/null; then
        print_error "nginx.conf contains 'more_clear_headers' (not available in Alpine nginx)"
    fi

    # Validate nginx config syntax (if nginx is available in container)
    if command_exists docker && validate_docker_compose; then
        print_info "Nginx syntax validation will be performed during deployment"
    fi
}

# Check deployment scripts
check_scripts() {
    print_header "Deployment Scripts"

    local scripts=(
        "setup.sh"
        "validate.sh"
        "deploy.sh"
        "ssl.sh"
    )

    for script in "${scripts[@]}"; do
        local script_path="$SCRIPT_DIR/$script"
        if [[ ! -f "$script_path" ]]; then
            print_error "$script not found"
        elif [[ ! -x "$script_path" ]]; then
            print_warning "$script is not executable"
            print_warning "Run: chmod +x scripts/$script"
        else
            print_ok "$script exists and is executable"
        fi
    done

    # Check optional scripts
    local optional_scripts=("optional/backup.sh" "optional/security-setup.sh")
    for script in "${optional_scripts[@]}"; do
        local script_path="$SCRIPT_DIR/$script"
        if [[ ! -f "$script_path" ]]; then
            print_warning "$script not found (optional)"
        elif [[ ! -x "$script_path" ]]; then
            print_warning "$script is not executable"
            print_warning "Run: chmod +x scripts/$script"
        else
            print_ok "$script exists and is executable"
        fi
    done

    # Check common libraries
    local libs=("common.sh" "validation.sh" "template-engine.sh")
    for lib in "${libs[@]}"; do
        local lib_path="$SCRIPT_DIR/common/$lib"
        if [[ ! -f "$lib_path" ]]; then
            print_error "scripts/common/$lib not found"
        else
            print_ok "scripts/common/$lib exists"
        fi
    done
}

# Check directories
check_directories() {
    print_header "Directory Structure"

    local required_dirs=(
        "$DEPLOY_ROOT/templates"
        "$DEPLOY_ROOT/templates/env"
        "$DEPLOY_ROOT/templates/docker"
        "$DEPLOY_ROOT/templates/nginx"
        "$DEPLOY_ROOT/generated"
        "$DEPLOY_ROOT/generated/nginx"
        "$DEPLOY_ROOT/scripts"
        "$DEPLOY_ROOT/scripts/common"
    )

    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            print_error "Directory not found: $dir"
        else
            print_ok "Directory exists: $(basename "$dir")"
        fi
    done

    # Check runtime directories (created at deployment)
    local runtime_dirs=(
        "$DEPLOY_ROOT/certbot/conf"
        "$DEPLOY_ROOT/certbot/www"
        "$DEPLOY_ROOT/ssl"
    )

    for dir in "${runtime_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            print_warning "$(basename "$(dirname "$dir")")/$(basename "$dir") doesn't exist (will be created at deployment)"
        else
            print_ok "$(basename "$(dirname "$dir")")/$(basename "$dir") exists"
        fi
    done
}

# Check dependencies
check_dependencies() {
    print_header "System Dependencies"

    # Check Docker
    if command_exists docker; then
        local docker_version=$(docker --version | cut -d' ' -f3 | tr -d ',')
        print_ok "Docker installed: $docker_version"

        # Check if Docker daemon is running
        if docker info &>/dev/null; then
            print_ok "Docker daemon is running"
        else
            print_error "Docker daemon is not running"
        fi
    else
        print_error "Docker is not installed"
    fi

    # Check Docker Compose
    if docker compose version &>/dev/null; then
        local compose_version=$(docker compose version --short 2>/dev/null || docker compose version | grep -oP 'v?\K[0-9.]+' | head -1)
        print_ok "Docker Compose (V2) installed: $compose_version"
    elif command_exists docker-compose; then
        local compose_version=$(docker-compose --version | grep -oP 'v?\K[0-9.]+' | head -1)
        print_ok "Docker Compose (V1) installed: $compose_version"
        print_warning "Consider upgrading to Docker Compose V2"
    else
        print_error "Docker Compose is not installed"
    fi

    # Check Git
    if command_exists git; then
        local git_version=$(git --version | cut -d' ' -f3)
        print_ok "Git installed: $git_version"
    else
        print_warning "Git is not installed (recommended for version control)"
    fi

    # Check openssl
    if command_exists openssl; then
        print_ok "OpenSSL installed"
    else
        print_warning "OpenSSL not found (needed for secret generation)"
    fi
}

# Check DNS (optional)
check_dns() {
    print_header "DNS Configuration (Optional)"

    # Load config to get domains
    if [[ -f "$DEPLOY_ROOT/config.env" ]]; then
        set -a
        source "$DEPLOY_ROOT/config.env"
        set +a

        local api_domain="${API_SUBDOMAIN}.${BASE_DOMAIN}"
        local flower_domain="${FLOWER_SUBDOMAIN}.${BASE_DOMAIN}"
    else
        print_warning "config.env not found, skipping DNS check"
        return
    fi

    if ! command_exists dig; then
        print_warning "dig not installed, skipping DNS check"
        print_info "Install with: apt install dnsutils (Debian/Ubuntu) or brew install bind (macOS)"
        return
    fi

    local domains=("$api_domain" "$flower_domain")

    for domain in "${domains[@]}"; do
        if dig +short "$domain" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
            local ip=$(dig +short "$domain" | head -1)
            print_ok "$domain resolves to $ip"
        else
            print_warning "$domain does not resolve (DNS may not be configured yet)"
        fi
    done
}

# Check ports availability (only if on deployment server)
check_ports() {
    print_header "Port Availability (Optional)"

    if ! command_exists netstat && ! command_exists ss; then
        print_warning "netstat/ss not available, skipping port check"
        return
    fi

    local ports=(80 443)
    for port in "${ports[@]}"; do
        if command_exists netstat; then
            if netstat -tuln 2>/dev/null | grep -q ":$port "; then
                print_warning "Port $port is already in use"
            else
                print_ok "Port $port is available"
            fi
        elif command_exists ss; then
            if ss -tuln 2>/dev/null | grep -q ":$port "; then
                print_warning "Port $port is already in use"
            else
                print_ok "Port $port is available"
            fi
        fi
    done
}

# Main execution
main() {
    print_header "Deploy-v2 Configuration Validation - ${ENVIRONMENT}"

    check_config_env
    check_environment_file
    check_docker_compose
    check_nginx_config
    check_scripts
    check_directories
    check_dependencies
    check_dns
    check_ports

    # Summary
    print_separator
    print_header "Validation Summary"

    if [[ $ERRORS -eq 0 ]] && [[ $WARNINGS -eq 0 ]]; then
        print_success "All checks passed!"
        echo ""
        echo "Your ${ENVIRONMENT} deployment configuration is ready."
        echo ""
        print_info "Next steps:"
        echo "  1. Review .env.${ENVIRONMENT} one more time"
        echo "  2. Deploy: ./scripts/deploy.sh init --env ${ENVIRONMENT}"
        echo "  3. Setup SSL: ./scripts/ssl.sh setup --env ${ENVIRONMENT}"
        echo ""
        exit 0
    elif [[ $ERRORS -eq 0 ]]; then
        print_warning "Validation completed with $WARNINGS warning(s)"
        echo ""
        echo "You can proceed with deployment, but review the warnings above."
        echo ""
        print_info "Next steps:"
        echo "  1. Address warnings if critical"
        echo "  2. Deploy: ./scripts/deploy.sh init --env ${ENVIRONMENT}"
        echo "  3. Setup SSL: ./scripts/ssl.sh setup --env ${ENVIRONMENT}"
        echo ""
        exit 0
    else
        print_error "Validation failed with $ERRORS error(s) and $WARNINGS warning(s)"
        echo ""
        print_info "Please fix the errors above before deploying."
        echo ""
        print_info "Common fixes:"
        echo "  • Missing files: ./scripts/setup.sh --force"
        echo "  • Placeholder values: Edit config.env and regenerate"
        echo "  • Permissions: chmod 600 config.env .env.${ENVIRONMENT}"
        echo ""
        exit 1
    fi
}

# Run main
main
