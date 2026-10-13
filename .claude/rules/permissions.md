---
paths:
  - "app/iam/**"
  - "app/**/permissions.py"
---
# Permissions and RBAC

> The long version: [`docs/PROJECT_CONVENTIONS.md`](../../docs/PROJECT_CONVENTIONS.md) §9 ·
> the module note: [`app/iam/iam_doc/how-it-works.md`](../../app/iam/iam_doc/how-it-works.md).
> Last verified against the code: 13 October 2026.

## The rules

1. **Gate every route on a permission, never a role.**
   `Depends(require_permission("leads:update"))`. A role is a bundle the client rearranges from the
   access-control screen; a role check hard-codes today's bundle and breaks **silently** the day
   someone edits it.
2. **New permissions go in [`app/iam/permission_catalog.py`](../../app/iam/permission_catalog.py)**,
   as `(resource, action, description)`, stored as `resource:action[:scope]`.
3. **The seed is additive.** `app/iam/seed.py` inserts what is missing and never recomputes an
   existing role's grants. A new permission reaches `developer_admin` automatically; every other
   role's grants are whatever they already were. Do not assume a re-seed fixes a grant.
4. **Add a permission only when a route gates on it.** One that gates nothing still appears on the
   access-control screen looking like a control, and is not one.
5. **Own-scope is a second permission**, not an `if` on the role: `<resource>:read` for your own rows,
   `<resource>:read_all` for everyone's.
6. **A denied single-record read returns 404, not 403.** A 403 confirms the row exists to someone not
   allowed to know that.
7. **Two total bypasses, and only two**: the `is_superuser` column and the `developer_admin` role.
   `developer_admin` is **never grantable through the API** — `app/iam/create_admin.py` only.
   `AdminService.assign_roles` refuses it with `RoleNotGrantableError` before writing anything;
   `app/iam/tests/test_role_assignment.py` pins it.
8. **Never cache a permission check or the auth principal.** `app/iam/user/query_service.py` caches
   user *roles* for display and invalidates after commit; that cache must never become a gate.
9. **A dropdown is not a register read.** An options/picker endpoint is authenticated but ungated.
   Gating a picker on the owning module's permission leaves whole roles staring at a permanently
   empty required field.
10. **401 means the session, never a bad value in a body.** A client answers 401 by refreshing and
    retrying once, then declaring the session dead — so a 401 for anything a refresh cannot fix signs
    the user out of a live session. Bad value in an authenticated body is **400**; not allowed is
    **403**.

## Where it IS used

| Where | What |
|---|---|
| [`app/iam/permission_catalog.py`](../../app/iam/permission_catalog.py) | `PLATFORM_ROLES` (`developer_admin`, `admin`, `member`) and `PLATFORM_PERMISSIONS` |
| [`app/iam/seed.py`](../../app/iam/seed.py) | Idempotent, additive; runs from `lifespan` on startup |
| [`app/iam/permission/utils.py`](../../app/iam/permission/utils.py) | `require_permission(...)` — the guard itself; denies with `MissingPermissionError` (403) |
| [`app/iam/user/services.py`](../../app/iam/user/services.py) | `assign_roles` refuses `developer_admin` (rule 7) |
| [`app/iam/config.py`](../../app/iam/config.py) | `DEVELOPER_ADMIN_ROLE`, defined once |
| [`app/activity/routes.py`](../../app/activity/routes.py) | Router-level guard — `activity:read_all` on the whole module |

## Where it is deliberately NOT applied

- **`app/release_notes`' published list is ungated.** It is the product's own changelog; requiring a
  permission to read it defeats the point.
- **Auth routes are unauthenticated by necessity** (login, refresh, signup, reset). The intended
  protection is a throttle instead of a gate — **per identity, not per IP**, because behind a proxy
  every browser shares one source IP, so a per-IP cap throttles everyone at once and stops nobody.
  Today only the phone OTP has one; see Known gaps.
- **`PermissionService` and `AdminService` compare `role.name` to `DEVELOPER_ADMIN_ROLE`.** Neither is
  a gate (rule 1): both *protect* the bypass role — its grants cannot be edited
  (`ProtectedRoleError`) and it cannot be granted (`RoleNotGrantableError`).
- **`app/iam/auth/current_user.py` and `tokens.py` build `HTTPException` directly.** They are the
  auth layer; they predate any module's `exceptions.py` and are the documented exception to
  [`layering.md`](layering.md).

## Known gaps

- **Rule 3 is the intent, not what the code does.** `_seed_role_permissions` inserts every catalogue
  grant that is missing, for every role, on every startup (the seed runs in `lifespan`). So revoking
  a catalogue grant on the access-control screen lasts only until the next restart. Verified
  13 October 2026: revoke `users:delete` from `admin` → re-seed → granted again. Making rule 3 true
  (seed grants only for a role the run creates, plus `developer_admin`) changes behaviour on every
  running deployment — and stops new catalogue grants reaching existing roles — so it needs a decision.
- **Admin routes are gated on `SuperUserDep`, not on a permission — 18 of them**, across
  `app/iam/user/routes.py` (10), `app/iam/permission/routes.py` (3) and `app/release_notes/routes.py`
  (5). `SuperUserDep` admits only `is_superuser` or the `developer_admin` role: a role check, which
  rule 1 forbids. The consequence is rule 4 at scale — **17 of the 18 catalogue permissions gate
  nothing** (only `activity:read_all` does), so the seeded `admin` role, granted `users:*`, is refused
  by every admin route, and the access-control screen shows 17 toggles that control nothing. Moving
  these routes to `require_permission(...)` *widens* access to `admin`-role users — a product
  decision, not a refactor.
- **No login throttle.** Email/password login, signup, refresh and reset have no rate limit at all;
  the only cap is `OTP_MAX_ATTEMPTS` per phone OTP code. A password guess costs one Argon2 verify.
- No test asserts that every route carries a permission gate. Adding one would be a good next
  convention test.
- Permission strings are not checked against the catalogue at startup, so a typo in
  `require_permission("leadz:update")` fails closed at request time rather than loudly at boot.

## How to re-check this rule

```bash
# Every gate in the codebase, and the catalogue it must match.
grep -rn "require_permission(" app --include="*.py" | grep -v "def require_permission"
grep -c '^    ("' app/iam/permission_catalog.py      # 18 permissions; needs no .env

# Exactly two hits, both protecting developer_admin (see "deliberately NOT applied").
# A third is a role being used as a gate.
grep -rn '\.name ==\|role ==' app --include="routes.py" --include="services.py"

# Routes gated on a role check instead of a permission — 18 today (Known gaps).
grep -rn ": SuperUserDep" app --include="routes.py" | wc -l
```
