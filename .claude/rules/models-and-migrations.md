---
paths:
  - "app/**/models.py"
  - "app/**/models/**"
  - "app/core/alembic_models_import.py"
  - "migrations/**"
---
# Models and migrations

> The long version: [`docs/PROJECT_CONVENTIONS.md`](../../docs/PROJECT_CONVENTIONS.md) §4, §6, §8 ·
> layer packages: [`docs/MODULE_CONVENTIONS.md`](../../docs/MODULE_CONVENTIONS.md) §6.
> Last verified against the code: 10 September 2026.

## The rules

1. **Register every model in [`app/core/alembic_models_import.py`](../../app/core/alembic_models_import.py)**
   or `alembic revision --autogenerate` cannot see it and the table is never created. Those imports
   look unused — `ruff` is configured to ignore `F401` in that file. **Never let an autofixer remove
   them.** Checked by `app/core/tests/test_alembic_models_registered.py`.
2. **In a layered module, `models/__init__.py` must re-export every model.**
   `alembic_models_import.py` imports the *package*, so a model whose sibling is missing from that
   `__init__.py` is invisible to autogenerate — the same silent failure as rule 1, one level down,
   and the one the registration test cannot see. Every `class X(Base)` in `models/` appears in
   `__all__`.
3. `migrations/env.py` does `from app.core.alembic_models_import import *`. Never add a model to
   `env.py` directly.
4. **`op.add_column` does not emit `CREATE TYPE`.** A new `SQLEnum` column needs an explicit
   `postgresql.ENUM(..., name="…").create(op.get_bind(), checkfirst=True)` in `upgrade()` and a
   matching `.drop(..., checkfirst=True)` in `downgrade()`. Without it the migration dies with
   `type "x" does not exist` — on the deploy, not on your machine.
5. **Apply `upgrade` *and* `downgrade` before committing.** A migration you cannot reverse is one you
   cannot deploy twice.
6. **Autogenerate against a database already at head**, or it will try to recreate every table.
7. **Store enums as Postgres enums of the member *values***:
   `SQLEnum(E, values_callable=lambda e: [m.value for m in e])`. Without `values_callable`,
   SQLAlchemy stores the member *names*, and your data no longer matches your Python.
8. **Money is `Decimal`, never `float`,** and always paired with a currency.
9. **Timestamps use `utc_now()` from `app.core.utils`** — never `datetime.utcnow()`, which returns a
   naive datetime and compares wrongly against a timezone-aware column.
10. **Relationships load explicitly** with `selectinload(...)` in a dedicated `get_with_relations`.
   Implicit lazy loading raises under async.
11. **A relationship naming a class in another sibling file is a string, and a string is invisible to
   static analysis.** Import the target under `if TYPE_CHECKING:` so a reader and `ruff` can resolve
   it. SQLAlchemy resolves the string through its own registry at mapper-configuration time, so
   nothing is imported at runtime and the circular import never happens.

    ```python
    if TYPE_CHECKING:  # pragma: no cover - resolving the string annotations only
        from .workspace import Workspace
    ```

12. **Models are pure data.** No business logic, no queries, no HTTP.

## Where it IS used

| Where | What |
|---|---|
| [`app/core/alembic_models_import.py`](../../app/core/alembic_models_import.py) | The single registration point |
| [`app/core/models.py`](../../app/core/models.py) | `Base` — every model inherits from here |
| [`app/iam/user/models.py`](../../app/iam/user/models.py) | The shape to copy: UUID pk, timestamps, soft delete |
| [`app/activity/models.py`](../../app/activity/models.py) | Append-only; `resource_id` is a string, **not** a foreign key, so the log outlives the row |
| `migrations/versions/` | `YYYY_MM_DD_HHMM-<rev>_<slug>.py`, set by `file_template` in `alembic.ini` |

## Where it is deliberately NOT applied

- **There are no shared model mixins.** `app/iam/user/models.py` is copied rather than inherited from.
  Promote UUID-pk / timestamps / soft-delete into `app/core/models.py` when a **third** module needs
  the same three — not before.
- **`migrations/versions/` is excluded from ruff** (`extend-exclude` in `pyproject.toml`). Generated
  files are not style-checked; do not "clean them up".
- **`app/activity.resource_id` has no FK on purpose** — an audit row must survive the record it
  describes.

## Known gaps

- Nothing checks that a migration's `downgrade()` was ever run. Rule 5 is on you.
- `app/core/tests/test_alembic_models_registered.py` finds models by AST (`class X(Base)`), so a model
  declared through an unusual metaclass or a factory would not be seen. No such model exists today.
- **Nothing checks rule 2.** The test compares declared classes against `alembic_models_import.py`,
  which would still pass if a layered module's `models/__init__.py` omitted a sibling and the
  registry imported the sibling directly. No module here is layered yet; write the check with the
  first one.

## How to re-check this rule

```bash
uv run pytest app/core/tests/test_alembic_models_registered.py -v

# Should print the same set of class names as alembic_models_import.py imports.
grep -rhn "^class .*(Base)" app --include="models.py" --include="models/*.py" | sed 's/.*class \([A-Za-z_]*\).*/\1/' | sort

docker compose exec api alembic upgrade head && docker compose exec api alembic downgrade -1
docker compose exec api alembic upgrade head
```
