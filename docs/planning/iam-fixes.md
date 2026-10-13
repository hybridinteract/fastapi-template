# IAM fixes tracker

> Status: **IN PROGRESS** — 5 of 17 done.
> Last verified against the code: 13 October 2026.

Functionality and security issues in `app/iam`, found by `/review-module iam` on 13 October 2026.
Each was confirmed in the code, except items marked †, which come from the review only. Structure
is out of scope: `app/iam` is not reviewed for shape or placement.

**Found while fixing S4:** no `app/iam` action had ever reached the audit log — the adapter passed
plain strings where `app.activity` expects its enum, and swallowed the error. Fixed with S4; pinned
by `app/iam/tests/test_activity_adapter.py`. Decisions for S1 and S3: `../DECISIONS.md`,
13 October 2026.

**How to work through it:** one item per change. Set its status in the table below and add the
commit beside it. An item whose status is **Decide** needs a product answer first: record the
answer in [`../DECISIONS.md`](../DECISIONS.md), then fix.

## Status

| ID | Issue | Severity | Status |
|---|---|---|---|
| S1 | `GET /users/me/by-role/{role}` has no permission gate | High | Done — picker returns `UserOption` |
| S2 | Restoring a deleted user always makes them active | Medium | Done |
| S3 | Changing the password keeps other sessions signed in | Medium | Done — revokes all, no new pair |
| S4 | Privilege changes leave no audit record | Medium | Done — and the adapter fix below |
| S5 | Three permissions gate nothing | Low–medium | Decide (after F4) |
| S6 | The API can remove `developer_admin` | — | Decide |
| S7 | `require_permission` and `SuperUserDep` disagree on `is_superuser` | Low | Decide |
| F1 | An admin update allows a duplicate phone | Medium | Done |
| F2 | Expired refresh tokens and OTPs are never deleted | Low–medium | Open |
| F3 | Assigning roles returns the old roles | Low–medium | Open |
| F4 | No sign-up path assigns a role | — | Decide |
| F5 | An over-long phone or `device_info` gives a database error | Low | Open |
| F6 | A deleted user's email can never be reused | — | Decide |
| F7 | The iam README misdescribes refresh tokens | Low | Open (after F2) |
| F8 | A migration hard-codes `developer_admin` † | Low | Decide |
| F9 | Exceptions re-raised without their cause † | Low | Open |
| F10 | User search has no length bound and no index † | Low | Open |

## Security

### S1 — `GET /users/me/by-role/{role}` has no permission gate

- **Where:** `app/iam/user/routes.py:57`, `get_users_by_role`.
- **Problem:** it checks only that the caller is signed in, and sign-up is public. It returns
  `UserResponse` — email, phone, `is_superuser`, last login — for up to 10,000 active users per
  role. `/by-role/developer_admin` lists the accounts that bypass every permission.
- **Decide:** what calls it. A user picker returns a minimal schema (`id`, `full_name`); a user
  register gates on `users:read_all`.
- **Done when:** a caller without the permission gets 403, or sees only the minimal fields — with a
  test.

### S2 — Restoring a deleted user always makes them active

- **Where:** `app/iam/user/services.py:266`, `restore_user`.
- **Problem:** it sets `status = ACTIVE`. A soft delete leaves the status alone, so a user who was
  suspended, then deleted, comes back active.
- **Fix:** drop the assignment, so the user returns with the status they had. Making them active is
  then an explicit status change.
- **Done when:** suspend → delete → restore leaves the user suspended — with a test.

### S3 — Changing the password keeps other sessions signed in

- **Where:** `app/iam/auth/providers/email_password.py:131`, `change_password`.
- **Problem:** no refresh token is revoked, so a stolen one keeps working after the change.
- **Fix:** revoke all the user's refresh tokens in the same transaction, before the commit —
  `refresh_token_crud.revoke_all_user_tokens` already does it (`app/iam/auth/services.py:150`).
- **Decide:** whether the response returns a fresh token pair, so the current device stays signed
  in (an API change), or the current device signs in again when its access token expires.
- **Done when:** a refresh token issued before the change is refused — with a test.

### S4 — Privilege changes leave no audit record

- **Where:** `assign_roles`, `remove_role` and `hard_delete_user` in `app/iam/user/services.py`;
  `set_role_permissions` in `app/iam/permission/services.py`.
- **Fix:** `log_activity` after the commit, as `update_user` does: `ASSIGN` / `UNASSIGN` for roles,
  `UPDATE` for a role's permissions, `DELETE` for a hard delete, with the role or permission names
  in `details`.
- **Done when:** each writes one activity entry — with a test.

### S5 — Three permissions gate nothing

- **Where:** the provider permission lists — `email_password.py:215`, `google_oauth.py:147`,
  `phone_otp.py:168`.
- **Problem:** `auth:password_change`, `auth:google_link` and `auth:phone_link` appear on the
  access-control screen, but revoking them changes nothing (`CLAUDE.md` §5).
- **Decide, after F4:** gate change-password on `auth:password_change` — safe only once sign-up
  assigns a role, or every user loses it — or remove it. The two link permissions have no routes:
  remove them.
