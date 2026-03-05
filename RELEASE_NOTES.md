# Release Notes

All notable changes to this project template are tracked here.
Follow [Semantic Versioning](https://semver.org/).

---

## [0.1.0] — 2026-03-05

### 🎉 Initial Template Release

This is the cleaned base template extracted from the salescrm_backend project.
It provides a production-ready starting point for any FastAPI + PostgreSQL + Redis backend.

#### Included Modules
- **`core/`** — Shared infrastructure: database, settings, CRUD base, exceptions, middleware, logging, metrics, Celery, Redis cache, object storage
- **`user/`** — Complete auth + RBAC: JWT (access + refresh tokens), role/permission management, user admin
- **`activity/`** — Append-only audit log (actor, action, resource, details, IP)
- **`release_notes/`** — "What's New" system with versioned, publishable release notes

#### Base Roles
- `super_admin` — Full access, bypasses all permission checks
- `admin` — User + system management
- `member` — Standard authenticated user

#### Infrastructure
- Async SQLAlchemy 2.0 + asyncpg
- Alembic async migrations (timestamped filenames)
- Celery + Redis (broker DB 0, result backend DB 1)
- Prometheus metrics via `/metrics`
- DigitalOcean Spaces / S3-compatible object storage
- Multi-stage Dockerfile (`python:3.13-slim`, non-root user)
- Docker Compose with health checks on all services

---

<!-- Template: copy this block when creating a new release -->
<!--
## [X.Y.Z] — YYYY-MM-DD

### Added
- 

### Changed
- 

### Fixed
- 

### Removed
- 
-->
