#!/usr/bin/env bash

##############################################################################
# Template Engine Library
# Handles template processing and placeholder substitution
##############################################################################

# Source common functions if not already loaded
if ! declare -f print_error > /dev/null 2>&1; then
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    source "$SCRIPT_DIR/common.sh"
fi

# Derive configuration values from base config
derive_config_values() {
    local environment="${1:-production}"

    print_debug "Deriving configuration values for environment: $environment"

    # Derive domains from base domain and subdomains
    export API_DOMAIN="${API_SUBDOMAIN}.${BASE_DOMAIN}"
    # Only set FLOWER_DOMAIN if FLOWER_SUBDOMAIN is configured
    if [[ -n "${FLOWER_SUBDOMAIN:-}" ]]; then
        export FLOWER_DOMAIN="${FLOWER_SUBDOMAIN}.${BASE_DOMAIN}"
    else
        export FLOWER_DOMAIN=""
    fi

    print_debug "API_DOMAIN: $API_DOMAIN"
    print_debug "FLOWER_DOMAIN: $FLOWER_DOMAIN"

    # Sanitize project name for use in container names
    export PROJECT_PREFIX=$(sanitize_project_name "$PROJECT_NAME")

    print_debug "PROJECT_PREFIX: $PROJECT_PREFIX"

    # Derive container prefix with environment suffix if staging
    if [[ "$environment" == "staging" ]]; then
        export CONTAINER_PREFIX="${PROJECT_PREFIX}_staging"
        export NETWORK_PREFIX="${PROJECT_PREFIX}_staging"
        export VOLUME_PREFIX="${PROJECT_PREFIX}_staging"
        export NETWORK_SUBNET="172.21.0.0/16"
    else
        export CONTAINER_PREFIX="${PROJECT_PREFIX}"
        export NETWORK_PREFIX="${PROJECT_PREFIX}"
        export VOLUME_PREFIX="${PROJECT_PREFIX}"
        export NETWORK_SUBNET="172.22.0.0/16"
    fi

    print_debug "CONTAINER_PREFIX: $CONTAINER_PREFIX"

    # Derive TRUSTED_HOSTS - convert to JSON array format for pydantic
    export TRUSTED_HOSTS='["localhost","127.0.0.1","'${API_DOMAIN}'","'${BASE_DOMAIN}'","*.'${BASE_DOMAIN}'"]'

    # Derive CORS_ORIGINS (basic set, user can customize in generated .env file)
    export CORS_ORIGINS="http://localhost:3000,https://${BASE_DOMAIN},https://www.${BASE_DOMAIN},https://app.${BASE_DOMAIN}"

    # Environment-specific settings
    if [[ "$environment" == "staging" ]]; then
        export API_WORKERS="${STAGING_API_WORKERS:-1}"
        export CELERY_WORKERS="${STAGING_CELERY_WORKERS:-1}"
        export POSTGRES_HOST="${STAGING_POSTGRES_HOST:-postgres}"
        export POSTGRES_PORT="${STAGING_POSTGRES_PORT:-5432}"
        export DB_SSL_MODE="${STAGING_DB_SSL_MODE:-disable}"
        export ENABLE_DOCS="true"
        export LOG_LEVEL="INFO"
        export ENV_DISPLAY_NAME="Staging"
    else
        export API_WORKERS="${PRODUCTION_API_WORKERS:-4}"
        export CELERY_WORKERS="${PRODUCTION_CELERY_WORKERS:-4}"
        export POSTGRES_HOST="${PRODUCTION_POSTGRES_HOST}"
        export POSTGRES_PORT="${PRODUCTION_POSTGRES_PORT:-25060}"
        export DB_SSL_MODE="${PRODUCTION_DB_SSL_MODE:-require}"
        export ENABLE_DOCS="false"
        export LOG_LEVEL="WARNING"
        export ENV_DISPLAY_NAME="Production"
    fi

    print_success "Configuration values derived successfully"
    return 0
}

