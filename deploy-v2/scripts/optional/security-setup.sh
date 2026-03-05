#!/usr/bin/env bash

##############################################################################
# Server Security Setup Script
# Configures UFW firewall, fail2ban, SSH hardening, and system security
#
# Usage: sudo ./scripts/security-setup.sh
#
# Requirements:
#   • Must be run as root (use sudo)
#   • Ubuntu/Debian-based system
#   • Internet connection for package installation
##############################################################################

set -euo pipefail

# Script directory and imports
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPTS_ROOT="$(dirname "$SCRIPT_DIR")"
readonly DEPLOY_ROOT="$(dirname "$SCRIPTS_ROOT")"

# Source common libraries
source "$SCRIPTS_ROOT/common/common.sh"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    print_error "This script must be run as root"
    print_info "Usage: sudo $0"
    exit 1
fi

# Load configuration for email
ADMIN_EMAIL="admin@example.com"
if [[ -f "$DEPLOY_ROOT/config.env" ]]; then
    source "$DEPLOY_ROOT/config.env" 2>/dev/null || true
    ADMIN_EMAIL="${ACME_EMAIL:-admin@example.com}"
fi

# System update
update_system() {
    print_header "System Update"

    print_info "Updating package lists..."
    apt-get update

    print_info "Upgrading packages..."
    apt-get upgrade -y

    print_success "System updated"
}

# UFW Firewall setup
setup_ufw() {
    print_header "UFW Firewall Setup"

    # Install UFW if not installed
    if ! command_exists ufw; then
        print_info "Installing UFW..."
        apt-get install -y ufw
    fi

    # Reset UFW to default
    print_info "Resetting UFW to defaults..."
    ufw --force reset

    # Set default policies
    print_info "Setting default policies..."
    ufw default deny incoming
    ufw default allow outgoing

    # Allow SSH (IMPORTANT: Do this before enabling!)
    print_info "Allowing SSH on port 22..."
    ufw allow 22/tcp comment 'SSH'

    # Allow HTTP and HTTPS
    print_info "Allowing HTTP (80) and HTTPS (443)..."
    ufw allow 80/tcp comment 'HTTP'
    ufw allow 443/tcp comment 'HTTPS'

    # Rate limit SSH connections (prevent brute force)
    print_info "Enabling SSH rate limiting..."
    ufw limit 22/tcp

    # Enable UFW
    print_info "Enabling UFW firewall..."
    ufw --force enable

    # Show status
    print_separator
    ufw status verbose

    print_separator
    print_success "UFW firewall configured"
}

# Fail2ban setup
setup_fail2ban() {
    print_header "Fail2ban Setup"

    # Install fail2ban
    if ! command_exists fail2ban-client; then
        print_info "Installing fail2ban..."
        apt-get install -y fail2ban
    fi

    # Create custom jail configuration
    print_info "Creating fail2ban configuration..."
    cat > /etc/fail2ban/jail.local <<EOF
[DEFAULT]
# Ban hosts for 1 hour
bantime = 3600

# A host is banned if it has generated "maxretry" during the last "findtime"
findtime = 600
maxretry = 5

# Ignore local connections
ignoreip = 127.0.0.1/8 ::1

# Email notifications
destemail = ${ADMIN_EMAIL}
sendername = Fail2Ban Security Alert
action = %(action_mwl)s

# SSH Protection
[sshd]
enabled = true
port = 22
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600

# Nginx HTTP Auth
[nginx-http-auth]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 3
bantime = 3600

# Nginx No Script
[nginx-noscript]
enabled = true
port = http,https
logpath = /var/log/nginx/access.log
maxretry = 6
bantime = 3600

# Nginx Bad Bots
[nginx-badbots]
enabled = true
port = http,https
logpath = /var/log/nginx/access.log
maxretry = 2
bantime = 86400

# Nginx No Proxy
[nginx-noproxy]
enabled = true
port = http,https
logpath = /var/log/nginx/access.log
maxretry = 2
bantime = 86400

# Nginx Rate Limit
[nginx-limit-req]
enabled = true
port = http,https
logpath = /var/log/nginx/error.log
maxretry = 10
findtime = 600
bantime = 3600
EOF

    # Enable and start fail2ban
    print_info "Enabling fail2ban..."
    systemctl enable fail2ban
    systemctl restart fail2ban

    # Wait for fail2ban to start
    sleep 3

    # Show status
    print_separator
    fail2ban-client status

    print_separator
    print_success "Fail2ban configured"
}

# Automatic security updates
setup_auto_updates() {
    print_header "Automatic Security Updates"

    # Install unattended-upgrades
    print_info "Installing unattended-upgrades..."
    apt-get install -y unattended-upgrades apt-listchanges

    # Configure automatic updates
    print_info "Configuring automatic security updates..."
    cat > /etc/apt/apt.conf.d/50unattended-upgrades <<'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}";
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};

Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::InstallOnShutdown "false";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
Unattended-Upgrade::Automatic-Reboot-Time "03:00";
EOF

    # Enable automatic updates
    cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Download-Upgradeable-Packages "1";
APT::Periodic::AutocleanInterval "7";
APT::Periodic::Unattended-Upgrade "1";
EOF

    print_success "Automatic security updates configured"
}

