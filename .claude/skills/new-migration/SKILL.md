---
name: new-migration
description: Create, apply and reverse an Alembic migration in this repo. Use when adding or changing a model, when asked for a migration or schema change, or when alembic autogenerate produces a wrong or empty diff.
---

# New migration

Migrations run **in the container**; tests and lint run on the host. Both reach the same
database.

## 1. Before generating

- **The model must be imported in `app/core/alembic_models_import.py`.** Autogenerate reads
  metadata, and metadata only knows about imported classes. A missing import produces a
  migration that silently omits your table. `uv run pytest app/core/tests/test_alembic_models_registered.py`
  checks this — run it first.
- **The database must already be at head**, or autogenerate will try to recreate every table.

```bash
uv run pytest app/core/tests/test_alembic_models_registered.py
docker compose exec api alembic upgrade head
```

## 2. Generate

```bash
docker compose exec api alembic revision --autogenerate -m "<short description>"
```

The filename is `YYYY_MM_DD_HHMM-<rev>_<slug>.py`, set by `file_template` in `alembic.ini`.

**Read the generated file before applying it.** Autogenerate is a first draft, not an
answer. Things it routinely gets wrong here:

## 3. The enum trap — the one that fails on deploy, not locally

**`op.add_column` does not emit `CREATE TYPE`.** A new `SQLEnum` column needs the type
created explicitly, or the migration dies with `type "x" does not exist` — on the
environment that has never seen the type, which is never your machine.

```python
from sqlalchemy.dialects import postgresql


def upgrade() -> None:
    status = postgresql.ENUM("draft", "published", name="release_status")
    status.create(op.get_bind(), checkfirst=True)
    op.add_column("release_notes", sa.Column("status", status, nullable=False))


def downgrade() -> None:
    op.drop_column("release_notes", "status")
    postgresql.ENUM(name="release_status").drop(op.get_bind(), checkfirst=True)
```

**`op.create_table` with an inline `sa.Enum` creates the type, but `op.drop_table(name)` never
drops it.** Autogenerate's `downgrade()` leaves it behind and the next `upgrade` dies with
`type "x" already exists` — add the same `postgresql.ENUM(name=...).drop(...)` after the table.

Models must declare enums by **value**, or the column stores member names and stops
matching your Python:

```python
SQLEnum(MyEnum, values_callable=lambda e: [m.value for m in e])
```

## 4. Other things to check in the draft

- **A rename read as drop + add.** Autogenerate cannot see intent. Replace it with
  `op.alter_column(..., new_column_name=...)` or the data is destroyed.
- **`nullable=False` with no `server_default` on a table that has rows** fails on any
  environment that is not empty. Add the column nullable, backfill, then alter.
- **An index or constraint you did not ask for**, from a model change you did not intend.
- **An empty diff** means the model is not registered, or the DB is not at head.

## 5. Apply, and prove it reverses

**Both directions, before committing.** A migration you cannot reverse is one you cannot
deploy twice.

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1
docker compose exec api alembic upgrade head
docker compose exec api alembic check   # must say "No new upgrade operations detected."
```

`alembic check` is the step that proves the migration matches the models. CI runs it too, but
only after you push.

## 6. Data migrations

Put data changes in their own revision, separate from the schema change. A schema
migration that also moves data cannot be reverted without losing the data, and it is much
harder to reason about when it fails halfway.

## 7. If you generated a probe migration

Relocating code (`docs/MODULE_CONVENTIONS.md` §8) uses autogenerate as a **check**: a pure
move must produce an **empty** diff. Confirm it is empty, then delete the file. Do not
commit a probe.
