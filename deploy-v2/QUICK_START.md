# SalesCRM Backend - Deploy-v2 Quick Start

Step-by-step guide to deploy the SalesCRM backend from your local machine to a production/staging server.

---

## Prerequisites

- **Server**: Ubuntu/Debian Linux with SSH access (DigitalOcean droplet, AWS EC2, etc.)
- **Domain**: A registered domain with DNS access
- **Database**: PostgreSQL (managed DB for production, containerized for staging)

---

## How It Works

```
config.env (your settings)
    |
    v
setup.sh (interactive wizard)
    |
    v
Templates (deploy-v2/templates/)
    |
    v
Generated configs (deploy-v2/generated/)
    |       - docker-compose.production.yml
    |       - nginx configs
    |       - redis configs
    |       - .env.production
    v
deploy.sh init --> Docker containers running
    |
    v
ssl.sh setup --> HTTPS enabled
```

**Services deployed:**
- **Nginx** — reverse proxy with SSL
- **Redis** — cache & Celery message broker
- **API** — FastAPI app (gunicorn + uvicorn workers)
- **Celery Worker** — background task processing
- **Celery Beat** — scheduled task scheduling
- **Flower** — Celery monitoring dashboard (production only)
- **Certbot** — automatic SSL certificate renewal
- **PostgreSQL** — containerized (staging only; production uses managed DB)

---

## Script Execution Order

Run these scripts in this exact order. Each step depends on the previous one.

| Order | Script | Purpose | Run Once or Repeat? |
|-------|--------|---------|---------------------|
| 1 | `setup.sh` | System checks + collect config + generate all files | Once (or `--force` to regenerate) |
| 2 | _(manual)_ | Edit `.env.production` to add API keys | Once |
| 3 | `validate.sh` | Verify everything is correct before deploying | Before each deploy |
| 4 | `deploy.sh init` | First-time deployment (build + start containers + migrate DB) | Once |
| 5 | `ssl.sh setup` | Obtain Let's Encrypt SSL certificates | Once |
| 6 | `deploy.sh update` | Pull code, rebuild, migrate, restart (for subsequent deploys) | Every update |

---

## Step 1: Prepare the Server

SSH into your server and install Docker:

```bash
ssh user@your-server-ip

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Log out and back in for group to take effect
exit
ssh user@your-server-ip

# Verify
docker --version
docker compose version
```

---

## Step 2: Clone the Repository

```bash
cd ~
git clone <your-salescrm-repo-url> salescrm-backend
cd salescrm-backend/deploy-v2

# Make all scripts executable
chmod +x scripts/*.sh
chmod +x scripts/optional/*.sh
chmod +x scripts/common/*.sh
```

---

## Step 3: Configure DNS

Point your domain to the server's IP address. Create these A records:

| Record Type | Name | Value |
|-------------|------|-------|
| A | `api.yourdomain.com` | Your Server IP |
| A | `flower.yourdomain.com` | Your Server IP |

For staging, use `staging-api.yourdomain.com` and `staging-flower.yourdomain.com`.

Wait 5-10 minutes, then verify:
```bash
dig api.yourdomain.com +short
```

---

## Step 4: Run Setup

```bash
cd ~/salescrm-backend/deploy-v2
./scripts/setup.sh
```

The interactive wizard will:
1. Check system prerequisites (Docker, ports, disk space)
2. Ask: Production, Staging, or Both?
3. Collect project info (name, domain, email)
4. Collect database credentials
5. Generate all config files with secure random secrets

**Example prompts:**
```
Project name: salescrm
Base domain: yourdomain.com
API subdomain [api]: api
Flower subdomain [flower]: flower
Admin email: admin@yourdomain.com

Production PostgreSQL host: your-db.ondigitalocean.com
Production PostgreSQL port [25060]: 25060
Production PostgreSQL database: salescrm_prod
Production PostgreSQL user: doadmin
Production PostgreSQL password: ********
```

**What gets generated:**
- `config.env` — your project settings (single source of truth)
- `.env.production` — full environment file with auto-generated secrets
- `generated/docker-compose.production.yml` — Docker Compose config
- `generated/nginx/*.conf` — Nginx configs
- `generated/redis/` — Redis configs

---

## Step 5: Add API Keys (Optional)

After setup, edit the generated env file to add any third-party API keys:

```bash
nano .env.production
```

Look for sections marked `CHANGE_THIS` and update as needed:
- `SENTRY_DSN` — Error tracking (optional)
- `DO_SPACES_*` — Object storage (optional)

Save and exit (`Ctrl+X`, then `Y`, then `Enter`).

---

## Step 6: Validate Configuration

```bash
./scripts/validate.sh --env production
```

This checks:
- Config files exist and have no placeholder values
- Secret keys are strong enough
- Docker Compose syntax is valid
- Nginx configs are correct
- DNS resolution (warning if not ready)
- Port availability

**Fix any errors before proceeding.**

---

## Step 7: Deploy

```bash
./scripts/deploy.sh init --env production
```

This will:
1. Pull Docker images
2. Build the SalesCRM application container
3. Start Redis, API, Celery Worker, Celery Beat, Flower
4. Run Alembic database migrations
5. Show service status

Wait 3-5 minutes for everything to come up.

---