# SSH hardening
harden_ssh() {
    print_header "SSH Hardening"

    # Backup original sshd_config
    print_info "Backing up SSH configuration..."
    cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup.$(date +%Y%m%d_%H%M%S)

    # Create hardening config directory if it doesn't exist
    mkdir -p /etc/ssh/sshd_config.d

    # Apply SSH hardening
    print_info "Applying SSH hardening configuration..."
    cat > /etc/ssh/sshd_config.d/99-hardening.conf <<'EOF'
# SSH Hardening Configuration
# Generated by deploy-v2 security-setup.sh

# Disable root login
PermitRootLogin no

# Disable password authentication (use SSH keys only)
# WARNING: Make sure you have SSH keys set up before uncommenting!
# PasswordAuthentication no

# Disable empty passwords
PermitEmptyPasswords no

# Disable X11 forwarding
X11Forwarding no

# Limit authentication attempts
MaxAuthTries 3

# Set login grace time
LoginGraceTime 20

# Enable public key authentication
PubkeyAuthentication yes

# Disable host-based authentication
HostbasedAuthentication no

# Disable rhosts authentication
IgnoreRhosts yes

# Use strong ciphers and MACs
Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com,aes128-gcm@openssh.com
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
KexAlgorithms curve25519-sha256,curve25519-sha256@libssh.org,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512

# Enable strict mode
StrictModes yes

# Set client alive interval (prevent idle disconnects)
ClientAliveInterval 300
ClientAliveCountMax 2
EOF

    # Test SSH configuration
    print_info "Testing SSH configuration..."
    if sshd -t 2>&1; then
        print_success "SSH configuration is valid"
        print_separator
        print_warning "SSH will be restarted. Make sure you have another SSH session open!"
        print_info "Press Enter to restart SSH, or Ctrl+C to cancel..."
        read -r

        systemctl restart sshd
        print_success "SSH hardened and restarted"
    else
        print_error "SSH configuration test failed"
        print_warning "Reverting changes..."
        rm -f /etc/ssh/sshd_config.d/99-hardening.conf
        print_error "SSH hardening aborted due to configuration error"
        return 1
    fi
}

# Kernel security settings (sysctl)
setup_sysctl_security() {
    print_header "Kernel Security Settings"

    print_info "Configuring kernel security parameters..."
    cat > /etc/sysctl.d/99-security.conf <<'EOF'
# Network Security Settings
# Generated by deploy-v2 security-setup.sh

# IP Spoofing protection
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1

# Ignore ICMP redirects
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv6.conf.all.accept_redirects = 0
net.ipv6.conf.default.accept_redirects = 0

# Ignore send redirects
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0

# Disable source packet routing
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
net.ipv6.conf.all.accept_source_route = 0
net.ipv6.conf.default.accept_source_route = 0

# Log Martians
net.ipv4.conf.all.log_martians = 1
net.ipv4.icmp_ignore_bogus_error_responses = 1

# Ignore ICMP ping requests (set to 1 to ignore all pings)
net.ipv4.icmp_echo_ignore_all = 0

# Ignore broadcast ping requests
net.ipv4.icmp_echo_ignore_broadcasts = 1

# Enable TCP SYN Cookie Protection (DDoS protection)
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_max_syn_backlog = 2048
net.ipv4.tcp_synack_retries = 2
net.ipv4.tcp_syn_retries = 5

# Enable IP forwarding (required for Docker)
net.ipv4.ip_forward = 1

# Disable IPv6 if not needed (uncomment if you don't use IPv6)
# net.ipv6.conf.all.disable_ipv6 = 1
# net.ipv6.conf.default.disable_ipv6 = 1
# net.ipv6.conf.lo.disable_ipv6 = 1
EOF

    # Apply sysctl settings
    print_info "Applying kernel security settings..."
    sysctl -p /etc/sysctl.d/99-security.conf > /dev/null

    print_success "Kernel security settings applied"
}

# Main execution
main() {
    print_header "Server Security Setup"

    echo ""
    print_info "This script will:"
    echo "  • Update system packages"
    echo "  • Configure UFW firewall (allow SSH, HTTP, HTTPS)"
    echo "  • Install and configure fail2ban"
    echo "  • Enable automatic security updates"
    echo "  • Apply kernel security settings"
    echo "  • Optionally harden SSH configuration"
    echo ""
    print_warning "This script requires root privileges and will modify system configuration"
    echo ""

    if ! confirm_action "Continue with security setup?"; then
        print_info "Security setup cancelled"
        exit 0
    fi

    print_separator

    # System update
    update_system
    print_separator

    # UFW Firewall
    setup_ufw
    print_separator

    # Fail2ban
    setup_fail2ban
    print_separator

    # Automatic updates
    setup_auto_updates
    print_separator

    # SSH hardening (optional)
    print_info "SSH hardening (optional)"
    echo ""
    print_warning "SSH hardening will:"
    echo "  • Disable root login"
    echo "  • Limit authentication attempts"
    echo "  • Use strong ciphers"
    echo ""
    print_info "Make sure you have SSH keys configured before disabling password auth!"
    echo ""

    if confirm_action "Do you want to harden SSH configuration?"; then
        harden_ssh
    else
        print_info "Skipping SSH hardening"
    fi
    print_separator

    # Sysctl security
    setup_sysctl_security
    print_separator

    # Final summary
    print_header "Security Setup Complete!"

    echo ""
    print_success "Security measures applied:"
    echo "  ✓ UFW firewall enabled (SSH, HTTP, HTTPS allowed)"
    echo "  ✓ Fail2ban configured with nginx and SSH protection"
    echo "  ✓ Automatic security updates enabled"
    echo "  ✓ Kernel security settings applied"
    echo ""

    print_info "Next steps:"
    echo "  1. Check fail2ban status: sudo fail2ban-client status"
    echo "  2. Check UFW rules: sudo ufw status verbose"
    echo "  3. Monitor fail2ban: sudo tail -f /var/log/fail2ban.log"
    echo "  4. Review SSH config: cat /etc/ssh/sshd_config.d/99-hardening.conf"
    echo "  5. Consider setting up SSH keys and disabling password auth"
    echo ""

    print_info "Email notifications sent to: $ADMIN_EMAIL"
    echo ""
}

# Run main
main
