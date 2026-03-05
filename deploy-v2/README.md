# Deploy-v2: Reusable Deployment System

A template-based, zero-hardcoded deployment system for FastAPI + PostgreSQL + Redis + Celery applications. Deploy the same codebase to different servers and domains by changing a single configuration file.

## Table of Contents

- [What Makes This Different](#what-makes-this-different)
- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Detailed Setup Guide](#detailed-setup-guide)
- [Configuration Reference](#configuration-reference)
- [Available Commands](#available-commands)
- [Usage Examples](#usage-examples)
- [Troubleshooting](#troubleshooting)
- [How It Works](#how-it-works)

---

## What Makes This Different

### Old `deploy/` System
❌ Hardcoded domain references across multiple files
❌ Manual find/replace with sed (different on macOS vs Linux)
❌ Project-specific naming in containers/networks
❌ Configuration duplicated across env files, nginx configs, scripts
❌ Difficult to deploy to a new domain or server

### New `deploy-v2/` System
✅ **Zero hardcoded domains** - everything from `config.env`
✅ **Template-based** - `{{PLACEHOLDERS}}` auto-replaced
✅ **Project-agnostic** - works for any project
✅ **Cross-platform** - bash string substitution (no sed)
✅ **Single source of truth** - one config file controls everything
✅ **Environment support** - production and staging from same templates

---

## Quick Start

**📚 New to deployment? See [QUICK_START.md](./QUICK_START.md) for step-by-step guide!**

```bash
# 1. Navigate to deploy-v2 directory
cd deploy-v2

# 2. Make scripts executable (on server)
chmod +x scripts/*.sh scripts/optional/*.sh scripts/common/*.sh

# 3. Run complete setup (system checks + config + generation)
./scripts/setup.sh

# 4. Review and customize the generated environment file
nano .env.production
# Add your API keys (Fast2SMS, Sentry, DO Spaces, etc.)

# 5. Validate configuration
./scripts/validate.sh --env production

# 6. Deploy to production
./scripts/deploy.sh init --env production

# 7. Setup SSL certificates
./scripts/ssl.sh setup --env production

# 8. Check deployment status
./scripts/deploy.sh status --env production
```

**Done!** Your application is now deployed with SSL at `https://api.yourdomain.com` 🎉

---

## Prerequisites

### Required
- **Docker** (v20.10+) - [Install Docker](https://docs.docker.com/get-docker/)
- **Docker Compose** (v2.0+ or v1.29+)
- **Git** - For version control
- **Bash** (v4.0+) - Already on Linux/macOS

### Optional but Recommended
- **OpenSSL** - For generating secure secrets (usually pre-installed)
- **Domain with DNS access** - For production deployment
- **Server with root access** - For production deployment

### Verify Prerequisites

```bash
# Check Docker
docker --version
docker compose version  # or docker-compose --version

# Check Bash version
bash --version

# Check OpenSSL
openssl version
```

---

## Detailed Setup Guide

### Step 1: Complete Setup (System Checks + Configuration)

Run the complete setup script:

```bash
cd deploy-v2
./scripts/setup.sh
```

**This will automatically:**
1. ✅ Check Docker, Docker Compose, and system requirements
2. ✅ Check port availability (80, 443)
3. ✅ Check disk space
4. ✅ Collect your configuration interactively
5. ✅ Generate all configuration files

**You will be prompted for:**

1. **Project name** (e.g., "myhotel", "bookingapp")
   - Used for container names and identification
   - Stagingnumeric, hyphens, underscores allowed

2. **Base domain** (e.g., "example.com")
   - Your main domain name
   - Subdomains will be created automatically

3. **API subdomain** (default: "api")
   - API will be accessible at: `api.example.com`

4. **Flower subdomain** (default: "flower")
   - Celery monitoring at: `flower.example.com`

5. **Admin email** (e.g., "admin@example.com")
   - Used for SSL certificate notifications
   - Let's Encrypt renewal emails

**What happens:**
- Verifies system prerequisites
- Creates `config.env` with your settings
- Generates secure random secrets (SECRET_KEY, JWT_SECRET_KEY, etc.)
- Creates `.env.production` and/or `.env.staging` from templates
- Generates Docker Compose files
- Generates nginx configurations
- Generates Redis configurations

### Step 2: Configure Environment Variables

Edit the generated `.env.production` file:

```bash
nano .env.production
# or
code .env.production
```

**Required Configuration:**

1. **Database Credentials** (if using managed database)
   ```bash
   POSTGRES_HOST=your-db-host.db.ondigitalocean.com
   POSTGRES_PORT=25060
   POSTGRES_USER=your_db_user
   POSTGRES_PASSWORD=your_secure_password
   POSTGRES_DB=your_database_name
   ```

2. **Third-party API Keys** (if needed)
   ```bash
   # SMS Service (Fast2SMS)
   FAST2SMS_API_KEY=your_fast2sms_key

   # Object Storage (DigitalOcean Spaces)
   DO_SPACES_KEY=your_spaces_key
   DO_SPACES_SECRET=your_spaces_secret
   DO_SPACES_BUCKET=your_bucket_name

   # Error Tracking (Sentry)
   SENTRY_DSN=your_sentry_dsn
   ```

3. **Verify Auto-Generated Secrets**
   ```bash
   # These should already be filled with secure random values
   SECRET_KEY=<64-character-random-string>
   JWT_SECRET_KEY=<64-character-random-string>
   REDIS_PASSWORD=<32-character-random-string>
   FLOWER_PASSWORD=<24-character-random-string>
   ```

### Step 3: DNS Configuration

Before deploying, configure your DNS records:

**Required DNS Records:**

| Type | Name | Value | TTL |
|------|------|-------|-----|
| A | api.example.com | Your Server IP | 300 |
| A | flower.example.com | Your Server IP | 300 |

**Verify DNS:**
```bash
# Check if DNS is resolving
nslookup api.example.com
nslookup flower.example.com

# Or use dig
dig api.example.com +short
dig flower.example.com +short
```

**Note:** DNS propagation can take 5-60 minutes.

### Step 4: Validate Configuration

Run the validation script to catch any issues:

```bash
./scripts/validate.sh --env production
```

**What it checks:**
- ✓ `config.env` exists and is valid
- ✓ `.env.production` exists
- ✓ No placeholder values (CHANGE_THIS) remain
- ✓ Secret keys are at least 32 characters
- ✓ Docker is installed and running
- ✓ Docker Compose is available
- ✓ Generated files exist (docker-compose, nginx configs)
- ✓ Docker Compose syntax is valid
- ✓ Nginx configuration syntax is valid
- ✓ DNS resolves (warning if not ready)
- ✓ Ports 80 and 443 are available

**Exit codes:**
- `0` = All checks passed ✅
- `1` = Critical errors found ❌ (must fix before deploying)
- `2` = Warnings only ⚠️ (can proceed with caution)

### Step 5: Initial Deployment

Deploy all services for the first time:

```bash
./scripts/deploy.sh init --env production
```

**What happens:**
1. Validates prerequisites (Docker, config files)
2. Pulls Docker images
3. Builds application containers
4. Generates Redis password configuration
5. Creates Docker network and volumes
6. Starts all services:
   - Nginx (reverse proxy)
   - Certbot (SSL certificates)
   - Redis (cache & message broker)
   - API (FastAPI application)
   - Celery Worker (background tasks)
   - Celery Beat (scheduled tasks)
   - Flower (Celery monitoring)
7. Waits for health checks
8. Displays service status

**Expected output:**
```
✓ Docker is available and running
✓ Configuration loaded
✓ Generated Redis password configuration
✓ Building and starting services...
✓ All services started successfully

Service Status:
  nginx      ✓ healthy
  api        ✓ healthy
  redis      ✓ healthy
  celery     ✓ running
  flower     ✓ healthy

Next step: Setup SSL certificates
  ./scripts/ssl.sh setup --env production
```

### Step 6: Setup SSL Certificates

Obtain free SSL certificates from Let's Encrypt:

```bash
./scripts/ssl.sh setup --env production
```

**What happens:**
1. Validates DNS configuration
2. Tests ACME challenge endpoints
3. Requests certificates for:
   - `api.example.com`
   - `flower.example.com`
4. Installs certificates in nginx
5. Reloads nginx with SSL configuration
6. Sets up automatic renewal

**Certificate Renewal:**

Certificates auto-renew via the `certbot` container (runs every 12 hours).

To manually renew:
```bash
./scripts/ssl.sh renew --env production
```

To check certificate expiry:
```bash
./scripts/ssl.sh check --env production
```

### Step 7: Verify Deployment

Check that everything is working:

```bash
# Check service status
./scripts/deploy.sh status --env production

# View logs
./scripts/deploy.sh logs --env production

# Test API endpoint
curl https://api.example.com/health

# Test Flower dashboard (in browser)
# https://flower.example.com
# (use FLOWER_USERNAME and FLOWER_PASSWORD from .env.production)
```

---

## Configuration Reference

### config.env (Single Source of Truth)

Located at: `deploy-v2/config.env`

**Core Settings:**
```bash
# Project Identity
PROJECT_NAME=myhotel               # Your project name
BASE_DOMAIN=example.com            # Your main domain

# Subdomains
API_SUBDOMAIN=api                  # API accessible at api.example.com
FLOWER_SUBDOMAIN=flower            # Flower at flower.example.com

# Contact
ACME_EMAIL=admin@example.com       # SSL certificate notifications
```

**Environment-Specific Settings:**
```bash
# Production
PRODUCTION_API_WORKERS=4           # Gunicorn workers
PRODUCTION_CELERY_WORKERS=4        # Celery concurrency
PRODUCTION_POSTGRES_HOST=db-managed.digitalocean.com
PRODUCTION_POSTGRES_PORT=25060
PRODUCTION_DB_SSL_MODE=require

# Staging (for testing)
STAGING_API_WORKERS=2                # Fewer workers for staging
STAGING_CELERY_WORKERS=2
STAGING_POSTGRES_HOST=postgres       # Uses containerized PostgreSQL
STAGING_POSTGRES_PORT=5432
STAGING_DB_SSL_MODE=disable
```

**Auto-Derived Values:**

These are computed automatically by `setup.sh`:

```bash
API_DOMAIN = api.example.com       # ${API_SUBDOMAIN}.${BASE_DOMAIN}
FLOWER_DOMAIN = flower.example.com # ${FLOWER_SUBDOMAIN}.${BASE_DOMAIN}
PROJECT_PREFIX = myhotel           # Sanitized project name
CONTAINER_PREFIX = myhotel_*       # Container names
NETWORK_PREFIX = myhotel_network   # Docker network
```

### Changing Configuration

**To change domain or settings:**

1. Edit `config.env`:
   ```bash
   nano config.env
   # Change BASE_DOMAIN to new domain
   ```

2. Regenerate configurations:
   ```bash
   ./scripts/setup.sh --force
   ```

3. Update deployment:
   ```bash
   ./scripts/deploy.sh update --env production
   ./scripts/ssl.sh setup --env production
   ```

---

## Available Commands

### Core Scripts

#### 1. `setup.sh` - Complete Initial Setup
```bash
# Run interactive setup (system checks + config + generation)
./scripts/setup.sh

# Force regenerate existing configuration
./scripts/setup.sh --force
```

#### 2. `validate.sh` - Configuration Validation
```bash
# Validate configuration before deployment
./scripts/validate.sh --env production
./scripts/validate.sh --env staging
```

#### 3. `deploy.sh` - Deployment Management

```bash
# Initial deployment
./scripts/deploy.sh init --env production

# Update deployment (git pull, rebuild, rolling restart)
./scripts/deploy.sh update --env production

# Restart all services
./scripts/deploy.sh restart --env production

# Stop all services
./scripts/deploy.sh stop --env production

# Check service status
./scripts/deploy.sh status --env production

# View logs (live tail)
./scripts/deploy.sh logs --env production
```

#### 4. `ssl.sh` - SSL Certificate Management

```bash
# Initial SSL setup
./scripts/ssl.sh setup --env production

# Force certificate renewal
./scripts/ssl.sh renew --env production

# Check certificate expiry
./scripts/ssl.sh check --env production

# Test SSL configuration
./scripts/ssl.sh test --env production

# Test with Let's Encrypt staging (no rate limits)
./scripts/ssl.sh setup --env production --staging
```

### Optional Scripts

#### 5. `backup.sh` - Database Backups (Optional)

```bash
# Full backup (database, Redis, logs, config)
./scripts/optional/backup.sh full --env production

# Database only backup
./scripts/optional/backup.sh db --env production

# Restore from backup
./scripts/optional/backup.sh restore --env production backups/backup.tar.gz
```

#### 6. `security-setup.sh` - Server Hardening (Optional)

```bash
# Setup firewall, fail2ban, automatic updates (run once on fresh server)
sudo ./scripts/optional/security-setup.sh
```

---

## Usage Examples

### Example 1: Deploy Production

```bash
cd deploy-v2

# Complete setup (checks + config + generation)
./scripts/setup.sh
# Enter: myhotel, example.com, api, flower, admin@example.com

# Configure environment
nano .env.production
# Add database credentials and API keys

# Validate
./scripts/validate.sh --env production

# Deploy
./scripts/deploy.sh init --env production

# Setup SSL
./scripts/ssl.sh setup --env production

# Verify
curl https://api.example.com/health
```

### Example 2: Deploy Staging Environment

```bash
cd deploy-v2

# Staging environment already created by setup.sh
# Just customize if needed
nano .env.staging

# Deploy staging
./scripts/deploy.sh init --env staging

# Setup SSL for staging
./scripts/ssl.sh setup --env staging

# Check status
./scripts/deploy.sh status --env staging
```

### Example 3: Update Production Code

```bash
# Pull latest code
cd /path/to/salescrm-backend
git pull origin main

# Update deployment (auto: backup, rebuild, migrate, restart)
cd deploy-v2
./scripts/deploy.sh update --env production

# Check logs
./scripts/deploy.sh logs --env production
```

### Example 4: Move to New Domain

```bash
# Edit config
nano config.env
# Change: BASE_DOMAIN=newdomain.com

# Regenerate all configs
./scripts/setup.sh --force

# Update DNS records for new domain
# Point api.newdomain.com and flower.newdomain.com to server IP

# Update deployment
./scripts/deploy.sh update --env production

# Get new SSL certificates
./scripts/ssl.sh setup --env production

# Done! Now running on new domain
```

### Example 5: Backup Before Major Update

```bash
# Create full backup
./scripts/optional/backup.sh full --env production

# Backups saved to: deploy-v2/backups/
ls -lh backups/

# Deploy update
./scripts/deploy.sh update --env production

# If something breaks, restore:
./scripts/optional/backup.sh restore --env production backups/myhotel_backup_2025-01-01.tar.gz
```

---

## Troubleshooting

### Issue: DNS not resolving

**Symptom:**
```
✗ DNS does not resolve for: api.example.com
```

**Solution:**
1. Verify DNS records are configured correctly
2. Wait 5-60 minutes for DNS propagation
3. Check with: `nslookup api.example.com`
4. If urgent, add `--skip-dns-check` flag (not recommended)

### Issue: Port already in use

**Symptom:**
```
Error: Port 80 is already in use
```

**Solution:**
1. Check what's using the port: `sudo lsof -i :80`
2. Stop conflicting service: `sudo systemctl stop apache2` (or nginx)
3. Or configure deploy-v2 to use different ports

### Issue: SSL certificate failed

**Symptom:**
```
Error obtaining certificate from Let's Encrypt
```

**Solution:**
1. Ensure DNS resolves correctly (critical!)
2. Check firewall allows ports 80 and 443
3. Verify ACME challenge endpoint is accessible:
   ```bash
   curl http://api.example.com/.well-known/acme-challenge/test
   ```
4. Check Let's Encrypt rate limits (5 certs/week per domain)
5. Use staging environment for testing:
   ```bash
   ./scripts/ssl.sh setup --env production --staging
   ```

### Issue: Containers not starting

**Symptom:**
```
✗ Service api is unhealthy
```

**Solution:**
1. Check logs:
   ```bash
   ./scripts/deploy.sh logs --env production
   # Or directly:
   docker logs myhotel_api
   ```
2. Check environment variables in `.env.production`
3. Verify database credentials are correct
4. Check database is accessible:
   ```bash
   docker exec -it myhotel_api ping your-db-host
   ```

### Issue: Permission denied

**Symptom:**
```
Permission denied: ./scripts/setup.sh
```

**Solution:**
```bash
# Make scripts executable
chmod +x scripts/*.sh
chmod +x scripts/common/*.sh
```

### Issue: Database connection failed

**Symptom:**
```
could not connect to server: Connection refused
```

**Solution for Production (Managed DB):**
1. Verify `POSTGRES_HOST` in `.env.production`
2. Check firewall allows connection from your server IP
3. Verify database user has correct permissions
4. Test connection:
   ```bash
   docker exec -it myhotel_api psql -h $POSTGRES_HOST -U $POSTGRES_USER -d $POSTGRES_DB
   ```

**Solution for Staging (Containerized DB):**
1. Ensure postgres container is healthy:
   ```bash
   docker ps | grep postgres
   ```
2. Check postgres logs:
   ```bash
   docker logs myhotel_staging_postgres
   ```

### Get Help

**Check logs:**
```bash
# All services
./scripts/deploy.sh logs --env production

# Specific service
docker logs myhotel_api
docker logs myhotel_nginx
docker logs myhotel_redis
```

**Interactive debugging:**
```bash
# Access API container
docker exec -it myhotel_api bash

# Access database (if containerized)
docker exec -it myhotel_staging_postgres psql -U postgres

# Access Redis
docker exec -it myhotel_redis redis-cli -a <REDIS_PASSWORD>
```

---

## How It Works

### Template System

All configuration files are generated from templates:

**Template:** `templates/nginx/api.conf.template`
```nginx
server_name {{API_DOMAIN}};
ssl_certificate /etc/letsencrypt/live/{{API_DOMAIN}}/fullchain.pem;
```

**Generated:** `generated/nginx/api.conf`
```nginx
server_name api.example.com;
ssl_certificate /etc/letsencrypt/live/api.example.com/fullchain.pem;
```

**Placeholder Syntax:**
- `{{DOUBLE_BRACES}}` = Our template placeholders (replaced by setup.sh)
- `${SINGLE_BRACES}` = Docker/shell variables (preserved for runtime)

### Configuration Flow

```
config.env (user edits)
    ↓
scripts/setup.sh
    ↓
Derive values (API_DOMAIN, PROJECT_PREFIX, etc.)
    ↓
Process templates (replace {{PLACEHOLDERS}})
    ↓
generated/.env.production
generated/docker-compose.production.yml
generated/nginx/*.conf
    ↓
scripts/deploy.sh uses generated files
    ↓
Docker Compose starts containers
```

### Directory Structure

```
deploy-v2/
├── QUICK_START.md             # ← Step-by-step deployment guide
├── README.md                  # ← Comprehensive reference (this file)
├── config.env                 # ← Edit this (single source of truth)
├── .env.production            # ← Generated (add secrets here)
├── .env.staging               # ← Generated
│
├── templates/                 # ← Template files (never edit)
│   ├── env/
│   ├── docker/
│   └── nginx/
│
├── generated/                 # ← Auto-generated (never edit directly)
│   ├── docker-compose.production.yml
│   ├── docker-compose.staging.yml
│   ├── nginx/
│   └── redis/
│
└── scripts/                   # ← Core automation scripts
    ├── setup.sh               # Complete setup (checks + config + generation)
    ├── validate.sh            # Configuration validation
    ├── deploy.sh              # Deployment management
    ├── ssl.sh                 # SSL certificate management
    │
    ├── optional/              # Optional scripts
    │   ├── backup.sh          # Database backups
    │   └── security-setup.sh  # Server hardening
    │
    └── common/                # Shared libraries
        ├── common.sh          # Utility functions
        ├── validation.sh      # Validation helpers
        └── template-engine.sh # Template processor
```

### Why This Approach?

1. **Reusability:** Same templates work for any project
2. **Maintainability:** Update template once, applies everywhere
3. **Safety:** Generated files have warnings not to edit directly
4. **Flexibility:** Easy to customize by editing config.env
5. **Portability:** Move to new domain by changing one variable

---

## Differences from Old deploy/

| Feature | Old deploy/ | New deploy-v2/ |
|---------|------------|----------------|
| Hardcoded domains | 59 occurrences | 0 (all templated) |
| Initialization | Manual sed replacements | Interactive script |
| Configuration | Duplicated across files | Single config.env |
| Reusability | Difficult | Copy & run setup.sh |
| Documentation | 5 redundant files | 1 comprehensive README |
| SSL setup | 2 conflicting scripts | 1 unified script |
| Cross-platform | sed issues on macOS | Pure bash (works everywhere) |

---

## Advanced Topics

### Running Multiple Environments Side-by-Side

Production and staging can run on the same server:

```bash
# Different ports, networks, containers
Production: ports 80/443, network myhotel_network
Staging: ports 8080/8443, network myhotel_staging_network
```

### Custom Template Modifications

1. Edit template in `templates/`:
   ```bash
   nano templates/nginx/api.conf.template
   ```

2. Regenerate:
   ```bash
   ./scripts/setup.sh --force
   ```

3. Apply changes:
   ```bash
   ./scripts/deploy.sh restart --env production
   ```

### Using with CI/CD

```yaml
# Example GitHub Actions
- name: Deploy to production
  run: |
    cd deploy-v2
    ./scripts/validate.sh --env production
    ./scripts/deploy.sh update --env production
```

---

## Support

For issues or questions:
1. Check this README
2. Check troubleshooting section
3. Review logs: `./scripts/deploy.sh logs --env production`
4. Check generated configs in `generated/` directory

---

## License

Part of the SalesCRM Backend project.
