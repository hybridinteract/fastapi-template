---
name: new-module
description: Choose a module's shape and scaffold it to the module anatomy in CLAUDE.md §1, then walk the registration checklist. Use when creating a new module, adding a domain area or feature package under app/, when asked to "add a <thing> module", or when deciding whether something should be flat, layered, composite or a shared kernel.
---

# New module

Two decisions before any file exists: **should this module exist**, and **what shape is it**. Both
get stated out loud. Then scaffold, then register it in the four places where forgetting fails
silently.

## 0. Should it exist at all?

`docs/MODULE_CONVENTIONS.md` §4 — the default is **don't**. A new top-level module needs **all four**:

1. It owns at least one table nothing else owns.
2. It has its own permissions — someone could be granted this and nothing else.
3. Its rules still make sense if the neighbouring module were deleted.
4. You can say what it does in one sentence with no "and".

If only 1 and 2 hold it is a **sub-module** of an existing module. If only 4 holds it is a service
method. **Say which of the four you checked** before creating anything.

## 1. Which shape?

**Answer this before writing a file, and say which step decided it.** Shape is chosen once, at the
start — converting later is a churn commit that touches every layer at once.

```
1. Does it own tables AND expose routes?
   NO  → SHARED KERNEL
   YES → continue

2. Does it hold two or more sub-domains that each own entities, where you would
   want a hard one-way import direction between them?
   YES → COMPOSITE MODULE
   NO  → continue

3. Will it ever hold a second entity?
   YES → LAYERED MODULE     ← the default for a domain module
   NO  → FLAT MODULE
```

Step 3 is a question about the **domain**, not the code, so it is answerable now. "Will a purchase
order ever need a supplier record?" — yes, so it is layered, before a line is written.

Report it like this, then proceed:

> **Shape: layered.** Step 3 — `billing` will hold `Invoice`, `LineItem` and `Payment`.

Full reasoning and the contracts: `docs/MODULE_CONVENTIONS.md` §6.

## 2. Scaffold

### Flat module — one table, no business rules

```
app/<module>/
├── __init__.py  dependencies.py  exceptions.py  enums.py
├── models.py  schemas.py  crud.py  services.py  routes.py  tasks.py
├── README.md
└── tests/__init__.py
```

Copy the shape from `app/activity/` — it is also the reference implementation of the list-endpoint
pattern.

### Layered module — the default

```
app/<module>/
├── __init__.py            # docstring; imports nothing heavy
├── dependencies.py        # REQUIRED, flat — the only file importing across modules
├── exceptions.py          # REQUIRED, flat
├── enums.py  list_params.py  tasks.py     # always flat, never folders
├── models/  schemas/  crud/  services/  routes/
├── README.md
└── tests/__init__.py
```

**A folder holding one file is the correct starting shape.** `services/` with a single
`<module>_service.py` is right — the second service has somewhere to go, and adding it is a new file
rather than a restructure.

Each layer package's `__init__.py` carries a docstring saying what it holds, then re-exports:

| Package | `__init__.py` must re-export | Why |
|---|---|---|
| `models/` | **every** model class | `alembic_models_import.py` imports the package; an omission is a table autogenerate stops seeing |
| `crud/` | each CRUD class **and** its singleton | the singleton is what `dependencies.py` wires; a second instance gives DI and tests different objects |
| `schemas/` | the public schemas | callers import from the package, never the sibling |
| `services/` | the service classes | same |
| `routes/` | each router — **and build no aggregator** | `app/apis/v1.py` registers them one by one, keeping the ordering hazard visible in one file |

### Composite module — sub-domains inside one bounded context

```
app/<module>/
├── __init__.py            # exports NOTHING — a docstring that DECLARES THE RANK ORDER
├── dependencies.py        # ONE, for every sub-module. The only file importing across modules
├── seed.py  tasks.py      # one seeder, one Celery surface
├── README.md              # ONE doc, covering every sub-module (docs/ beside it if needed)
├── tests/                 # ONE tests package, incl. test_module_boundary.py
├── <sub_0>/               # rank 0 — imports no sibling
│   ├── __init__.py        #   THE public surface: re-exports models, enums, exceptions
│   ├── enums.py  exceptions.py  list_params.py
│   └── models/  schemas/  crud/  services/  routes/
├── <sub_1>/               # rank 1 — may import rank 0
└── <sub_2>/               # rank 2 — may import ranks 0 and 1
```

What goes up and what goes down:

- **Root only:** `dependencies.py`, `seed.py`, `tasks.py`, `README.md`, `docs/`, `tests/`. One of each.
  Three `dependencies.py` files and you have three modules wearing a trench coat.
