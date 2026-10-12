# `app/release_notes` — the "What's New" system

> Version announcements, drafted privately and published to users.
> Last verified against the code: 9 September 2026.

## What it is for

Telling users what changed. A note is written as a **draft**, reviewed, then **published** — at which
point it becomes visible and `published_at` is stamped.

## The table

`release_notes` — `version` (unique) · title · body · `is_published` · `published_at` ·
`created_by` · timestamps.

**`version` is unique**, and the service checks for a duplicate before both create and update. That
check is a race under concurrent writes; the unique constraint is what actually protects you, and the
check exists to turn a 500 into a 409 in the common case.

## The lifecycle

```
draft ──publish──▶ published
      ◀─unpublish─
```

`published_at` is set when publishing and left alone when unpublishing, so a re-published note keeps
its original announcement date. If you need "last published" semantics instead, change it
deliberately and say so here.

## Reading and writing

Public reads (the latest published note, the published list) are separate from the admin surface that
creates, edits and publishes. Gate the admin routes on permissions; the published list is the one
place where an ungated read is correct — it is the product's own changelog.

## Things that are easy to miss

- **Creating does not publish.** A note created through the API is invisible until it is published.
  This surprises people who expect `POST` to mean "announce".
- **The service owns the transaction.** `crud.py` flushes; `service.py` calls `commit()` exactly once
  per mutation and then `refresh()`.
- **Errors come from `exceptions.py`.** `ReleaseNoteNotFoundError` (404) and
  `ReleaseNoteVersionExistsError` (409). Never build a raw `HTTPException` here — `CLAUDE.md` §6.
- **This module is a template default.** If your product announces changes some other way, delete it:
  drop the router from `app/apis/v1.py`, the model from `app/core/alembic_models_import.py`, and write
  the removal down in `docs/DECISIONS.md`.

## The files

`models.py` · `schemas.py` · `crud.py` · `service.py` · `routes.py` · `dependencies.py` ·
`exceptions.py`
