# Search — choosing the technique and preparing the table

> Owns the trade-offs for every search on a list or GET endpoint. To design one step by step, use
> the `search-endpoint` skill (`.claude/skills/search-endpoint/SKILL.md`), which applies this guide.
> Last verified against the code: 13 October 2026 — and against the PostgreSQL 18 and pgvector
> 0.8.7 docs. Everything here also works on PostgreSQL 16, which the app runs: the code in §7 and
> §12, the index plans and the scores in §8 were checked on PostgreSQL 16.14 with SQLAlchemy 2.0.54
> and Alembic 1.20. Sources are at the end.

**§1–§7 are all a default search needs.** Their pointers into §8–§12 are for the steps beyond the
default — follow one only when §4 chose that step.

## 1. Terms

| Term | Means |
|---|---|
| **Term** | The raw string the user typed |
| **Short text** | A value of a few words: name, title, email, label |
| **Long text** | Prose: description, notes, body, comment |
| **Identifier** | A value with a known format: code, SKU, invoice number, phone |
| **Bounded table** | Its row count is capped by the business (departments, currencies, roles), not by use |
| **Growing table** | Every other table — including one that is small today |
| **Search-as-you-type** | Results refresh on each keystroke, so the term is often a partial word |
| **Submitted search** | The user types whole words and presses Enter |
| **Typo-tolerant** | "jonathon" finds "Jonathan" — see §8 for what trigrams can and cannot forgive |
| **Ranked** | Ordered by how well each row matches, not by a column |

## 2. Start simple

**The default search** — what most list endpoints need, and the industry-standard first step:

- `ILIKE '%term%'` on each short-text field the search box covers, `OR`-ed together;
- one GIN trigram index per field (§8);
- `escape_like()` on the term, `min_length=3`, `max_length=100`;
- no ranking — the endpoint's normal sort.

Go beyond it one step at a time, and only for a reason you can name:

| Add | Only when |
|---|---|
| Typo tolerance (`<%`) | The field holds names or labels people type from memory |
| Full-text | Long text must be searched, or results must be ranked |
| Full-text + trigram in one box | Both rows above apply to one search box |
| Vector | Users search by meaning, and an embedding pipeline already exists |
| A partial or multicolumn index, GiST | `EXPLAIN ANALYZE` on real data shows the plain indexes are not enough (§5) |
| `setweight`, `ts_headline`, input classification | The feature asks for it |

## 3. The techniques

| Technique | Predicate | Index | Partial words | Typos | Ranks |
|---|---|---|---|---|---|
| Exact | `col = term` | B-tree | — | No | No |
| Prefix | `col LIKE 'term%'` | B-tree `text_pattern_ops` | Start only | No | No |
| Substring | `col ILIKE '%term%'` | GIN `gin_trgm_ops` | Yes | No | No |
| Trigram similarity | `term <% col` | GIN `gin_trgm_ops` | Yes | **Yes** | Yes — word distance |
| Full-text | `vector @@ websearch_to_tsquery(cfg, term)` | GIN on a stored `tsvector` | **No** — whole words | No | Yes — `ts_rank_cd` |
| Vector | `embedding <=> query_embedding` | HNSW | — | Meaning | Yes — distance |

Every index slows every insert and update on its table, for the life of the table. Choose the
lightest technique that meets the facts.

## 4. Decide — per field, first match wins

```
1. Identifier?       exact match  → =             B-tree (often the unique constraint you already have)
                     starts-with  → LIKE 'term%'  on lower(col), B-tree text_pattern_ops          §12.1
                     digits/phone → ILIKE         on a digits-only generated column, GIN trigram   §5
2. Bounded table?    → ILIKE '%term%', no index — a sequential scan of a capped table is cheap
3. Short text?       → the default (§2)                                                         §7
                       typo-tolerant → also term <% col, ordered by word distance                §8
4. Long text?        submitted search   → full-text                                             §9
                     search-as-you-type → full-text cannot match partial words: search a short
                                          field with trigram instead, or accept whole words
5. Meaning, not      → pgvector, only if an embedding pipeline already exists;
   words?              combine with full-text by Reciprocal Rank Fusion                        §10, §11
```