- **Per sub-module:** `enums.py`, `exceptions.py`, `list_params.py` and the layer packages. Each
  sub-domain has its own vocabulary.
- **The root `__init__.py` exports nothing.** Re-exporting would make the sub-domains look like one
  flat namespace, which is the first step back to a module with no internal boundary. Callers write
  `from app.<module>.<sub> import X`.

Then do step 5 — it is not optional.

### Shared kernel — business primitives, no HTTP

```
app/<module>/
├── __init__.py            # the single public surface — an explicit __all__
├── <concept>.py …         # value objects and rules, named for concepts
├── exceptions.py          # plain ValueError subclasses — NOT HTTPException
├── README.md
└── tests/__init__.py
```

**No models, no schemas, no crud, no routes, no `dependencies.py`, no migration, no permissions.**
If you find yourself adding a route, it should have been a domain module. It is **not** `core/`
either — `core/` is business-free, and a kernel names business concepts.

> **A kernel or composite module will fail `app/core/tests/test_module_anatomy.py` today.** That test
> requires `dependencies.py` and a root `exceptions.py` on every module, which is right for flat and
> layered and wrong for these two. Making it shape-aware is a tracked follow-up — say so rather than
> weakening the test, and never delete the assertion to get green.

## 3. Write it in dependency order

`models` → `schemas` → `crud` → `services` → `dependencies.py` → `routes`.

The contract, from `.claude/rules/layering.md` — that file loads automatically once you open a
service or CRUD file, so read what it says rather than guessing:

- **Service owns the transaction.** Exactly one `await session.commit()` per mutation.
- **CRUD flushes only.** `flush()` then `refresh()`. Never `commit()` / `rollback()`.
- **Routes never touch CRUD** and never build a raw `HTTPException`.
- Every route dependency is an `Annotated` alias declared in `dependencies.py`.
- A query-params model binds as `Annotated[XListParams, Query()]` — **never `Depends()`**.
- A list endpoint with a `search` field: choose its technique and index with `/search-endpoint`
  before writing the CRUD. An `ilike('%term%')` with no index is right only for a bounded table.
- A model relationship naming a class in another sibling file is a string: import the target under
  `if TYPE_CHECKING:` so `ruff` and a reader can resolve it.

## 4. Register it — all four, or it fails silently

1. **Models** → `app/core/alembic_models_import.py`. Missing means autogenerate never sees the table.
   For a layered module, import from the **package** — and make sure `models/__init__.py` re-exports
   every sibling, or the same failure happens one level down.
2. **Router** → `app/apis/v1.py`. **Literal prefixes before wildcard ones** — read the comment in
   that file before inserting your line. A composite registers each sub-module's routers
   individually; there is no aggregator to include.
3. **Permissions** → `app/iam/permission_catalog.py`, as `(resource, action, description)`. Only add
   one a route actually gates on.
4. **Migration** → use the `/new-migration` skill. There is a trap with enum types.

## 5. Composite only — the rank and its test

**Declare the rank in the root `__init__.py` docstring**, lowest first, and say what each sub-module
is for. Then write the boundary test **before the second sub-module exists**. A boundary test added
after the first breach starts red and gets weakened until it passes.

Why this is a test and not a convention: `app/iam` is a composite module with neither a rank nor a
test, and its boundary dissolved into a cycle — `auth/` imports `user/` in 8 places, `user/` imports
`auth/` in 4, and one function-local import at `app/iam/auth/current_user.py:44` is what stops
startup deadlocking. Each of those imports passed review on its own.

Copy `.claude/skills/new-module/templates/test_module_boundary.py` to
`app/<module>/tests/test_module_boundary.py`, then set `RANK` to the sub-module names, lowest rank
first — the order the root `__init__.py` docstring declares. Nothing else in the file changes.

## 6. Document, test, verify

- `app/<module>/README.md` — what it is for, **its shape and the step that chose it**, its tables,
  how a request flows through it, where it joins other modules, and the rules that are easy to trip
  over. `app/iam/README.md` is the reference. Add the stamp line:
  `Last verified against the code: <DD Month YYYY>`. A second document goes in `app/<module>/docs/`,
  linked from the README — never loose beside the code.
- `app/<module>/tests/` — a package with `__init__.py`. Any file needing Postgres gets
  `pytestmark = pytest.mark.integration` under its imports, per file.

```bash
uv run pytest                    # the convention tests cover most of step 4
python3 scripts/check_docs.py
uv run ruff check app/<module>
```

Then confirm the migration reverses:

```bash
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1
docker compose exec api alembic upgrade head
```

If the module changes an architectural assumption, add an entry to `docs/DECISIONS.md`.
