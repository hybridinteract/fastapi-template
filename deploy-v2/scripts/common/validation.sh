#!/usr/bin/env bash

##############################################################################
# Validation Functions Library
# Provides validation helpers for domains, emails, project names, etc.
##############################################################################

# Source common functions if not already loaded
if ! declare -f print_error > /dev/null 2>&1; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    source "$SCRIPT_DIR/common.sh"
fi

# Validate required variables are set
validate_required_vars() {
    local missing_vars=()

    for var in "$@"; do
        if [[ -z "${!var}" ]]; then
            missing_vars+=("$var")
        fi
    done

    if [[ ${#missing_vars[@]} -gt 0 ]]; then
        print_error "Required variables not set: ${missing_vars[*]}"
        return 1
    fi

    return 0
}

# Validate domain format
validate_domain_format() {
    local domain="$1"

    # Basic regex for domain validation
    # Allows: example.com, sub.example.com, sub-domain.example.co.uk
    local domain_regex='^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*\.[a-zA-Z]{2,}$'

    if [[ ! "$domain" =~ $domain_regex ]]; then
        print_error "Invalid domain format: $domain"
        print_info "Domain should be like: example.com or api.example.com"
        return 1
    fi

    return 0
}

# Validate subdomain format
validate_subdomain_format() {
    local subdomain="$1"

    # Subdomain can contain stagingnumeric, hyphens, and dots
    # Each label (part between dots) must start and end with stagingnumeric
    local subdomain_regex='^[a-zA-Z0-9]([a-zA-Z0-9.-]{0,61}[a-zA-Z0-9])?$'

    if [[ ! "$subdomain" =~ $subdomain_regex ]]; then
        print_error "Invalid subdomain format: $subdomain"
        print_info "Subdomain should be like: api, flower, api-staging, staging.api"
        return 1
    fi

    return 0
}

# Validate email format
validate_email_format() {
    local email="$1"

    # Basic email regex
    local email_regex='^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if [[ ! "$email" =~ $email_regex ]]; then
        print_error "Invalid email format: $email"
        print_info "Email should be like: admin@example.com"
        return 1
    fi

    return 0
}

# Validate project name
validate_project_name() {
    local name="$1"

    # Project name: stagingnumeric, hyphens, underscores, spaces (will be sanitized)
    # Min 2 chars, max 30 chars
    if [[ ${#name} -lt 2 || ${#name} -gt 30 ]]; then
        print_error "Project name must be between 2 and 30 characters"
        return 1
    fi

    local name_regex='^[a-zA-Z0-9][a-zA-Z0-9 _-]*[a-zA-Z0-9]$'

    if [[ ! "$name" =~ $name_regex ]]; then
        print_error "Invalid project name: $name"
        print_info "Project name should contain only letters, numbers, spaces, hyphens, underscores"
        return 1
    fi

    return 0
}

# Validate file exists
validate_file_exists() {
    local file="$1"
    local description="${2:-File}"

    if [[ ! -f "$file" ]]; then
        print_error "$description not found: $file"
        return 1
    fi

    return 0
}

# Validate directory exists
validate_dir_exists() {
    local dir="$1"
    local description="${2:-Directory}"

    if [[ ! -d "$dir" ]]; then
        print_error "$description not found: $dir"
        return 1
    fi

    return 0
}

# Validate command exists
validate_command_exists() {
    local cmd="$1"
    local description="${2:-$cmd}"

    if ! command -v "$cmd" &>/dev/null; then
        print_error "$description command not found: $cmd"
        return 1
    fi

    return 0
}

# Validate docker is installed and running
validate_docker() {
    if ! validate_command_exists "docker" "Docker"; then
        print_info "Install Docker from: https://docs.docker.com/get-docker/"
        return 1
    fi

    if ! docker info &>/dev/null; then
        print_error "Docker daemon is not running"
        print_info "Start Docker and try again"
        return 1
    fi

    print_success "Docker is available and running"
    return 0
}

# Validate docker compose is available
validate_docker_compose() {
    # Check for docker compose (v2) or docker-compose (v1)
    if docker compose version &>/dev/null; then
        export DOCKER_COMPOSE_CMD="docker compose"
        print_success "Docker Compose (v2) is available"
        return 0
    elif command -v docker-compose &>/dev/null; then
        export DOCKER_COMPOSE_CMD="docker-compose"
        print_success "Docker Compose (v1) is available"
        return 0
    else
        print_error "Docker Compose not found"
        print_info "Install Docker Compose from: https://docs.docker.com/compose/install/"
        return 1
    fi
}

# Validate secret key length
validate_secret_length() {
    local secret="$1"
    local min_length="${2:-32}"
    local name="${3:-Secret}"

    if [[ ${#secret} -lt $min_length ]]; then
        print_error "$name is too short (${#secret} chars, minimum $min_length required)"
        return 1
    fi

    return 0
}

# Check for placeholder values
check_for_placeholders() {
    local file="$1"
    local placeholders=("CHANGE_THIS" "YOUR_" "REPLACE_" "PLACEHOLDER" "{{")

    for placeholder in "${placeholders[@]}"; do
        if grep -q "$placeholder" "$file" 2>/dev/null; then
            print_error "Found placeholder '$placeholder' in $file"
            print_info "Please replace all placeholder values before deploying"
            return 1
        fi
    done

    return 0
}

# Validate DNS resolution
validate_dns() {
    local domain="$1"
    local warn_only="${2:-true}"

    if ! host "$domain" &>/dev/null && ! nslookup "$domain" &>/dev/null; then
        if [[ "$warn_only" == "true" ]]; then
            print_warning "DNS does not resolve for: $domain"
            print_info "Make sure to configure DNS before deploying"
            return 0
        else
            print_error "DNS does not resolve for: $domain"
            return 1
        fi
    fi

    print_success "DNS resolves for: $domain"
    return 0
}

# Validate port is available
validate_port_available() {
    local port="$1"

    if lsof -Pi ":$port" -sTCP:LISTEN -t >/dev/null 2>&1 || netstat -an | grep -q ":$port.*LISTEN" 2>/dev/null; then
        print_warning "Port $port is already in use"
        return 1
    fi

    print_success "Port $port is available"
    return 0
}

# Export functions for subshells
export -f validate_required_vars validate_domain_format validate_subdomain_format
export -f validate_email_format validate_project_name validate_file_exists
export -f validate_dir_exists validate_command_exists validate_docker
export -f validate_docker_compose validate_secret_length check_for_placeholders
export -f validate_dns validate_port_available
