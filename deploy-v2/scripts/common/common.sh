#!/usr/bin/env bash

##############################################################################
# Common Utilities Library
# Provides color definitions, print functions, and common helpers
##############################################################################

# Color definitions
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly MAGENTA='\033[0;35m'
readonly NC='\033[0m' # No Color

# Print functions
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║  $1${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_debug() {
    if [[ "${DEBUG:-false}" == "true" ]]; then
        echo -e "${CYAN}[DEBUG]${NC} $1"
    fi
}

# Confirm action with user
confirm_action() {
    local prompt="$1"
    local default="${2:-n}"

    if [[ "$default" == "y" ]]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi

    read -p "$(echo -e "${YELLOW}$prompt${NC}")" response
    response=${response:-$default}

    case "$response" in
        [yY][eE][sS]|[yY])
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

# Print separator line
print_separator() {
    echo -e "${BLUE}────────────────────────────────────────${NC}"
}

# Get script directory (absolute path)
get_script_dir() {
    echo "$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
}

# Get deploy-v2 root directory
get_deploy_root() {
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[1]}")" && pwd)"
    # If we're in scripts/ or scripts/common/, go up to deploy-v2/
    if [[ "$(basename "$script_dir")" == "common" ]]; then
        echo "$(dirname "$(dirname "$script_dir")")"
    elif [[ "$(basename "$script_dir")" == "scripts" ]]; then
        echo "$(dirname "$script_dir")"
    else
        echo "$script_dir"
    fi
}

# Load configuration file
load_config() {
    local deploy_root="${1:-$(get_deploy_root)}"
    local config_file="$deploy_root/config.env"

    if [[ ! -f "$config_file" ]]; then
        print_error "config.env not found at: $config_file"
        print_info "Run './scripts/setup.sh' first to initialize the deployment"
        return 1
    fi

    print_debug "Loading config from: $config_file"

    # Validate config file format before sourcing
    if ! grep -q "^PROJECT_NAME=" "$config_file"; then
        print_error "config.env appears to be invalid or corrupted"
        print_info "Expected format: PROJECT_NAME=value"
        print_info "First few lines of config.env:"
        head -5 "$config_file" 2>/dev/null || true
        print_info "Please regenerate config.env by running: ./scripts/setup.sh"
        return 1
    fi

    # Source config file with auto-export and error handling
    set -a
    if ! source "$config_file" 2>&1; then
        set +a
        print_error "Failed to load config.env - syntax error in file"
        print_info "Please check the file and regenerate if needed: ./scripts/setup.sh"
        return 1
    fi
    set +a

    # Validate required variables are set
    local required_vars=("PROJECT_NAME" "BASE_DOMAIN")
    local missing=0
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            print_error "Required variable not set: $var"
            ((missing++))
        fi
    done

    if [[ $missing -gt 0 ]]; then
        print_error "config.env is missing required variables"
        print_info "Please regenerate: ./scripts/setup.sh"
        return 1
    fi

    print_success "Configuration loaded"
    return 0
}

# Check if command exists
command_exists() {
    command -v "$1" &>/dev/null
}

# Get timestamp
get_timestamp() {
    date +"%Y-%m-%d_%H-%M-%S"
}

# Sanitize project name (remove special chars, lowercase)
sanitize_project_name() {
    local name="$1"
    # Convert to lowercase, replace spaces/dots with hyphens, remove other special chars
    echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' .' '-' | sed 's/[^a-z0-9-]//g' | cut -c1-20
}

# Generate secure random string
generate_secret() {
    local length="${1:-64}"

    if command_exists openssl; then
        openssl rand -hex "$((length / 2))"
    elif [[ -c /dev/urandom ]]; then
        tr -dc 'a-zA-Z0-9' < /dev/urandom | head -c "$length"
    else
        print_error "No secure random source available (need openssl or /dev/urandom)"
        return 1
    fi
}

# Get docker compose command (V2 preferred, V1 fallback)
get_docker_compose_cmd() {
    # Check if already detected
    if [[ -n "${DOCKER_COMPOSE_CMD:-}" ]]; then
        echo "$DOCKER_COMPOSE_CMD"
        return 0
    fi

    # Prefer docker compose (V2)
    if docker compose version &>/dev/null; then
        export DOCKER_COMPOSE_CMD="docker compose"
        echo "docker compose"
        return 0
    # Fallback to docker-compose (V1)
    elif command_exists docker-compose; then
        export DOCKER_COMPOSE_CMD="docker-compose"
        echo "docker-compose"
        return 0
    else
        print_error "Docker Compose not found (neither 'docker compose' nor 'docker-compose')"
        return 1
    fi
}

# Export functions for subshells if needed
export -f print_header print_info print_success print_error print_warning print_debug
export -f print_separator confirm_action get_timestamp sanitize_project_name
export -f generate_secret get_docker_compose_cmd command_exists
