# IAM — how it works

> One-page tour of `app/iam` — signing in, users, roles and permissions.
>
> **Last verified against the code: 9 September 2026.**

## What it is for

Who you are, and what you are allowed to do. Three parts in one module:

- `auth/` — signing in, tokens, logout, `/me`, and the pluggable providers
- `user/` — user accounts, profiles, admin user management
- `permission/` — roles, permissions, and the route guards

It is written to be portable. It leans on a short list of `app.core` symbols and
nothing project-specific, so it can be lifted into another project as a folder.

## The tables

| Table | Holds |
|---|---|
| `users` | the account — email, hashed password, name, status |
| `roles` | named roles. System roles are flagged `is_system` |
| `permissions` | the catalogue of permission strings |
| `role_permissions` | which permissions a role has |
| `user_roles` | which roles a user has |
| `refresh_tokens` | one row per live session |
| `oauth_accounts` | one row per linked Google (or later) identity |
| `phone_otps` | for the phone provider, which is **off** by default |

Both join tables use a composite primary key and `ON DELETE CASCADE` on their
role reference, so deleting a role cleans up after itself.

## Layout

```
app/iam/
├── __init__.py            # the module's public API — import from here
├── config.py              # AuthConfig: provider toggles, token policy, role name
├── dependencies.py        # DI wiring (CRUD → Service), the Dep aliases
├── enums.py               # UserStatus
├── exceptions.py          # module-level exceptions
├── extensions.py          # extension points for downstream projects
├── permission_catalog.py  # PLATFORM_ROLES / PERMISSIONS / ROLE_PERMISSIONS
├── seed.py                # idempotent seeder — `python -m app.iam.seed`
├── create_admin.py        # `python -m app.iam.create_admin`
├── auth/                  # providers/, tokens, current_user, services, routes
├── user/                  # crud, services, query_service, routes, schemas
└── permission/            # crud, services, utils (the guards), routes
```

## Signing in

Email + password is always on. The other two providers are opt-in, gated by
config flags in `config.py` and registered at import time by
`auth/providers/__init__.py`:

| Provider | Flag | Default |
|---|---|---|
| `email_password` | — | always on |
| `google_oauth` | `AUTH_GOOGLE_OAUTH_ENABLED` | off |
| `phone_otp` | `AUTH_PHONE_OTP_ENABLED` | off |

A provider is a frozen `Provider` dataclass exporting a router plus the
permissions and role-permission links it needs. There is no Protocol and no
registry class — adding one means dropping a file in `auth/providers/` and adding
a `_register(...)` line.

The core auth routes are `POST /auth/refresh`, `POST /auth/logout`,
`POST /auth/logout-all`, and `GET /auth/me`. Each provider mounts its own
sub-path — email/password contributes `/auth/password/login`,
`/auth/password/register` and `/auth/password/change-password`.

## Tokens

Access tokens are JWTs (default 120 minutes). Refresh tokens are stored hashed
(SHA-256), one row per session, so `logout-all` is a real server-side revocation
rather than a client-side token drop. Passwords use Argon2 for new hashes with
bcrypt retained for verifying old ones, and `verify_and_update_password` returns
an upgraded hash when it meets an older scheme — so hashes migrate forward on login.

`UserStatus` gates access: `active`, `inactive`, `suspended`,
`pending_verification`. Anything other than `active` cannot log in.

## Roles and permissions

Permission names are `resource:action` — `users:read`, `activity:read_all`. The
catalogue lives in `permission_catalog.py` as code, not data. Three roles ship
with the template:

| Role | What it is |
|---|---|
| `developer_admin` | bypasses every permission check |
| `admin` | broad administrative access, but still checked |
| `member` | standard authenticated user |

**Gate endpoints on permissions, never on roles.** A role is a bundle an
administrator can rearrange at runtime from the access-control screen; a role
check hard-codes today's bundle into the code and breaks the moment they change
it.

```python
_: Annotated[User, Depends(require_permission("users:update"))]   # yes
if user.role == "admin":                                          # no
```

`developer_admin` is the one exception, and it is deliberately not a permission
check — `BasePermissionChecker` short-circuits on it before looking at anything
else. The role name is configurable via `DEVELOPER_ADMIN_ROLE`, defined once in
`config.py` and derived everywhere else. `SuperUserDep` is the dependency alias
that requires it.

## The seed is additive

`python -m app.iam.seed` runs three passes in one transaction:

1. platform permissions, roles, and role-permission links from `permission_catalog.py`
2. permissions contributed by each **enabled** provider
3. permissions, roles and links contributed by `extensions.py`

Every pass creates only what is missing. It never renames and never deletes, so
removing an entry from `permission_catalog.py` leaves the row in the database
until you drop it by hand — and **renaming** anything seeded needs its own data
migration, because the seed will simply create the new name alongside the old.

Run it on every deploy; it is safe to run repeatedly.

## Extending it from a downstream project

`extensions.py` is the seam, so projects do not fork the module:

- `ExtraUserFieldsMixin` — add columns to `users` via a subclass with
  `__table_args__ = {"extend_existing": True}`
- `extra_permissions()` / `extra_roles()` / `extra_role_permissions()` — return
  project-specific entries and the seeder picks them up in pass 3

## The two CLIs

```bash
python -m app.iam.seed           # roles + permissions (run first)
python -m app.iam.create_admin   # interactive developer-admin creation
python -m app.iam.create_admin --force   # non-interactive dev/test accounts
```

`create_admin` refuses to run until the roles exist, so seed first.

## Adding a permission

1. Add the `(resource, action, description)` tuple to `PLATFORM_PERMISSIONS`
2. Grant it to the roles that should hold it in `PLATFORM_ROLE_PERMISSIONS`
3. Guard the route with `require_permission("resource:action")`
4. Re-run the seed

Only add one when a route actually gates on it. A permission that gates nothing
looks like a control and is not one.

## Hard rules

- Routes call **services**, never CRUD directly
- Services own the transaction; CRUD never commits
- All DI wiring lives in `dependencies.py`
- Gate on permissions, not roles
- Import from `app.iam` (the package `__init__`), not from deep module paths,
  when consuming the module from elsewhere in the app