- **One box over several fields:** `OR` the per-field predicates — each field keeps its own index.
- **One box for identifiers and text:** classify the term first, then search only the matching
  fields (§11.1).
- **Today's row count never decides.** A growing table that is small now gets its index from the
  start — on an empty table it costs nothing, and later it needs a concurrent build (§12.3).

## 5. Prepare the table

**Do — in the migration that adds the table or column:**

1. **One index per searched field**, of the type its technique needs (§3).
2. **A B-tree on each filter that narrows the list to a small share of rows** — a foreign key, an
   owner, a date range. Foreign keys first: PostgreSQL never indexes the referencing column for
   you. Keep them single-column — the planner combines them with the search index (bitmap `AND`).
3. **Normalise loosely typed identifiers into one stored form.** A phone becomes a digits-only
   generated column (`GENERATED ALWAYS AS (…) STORED`), which never drifts from its source; a code
   is matched through an index on `lower(code)`.
4. **A derived search target is a stored generated column** — a digits-only phone, a `tsvector` —
   never computed inside the query, where it cannot use an index.
5. **`ANALYZE` the table after a bulk load or backfill.** The planner chooses indexes from
   statistics; autovacuum keeps them current otherwise.

**Do not — until `EXPLAIN ANALYZE` on real data asks for it:**

- **An index on a low-selectivity column** (a status, a boolean). A value matching more than a few
  percent of rows is read by a sequential scan anyway.
- **A multicolumn index.** The docs say to use them sparingly; when one is needed, the equality
  filter leads.
- **A partial index** (`WHERE is_deleted = false`). It helps only when the excluded rows are a large
  share, and only queries that state the same condition literally use it — a bound parameter never
  does.
- **GiST, `siglen`, `fastupdate` tuning, partitioning.**

**Check after real traffic:** an index with `idx_scan = 0` in `pg_stat_user_indexes` (or an old
`last_idx_scan`) is never used. Drop it — it costs every write.

## 6. Rules for every search

1. **Search and filters in one `WHERE`, in one query.** Filtering in Python makes the total wrong.
2. **`escape_like()` on every `LIKE` / `ILIKE` term.** Backslash is PostgreSQL's default escape.
3. **Never format user input into SQL or tsquery text** — bind it.
4. **The query's expression is the index's expression.** An index on `lower(code)` serves only
   `lower(code) LIKE …`.
5. **`ORDER BY` ends with `id`**, or pages repeat and skip rows.
6. **Bound the term** with `max_length`.
7. **Prove the index is usable, then let the planner choose.** On a test table, run
   `SET enable_seqscan = off` and `EXPLAIN` — the index name must appear; if it does not, the query
   and index expressions differ (rule 4). Without that setting the planner may still pick a
   sequential scan when it estimates one is cheaper — on 60 000 short rows it did for `ILIKE`. That
   is its call to make; judge speed with `EXPLAIN ANALYZE` on production-sized data.
8. **After `pg_upgrade` to 18 or later** on an ICU or builtin collation provider, reindex the
   full-text and trigram indexes.

## 7. Build the default

The list-endpoint plumbing is `docs/PROJECT_CONVENTIONS.md` §10. The default search adds three
pieces.

### 7.1 Model — the indexes

Declare every search index on the model, so autogenerate and `alembic check` see it.

```python
class Customer(Base):
    __tablename__ = "customers"
    __table_args__ = (
        # The default: one GIN trigram index per searched short-text field
        Index("ix_customers_name_trgm", "name",
              postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"}),
        Index("ix_customers_email_trgm", "email",
              postgresql_using="gin", postgresql_ops={"email": "gin_trgm_ops"}),
    )
```

