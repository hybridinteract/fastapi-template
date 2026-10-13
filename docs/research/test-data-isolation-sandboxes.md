# Test data isolation — sandbox deployment vs Postgres schemas

> Status: **STILL A PROPOSAL** — direction agreed 12 October 2026 (sandbox deployment, one database
> per sandbox). Implementation and detailed planning come later; promote when built.
> Last verified against the code: 12 October 2026.

## The question

Testers, trainees and feature branches need data that is isolated from production and from each
other, and that can be reset without wiping everyone at once. The proposal on the table was to use
PostgreSQL schemas — one per sandbox — **inside the production deployment**, with a "test mode"
choice on the login screen. Is that a good idea, and if not, what instead?

What forced it now, from herbally-backend (the downstream app this was evaluated against):

- There is one test server, `herballytest`. Resetting it means running
  `danger-scripts/reset_transactional_data.sql`, which wipes **everyone's** transactional data at
  once and needs an explicit table list kept up to date by hand.
- Several git branches (`f/accounting`, `fix/accounting-001`, …) need their own test environment.
- Accounting is not location-scoped (vouchers carry no location), so parallel testers see each
  other's entries in ledgers and reports — correct in production, noise during testing.
- New users will need a training environment after go-live.

## Constraints

- Stack as in this template: one async SQLAlchemy engine and pool per process
  (`app/core/database.py`), Celery workers, Redis cache, S3-compatible object storage, PyJWT.
- The session stays open **after** the service's single commit, until the response is sent.
- Accounting data: a leak of test entries into the real ledger is expensive and silent.
- Small team: anything that adds a per-feature obligation to every future PR is a real cost.
- Server memory is limited — herbally runs on one VPS.

## Options considered

### Option A — schema per sandbox, inside the production deployment (the original proposal)

One database, `public` for production plus `sandbox_x` schemas; the request picks the schema via
`search_path` or `schema_translate_map`.