# Substitute placeholders in content
# Uses bash parameter expansion (cross-platform, no sed needed)
substitute_placeholders() {
    local content="$1"

    # Perform substitutions (ORDER MATTERS - most specific first!)
    # Domains
    content="${content//\{\{API_DOMAIN\}\}/${API_DOMAIN}}"
    content="${content//\{\{FLOWER_DOMAIN\}\}/${FLOWER_DOMAIN:-}}"
    content="${content//\{\{BASE_DOMAIN\}\}/${BASE_DOMAIN}}"
    content="${content//\{\{API_SUBDOMAIN\}\}/${API_SUBDOMAIN}}"
    content="${content//\{\{FLOWER_SUBDOMAIN\}\}/${FLOWER_SUBDOMAIN:-}}"

    # Project identifiers
    content="${content//\{\{PROJECT_NAME\}\}/${PROJECT_NAME}}"
    content="${content//\{\{PROJECT_PREFIX\}\}/${PROJECT_PREFIX}}"
    content="${content//\{\{CONTAINER_PREFIX\}\}/${CONTAINER_PREFIX}}"
    content="${content//\{\{NETWORK_PREFIX\}\}/${NETWORK_PREFIX}}"
    content="${content//\{\{VOLUME_PREFIX\}\}/${VOLUME_PREFIX}}"

    # Network
    content="${content//\{\{NETWORK_SUBNET\}\}/${NETWORK_SUBNET}}"

    # Email
    content="${content//\{\{ACME_EMAIL\}\}/${ACME_EMAIL}}"

    # Environment
    content="${content//\{\{ENVIRONMENT\}\}/${ENVIRONMENT:-production}}"
    content="${content//\{\{ENV_DISPLAY_NAME\}\}/${ENV_DISPLAY_NAME}}"
    content="${content//\{\{DEBUG\}\}/false}"
    content="${content//\{\{ENABLE_DOCS\}\}/${ENABLE_DOCS}}"
    content="${content//\{\{LOG_LEVEL\}\}/${LOG_LEVEL}}"

    # Server settings
    content="${content//\{\{API_WORKERS\}\}/${API_WORKERS}}"
    content="${content//\{\{CELERY_WORKERS\}\}/${CELERY_WORKERS}}"

    # Database
    content="${content//\{\{POSTGRES_HOST\}\}/${POSTGRES_HOST}}"
    content="${content//\{\{POSTGRES_PORT\}\}/${POSTGRES_PORT}}"
    content="${content//\{\{DB_SSL_MODE\}\}/${DB_SSL_MODE}}"

    # Security & Network
    content="${content//\{\{TRUSTED_HOSTS\}\}/${TRUSTED_HOSTS}}"
    content="${content//\{\{CORS_ORIGINS\}\}/${CORS_ORIGINS}}"

    # Secrets (these will be replaced with placeholders for user to fill or generated)
    content="${content//\{\{SECRET_KEY\}\}/${SECRET_KEY:-CHANGE_THIS_SECRET_KEY}}"
    content="${content//\{\{JWT_SECRET_KEY\}\}/${JWT_SECRET_KEY:-CHANGE_THIS_JWT_SECRET_KEY}}"
    content="${content//\{\{REDIS_PASSWORD\}\}/${REDIS_PASSWORD:-CHANGE_THIS_REDIS_PASSWORD}}"
    content="${content//\{\{FLOWER_USERNAME\}\}/${FLOWER_USERNAME:-admin}}"
    content="${content//\{\{FLOWER_PASSWORD\}\}/${FLOWER_PASSWORD:-CHANGE_THIS_FLOWER_PASSWORD}}"
    content="${content//\{\{GRAFANA_PASSWORD\}\}/${GRAFANA_PASSWORD:-CHANGE_THIS_GRAFANA_PASSWORD}}"

    # Database credentials
    content="${content//\{\{POSTGRES_USER\}\}/${POSTGRES_USER:-CHANGE_THIS_POSTGRES_USER}}"
    content="${content//\{\{POSTGRES_PASSWORD\}\}/${POSTGRES_PASSWORD:-CHANGE_THIS_POSTGRES_PASSWORD}}"
    content="${content//\{\{POSTGRES_DB\}\}/${POSTGRES_DB:-CHANGE_THIS_POSTGRES_DB}}"

    echo "$content"
}

# Process a template file and write output
process_template_file() {
    local template_file="$1"
    local output_file="$2"

    if [[ ! -f "$template_file" ]]; then
        print_error "Template file not found: $template_file"
        return 1
    fi

    print_debug "Processing template: $template_file → $output_file"

    # Read template content
    local content
    content=$(<"$template_file")

    # Add generated file header
    local header="# Generated from template - DO NOT EDIT DIRECTLY
# Edit config.env and regenerate using: ./scripts/setup.sh --force
# Generated at: $(date '+%Y-%m-%d %H:%M:%S')

"

    # Substitute placeholders
    content=$(substitute_placeholders "$content")

    # Create output directory if needed
    local output_dir
    output_dir=$(dirname "$output_file")
    mkdir -p "$output_dir"

    # Write output file
    echo -n "$header$content" > "$output_file"

    print_success "Generated: $output_file"
    return 0
}

# Validate no placeholders remain in file
validate_no_placeholders() {
    local file="$1"

    if [[ ! -f "$file" ]]; then
        print_error "File not found for validation: $file"
        return 1
    fi

    # Check for {{PLACEHOLDERS}}
    if grep -q '{{' "$file" 2>/dev/null; then
        print_error "Unresolved placeholders found in: $file"
        print_info "The following lines contain {{}} placeholders:"
        grep -n '{{' "$file" | head -5
        return 1
    fi

    print_success "No unresolved placeholders in: $file"
    return 0
}

# Export functions for subshells
export -f derive_config_values substitute_placeholders process_template_file
export -f validate_no_placeholders
