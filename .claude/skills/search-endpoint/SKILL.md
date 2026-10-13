---
name: search-endpoint
description: Choose and build the search for a list or GET endpoint — ILIKE, trigram, full-text, hybrid or pgvector — with its indexes, table preparation and migration. Use when adding a `search` parameter or search box to an endpoint, when a search is slow or misses typos, when results must be ranked by relevance, or when choosing a search technique or search index.
---

# Search endpoint

Pick the search technique **per field, from facts**, prepare the table for it, then build it.
**Start with the default and step up only for a reason you can name** — most endpoints never need
more than the default.

`app/core/crud/docs/search-strategy.md` ("the guide") owns the trade-offs, the decision and the
code. **Read the guide's §1–§7 now** — terms, the default, the techniques, the decision, table
preparation, the rules and the default's code. That is all a default search needs. The
list-endpoint plumbing (`ListParams`, `get_list_filtered`, `paginated_select`) is
`docs/PROJECT_CONVENTIONS.md` §10.

## 1. Collect the facts — read the code first, ask only for the rest

The terms below are defined in the guide's §1.

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

Walk the guide's decision (§4) for each field, starting from the default (§2). Any step past the
default needs one of the reasons in the §2 table.

## 3. Say what you chose before writing code

Three or four lines to the user: per field, the technique and its index; the trade-off accepted
("email is not typo-tolerant", "a swapped letter in a short name is not forgiven"); and what would
justify the next step ("if users search notes, add full-text"). Put the same under a **Search**
heading in the module's `README.md` — the code shows what was chosen, not why.

## 4. Build it

1. **Prepare the table** — the *Do* list in the guide's §5. Its *Do not* list waits for a
   measurement.
2. **The default** — the guide's §7: the model's indexes, `list_params.py`, the CRUD predicate.
3. **Each step beyond the default** — read its technique section, then its code in §12: trigram typo
   tolerance §8, full-text §9, vector §10, mixed input or combined ranking §11.
4. **Service and route** — unchanged. No search logic in either.
5. **Migration** — `/new-migration`. Add `CREATE EXTENSION IF NOT EXISTS pg_trgm` by hand before the
   first trigram index; autogenerate never renders it. On a table already large in production,
   build the index concurrently (§12.3).
6. **Tests** — an `integration` file: the search finds the right rows; search plus a filter gives
   the right total; `%` and `_` in the term match literally; a typo matches if you chose typo
   tolerance — pick one that §8 lists as forgiven.

## 5. Check before you finish

- [ ] Each searched field is the default, or has a reason from the guide's §2 table
- [ ] The guide's §5 *Do* list is done, and nothing from its *Do not* list was added
- [ ] Every rule in the guide's §6 holds — check them one by one
- [ ] The module's README says what was chosen and why
- [ ] The migration was upgraded **and** downgraded, and `alembic check` reports nothing

```bash
uv run pytest app/<module> -m ""
docker compose exec api alembic check
```
