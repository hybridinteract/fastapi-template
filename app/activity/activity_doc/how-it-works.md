# `app/activity` — the append-only audit trail

> Who did what, to which record, when. Written from anywhere, read through one gated endpoint.
> Last verified against the code: 9 September 2026.

## What it is for

A record of actions taken by people, kept separately from application state so that deleting a
record does not delete the evidence that someone deleted it. It is **append-only**: nothing in this
module updates a row.

## The table

`activity_logs` — one row per action. `actor_id` · `actor_name` · `action` · `resource_type` ·
`resource_id` · `details` (JSONB) · `ip_address` · `created_at`.

`resource_id` is a **string**, not a foreign key. That is deliberate: the log must survive the row it
describes, and a foreign key would either block the delete or cascade the evidence away. It also lets
one table cover every resource in the product without a join table per module.

Five indexes, all on the read paths the list endpoint offers: `actor_id`, `(resource_type,
resource_id)`, `action`, `created_at`, and `(actor_id, created_at)` for "what did this person do
lately", which is the query people actually run.

## Writing a log entry

```python
from app.activity import activity, ActivityAction

activity.log(
    actor_id=current_user.id,
    action=ActivityAction.UPDATE,
    resource_type="lead",
    resource_id=str(lead.id),
    details={"field": "status", "to": "won"},
)
```

`ActivityLogger.log()` is **fire-and-forget**: it dispatches the Celery task `write_activity_log` on
the `low_priority` queue and returns immediately. It is not awaited and returns nothing.

Three rules that matter:

- **Call it after `commit()`, never inside the transaction.** A log written inside a transaction that
  later rolls back records something that did not happen; worse, the dispatch is not transactional so
  it fires either way.
- **`action` must be an `ActivityAction` member.** The values are uppercase, and the API filters on
  exact string match — a hand-written lowercase string writes a row that can never be filtered for.
- **Never swallow a dispatch failure.** If the broker is down you want to know. A bare `except: pass`
  around this is how an audit trail silently stops existing.

`app/iam` does not import this module directly — it goes through the adapter at
[`app/iam/auth/activity.py`](../../iam/auth/activity.py), which no-ops when `app.activity` is absent.
That is what keeps `app/iam` a portable drop-in for a project that deletes this module.

## Reading

One router, gated at the router level on `activity:read_all` — there is no per-user view of your own
activity, by design: partial visibility into an audit trail is worse than none.

- `GET /activity` — filtered, sorted, paginated. This module is the **reference implementation of the
  list-endpoint pattern**; read `schemas.py` (`ActivityListParams`), `crud.py` (`get_list_filtered`),
  `service.py` and `routes.py` together as a worked example.
- `DELETE /activity` — hard delete by ID, 1–200 per request (`BulkDeleteRequest`). The one exception
  to append-only, for retention.

`ActivityListParams` keeps a page size of 50 rather than inheriting `ListParams`' 100. When
subclassing `ListParams`, re-declare any default you want to differ — otherwise adopting the base
class silently changes your endpoint's contract.

## Things that are easy to miss

- **A missing `celery_worker` means no logs and no error.** The API dispatches happily. Check
  `docker compose logs celery_worker`, not the API's log.
- **`details` is unvalidated JSONB.** Never put a secret, a token, or a password in it.
- **Extending the actions:** add members to `ActivityAction`. Anything you add must also be
  understood by whoever reads the log — an action nobody can interpret is noise.

## The files

`models.py` · `enums.py` (`ActivityAction`) · `logger.py` (the fire-and-forget façade) ·
`tasks.py` (the Celery task that writes the row) · `crud.py` · `service.py` · `routes.py` ·
`schemas.py` · `dependencies.py` · `exceptions.py`
