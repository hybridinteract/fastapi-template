#!/usr/bin/env bash

##############################################################################
# SSL Certificate Management
# Manages Let's Encrypt SSL certificates using Certbot
#
# Usage:
#   ./scripts/ssl.sh <command> [--env production|staging] [--staging]
#
# Commands:
#   setup    - Initial SSL certificate setup
#   renew    - Renew existing certificates
#   check    - Check certificate expiry
#   test     - Test SSL configuration
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
STAGING=false

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
            --staging)
                STAGING=true
                shift
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
SSL Certificate Management Script

Usage: $0 <command> [--env production|staging] [--staging]

Commands:
  setup    - Initial SSL certificate setup
  renew    - Renew existing certificates
  check    - Check certificate expiry
  test     - Test SSL configuration

Options:
  --env ENV      Environment to use (production or staging, default: production)
  --staging      Use Let's Encrypt staging server (for testing)
  -h, --help     Show this help message

Examples:
  $0 setup --env production              # Setup production SSL
  $0 setup --env production --staging    # Test with staging server
  $0 renew --env production               # Renew production certificates
  $0 check --env staging                    # Check staging certificates
  $0 test --env production                # Test production SSL

Notes:
  • Certificates are valid for 90 days
  • Let's Encrypt has rate limits (5 per domain per week)
  • Use --staging for testing to avoid rate limits
  • DNS must be configured before running setup

EOF
}

# Load configuration
load_ssl_config() {
    print_info "Loading configuration..."

    # Check Docker Compose
    if ! validate_docker_compose; then
        print_error "Docker Compose not available"
        exit 1
    fi
    COMPOSE="$(get_docker_compose_cmd)"

    # Load config.env
    if [[ ! -f "$DEPLOY_ROOT/config.env" ]]; then
        print_error "config.env not found"
        print_info "Run: ./scripts/setup.sh"
        exit 1
    fi

    set -a
    source "$DEPLOY_ROOT/config.env"
    set +a

    # Derive configuration values
    derive_config_values "$ENVIRONMENT"

    # Set domains
    API_DOMAIN="${API_SUBDOMAIN}.${BASE_DOMAIN}"
    # Only set FLOWER_DOMAIN if FLOWER_SUBDOMAIN is configured
    if [[ -n "${FLOWER_SUBDOMAIN:-}" ]]; then
        FLOWER_DOMAIN="${FLOWER_SUBDOMAIN}.${BASE_DOMAIN}"
    else
        FLOWER_DOMAIN=""
    fi
    EMAIL="${ACME_EMAIL}"

    # Set compose file
    COMPOSE_FILE="$DEPLOY_ROOT/generated/docker-compose.${ENVIRONMENT}.yml"
    if [[ ! -f "$COMPOSE_FILE" ]]; then
        print_error "Docker Compose file not found: $COMPOSE_FILE"
        print_info "Run: ./scripts/setup.sh --force"
        exit 1
    fi

    print_success "Configuration loaded"
}

# Check DNS configuration
check_dns() {
    local domain="$1"
    print_info "Checking DNS for $domain..."

    # Get server's public IP
    local server_ip
    server_ip=$(curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null || curl -s api.ipify.org 2>/dev/null || echo "")

    if [[ -z "$server_ip" ]]; then
        print_warning "Could not determine server IP address"
        return 1
    fi

    # Check if domain resolves
    if ! command_exists dig; then
        print_warning "dig not available, skipping DNS check"
        return 0
    fi

    local domain_ip
    domain_ip=$(dig +short "$domain" 2>/dev/null | tail -n1)

    if [[ -z "$domain_ip" ]]; then
        print_error "$domain does not resolve to any IP"
        return 1
    elif [[ "$domain_ip" == "$server_ip" ]]; then
        print_success "$domain resolves to $server_ip ✓"
        return 0
    else
        print_warning "$domain resolves to $domain_ip, but server IP is $server_ip"
        return 1
    fi
}

# Check containers are running
check_containers() {
    print_info "Checking containers..."

    # Check if nginx is running
    if docker ps --format '{{.Names}}' | grep -q "${CONTAINER_PREFIX}_nginx"; then
        print_success "Nginx container is running"
        return 0
    else
        print_warning "Nginx container is not running"
        print_info "SSL setup requires nginx for ACME challenge"
        return 1
    fi
}

