# Frontend Conventions

> A brief only. The frontend is a separate repo, built from its own template, and **its conventions
> live there** — stack, structure, naming, state, styling, checklists. They are not repeated here.
> Last verified against the code: 13 October 2026.

This file holds the one thing the backend owns: **the API contract a frontend can rely on.** Change
any of it and every client breaks, so treat it as a breaking change and record it in
`RELEASE_NOTES.md`.

## The contract

| Topic | What the backend guarantees | Owned by |
|---|---|---|
| Types | `/openapi.json` (and `/docs`) is the source of truth — generate client types from it rather than writing them by hand | FastAPI |
| Field names | JSON fields are `snake_case` — Pydantic field names, no alias generator. Any conversion to `camelCase` is the frontend's job, done once at its API boundary | `app/<module>/schemas` |
| Errors | Every error body carries `detail`: a **list** of field errors (`loc`, `msg`, `type`) on a 422, a message string otherwise. Errors from the global handlers also carry `error`, `timestamp` and `path` | [`PROJECT_CONVENTIONS.md`](PROJECT_CONVENTIONS.md) §13 |
| Auth | Bearer access token in `Authorization`. `POST /api/v1/auth/refresh` rotates the refresh token — the old one stops working | [`iam how-it-works`](../app/iam/iam_doc/how-it-works.md) |
| Permissions | Named `resource:action[:scope]`. Hide UI by permission, never by role name — roles are rearranged at runtime | [`PROJECT_CONVENTIONS.md`](PROJECT_CONVENTIONS.md) §9 |
| Lists | Filtering, sorting and pagination follow one shape across every list endpoint | [`PROJECT_CONVENTIONS.md`](PROJECT_CONVENTIONS.md) §10 |

For anything else about the frontend, read the frontend repo's own conventions.