Autogenerate renders these indexes, and every one in §12.1, as written here, and `alembic check`
then reports nothing. It never renders the extension: the first trigram index's migration adds
`op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")` before it, and `downgrade` leaves the
extension, since other tables may use it.

### 7.2 `list_params.py`

```python
search: str | None = Field(None, min_length=3, max_length=100)     # min_length: trigram, §8
sort_by: Literal["relevance", "created_at", "name"] | None = None  # "relevance" only if ranked
```

### 7.3 CRUD — the predicate goes in the same `filters` list

```python
if search:
    pattern = f"%{escape_like(search.strip())}%"
    filters.append(or_(Customer.name.ilike(pattern), Customer.email.ilike(pattern)))
```

The route and service stay unchanged: the route binds `Annotated[XListParams, Query()]`, the
service passes `params` through.

## 8. Trigram (`pg_trgm`)

- **Index the plain column:** `GIN (name gin_trgm_ops)`. It serves `LIKE`, `ILIKE`, `~`, `~*` and
  the similarity operators. Trigrams are case-insensitive, so `lower()` adds nothing for `ILIKE`.
- **Under three characters, the index cannot help.** A pattern with no extractable trigram becomes
  a full-index scan — hence `min_length=3` on a growing table.
- **Only the operators use the index.** `similarity(a, b) > 0.3` in a `WHERE` reads every row; write
  `a % b` or `term <% col`.
- **`<%` is the search-box operator.** `%` compares whole strings (`similarity`, threshold 0.3), so a
  short term against a long value scores low. `<%` compares the term with the best-matching stretch
  of the value (`word_similarity`, threshold 0.6). `<<%` also aligns to word boundaries
  (`strict_word_similarity`, threshold 0.5).
- **Thresholds are settings, not predicates:** `SET LOCAL pg_trgm.word_similarity_threshold = 0.5`
  inside the transaction.
- **What trigram typo tolerance catches**, measured with `word_similarity` at the default 0.6: one
  missing, extra or wrong letter in a longer word (`jonathon` → "Jonathan Smith" 0.67, `alexandr`
  → "Alexander Grant" 0.78). It misses swapped letters in a short word (`jhon` → "John Smith"
  0.20, `smiht` 0.50) and sound-alikes (`smyth` 0.33). Lowering the threshold to 0.5 catches more
  and returns more noise. Sound-alike names need `fuzzystrmatch` (`dmetaphone`) — beyond trigram.
- **Order typo-tolerant results by word distance:** `term <<-> col` (`1 − word_similarity`), lowest
  first.
- **Punctuation is ignored** when trigrams are extracted — `foo|bar` indexes like `foo bar`. That is
  why phones get their own digits-only column (§5).
- **GIN by default.** GiST only for index-ordered nearest-match (`ORDER BY col <-> term LIMIT n` —
  GIN cannot order by distance), or when write cost is the measured bottleneck.
- **Enable once per database:** `CREATE EXTENSION IF NOT EXISTS pg_trgm`. It is a trusted
  extension — a user with `CREATE` on the database installs it without superuser.

## 9. Full-text

- **Store the vector:** a generated column `GENERATED ALWAYS AS (to_tsvector('simple', …)) STORED`
  with a GIN index. It is faster than an expression index, which must recompute `to_tsvector` to
  recheck matches.
- **Always pass the configuration** — `to_tsvector('simple', …)`. The one-argument form depends on
  `default_text_search_config`, so it cannot be indexed or generated.
- **`coalesce()` every column** in the vector. One `NULL` makes the whole vector `NULL`.
- **Configuration:** `'simple'` — no stemming, no stop words — for names, codes and mixed-language
  data. `'english'` for English prose, where "running" should find "run". **The query uses the
  vector's configuration.**