## Step 8: Setup SSL

```bash
./scripts/ssl.sh setup --env production
```

This will:
1. Check DNS points to this server
2. Create temporary self-signed certs
3. Start Nginx
4. Request real Let's Encrypt certificates
5. Reload Nginx with HTTPS

**Tip:** Test with Let's Encrypt staging server first (no rate limits):
```bash
./scripts/ssl.sh setup --env production --staging
```
Then run without `--staging` for real certificates.

---

## Step 9: Verify

```bash
# Check all services are running
./scripts/deploy.sh status --env production

# Test the API
curl https://api.yourdomain.com/health

# View logs
./scripts/deploy.sh logs --env production

# Flower dashboard (Celery monitoring)
# Open: https://flower.yourdomain.com
# Login with FLOWER_USERNAME/FLOWER_PASSWORD from .env.production
```

---

## Day-to-Day Operations

### Update After Code Changes
```bash
cd ~/salescrm-backend/deploy-v2
./scripts/deploy.sh update --env production
```
This pulls latest code, rebuilds containers, runs migrations, and restarts with zero-downtime.

### Restart Services
```bash
./scripts/deploy.sh restart --env production
```

### Stop Services
```bash
./scripts/deploy.sh stop --env production
```

### View Logs
```bash
./scripts/deploy.sh logs --env production
```

### Check Status
```bash
./scripts/deploy.sh status --env production
```

### Renew SSL (auto-renews, but manual if needed)
```bash
./scripts/ssl.sh renew --env production
./scripts/ssl.sh check --env production   # check expiry
```

---

## Optional: Security Hardening

Harden the server (firewall, fail2ban, SSH hardening):
```bash
sudo ./scripts/optional/security-setup.sh
```

## Optional: Database Backups

```bash
# Full backup (DB + Redis + logs + config)
./scripts/optional/backup.sh full --env production

# Database only
./scripts/optional/backup.sh db --env production

# Restore
./scripts/optional/backup.sh restore --env production backups/your-backup.tar.gz
```

---

## Staging Deployment

Staging uses a containerized PostgreSQL (no managed DB needed):

```bash
./scripts/setup.sh           # Select "Staging" or "Both"
./scripts/validate.sh --env staging
./scripts/deploy.sh init --env staging
./scripts/ssl.sh setup --env staging

# Get a shell inside the staging container
./get-into-staging-container.sh
```

Flower is **disabled by default** in staging to save RAM.

---

## Changing Configuration

To change domain, workers, or other settings:

```bash
# 1. Edit config
nano config.env

# 2. Regenerate all configs
./scripts/setup.sh --force

# 3. Update deployment
./scripts/deploy.sh update --env production

# 4. Re-setup SSL (if domain changed)
./scripts/ssl.sh setup --env production
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Docker daemon not running | `sudo systemctl start docker && sudo systemctl enable docker` |
| Port 80/443 in use | `sudo lsof -i :80` to find what's using it; stop conflicting service |
| DNS not resolving | Wait 10-15 min; verify A records in DNS provider |
| SSL certificate failed | Check DNS points to server; check port 80 open; use `--staging` flag first |
| Container won't start | `./scripts/deploy.sh logs --env production` to see errors |
| Database connection failed | Verify credentials in `.env.production`; check DB firewall allows server IP |

### View Container Logs Directly
```bash
docker logs salescrm_api
docker logs salescrm_nginx
docker logs salescrm_celery_worker
docker logs salescrm_redis
```

---

## File Structure After Setup

```
deploy-v2/
├── config.env                    # Your settings (single source of truth)
├── .env.production               # Generated env file (add API keys here)
├── .env.staging                  # Generated staging env
│
├── scripts/
│   ├── setup.sh                  # [1] Initial setup wizard
│   ├── validate.sh               # [2] Validate before deploy
│   ├── deploy.sh                 # [3] Deploy & manage services
│   ├── ssl.sh                    # [4] SSL certificate management
│   ├── common/                   # Shared libraries (don't run directly)
│   └── optional/
│       ├── backup.sh             # Database backup/restore
│       └── security-setup.sh     # Server hardening
│
├── templates/                    # Source templates (don't edit generated files)
│   ├── docker/
│   ├── env/
│   ├── nginx/
│   └── redis/
│
├── generated/                    # Auto-generated (gitignored)
│   ├── docker-compose.production.yml
│   ├── docker-compose.staging.yml
│   ├── nginx/
│   └── redis/
│
├── certbot/                      # SSL certificates (created at deploy)
├── ssl/                          # SSL config (created at deploy)
└── get-into-staging-container.sh # Quick shell into staging container
```

---

## TL;DR — Minimum Commands

```bash
# On server:
curl -fsSL https://get.docker.com | sudo sh
git clone <repo> salescrm-backend && cd salescrm-backend/deploy-v2
chmod +x scripts/*.sh scripts/optional/*.sh scripts/common/*.sh

# Configure DNS: api.yourdomain.com → server IP

./scripts/setup.sh                              # Interactive setup
nano .env.production                            # Add API keys
./scripts/validate.sh --env production          # Check config
./scripts/deploy.sh init --env production       # Deploy
./scripts/ssl.sh setup --env production         # Enable HTTPS

# Done! Visit https://api.yourdomain.com/health
```
