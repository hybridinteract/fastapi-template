# <Feature or module name>

> What this will be, before it exists. Copy this file, keep the sections in order, delete this line.
> Status: **PLANNED** | IN PROGRESS | SHIPPED | ABANDONED
> Last verified against the code: <DD Month YYYY>.

## Summary

One paragraph. What this is and who it is for. If you need "and" twice, it may be two features —
see [`../MODULE_CONVENTIONS.md`](../MODULE_CONVENTIONS.md) §4.

## What exists to build on

The code already in the repo that this uses — `CRUDBase`, the cache, the Celery decorators, an
existing module's service. Name files. This section is what stops a rebuild of something we have.

## Functionality

What a user can do, as a list. One line each, no implementation.

## Workflow

The path through the system, phase by phase, with any state machine written out. States are the
`StrEnum` values as they will appear in the code.

## Models with fields

| Table | Column | Type | Notes |
|---|---|---|---|

Money is `Decimal` with a currency, never `float`. Enums are stored as Postgres enums of the member
**values**. Say which columns are indexed and why.

## Permissions

`resource:action[:scope]`, as they will appear in `app/iam/permission_catalog.py`. Add a permission
only when a route will gate on it — one that gates nothing looks like a control and is not one.

## Background work

Celery tasks, their queue, and what happens when one fails. Nothing that must be transactional.

## Edge cases

The cases that will be got wrong. Concurrent writes, partial failure, empty states, the second time
someone clicks the button.

## Decide while building

Questions that do not block the design but need an answer before the code is finished. Move each into
[`../DECISIONS.md`](../DECISIONS.md) as it is settled.

## Deliberately not built

What we are choosing to leave out, **and why**. Without this, the next person builds it and a
reviewer flags its absence as an oversight.

## Open questions — need a human

Anything needing a product call. Name who can answer it.

## Exit criteria

Checkable by someone who did not write this plan.

- [ ] <route/behaviour> works end to end
- [ ] Migration applies **and** reverses
- [ ] `app/<module>/README.md` written (more than one doc → `app/<module>/docs/`)
- [ ] `uv run pytest app/<module>` green
