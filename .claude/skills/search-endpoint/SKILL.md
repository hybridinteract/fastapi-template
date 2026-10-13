---
name: search-endpoint
description: Choose and build the search for a list or GET endpoint — ILIKE, trigram, full-text, hybrid or pgvector — with its indexes, table preparation and migration. Use when adding a `search` parameter or search box to an endpoint, when a search is slow or misses typos, when results must be ranked by relevance, or when choosing a search technique or search index.
---

# Search endpoint

Pick the search technique **per field, from facts**, prepare the table for it, then build it.
**Start with the default and step up only for a reason you can name** — most endpoints never need
more than the default.

This skill is the procedure. `app/core/crud/docs/search-strategy.md` ("the guide") owns the
trade-offs, the decision and the code. **Read the guide in full before deciding** — it is short.
The list-endpoint plumbing is `docs/PROJECT_CONVENTIONS.md` §10; `app/activity/` is its example.

## 1. Collect the facts — read the code first, ask only for the rest

The guide's §1 defines every term below.

| Fact | Read it from | Ask when |
|---|---|---|
| Which fields the search covers | The task, the frontend's search box | The task only says "add search" |
| Short text, long text or identifier, per field | The model's column types and names | A column's name and type disagree |
| Bounded or growing table | The domain — departments are bounded, leads are not | It is not obvious |
| Search-as-you-type or submitted search | The task, the frontend | Long text is searched |
| Typo tolerance | — | A person's name or a free-typed label is searched |
| Ranked by best match | Long text usually is | Short text is searched and no `sort_by` is given |
| One box for mixed input (name **or** phone **or** code) | The task, the frontend | Both identifiers and text are searched |
| An embedding pipeline | `git grep -n pgvector` | Never assume one exists |
| The filters the endpoint combines with search | The existing `list_params.py` | — |

**Ask everything missing in one message, each question with your recommended default**, so a
one-word reply settles it. Do not ask what the code already answers.

## 2. Decide

Walk the guide's §4 per field, starting from the default in §2. Any step past the default needs
the reason from §2's table.

## 3. Say what you chose before writing code

Three or four lines to the user: per field, the technique and its index; the trade-off accepted
("email is not typo-tolerant", "a swapped letter in a short name is not forgiven"); and what would
justify the next step ("if users search notes, add full-text"). Put the same under a **Search**
heading in the module's `README.md` — the code shows what was chosen, not why.

## 4. Build it

1. **Prepare the table** — guide §5, the *Do* list only. The *Do not* list waits for a
   measurement.
2. **Model** — the indexes and generated columns, as in guide §10.1.
3. **`list_params.py`** — guide §10.2.
4. **CRUD** — guide §10.3: the predicate in the same `filters` list as every other filter,
   `escape_like()` on every `LIKE` / `ILIKE`, relevance as the default sort when ranked.
5. **Service and route** — unchanged. No search logic in either.
6. **Migration** — `/new-migration`. Autogenerate renders the indexes; add
   `CREATE EXTENSION IF NOT EXISTS pg_trgm` by hand before the first trigram index. A table already
   large in production builds its index concurrently — guide §10.4.
7. **Tests** — an `integration` file: the search finds the right rows; search plus a filter gives
   the right total; `%` and `_` in the term match literally; a typo matches if you chose typo
   tolerance — use one the guide's §6 says trigrams forgive.
8. **Prove each index is usable** — guide §11 rule 7.

## 5. Check before you finish

- [ ] Each searched field is the default or has a named reason for more (guide §2)
- [ ] Every index the technique needs exists, and the query uses its exact expression
- [ ] Filters that narrow the list have B-tree indexes; nothing from §5's *Do not* list was added
- [ ] Search and filters sit in one `WHERE`, in one query
- [ ] `escape_like()` on every `ILIKE`; `websearch_to_tsquery` for every user-typed tsquery
- [ ] `ORDER BY` ends with `id`; no search logic in the route or service
- [ ] The module's README says what was chosen and why
- [ ] The migration was upgraded **and** downgraded, and `alembic check` reports nothing

```bash
uv run pytest app/<module> -m ""
docker compose exec api alembic check
```