- **Parser:** `websearch_to_tsquery` for every user-typed term. It never raises; it reads
  `"a phrase"`, `OR` and `-word`, and ignores other punctuation — so it has no prefix match.
  `to_tsquery` raises on bad syntax: never pass it user input. SQLAlchemy's `col.match()` emits
  `plainto_tsquery`; use `col.bool_op("@@")(func.websearch_to_tsquery(cfg, term))`.
- **Rank with `ts_rank_cd`** (cover density — near terms rank higher). It needs positions: on a
  stripped `tsvector` it returns 0. Normalisation `32` scales the rank into 0–1.
- **Weights only when one field outranks another:** `setweight(…, 'A')` for the title, `'B'`–`'D'`
  for the rest (default weights 1.0 / 0.4 / 0.2 / 0.1). GIN stores no weights, so a weighted query
  rechecks rows.
- **Ranking reads every matching row** before `LIMIT`. A broad term on a large table is slow —
  keep the endpoint's filters in the same `WHERE`.
- **`ts_headline` (snippets)** reads the original text, so it is slow: run it on the returned page
  only. Its output is not HTML-safe.

## 10. Vector (`pgvector`)

Only when an embedding pipeline already exists — the embeddings are the expensive part.

- **HNSW by default:** better speed–recall than IVFFlat, and buildable on an empty table. IVFFlat
  builds faster and uses less memory, but must be created after the table has data.
- **Filters apply after the index scan.** With the default `hnsw.ef_search` of 40 and a filter that
  keeps 10 % of rows, about 4 rows come back. Use iterative scans (pgvector ≥ 0.8:
  `SET LOCAL hnsw.iterative_scan = relaxed_order`), a partial index, or partitioning.
- **Operator:** `<=>` cosine distance; `<#>` (negative inner product) when embeddings are normalised
  to length 1.
- **Index limits:** `vector` up to 2,000 dimensions, `halfvec` up to 4,000.

## 11. Mixed input and combined ranking

### 11.1 Classify the term

```python
def classify(term: str) -> str:
    t = term.strip()
    if re.fullmatch(r"[A-Za-z]{1,4}-?\d+", t):
        return "identifier"                      # C0042, INV-001
    if re.fullmatch(r"[\d\s()+.-]+", t) and len(re.sub(r"\D", "", t)) >= 6:
        return "phone"
    return "text"
```

Fit the patterns to the module's real formats; the classifier belongs in CRUD.

### 11.2 Combine ranks — never add raw scores

Scores from different techniques are on different scales, so adding them lets one dominate.

- **Two techniques in one query** (full-text with a trigram fallback): order by tiers —
  `ORDER BY (vector @@ q) DESC, ts_rank_cd(vector, q) DESC, term <<-> name, id DESC`.
  Full-text hits come first, typo-only hits after.
- **Two separate searches** (full-text and vector): Reciprocal Rank Fusion — each row scores
  `Σ 1 / (k + rank)` across the lists, with `k = 60`, the constant from the original RRF paper.
  Run each search as a CTE with `row_number()`, then `FULL OUTER JOIN` on id.

## 12. Build the steps beyond the default

Each piece below is needed only when §4 chose its technique. It extends §7.

### 12.1 Model — generated columns and more indexes

```python
class Customer(Base):
    __table_args__ = (
        ...,  # the default indexes, §7.1
        # Phone search: trigram on the digits-only generated column
        Index("ix_customers_phone_digits_trgm", "phone_digits",
              postgresql_using="gin", postgresql_ops={"phone_digits": "gin_trgm_ops"}),
        # Full-text
        Index("ix_customers_search_vector", "search_vector", postgresql_using="gin"),
    )
    phone_digits: Mapped[str | None] = mapped_column(
        Text, Computed("regexp_replace(phone, '[^0-9]', '', 'g')", persisted=True)
    )
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('simple', coalesce(name, '') || ' ' || coalesce(notes, ''))",
                 persisted=True),
        deferred=True,  # never loaded by a list query
    )


# Code prefix: an expression index, declared after the class where the column exists
Index("ix_customers_code_prefix", func.lower(Customer.code).label("code_lower"),
      postgresql_ops={"code_lower": "text_pattern_ops"})
```

