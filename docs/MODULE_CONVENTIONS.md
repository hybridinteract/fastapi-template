# Module Conventions — where code goes

> [`PROJECT_CONVENTIONS.md`](PROJECT_CONVENTIONS.md) governs **how** code is built. This file governs
> **where** it goes: placement, granularity, module shape, and when a new module is justified.
> Read it before creating any module or folder — not by default.
> Last verified against the code: 13 October 2026.

## 0. The golden rule

**Code lives with the thing it is about.** A file belongs to the module whose behaviour it changes,
not to the layer it happens to resemble. If you cannot name the module a helper belongs to, you have
not finished designing it — do not park it in `core/`.

## 1. The layer model

```
Route → Service → CRUD → Model
```

The direction is strict and one-way. `dependencies.py` is the only file that wires a service into
routes, and the only file that imports across modules. Full rules: `PROJECT_CONVENTIONS.md` §4 and §5.

**Every module is layered.** What differs between modules is whether a layer is a *file* or a
*package* — that is the module's **shape**, and §6 decides it.

### What a module is

Four classifications. This is a different question from shape, and it comes first.

| Classification | Nature | Contains | Never contains |
|---|---|---|---|
| **Technical core** — `app/core/` | Portable infrastructure, **zero business** | db, cache, settings, storage, logging, middleware, generic CRUD base, Celery infra | Any business rule, value or term |
| **Reusable capability** | A vertical feature that is **product-agnostic** | Its own models → routes | Project-specific business rules |
| **Domain module** | Exactly **one bounded context** | That domain's models → routes | Another domain's logic |
| **Shared kernel** | Cross-cutting **business primitives**, no HTTP surface, no single owner | Value objects and the rules many domains depend on | Routes, tables, one-domain logic |

Here: `app/core/` is the technical core; `app/iam`, `app/activity` and `app/release_notes` are
reusable capabilities. Every module added for the product itself is a domain module.
There is no shared kernel here yet — §6.2 describes the shape for the first one.

## 2. The `core/` gate (strict)

`app/core/` is **infrastructure that would be identical in a completely different product**. Session
factory, `CRUDBase`, pagination helpers, settings, cache, Celery plumbing, object storage.

A thing may go in `core/` only if **all** of these hold:

1. **Portability** — it has no knowledge of any business concept in this product.
2. **Independence** — deleting every business module would leave it still correct and still useful.
3. **Two callers** — at least two existing modules use it, today, in committed code.

Rule 3 is the one that gets skipped. "We will need it elsewhere" is not two call sites. Build it in
the module that needs it; promote it on the **third** caller, when the shape has stopped moving.

**Never in `core/`:** a permission name, a role, a status enum, a business rule, a table that models a
domain entity, or a helper whose name contains a domain noun.

> **The trap is a generic-sounding name, not an obviously domain one.** A tax or currency-rounding
> engine called `money` reads like infrastructure and is not — it encodes business rules. That is
> what the **shared kernel** classification is for (§6.2), and it is why the gate above is two
> mechanical tests rather than a list of banned filenames: a list would have passed `money`.

## 3. Where business helpers go — the anti-`utils` rule

**There is no `utils.py`, `helpers.py`, `common.py` or `shared/` for business code.** Those names
describe nothing, so everything ends up in them and nothing can be safely deleted.

A helper goes in the module that owns the concept:

| Helper about… | Lives in |
|---|---|
| One module's rules | `app/<module>/` — a sibling named for the concept, e.g. `scope.py` |
| A business primitive **many** modules need, with no owner and no HTTP | A **shared kernel** module (§6.2) |
| Building SQL or queries | `app/core/crud/` |
| The framework, not the domain | `app/core/<subject>.py`, subject to §2 |

`app/core/utils.py` exists and is the one exception: date/time and string primitives with no domain
meaning (`utc_now()`, `escape_like()`). Do not grow it. If your addition needs a comment explaining which feature it
serves, it does not belong there.

## 4. Creating a new top-level module — the bar