- **Fix:** removal needs a data migration that deletes the rows and their grants; the seed never
  deletes.
- **Done when:** every permission in the catalog and the providers is gated by a route.

### S6 — The API can remove `developer_admin`

- **Where:** `app/iam/user/services.py`, `remove_role`.
- **Problem:** the API cannot grant `developer_admin` (`RoleNotGrantableError`), but it can take it
  away — including from its last holder.
- **Decide:** refuse it as `assign_roles` does, or allow it but refuse the last holder.
- **Done when:** the chosen rule has a test.

### S7 — `require_permission` and `SuperUserDep` disagree on `is_superuser`

- **Where:** `app/iam/permission/utils.py:74`, and `SuperUserDep`.
- **Problem:** `require_permission` bypasses only for the `developer_admin` role; `SuperUserDep`
  honours the `is_superuser` flag. Harmless while `create_admin` sets both; they diverge once the 18
  admin routes move from `SuperUserDep` to permissions.
- **Decide:** one bypass rule, before those routes move.

## Functionality

### F1 — An admin update allows a duplicate phone

- **Where:** `app/iam/user/services.py:200`, `update_user`.
- **Problem:** it checks that the email is free, not the phone, and `ix_users_phone` is not unique.
  `get_by_phone` then finds two rows, and phone sign-in for that number fails.
- **Fix:** the self-service check (`services.py:94–96`), raising `PhoneAlreadyInUseError`.
- **Decide:** whether to also make the phone index unique — existing duplicates must be found first.
- **Done when:** an admin update to a phone in use returns 409 — with a test.

### F2 — Expired refresh tokens and OTPs are never deleted

- **Where:** `cleanup_expired` in `app/iam/auth/crud.py:68` (`RefreshTokenCRUD`) and `:207`
  (`PhoneOTPCRUD`) — neither has a caller.
- **Problem:** each refresh revokes the old token, correctly, and adds a row. Expired rows stay
  forever.
- **Fix:** a periodic Celery task that calls both. The beat schedule in
  `app/core/background/celery_app.py` already runs `cleanup_expired_task_results`.
- **Done when:** the task is scheduled, and a test shows expired rows deleted.

### F3 — Assigning roles returns the old roles

- **Where:** `app/iam/user/services.py:328`, `assign_roles`.
- **Problem:** it reloads the user in the same session after the commit, and with
  `expire_on_commit=False` the loaded roles are kept (`.claude/rules/layering.md` → Known gaps).
  The database is right; the response is stale.
- **Fix:** reload with `.execution_options(populate_existing=True)`. `set_role_permissions` in
  `app/iam/permission/services.py` reloads the same way after `replace_role_permissions` inserts
  link rows, so its response is likely stale too — check and fix it here.
- **Done when:** both responses list the new state — with a test.

### F4 — No sign-up path assigns a role

- **Where:** register, Google and phone sign-up in `app/iam/auth/providers/`. Only
  `create_admin --force` assigns a role.
- **Problem:** the iam README calls `member` the standard role, but new users hold no permissions.
  Blocks S5.
- **Decide:** assign `member` on sign-up, or correct the README.

### F5 — An over-long phone or `device_info` gives a database error

- **Where:** `phone` and `device_info` fields in `app/iam/auth/schemas.py` and
  `app/iam/user/schemas.py`.
- **Fix:** `max_length=20` on `phone` and `500` on `device_info` — the column limits.
- **Done when:** over-long input returns 422 — with a test.

### F6 — A deleted user's email can never be reused

- **Where:** `email` in `app/iam/user/models.py` (`unique=True`).
- **Problem:** a soft-deleted row keeps its email, so registering, admin-creating or Google sign-in
  with it fails with a generic 409.
- **Decide:** keep blocking reuse, or replace the constraint with a partial unique index
  `WHERE is_deleted = false` (a migration) — and then `restore_user` must check the email is free.

### F7 — The iam README misdescribes refresh tokens

- **Where:** `app/iam/README.md`.
- **Fix, after F2:** one row per refresh, revoked on rotation, deleted by the cleanup task.

### F8 — A migration hard-codes `developer_admin` †

- **Where:** `migrations/versions/2026_09_09_1030-3c6589de23bb_rename_super_admin_role_to_developer_admin.py`.
- **Problem:** it renames `super_admin` to `developer_admin` even when `DEVELOPER_ADMIN_ROLE` is set
  to another name.
- **Decide:** note it in the iam README, or have the migration read the configured name. An applied
  migration is not edited.

### F9 — Exceptions re-raised without their cause †

- **Where:** `app/iam/auth/providers/google_oauth.py:44` and `:52` (ruff `B904`).
- **Fix:** `raise … from e`, or `from None` where the cause must not leak.

### F10 — User search has no length bound and no index †

- **Where:** `app/iam/user/crud.py:105` and `:131`.
- **Fix:** the default in `app/core/crud/docs/search-strategy.md` §2 — `min_length=3` and
  `max_length=100` on the term, and a GIN trigram index per searched field (a migration).

## Exit criteria

- [ ] Every item is Done, or decided against with an entry in `../DECISIONS.md`
- [ ] Each fix has the test its item names
- [ ] `uv run pytest app/iam -m ""` is green