# Test ACME challenge accessibility
test_acme_challenge() {
    print_info "Testing ACME challenge accessibility..."

    # Create test file
    local acme_dir="$DEPLOY_ROOT/certbot/www/.well-known/acme-challenge"
    mkdir -p "$acme_dir"
    echo "test" > "$acme_dir/test.txt"
    chmod -R 755 "$DEPLOY_ROOT/certbot/www"

    # Test HTTP access
    local test_url="http://${API_DOMAIN}/.well-known/acme-challenge/test.txt"
    local response
    response=$(curl -s -o /dev/null -w "%{http_code}" "$test_url" 2>/dev/null || echo "000")

    # Clean up test file
    rm -f "$acme_dir/test.txt"

    if [[ "$response" == "200" ]]; then
        print_success "ACME challenge accessible ✓"
        return 0
    elif [[ "$response" == "404" ]]; then
        print_success "ACME endpoint configured (404 is OK) ✓"
        return 0
    else
        print_warning "ACME challenge returned HTTP $response (may still work)"
        return 0
    fi
}

# Setup SSL certificates
setup_ssl() {
    print_header "SSL Certificate Setup - ${ENVIRONMENT}"

    load_ssl_config

    print_separator
    print_info "Configuration:"
    echo "  • API Domain: $API_DOMAIN"
    if [[ -n "$FLOWER_DOMAIN" ]]; then
        echo "  • Flower Domain: $FLOWER_DOMAIN"
    fi
    echo "  • Email: $EMAIL"
    echo "  • Environment: $ENVIRONMENT"
    if [[ "$STAGING" == "true" ]]; then
        echo "  • Mode: STAGING (testing mode)"
    else
        echo "  • Mode: PRODUCTION"
    fi
    echo ""

    # DNS validation
    print_separator
    print_info "Checking DNS configuration..."
    local dns_failed=0

    check_dns "$API_DOMAIN" || dns_failed=1
    if [[ -n "$FLOWER_DOMAIN" ]]; then
        check_dns "$FLOWER_DOMAIN" || dns_failed=1
    fi

    if [[ $dns_failed -eq 1 ]]; then
        print_separator
        print_error "DNS check failed for one or more domains"
        echo ""
        print_info "Make sure your DNS A records point to this server:"
        echo "  • $API_DOMAIN → Server IP"
        if [[ -n "$FLOWER_DOMAIN" ]]; then
            echo "  • $FLOWER_DOMAIN → Server IP"
        fi
        echo ""
        if ! confirm_action "Continue anyway?"; then
            print_info "SSL setup cancelled"
            exit 1
        fi
    fi

    # Create dummy self-signed certificates if they don't exist
    print_separator
    print_info "Checking for existing certificates..."

    local cert_path="$DEPLOY_ROOT/certbot/conf/live/$API_DOMAIN"
    if [[ ! -f "$cert_path/fullchain.pem" ]]; then
        print_warning "SSL certificates not found. Creating temporary self-signed certificates..."

        # Create certificate directories
        mkdir -p "$cert_path"
        if [[ -n "$FLOWER_DOMAIN" ]]; then
            mkdir -p "$DEPLOY_ROOT/certbot/conf/live/$FLOWER_DOMAIN"
        fi

        # Generate self-signed certificate for API domain
        openssl req -x509 -nodes -newkey rsa:2048 \
            -days 1 \
            -keyout "$cert_path/privkey.pem" \
            -out "$cert_path/fullchain.pem" \
            -subj "/CN=$API_DOMAIN" 2>/dev/null

        # Create chain.pem (same as fullchain for self-signed)
        cp "$cert_path/fullchain.pem" "$cert_path/chain.pem"

        # Generate self-signed certificate for Flower domain (if configured and enabled)
        # Note: Staging environments may have Flower disabled to save resources
        if [[ -n "$FLOWER_DOMAIN" ]] && ([[ "$ENVIRONMENT" != "staging" ]] || grep -q "flower:" "$COMPOSE_FILE" 2>/dev/null); then
            openssl req -x509 -nodes -newkey rsa:2048 \
                -days 1 \
                -keyout "$DEPLOY_ROOT/certbot/conf/live/$FLOWER_DOMAIN/privkey.pem" \
                -out "$DEPLOY_ROOT/certbot/conf/live/$FLOWER_DOMAIN/fullchain.pem" \
                -subj "/CN=$FLOWER_DOMAIN" 2>/dev/null

            cp "$DEPLOY_ROOT/certbot/conf/live/$FLOWER_DOMAIN/fullchain.pem" \
               "$DEPLOY_ROOT/certbot/conf/live/$FLOWER_DOMAIN/chain.pem"
        fi

        print_success "Temporary self-signed certificates created"
        print_warning "These will be replaced with Let's Encrypt certificates"
    else
        print_success "Certificates found"
    fi

    # Check containers
    print_separator
    if ! check_containers; then
        print_warning "Nginx is not running. Starting nginx..."
        $COMPOSE -f "$COMPOSE_FILE" up -d nginx
        print_info "Waiting for nginx to start..."
        sleep 10
    fi

    # Test ACME challenge
    print_separator
    test_acme_challenge

    # Confirm before proceeding
    print_separator
    print_warning "Ready to request SSL certificates from Let's Encrypt"
    echo ""
    if [[ "$STAGING" == "true" ]]; then
        print_info "Using STAGING server (certificates won't be trusted by browsers)"
    else
        print_warning "Using PRODUCTION server (rate limited: 5 per domain per week)"
    fi
    echo ""

    if ! confirm_action "Proceed with certificate request?"; then
        print_info "SSL setup cancelled"
        exit 0
    fi

    # Remove dummy self-signed certificates if they exist
    print_separator
    print_info "Removing temporary self-signed certificates..."

    # Check if certs are self-signed (only valid for 1 day)
    if [[ -f "$DEPLOY_ROOT/certbot/conf/live/$API_DOMAIN/fullchain.pem" ]]; then
        local cert_issuer=$(openssl x509 -in "$DEPLOY_ROOT/certbot/conf/live/$API_DOMAIN/fullchain.pem" -noout -issuer 2>/dev/null || echo "")
        if [[ "$cert_issuer" == *"$API_DOMAIN"* ]]; then
            print_info "Detected self-signed certificate, removing..."
            rm -rf "$DEPLOY_ROOT/certbot/conf/live/$API_DOMAIN"
            rm -rf "$DEPLOY_ROOT/certbot/conf/live/$FLOWER_DOMAIN"
            rm -rf "$DEPLOY_ROOT/certbot/conf/archive/$API_DOMAIN" 2>/dev/null || true
            rm -rf "$DEPLOY_ROOT/certbot/conf/archive/$FLOWER_DOMAIN" 2>/dev/null || true
            rm -rf "$DEPLOY_ROOT/certbot/conf/renewal/$API_DOMAIN.conf" 2>/dev/null || true
            rm -rf "$DEPLOY_ROOT/certbot/conf/renewal/$FLOWER_DOMAIN.conf" 2>/dev/null || true
            print_success "Temporary certificates removed"
        fi
    fi

    # Prepare certbot options
    local certbot_opts=(
        "certonly"
        "--webroot"
        "--webroot-path=/var/www/certbot"
        "--email" "$EMAIL"
        "--agree-tos"
        "--no-eff-email"
    )

    if [[ "$STAGING" == "true" ]]; then
        certbot_opts+=("--staging")
    fi

    # Request certificate for API domain
    print_separator
    print_info "Requesting certificate for $API_DOMAIN..."
    if $COMPOSE -f "$COMPOSE_FILE" run --rm --entrypoint certbot certbot \
        "${certbot_opts[@]}" -d "$API_DOMAIN"; then
        print_success "Certificate obtained for $API_DOMAIN ✓"
    else
        print_error "Failed to obtain certificate for $API_DOMAIN"
        echo ""
        print_info "Common issues:"
        echo "  • DNS not pointing to this server"
        echo "  • Port 80 blocked by firewall"
        echo "  • ACME challenge not accessible"
        echo "  • Rate limit exceeded (use --staging for testing)"
        exit 1
    fi

    # Request certificate for Flower domain (only if configured and enabled)
    if [[ -n "$FLOWER_DOMAIN" ]] && ([[ "$ENVIRONMENT" != "staging" ]] || grep -q "^[^#]*flower:" "$COMPOSE_FILE" 2>/dev/null); then
        print_separator
        print_info "Requesting certificate for $FLOWER_DOMAIN..."
        if $COMPOSE -f "$COMPOSE_FILE" run --rm --entrypoint certbot certbot \
            "${certbot_opts[@]}" -d "$FLOWER_DOMAIN"; then
            print_success "Certificate obtained for $FLOWER_DOMAIN ✓"
        else
            print_error "Failed to obtain certificate for $FLOWER_DOMAIN"
            exit 1
        fi
    else
        print_info "Skipping Flower SSL (not configured)"
    fi

    # Reload nginx
    print_separator
    print_info "Reloading nginx with SSL configuration..."

    # Test nginx config first
    if docker exec "${CONTAINER_PREFIX}_nginx" nginx -t 2>&1 | grep -q "successful"; then
        docker exec "${CONTAINER_PREFIX}_nginx" nginx -s reload
        print_success "Nginx reloaded ✓"
    else
        print_error "Nginx configuration test failed:"
        docker exec "${CONTAINER_PREFIX}_nginx" nginx -t || true
        exit 1
    fi

    # Final summary
    print_separator
    print_success "SSL Setup Complete!"
    echo ""
    echo "Your services are now secured:"
    echo "  ✓ https://$API_DOMAIN"
    if [[ -n "$FLOWER_DOMAIN" ]]; then
        echo "  ✓ https://$FLOWER_DOMAIN"
    fi
    echo ""
    print_info "Certificate details:"
    echo "  • Valid for 90 days"
    echo "  • Auto-renewal configured in Docker Compose"
    echo "  • Certbot runs twice daily to check for renewal"
    echo ""
    print_info "Test your SSL:"
    echo "  curl -I https://$API_DOMAIN/health"
    echo "  $0 test --env $ENVIRONMENT"
    echo ""
}