**Default: don't.** Most new work is a feature of a module that exists.

Create `app/<module>/` when **all** of these hold:

1. It owns at least one **table** nothing else owns.
2. It has its own **permissions** — someone could be granted this and nothing else.
3. Its rules would still make sense if the neighbouring module were deleted.
4. You can state what it does in one sentence with no "and".

If only 1 and 2 hold, it is probably a **sub-module** of an existing module (`app/iam/permission/` is
one). If only 4 holds, it is a service method.

A new module is a commitment: a router registration, a migration, permissions, a `<module>_doc/`, a
`tests/` package, and a line in this repo's structure that the next person has to understand.

## 5. Split vs keep together

Split when two halves have **different lifecycles** — different owners, different release cadence, or
one is deployable without the other. Keep together when they share invariants that would have to be
enforced twice.

Coupling is the test, not size. A 600-line module whose parts always change together is one module.
Two 80-line modules that never change together are two.

When the answer is "one module, but it has internal structure", that is a **composite module** —
§6.2.

---

## 6. Module shapes

### 6.1 The four shapes, and how to choose

| Shape | The module's layers are… | Choose it when |
|---|---|---|
| **Flat module** | files — `models.py`, `services.py` | It is genuinely one small thing: one table, no business rules |
| **Layered module** | packages — `models/`, `services/` | **The default for a domain module** |
| **Composite module** | sub-modules, each flat or layered | It is one bounded context with two or more sub-domains |
| **Shared kernel** | neither — concept-named files, no routes | Business primitives with no HTTP surface and no tables |

Two questions, in order. **What it is** comes before **how it is shaped.**

```
1. Does it own tables AND expose routes?
   NO  → SHARED KERNEL.  Cross-cutting business primitives, no HTTP.
   YES → a domain module; continue.

2. Does it hold two or more sub-domains that each own entities, where you would
   want a hard one-way import direction between them?
   YES → COMPOSITE MODULE.
   NO  → continue.

3. Will it ever hold a second entity?
   YES → LAYERED MODULE.     ← the default
   NO  → FLAT MODULE.
```

Step 3 is a question about the **domain**, not the code, so it is answerable before a line is
written. That is the point: shape is chosen deliberately, once, at the start.

**Name the shape and the deciding step in the module's `how-it-works.md`.** A shape nobody can
explain gets changed by the next person for a reason nobody records.

> **Why layered is the default, and why not "start flat and split when it gets big".**
> That was this file's rule until 10 September 2026, and it is wrong for a codebase being built.
> A domain module that will hold a second entity ends up split, so the flat file is a stage nobody
> stays in — and converting later is a churn commit that touches every layer at once and buries the
> real diff underneath it. **Start where you are going to end up.**
>
> The size version of the rule also never fires here. It implies a threshold around 600 lines;
> the largest file in any module is `app/iam/create_admin.py` at 367, and the largest anywhere is
> `app/core/cache/cache.py` at 531. A rule that never triggers does not make the decision — it just
> means the decision gets made by accident.
>
> **A folder holding one file is the correct starting shape, not a smell.** The second file has
> somewhere to go, and adding it is a new file rather than a restructure.
> Full reasoning: [`DECISIONS.md`](DECISIONS.md), 10 September 2026.

### 6.2 The shape contracts

#### Flat module

```
app/<module>/
├── __init__.py  dependencies.py  exceptions.py  enums.py
├── models.py  schemas.py  crud.py  services.py  routes.py  tasks.py
├── <module>_doc/how-it-works.md
└── tests/__init__.py
```

[`app/activity`](../app/activity) and [`app/release_notes`](../app/release_notes) are the worked
examples — one table each, no business rules worth a second entity. Both name the file `service.py`;
singular or plural is fine in a flat module, as long as the module is consistent.
`app/release_notes` has no `tests/` package yet.

#### Layered module — the default

