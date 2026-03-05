# API Documentation Authentication

The API documentation endpoints (`/docs`, `/redoc`, `/openapi.json`) are protected with HTTP Basic Authentication.

## Current Credentials

- **Username:** `admin`
- **Password:** `DocsPass2026!`

## Accessing Documentation

When you visit https://api.salescrm.hybridinteractive.in/docs, you will be prompted for username and password.

## Password File Location

The password file is located at:
```
/root/sales-crm-backend/deploy-v2/generated/nginx/auth/.htpasswd
```

This directory is bind-mounted into the nginx container at `/etc/nginx/auth/`.

## Changing the Password

To change the documentation password:

```bash
# From the host machine
cd /root/sales-crm-backend/deploy-v2/generated/nginx/auth

# Method 1: Using Docker with httpd image (recommended)
docker run --rm httpd:2.4-alpine htpasswd -nbB admin 'NEW_PASSWORD' > .htpasswd

# Method 2: If apache2-utils is installed on host
htpasswd -cb .htpasswd admin 'NEW_PASSWORD'

# Restart nginx to apply changes
cd /root/sales-crm-backend/deploy-v2
docker compose -f generated/docker-compose.production.yml restart nginx
```

## Adding Additional Users

```bash
# Add a new user (append mode)
cd /root/sales-crm-backend/deploy-v2/generated/nginx/auth
docker run --rm httpd:2.4-alpine htpasswd -nbB newuser 'PASSWORD' >> .htpasswd

# Restart nginx
cd /root/sales-crm-backend/deploy-v2
docker compose -f generated/docker-compose.production.yml restart nginx
```

## Removing a User

```bash
# Remove a user from the password file
cd /root/sales-crm-backend/deploy-v2/generated/nginx/auth
sed -i '/^username:/d' .htpasswd

# Restart nginx
cd /root/sales-crm-backend/deploy-v2
docker compose -f generated/docker-compose.production.yml restart nginx
```

## Security Notes

- ⚠️ **Change the default password immediately** after deployment
- Use a strong password (minimum 16 characters, mixed case, numbers, and symbols)
- The password file is mounted as read-only in the container for security
- Consider using a password manager to generate and store credentials
- Restrict SSH access to authorized personnel only
- The `generated/` directory is regenerated on deployment, but the `auth/` directory should persist

## Testing Authentication

```bash
# Should return 401 Unauthorized
curl -k -I https://api.salescrm.hybridinteractive.in/docs

# Should return 200 OK with valid credentials
curl -k -u admin:DocsPass2026! -I https://api.salescrm.hybridinteractive.in/docs
```

## Backup

Remember to backup the password file if you're setting up a new environment:

```bash
# Backup
cp /root/sales-crm-backend/deploy-v2/generated/nginx/auth/.htpasswd ~/docs-htpasswd-backup

# Restore
cp ~/docs-htpasswd-backup /root/sales-crm-backend/deploy-v2/generated/nginx/auth/.htpasswd
docker compose -f generated/docker-compose.production.yml restart nginx
```