# Renew SSL certificates
renew_ssl() {
    print_header "SSL Certificate Renewal - ${ENVIRONMENT}"

    load_ssl_config

    print_info "Renewing certificates for:"
    echo "  • $API_DOMAIN"
    echo "  • $FLOWER_DOMAIN"
    echo ""

    # Run certbot renew
    print_info "Running certbot renew..."
    if $COMPOSE -f "$COMPOSE_FILE" run --rm --entrypoint certbot certbot renew \
        --webroot \
        --webroot-path=/var/www/certbot; then
        print_success "Certificates checked/renewed ✓"
    else
        print_error "Certificate renewal failed"
        exit 1
    fi

    # Reload nginx
    print_info "Reloading nginx..."
    if docker exec "${CONTAINER_PREFIX}_nginx" nginx -s reload 2>/dev/null; then
        print_success "Nginx reloaded ✓"
    else
        print_warning "Could not reload nginx (may not be running)"
    fi

    print_separator
    print_success "Certificate renewal complete!"
}

# Check certificate expiry
check_ssl() {
    print_header "SSL Certificate Status - ${ENVIRONMENT}"

    load_ssl_config

    local domains=("$API_DOMAIN" "$FLOWER_DOMAIN")

    for domain in "${domains[@]}"; do
        print_separator
        print_info "Checking $domain..."

        # Check if certificate exists
        if $COMPOSE -f "$COMPOSE_FILE" run --rm --entrypoint certbot certbot \
            certificates -d "$domain" 2>/dev/null | grep -q "$domain"; then

            # Get certificate info
            local cert_info
            cert_info=$($COMPOSE -f "$COMPOSE_FILE" run --rm --entrypoint certbot certbot \
                certificates -d "$domain" 2>/dev/null)

            # Extract expiry date
            local expiry
            expiry=$(echo "$cert_info" | grep "Expiry Date" | head -1 | awk '{print $3, $4, $5}')

            if [[ -n "$expiry" ]]; then
                print_success "Certificate found for $domain"
                echo "  Expires: $expiry"

                # Calculate days until expiry (cross-platform)
                if command_exists date; then
                    local expiry_epoch now_epoch days_left
                    if [[ "$OSTYPE" == "darwin"* ]]; then
                        expiry_epoch=$(date -j -f "%Y-%m-%d %H:%M:%S" "$expiry" +%s 2>/dev/null || echo "0")
                    else
                        expiry_epoch=$(date -d "$expiry" +%s 2>/dev/null || echo "0")
                    fi
                    now_epoch=$(date +%s)

                    if [[ "$expiry_epoch" != "0" ]]; then
                        days_left=$(( (expiry_epoch - now_epoch) / 86400 ))

                        if [[ $days_left -lt 30 ]]; then
                            print_warning "Certificate expires in $days_left days - renewal recommended"
                        else
                            print_info "Certificate valid for $days_left more days"
                        fi
                    fi
                fi
            else
                print_warning "Could not parse expiry date"
            fi
        else
            print_error "No certificate found for $domain"
        fi
    done

    print_separator
}