```
app/<module>/
├── __init__.py            # docstring; imports nothing heavy
├── dependencies.py        # REQUIRED, flat — the only file importing across modules
├── exceptions.py          # REQUIRED, flat
├── enums.py               # flat
├── list_params.py         # flat — XListParams(ListParams)
├── tasks.py               # flat
├── <concept>.py           # a helper two siblings share, named for the concept — never utils.py
├── models/  schemas/  crud/  services/  routes/
├── <module>_doc/
└── tests/
```

**These five never become folders:** `dependencies.py`, `exceptions.py`, `enums.py`,
`list_params.py`, `tasks.py`. Stated once so the question does not come up again.

Rules inside a layer package:

- **One sibling per entity** for `models`, `schemas`, `crud`, `routes`; **one sibling per cohesive
  job** for `services`. Never split by line count.
- **The public import surface is the package, never a submodule.**
  `from app.<module>.crud import x_crud` is the only form callers use. Nobody reaches into `crud.x`.
- **`models/__init__.py` must re-export every model.**
  [`app/core/alembic_models_import.py`](../app/core/alembic_models_import.py) imports the *package*,
  so a model left out is a table autogenerate stops seeing — the same silent failure
  `app/core/tests/test_alembic_models_registered.py` already catches.
- **`crud/__init__.py` re-exports each CRUD class *and* its singleton.** The singleton is what
  `dependencies.py` wires; a second instance gives DI and the tests different objects.
- **`routes/__init__.py` re-exports each router and builds no aggregator.**
  [`app/apis/v1.py`](../app/apis/v1.py) registers them one by one. Splitting `routes.py` moves the
  literal-before-wildcard hazard out of one file's declaration order and into `v1.py`, where
  `app/apis/tests/test_route_registration.py` guards it.
- **A cross-sibling model relationship is a string, and a string is invisible to static analysis.**
  Import the target under `if TYPE_CHECKING:` so a reader and `ruff` can resolve it; SQLAlchemy
  resolves it through its own registry at runtime, so the circular import never happens.
- **Each `__init__.py` docstring says what the package holds and why it is split**, and nothing else.

> There is no layered module here yet — every module here predates this rule and is genuinely
> small. `/new-module` generates the shape correctly; the trees above are the specification until a
> module in this repo earns the conversion.

#### Composite module

> **A composite module is one bounded context whose internal sub-domains are separated into
> sub-modules, with a declared, test-enforced, one-way import order between them.**

Each clause is load-bearing. **One bounded context** — two halves with different owners and
different languages would be two top-level modules; this shape is for one thing that has internal
structure. **Sub-domains that each own entities** — a sub-module owning no table is a service file.
**Each sub-module is itself flat or layered** — the shape recurses. **Declared, enforced, one-way
order** — without the rank and the test you do not have a composite module, you have `app/iam`.

From outside it is one module: one `dependencies.py`, one `tests/`, one `<module>_doc/`, one seeder.
From inside it is several. That gap is the idea.

A **hypothetical** example — the only path in this file you cannot open, kept because it is the
shape's clearest illustration:

```
app/procurement/
├── __init__.py            # exports NOTHING — a docstring that DECLARES THE RANK ORDER
├── dependencies.py        # ONE, for all three. The only file that may import across modules
├── seed.py  tasks.py      # one seeder, one Celery surface
├── procurement_doc/       # ONE doc folder; one how-it-works.md covering all three
├── tests/                 # ONE tests package, incl. test_module_boundary.py
├── product/               # rank 0 — the catalogue
│   ├── __init__.py        #   THE public surface: re-exports models, enums, exceptions
│   ├── enums.py  exceptions.py  list_params.py
│   └── models/  schemas/  crud/  services/  routes/
├── inventory/             # rank 1 — stock per product
└── purchase/              # rank 2 — orders, receiving, supplier terms
```

1. **`dependencies.py` is singular and lives at the module root.** Keeping the wiring in one place is
   what stops each sub-module growing its own cross-module imports and quietly becoming a separate
   module that needs the others. Three `dependencies.py` files and you have three modules wearing a
   trench coat.