- **Cost:** no extra servers or RAM.
- **What breaks** (every item is a silent failure, found by reading herbally's code):
  - *Session/pool.* A plain `SET search_path` survives on the pooled connection after commit and
    leaks into the next request. `SET LOCAL` ends at commit, and because the session outlives the
    commit, any read or lazy load after it hits production. `schema_translate_map` is pool-safe but
    does not rewrite raw `text()` SQL — 28 herbally files use it.
  - *Extensions.* pg_trgm lives in `public` and is used by many indexes, so `public` must stay on
    the search path — which means a table missing from a sandbox silently falls through to
    production's.
  - *Cache.* Keys are global constants with no prefix — e.g. `settings:tax_rates:active`, 4-hour TTL
    (`app/settings/services/tax_rate.py:34`). A tax-rate edit in a sandbox can serve sandbox rates
    to production for up to four hours. The reset README already says "clear the cache after a
    reset" — the cache does not know which data it came from.
  - *Celery.* A task queued from test mode has no request and opens a session on production. Beat
    jobs (`reconcile-inventory-valuation-daily`, report purges) would only ever see one schema.
  - *Tokens.* Tokens carry only `sub` and `type`, signed with one `JWT_SECRET_KEY`
    (`app/user/auth_management/utils/password_utils.py:49`). A cloned sandbox shares UUIDs, so the
    server cannot tell which world a token was minted for; the mode would come from a header, and a
    stale tab writes a "test" invoice to production. (Roles are looked up from the database per
    request, so a sandbox admin does **not** become a production admin.)
  - *Advisory locks.* `pg_advisory_xact_lock` (purchase `_locks.py`, `sale_ledger_crud.py`,
    `lead_crud.py`) is scoped per **database**, not per schema — sandbox transactions on cloned
    UUIDs contend with production's.
  - *Object storage.* `generate_key` has no environment prefix and ten services delete the stored
    file when a record is edited or deleted — in a cloned sandbox sharing the bucket, deleting an
    attachment deletes the real file.
  - *Migrations.* `migrations/env.py` migrates one schema with one `alembic_version`. Needs a
    per-schema loop and version table; a deploy failing on schema 4 of 9 leaves mixed versions.
- **Also:** it runs production's code, so it cannot test an unreleased branch. Every
  `if test_mode` branch makes the sandbox behave *less* like production, not more.
- **Rules out:** nothing, but it makes every future cache key, task, upload and raw query
  responsible for knowing the schema, forever.

### Option B — one database per sandbox, inside the production deployment

Same login-time choice, but each sandbox is its own database; the app picks an engine per request.

- **Better than A:** no `search_path`, no shared advisory locks, `env.py` unchanged (run once per
  URL), native cloning with `CREATE DATABASE … TEMPLATE`.
- **Same as A:** cache keys, Celery, tokens, storage and outbound calls still need routing code, and
  a routing bug still reaches production. One small pool per sandbox database.
- **When to use:** only if a single deployment is a hard requirement.

### Option C — separate sandbox deployment, one database per sandbox ← recommended

Same image tag as production, its own URL, `JWT_SECRET_KEY`, Redis DB number and storage bucket or
prefix. Inside it, one Postgres database per sandbox, cloned from a golden template.

Two shapes, pick by how many sandboxes run at once:

- **C1 — one slim stack per sandbox.** API (1 worker) + Celery (concurrency 1), pointed at its own
  database. **Zero application code.** Postgres and Redis containers are shared, not copied.
- **C2 — one sandbox stack serving many sandbox databases**, chosen at login. RAM stays flat however
  many sandboxes exist. Needs Option B's routing code, but built only into the sandbox deployment,
  so a bug mixes test data with test data — never with the ledger.

### Option D — `is_test` / `sandbox_id` column on every row

Rejected without further study: every query needs the filter (one miss is a leak), and test
documents would consume the real number series — gaps in invoice and voucher numbering.

### Option E — do nothing (keep `herballytest` + the reset script)

Available, and is the status quo. Fails every need above: one shared dataset, reset wipes everyone,
the SQL's table list must be maintained by hand.

## What we actually tested

**Nothing was run.** This is a read-only code inspection on 12 October 2026 of
`herbally-project/herbally-backend` at commit `eb4079a` (branch `main`), plus this template's
`app/core/database.py` and `migrations/env.py`. No server was touched; memory figures are from the
deploy config's limits, not from `docker stats`.

```bash
grep -rn "branch_id" app                     → 0 (data has locations, not branches)
grep -rln "text(" app | wc -l                → 28 files with raw SQL
grep -rn "search_path\|schema=" app migrations → 0 (no schema awareness today)
grep -rnE "^(import|from) (httpx|requests|boto3|smtplib|openai|…)" app → only boto3 (DO Spaces)
grep -rn "storage.delete\|delete_file" app   → 10 services delete stored files
```

Notable facts found on the way:

- **The deploy environment called "production" is the test server.** `deploy/config/production.env`
  has `API_SUBDOMAIN=testapi1`, `POSTGRES_DB=herballytestdb`, one host, Postgres and Redis as
  containers, `API_MEM_LIMIT=768m` / `WORKER_MEM_LIMIT=512m`, 2 API + 2 Celery workers.
- **The pipeline already supports more environments.** `deploy.yml` deploys any tag to any
  `deploy/config/<name>.env` and migrates before rolling; `build-image.yml` publishes a `-dev` image
  for every non-main branch.
- **Outbound side effects are small today** — only DigitalOcean Spaces; `app/ai` has no Python files.
- **Side bug, unrelated to this decision:** `celery_app.py:373` swaps
  `database.async_session_factory` after the worker forks, but
  `background/internals/session.py:23` imported the name at package load
  (`background/__init__.py:50`), so `@db_task` tasks likely never use the `CELERY_DB_*` pool
  settings. Needs its own check.

## Recommendation

**Option C — a separate sandbox deployment, one database per sandbox.** Start with C1 for one or two
sandboxes; move to C2 when many run at once.

The tiebreaker is *where the upkeep lives*. Option A costs nothing in servers but adds a
schema-awareness obligation to every future PR, and its failure mode is test data in the client's
ledger. Option C's upkeep is operational and mostly automatable, and its failure mode is a stale or
down sandbox.

### Shape, as far as it is decided

- **Host:** a small separate VPS (2–4 GB) for all sandboxes is preferred; the current VPS works for
  one or two slim sandboxes if `docker stats` shows ~1–2 GB headroom.
- **Per sandbox:** a database cloned from `herbally_golden`, Redis DB number, storage
  bucket or prefix, subdomain.
- **Golden template:** master data only — chart of accounts, locations, products, tax rates, demo
  users. Never connected to by the app, never migrated in place.
- **Reset:** `DROP DATABASE sandbox_x` → `CREATE DATABASE sandbox_x TEMPLATE herbally_golden` →
  `alembic upgrade head`. Replaces `reset_transactional_data.sql`; touches one sandbox only.
- **Uses:** a sandbox per location for testing, per training batch, and per git branch (deploy the
  branch's `-dev` image against its own database).
- **UI:** a "Training" link to the sandbox URL and a loud banner — the separate URL is what stops
  users typing real invoices into a sandbox.

### Memory, measured from limits

| Container | Copied per sandbox? | Extra RAM |
|---|---|---|
| Postgres | No — new database in the same container | small |
| Redis | No — different DB number | negligible |
| Flower | No | 0 |
| API, 1 worker | Yes | ~250–400 MB |
| Celery, concurrency 1 | Yes | ~250–300 MB |

≈ 0.5–0.7 GB per C1 sandbox. Stop idle sandboxes with `docker compose down` (data stays). C2 keeps
it flat at one stack regardless of count.

### Keeping maintenance near zero

1. `release.yml` calls `deploy.yml` for the sandbox environment with the same tag as production —
   the sandbox can never drift.
2. A small script runs `alembic upgrade head` against every sandbox database on deploy.
3. Reset is a script, not a procedure.
4. No backups or alerting for sandboxes — losing one means a reset, not an incident.

What remains manual: one `deploy/config/sandbox.env`, its secrets, a DNS record, OS updates.

## What this rules out

- Test or training data in the production database or the production process.
- Postgres schemas as the isolation unit — databases are used instead (native `TEMPLATE` cloning,
  per-database advisory locks, no `search_path`).
- A test-mode toggle inside the production UI.
- Cloning production data into sandboxes without masking — the golden template holds synthetic
  masters instead.

## Open questions for the planning phase

- Is `herballytest` (the current "production" config) the client's live system? If so, it is the
  production box this note protects, and sandboxes must not share its host long-term.
- Real headroom on the current VPS — run `docker stats --no-stream` and check total RAM.
- Does `deployctl` (`MODE=single`, one `REMOTE_DIR`) support two projects on one host — ports,
  compose project name, reverse proxy?
- Golden-template contents and who owns refreshing it.
- When C2's login-time database selection is needed, design the token claim, Celery header and
  cache-key prefix together.

## If adopted, promote

- [ ] Decision + tiebreaker → [`../DECISIONS.md`](../DECISIONS.md)
- [ ] Any rule someone must follow → `.claude/rules/<topic>.md` or a `PROJECT_CONVENTIONS.md` section
- [ ] Sandbox create / reset / deploy steps → `docs/guides/`
- [ ] Status line above updated to `ADOPTED`