# Test SSL configuration
test_ssl() {
    print_header "SSL Configuration Test - ${ENVIRONMENT}"

    load_ssl_config

    local domains=("$API_DOMAIN" "$FLOWER_DOMAIN")

    for domain in "${domains[@]}"; do
        print_separator
        print_info "Testing $domain..."

        # Test with OpenSSL
        if command_exists openssl; then
            print_info "Testing SSL certificate..."
            if echo | openssl s_client -connect "$domain:443" -servername "$domain" 2>/dev/null | \
                grep -q "Verify return code: 0"; then
                print_success "SSL certificate verification successful ✓"
            else
                print_warning "SSL certificate verification failed"
            fi
        else
            print_warning "openssl not available, skipping certificate verification"
        fi

        # Test with curl
        if command_exists curl; then
            print_info "Testing HTTPS connection..."
            if curl -sI "https://$domain" -m 10 2>/dev/null | grep -q "HTTP/"; then
                local http_code
                http_code=$(curl -s -o /dev/null -w "%{http_code}" "https://$domain" -m 10 2>/dev/null)
                print_success "HTTPS connection successful (HTTP $http_code) ✓"
            else
                print_warning "HTTPS connection failed"
            fi
        fi
    done

    print_separator
    print_success "SSL testing complete!"
}

# Main execution
main() {
    parse_arguments "$@"

    case "$COMMAND" in
        setup)
            setup_ssl
            ;;
        renew)
            renew_ssl
            ;;
        check)
            check_ssl
            ;;
        test)
            test_ssl
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