2. **The root `__init__.py` exports nothing.** `from app.procurement import Product` would make the
   sub-domains look like one flat namespace, which is the first step back to a module with no
   internal boundary. Callers import `from app.procurement.product import Product`.
3. **The import direction is one-way and declared** — not at module level, not deferred, not inside
   a function.
4. **Declare a rank, not a single arrow.** Sub-modules form a chain, and each may import **only
   lower ranks**: `product (0) ← inventory (1) ← purchase (2)`. Nothing ever points left. The rank
   is stated in the root `__init__.py` docstring.
5. **The rank is a test, written before the second sub-module exists.** `tests/test_module_boundary.py`,
   generated by `/new-module`. A boundary test added after the first breach starts red and gets
   weakened until it passes.

**When it should NOT be composite.** The shape costs a boundary test and a level of navigation. If
the sub-domains change together and share transactions — a purchase order and a stock level written
in one commit — it is **one layered module** with `models/{product,stock_item,purchase_order}.py`.
The test is step 2's own wording: *would you want a hard one-way import direction between them?*
A boundary you have to keep crossing is not a boundary, it is a tax.

> **Why rule 5 is a test and not a convention — our own module is the cautionary tale.**
> [`app/iam`](../app/iam) is a composite module with no rank and no boundary test, and its boundary
> has dissolved: `auth/` imports `user/` in 8 places across 3 files, `user/services.py` imports
> `auth/` in 4, and one function-local import at
> [`app/iam/auth/current_user.py:44`](../app/iam/auth/current_user.py) is what stops startup
> deadlocking. Nobody decided that — it happened one reasonable-looking import at a time, and each
> one passed review. A convention on its own produces a cycle; the rank plus the test produces a
> chain.

#### Shared kernel

```
app/<module>/
├── __init__.py            # the single public surface — an explicit __all__
├── <concept>.py …         # value objects and rules, named for concepts
├── exceptions.py          # plain ValueError subclasses — NOT HTTPException
├── <module>_doc/  tests/
```

**No models, no schemas, no crud, no routes, no `dependencies.py`, no migration.** The test that it
is a kernel and not something else: *a route on a kernel means it should have been a domain module.*

It is **not** `core/`. A money, tax or pricing kernel fails §2's portability and vocabulary tests by
naming business concepts — which is exactly the mistake §2 exists to prevent. `core/` is
business-free; a kernel is business primitives that no single domain owns.

### 6.3 Where a module's documents live

**`app/<module>/<module>_doc/`** — every `.md` the module owns, starting with `how-it-works.md`. The
prefix is deliberate: it makes the folder a unique grep target and keeps editor tabs distinguishable.

- **No loose `.md` beside the `.py` files**, and nothing about one module in `docs/`.
- `how-it-works.md` is the developer note: what the module is for, **its shape and the step that
  chose it**, its tables, how a request flows through it, where it joins other modules, and the
  handful of rules that are easy to trip over.
  **Every module has one** — [`app/iam/iam_doc/how-it-works.md`](../app/iam/iam_doc/how-it-works.md)
  is the reference. `app/core/tests/test_module_anatomy.py` fails without it.
- A behaviour guide, `<module>-user-guide.md`, is added once a module has real business rules.
  Plumbing does not need one.
- **A composite module has one `<module>_doc/` at its root**, with a single `how-it-works.md`
  covering every sub-module. Behaviour guides may split per sub-domain, because they have different
  readers.

`app/core/<subpackage>/README.md` is the documented exception: those are libraries, and `README.md`
renders at the folder level on GitHub, which is what you want for something consumed by other code.
`app/core/crud/SEARCH_STRATEGY.md` sits beside its README as the long-form companion — the only one.

### 6.4 Where a module's tests live

**`app/<module>/tests/`** — a package with `__init__.py`. Repo-wide fixtures stay in `app/conftest.py`;
a module's own go in its `tests/conftest.py`. Rules: [`.claude/rules/tests.md`](../.claude/rules/tests.md).