### 12.2 CRUD — typo tolerance, prefixes, full-text, relevance

```python
term = search.strip()
rank = None  # set by the ranked option you keep

# Each block below is one option: keep only the ones §4 chose.

# Typo-tolerant name — same GIN index; word distance, lower is better
filters.append(or_(Customer.name.ilike(pattern), literal(term).bool_op("<%")(Customer.name)))
rank = literal(term).op("<<->", return_type=Float)(Customer.name)

# Code prefix — B-tree on lower(code) text_pattern_ops
filters.append(func.lower(Customer.code).like(f"{escape_like(term.lower())}%"))

# Full-text — GIN on search_vector; higher is better, so sort it desc()
q = func.websearch_to_tsquery("simple", term)
filters.append(Customer.search_vector.bool_op("@@")(q))
rank = func.ts_rank_cd(Customer.search_vector, q)
```

When the search is ranked, relevance is the default sort. Choosing a sort is query building, so
it lives here, not in the route:

```python
if sort_by is None:
    sort_by = "relevance" if rank is not None else "created_at"
if sort_by == "relevance" and rank is not None:
    order_clauses = [rank.asc(), Customer.id.desc()]      # .desc() for ts_rank_cd
else:
    col = _SORT_COL_MAP.get(sort_by, Customer.created_at)
    order_clauses = [col.asc() if sort_order == "asc" else col.desc(), Customer.id.desc()]
```

### 12.3 Index builds on a live table

A plain `CREATE INDEX` blocks writes for the whole build. On a large table already in production,
build it `CONCURRENTLY` — which cannot run in a transaction:

```python
with op.get_context().autocommit_block():   # commits everything before it
    op.create_index(..., postgresql_concurrently=True)
```

A failed concurrent build leaves an `INVALID` index that still slows writes: drop it and retry.
GIN builds are sensitive to `maintenance_work_mem`.

## Sources

- PostgreSQL 18 docs: [pg_trgm](https://www.postgresql.org/docs/current/pgtrgm.html) ·
  [text search indexes](https://www.postgresql.org/docs/current/textsearch-indexes.html) ·
  [text search tables](https://www.postgresql.org/docs/current/textsearch-tables.html) ·
  [parsing and ranking](https://www.postgresql.org/docs/current/textsearch-controls.html) ·
  [indexes](https://www.postgresql.org/docs/current/indexes.html) ·
  [index types](https://www.postgresql.org/docs/current/indexes-types.html) ·
  [multicolumn](https://www.postgresql.org/docs/current/indexes-multicolumn.html) ·
  [partial](https://www.postgresql.org/docs/current/indexes-partial.html) ·
  [operator classes](https://www.postgresql.org/docs/current/indexes-opclass.html) ·
  [examining index usage](https://www.postgresql.org/docs/current/indexes-examine.html) ·
  [foreign keys](https://www.postgresql.org/docs/current/ddl-constraints.html) ·
  [GIN tips](https://www.postgresql.org/docs/current/gin.html) ·
  [CREATE INDEX](https://www.postgresql.org/docs/current/sql-createindex.html) ·
  [LIKE](https://www.postgresql.org/docs/current/functions-matching.html) ·
  [index statistics](https://www.postgresql.org/docs/current/monitoring-stats.html) ·
  [release 18](https://www.postgresql.org/docs/18/release-18.html)
- [pgvector README](https://github.com/pgvector/pgvector) (0.8.7) — HNSW, filtering, hybrid search
- [SQLAlchemy 2.0 PostgreSQL dialect](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html) —
  `postgresql_ops`, `websearch_to_tsquery`, `match()`
- [Alembic `autocommit_block`](https://alembic.sqlalchemy.org/en/latest/api/runtime.html)
- [Supabase hybrid search](https://supabase.com/docs/guides/ai/hybrid-search) — Reciprocal Rank Fusion
