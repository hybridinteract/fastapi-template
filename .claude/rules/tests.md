---
paths:
  - "app/**/tests/**"
  - "app/**/conftest.py"
---
# Tests

> Last verified against the code: 13 October 2026.

## The rules

1. **Tests live in `app/<module>/tests/`** — a package with `__init__.py`, beside the code it tests.
   `testpaths = ["app"]`. Repo-wide fixtures are in `app/conftest.py`; a module's own go in its
   `tests/conftest.py`.
2. **One marker splits the suite, and the cheap half is the default.** A file that needs Postgres
   carries `pytestmark = pytest.mark.integration` under its imports — **per file, never per function**.

   ```bash
   uv run pytest app/<module>       # its fast tests — no database, seconds. The usual run.
   uv run pytest app/<module> -m "" # + its DB tests
   uv run pytest -m ""              # everything — only for app/core, a model, or a migration
   ```

   Two markers were rejected: forgetting one would drop a test out of **both** tiers silently. With
   one, forgetting it runs the test in the wrong tier, where it fails loudly.
3. **`asyncio_mode = "auto"`** — an async test needs no decorator.
4. **`-m ""` is an action, not a check.** It writes to the database named in `.env`. Run the smallest
   scope your change earns.
5. **Never patch a module-level singleton by assignment** (`mod.user_crud.get = fake`) — it leaks into
   every other test in the process. Use `monkeypatch.setattr`.
6. **Red means report and stop.** Do not loop edit-and-re-run until it goes green; name the failures.
   If something was already failing before you started, say how you know it predates you.
7. **Quote real numbers** (`<N> passed`), never "tests pass".

## The convention tests

Four tests enforce rules that would otherwise fail **silently in production**. They are pure
AST and filesystem checks — no database, no app import — so they run in the fast tier and stay fast.

| Test | Enforces |
|---|---|
| `app/core/tests/test_alembic_models_registered.py` | Every model is in `alembic_models_import.py`, or autogenerate skips its table |
| `app/core/tests/test_layering.py` | No `commit()`/`rollback()` in CRUD; no raw `HTTPException(...)` in a service or route |
| `app/core/tests/test_module_anatomy.py` | Every module matches the contract **for its shape** — see below |
| `app/apis/tests/test_route_registration.py` | Literal route prefixes register before wildcard ones |

**When one of these fails, fix the code, not the test.** If the rule is genuinely wrong, change it in
`CLAUDE.md` and `docs/DECISIONS.md` first, in the same change.

`test_module_anatomy.py` reads a module's **shape** from its layout — `conventions.module_shape()` —
and applies that shape's contract, because two of the four genuinely differ: a **shared kernel**
wires nothing so it has no `dependencies.py`, and a **composite** may carry `exceptions.py` per
sub-module rather than at the root. It also checks that a composite keeps **one** `dependencies.py`,
`tests/` and `<module>_doc/`, at the root. Shapes: `docs/MODULE_CONVENTIONS.md` §6.

## Where it is deliberately NOT applied

- **`app/conftest.py` sets required env vars before anything imports `app`.**
  `app/core/settings.py` instantiates `Settings()` at module import time and required secrets have no
  defaults — by design, so the app fails fast rather than booting with a guessable key. The
  consequence is that *importing* any app module needs env, so the conftest supplies throwaway values.
  Do not "fix" the settings module to have defaults.
- **The four convention tests do not import the app** (except the router one), specifically so they
  keep working when a module is half-built.

## Known gaps

- **Behaviour tests are few** — `app/activity/tests/` and `app/iam/tests/`, database-free regression
  tests for bugs that were fixed. Every module should add its own; the convention tests are the
  floor, not the target.
- **A model with no migration is caught only by CI's integration job** (`alembic check`, added after
  the `oauth_accounts` and `phone_otps` tables shipped without one — migration `43b28eb98417`). The
  fast tier cannot see it; run `alembic check` locally after any model change.
- **Nothing enforces a composite module's rank.** `/new-module` generates
  `tests/test_module_boundary.py` for a new one, but `app/iam` predates the rule and has neither a
  rank nor the test — its `auth/` ↔ `user/` cycle is documented in `docs/MODULE_CONVENTIONS.md` §6.2
  as the cautionary tale, not fixed. Do not add the test to `app/iam` without fixing the cycle first:
  a boundary test that starts red gets weakened until it passes.
- No coverage measurement is configured, deliberately — a coverage number on a codebase this young
  is noise.

## How to re-check this rule

```bash
uv run pytest -q                       # fast tier; should be green on a clean checkout
uv run pytest --collect-only -q | tail -3
uv run pytest -m "" -q                 # + integration; needs Postgres
```