**One `tests/` per module, not per sub-module.** A composite module has sub-modules inside it and
**one** `tests/` package at the root. The module is the unit that gets moved, owned and deleted, so
it is the unit that owns the tests.

## 7. Naming = nature

The name says what the thing **is**, not what it is made of or when it was added.

- `app/billing/`, not `app/billing_module/` or `app/new_billing/`.
- `crud` / `services` / `routes` — the canonical names, whether file or package. A module with
  `repository.py` or `handlers.py` costs every reader a translation step.
- **A layer's name does not change when it is a package.** `services.py` and `services/` are the
  same layer; never `service_impl/`.
- Singular for a concept, plural for a collection: `app/iam/permission/` holds the permission model;
  `PLATFORM_PERMISSIONS` is the catalogue.
- **Smell list** — if you reach for one of these you have not found the real concept yet:
  `utils`, `helpers`, `common`, `shared`, `misc`, `core_*`, `*_stuff`.

> **On "composite module".** It is this codebase's own term, not standard vocabulary — there is no
> established industry name for this file shape. It was chosen because it says *made of parts*
> without implying size, and because it collides with nothing already in use here: DDD's
> **Aggregate** is a consistency boundary, **Bounded Context** is the module itself, and **Shared
> Kernel** is §6.2's fourth shape. `influen-backend` calls the same thing "subpackages"; if you move
> between the two repos, they are one idea with two names.

## 8. Changing a module's shape, or fixing a misplacement

Both are a **move, not a rewrite**:

1. `git mv` so history follows the file.
2. **Exported names must not change.** `from app.<module>.crud import x_crud` must resolve exactly as
   it did — which for a layer package means the new `__init__.py` re-exports everything the old file
   did. Re-export from the old location if anything outside the repo imports it.
3. **`alembic revision --autogenerate` must produce an empty diff afterwards.** Run it, confirm it is
   empty, then delete the probe migration. That empty diff is the proof the models package is
   schema-identical — a non-empty one means you changed a table, not a location.
4. Update the module's `<module>_doc/` — including the shape it now is — and any link into it, in the
   same change. `scripts/check_docs.py` catches the links you miss.

**Do the conversion alone.** A shape change touches every layer at once; on a branch that is also
doing something else, the real diff is unreviewable underneath it.

## 9. Decision flow

Two passes. First **where does this code live**:

```
Pure technical infra, portable to any project, zero business terms, ≥2 callers today?
  yes → app/core/
  no  ↓
A business primitive many domains need, with no HTTP and no single owner?
  yes → a shared kernel module
  no  ↓
Does it own a table + its own permissions, and stand alone?  (§4's four tests)
  yes → a new app/<module>/
  no  ↓
A distinct sub-domain inside a module that owns tables?
  yes → a sub-module: app/<module>/<sub>/
  no  → a function in the owning module's services
```

Then, for a new module, **what shape** — §6.1.

## 10. PR gate

Block the change if any of these fail:

- [ ] The module's **shape is named** in `<module>_doc/how-it-works.md`, with the step that chose it.
- [ ] New module has `__init__.py`, `dependencies.py`, `exceptions.py`, and `<module>_doc/how-it-works.md`.
      *(A shared kernel has no `dependencies.py`; a composite carries `exceptions.py` per sub-module.)*
- [ ] A layered module's `models/__init__.py` re-exports **every** model; `crud/__init__.py`
      re-exports each class **and** its singleton; `routes/__init__.py` builds no aggregator.
- [ ] A composite module declares its **rank order** and has `tests/test_module_boundary.py`.
- [ ] Models registered in `app/core/alembic_models_import.py`, and the migration applies, reverses,
      and leaves `alembic check` clean.
- [ ] Router registered in `app/apis/v1.py`, specific prefixes before wildcard ones.
- [ ] Nothing domain-specific was added to `app/core/`.
- [ ] No new `utils.py` / `helpers.py` / `shared/` holding business code.
- [ ] `uv run pytest` green — the convention tests cover several of the rows above.
