# PostgreSQL Search Strategy — Decision Guide

> Authoritative reference for choosing search techniques in enterprise endpoints.  
> All strategies assume PostgreSQL ≥ 14, async SQLAlchemy 2.0, FastAPI.

- This is version 0.1 - Iteratively improving based on real-world application and feedback.

---

## Table of Contents

1. [The Four Techniques — Quick Comparison](#1-the-four-techniques--quick-comparison)
2. [Decision Tree — Which Technique to Use](#2-decision-tree--which-technique-to-use)
3. [Endpoint Archetype Map](#3-endpoint-archetype-map)
4. [Full-Text Search — The Three Sub-Decisions](#4-full-text-search--the-three-sub-decisions)
5. [Filter + Search Sync (Critical Rule)](#5-filter--search-sync-critical-rule)
6. [Indexing Strategy](#6-indexing-strategy)
7. [Implementation Patterns](#7-implementation-patterns)
8. [When to Apply Each Technique](#8-when-to-apply-each-technique)
9. [Migration Checklist](#9-migration-checklist)
10. [Anti-Patterns to Avoid](#10-anti-patterns-to-avoid)

---

## 1. The Four Techniques — Quick Comparison

PostgreSQL exposes four distinct search mechanisms. Each is optimal for a
specific class of query. **Do not reach for a heavier technique when a lighter
one is sufficient.**

| # | Technique | PG Feature | GIN/GiST? | Handles typos? | Ranks results? | Setup cost |
|---|---|---|---|---|---|---|
| 1 | **Prefix / substring match** | `iLIKE '%term%'` | Via pg_trgm | ❌ | ❌ | Lowest |
| 2 | **Trigram similarity** | `pg_trgm` `%`, `similarity()` | GIN / GiST | ✅ | Similarity score | Low |
| 3 | **Full-text search (FTS)** | `tsvector` / `tsquery` | GIN | ❌ (stems words) | `ts_rank_cd` | Medium |
| 4 | **Vector / semantic search** | `pgvector` | HNSW / IVFFlat | ✅ (conceptual) | Cosine distance | High (LLM needed) |

### When each is correct

| Technique | Use when |
|---|---|
| **iLIKE** | Exact/near-exact values — codes, emails, short names. Clean data, no typos expected. |
| **Trigram (pg_trgm)** | Users type partial strings or make minor typos. Names, short labels, addresses. |
| **FTS** | Long-form content (notes, descriptions, comments). Ranked relevance required. |
| **pgvector** | Semantic/intent search where keywords won't match. Requires an embedding pipeline. |

---

## 2. Decision Tree — Which Technique to Use

Start from the top. Stop at the first match.

```
Is the searched value a structured identifier?
(phone number, patient ID, SKU, code, email)
    ↓ YES
    → Use iLIKE prefix + B-tree index
      (digits-only: normalize the column; IDs: exact iLIKE prefix)

Is the table small (< 5 000 rows) and the search box is simple?
    ↓ YES
    → Plain iLIKE '%term%' — no index needed, seq scan is fast enough

Is the text short (< ~10 words: names, short titles, labels)?
Does the user expect fuzzy / typo-tolerant matching?
    ↓ YES
    → Trigram (pg_trgm GIN) + iLIKE (pg_trgm GIN also accelerates iLIKE)

Is the text long-form content (descriptions, notes, comments)?
Must results be ranked by relevance?
    ↓ YES
    → Full-text search (GIN on stored tsvector column)
      + trigram fallback for typo tolerance (hybrid)

Does the search need to understand meaning / intent
beyond keywords? (clinical summaries, semantic product search)
    ↓ YES
    → Vector search (pgvector) — only if embedding pipeline exists
```

### Condensed recommendation for 95 % of endpoints

| Search box type | Recommended approach |
|---|---|
| Name / short label field | **Trigram GIN** — `name.ilike('%term%')` accelerated by `gin_trgm_ops` |
| Code / ID / phone | **iLIKE prefix** on normalized column + B-tree (or trigram GIN for substring) |
| Multi-field (name + email + phone) | **Trigram GIN** on each column |
| Long text / description / notes | **FTS** — stored `tsvector` + GIN index |
| Mixed (short name + long description, ranked) | **Hybrid** — FTS for ranking + trigram fallback for typos |
| Semantic / intent search | **pgvector** — only when an embedding pipeline exists |

---

## 3. Endpoint Archetype Map

The following archetypes cover the endpoints found in enterprise management
software. Pick the matching row and follow the prescribed approach.

### 3.1 Lookup / admin list (employees, products, users)

**Typical search:** "Find employee by name or code"  
**Data:** Short strings, clean, rarely changes.  
**Approach:** `iLIKE '%term%'` on `name` + `code` columns, accelerated by
`GIN (col gin_trgm_ops)`.  
**Rank needed?** No — alphabetical or created_at sort is sufficient.

```sql
-- Migration
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE INDEX ix_employees_name_trgm  ON employees USING GIN (lower(name) gin_trgm_ops);
CREATE INDEX ix_employees_code_trgm  ON employees USING GIN (lower(employee_code) gin_trgm_ops);
```

```python
# CRUD
from app.core.utils.text import escape_like

term = f"%{escape_like(search.lower())}%"
filters.append(or_(
    func.lower(Employee.name).ilike(term),
    func.lower(Employee.employee_code).ilike(term),
))
```

### 3.2 CRM entity search (leads, customers)

**Typical search:** "Find by name, email, OR phone number"  
**Data:** Short strings. Phone numbers need normalization.  
**Approach:** Trigram on name/email + normalized phone column for digits.

```sql
-- Migration
ALTER TABLE crm_leads
    ADD COLUMN mobile_normalized TEXT GENERATED ALWAYS AS (
        regexp_replace(mobile, '[^0-9]', '', 'g')
    ) STORED;

CREATE INDEX ix_leads_mobile_norm_trgm ON crm_leads
    USING GIN (mobile_normalized gin_trgm_ops);
CREATE INDEX ix_leads_name_trgm ON crm_leads
    USING GIN (lower(first_name || ' ' || last_name) gin_trgm_ops);
CREATE INDEX ix_leads_email_trgm ON crm_leads
    USING GIN (lower(email) gin_trgm_ops);
```

```python
digits = re.sub(r'\D', '', search)
name_col = func.lower(func.concat(Lead.first_name, ' ', Lead.last_name))

filters.append(or_(
    name_col.ilike(f"%{escape_like(search.lower())}%"),
    func.lower(Lead.email).ilike(f"%{escape_like(search.lower())}%"),
    column('mobile_normalized').ilike(f"%{digits}%") if digits else literal(False),
))
```

### 3.3 Primary entity with ranked search (leads v2, patients, documents)

**Typical search:** "Find by name / keyword across multiple fields, ranked"  
**Data:** Short names + optional long notes/description.  
**Approach:** Hybrid — FTS on `search_vector` (primary, ranked) + trigram
fallback (tolerates misspellings).

> See [§4](#4-full-text-search--the-three-sub-decisions) for the three FTS
> sub-decisions: configuration (`'simple'` for names, `'english'` for prose),
> query parser (`websearch_to_tsquery` for user input), and ranking
> (`ts_rank_cd` with optional `setweight` for multi-field documents).

```sql
-- Migration
ALTER TABLE crm_leads
    ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('simple',
            coalesce(first_name, '') || ' ' ||
            coalesce(last_name,  '') || ' ' ||
            coalesce(email,      '') || ' ' ||
            coalesce(mobile,     '')
        )
    ) STORED;

CREATE INDEX ix_leads_search_vector ON crm_leads USING GIN (search_vector);
```

```python
ts_query = func.websearch_to_tsquery('simple', search)
name_col  = func.lower(func.concat(Lead.first_name, ' ', Lead.last_name))

filters.append(or_(
    column('search_vector').op('@@')(ts_query),
    name_col.op('%')(search.lower()),           # trigram fallback
))

rank_expr = (
    func.coalesce(func.ts_rank_cd(column('search_vector'), ts_query), 0.0)
    + func.similarity(name_col, search.lower())
)
# Use rank_expr.desc() as the first order clause when sort_by == 'relevance'
```

### 3.4 Structured identifier lookup (SKU, invoice number, contact ID)

**Typical search:** "Find by exact or partial code"  
**Data:** Alphanumeric codes with known structure.  
**Approach:** `iLIKE 'CODE%'` (prefix) covered by a GIN trigram index.
For exact lookup (`= 'CODE-001'`) use a B-tree index instead.

```sql
CREATE INDEX ix_products_sku_trgm   ON products USING GIN (lower(sku) gin_trgm_ops);
CREATE INDEX ix_invoices_number_bt  ON invoices USING BTREE (invoice_number);
```

```python
# Prefix search — index on sku covers this
filters.append(Product.sku.ilike(f"{escape_like(search)}%"))

# OR exact lookup — btree covers this
filters.append(Invoice.invoice_number == search.upper())
```

### 3.5 Long-text / notes / content search

**Typical search:** Full sentence search across clinical notes, activity logs.  
**Data:** Long paragraphs. Keyword ranking important.  
**Approach:** FTS only. No trigram (too large, noisy).

```sql
ALTER TABLE clinical_notes
    ADD COLUMN search_vector tsvector GENERATED ALWAYS AS (
        to_tsvector('english', coalesce(body, ''))
    ) STORED;

CREATE INDEX ix_clinical_notes_sv ON clinical_notes USING GIN (search_vector);
```

```python
ts_query = func.websearch_to_tsquery('english', search)
filters.append(column('search_vector').op('@@')(ts_query))
order_clauses = [func.ts_rank_cd(column('search_vector'), ts_query).desc(), model.id.desc()]
```

---

## 4. Full-Text Search — The Three Sub-Decisions

Once the decision tree (§2) tells you to use FTS, three sub-decisions remain.
They are independent of each other and each has a **safe default** that
covers the majority of enterprise endpoints. Override the default only with
a concrete reason.

### 4.1 Configuration choice — `'simple'` vs `'english'` (vs others)

A text-search *configuration* drives parsing, stemming, and stop-word removal.
The wrong choice silently breaks recall.

| Configuration | Behaviour | Use when |
|---|---|---|
| `'simple'` | No stemming, no stop-word removal. Lowercases tokens only. | **Default for proper nouns, names, identifiers, codes, mixed-language data, multi-tenant SaaS.** Anything where a token like "Rajesh" or "acme" must match itself exactly. |
| `'english'` | Snowball stemmer + English stop-word list. "running", "runs", "ran" → `run`; drops `the`, `is`, `on`, etc. | Long-form English content: clinical notes, product descriptions, articles, comments. |
| `'pg_catalog.<lang>'` | Same as `'english'` but per language (`spanish`, `french`, `russian`, ...). | Single-language content where stemming meaningfully improves recall. |

> **Rule.** Names, codes, identifiers, multi-language data → `'simple'` (no stemming, no stop-word removal — every token preserved verbatim).  
> Long English prose → `'english'` (Snowball stemmer + stop-word removal improves recall for natural-language queries).  
> When in doubt → `'simple'`.

### 4.2 Query parser choice — `websearch_to_tsquery` vs alternatives

PostgreSQL provides four functions to convert user input into a `tsquery`.
Only one is appropriate for raw user input from a public endpoint.

| Function | Recognises operators? | Raises on bad syntax? | Use when |
|---|---|---|---|
| `websearch_to_tsquery` | Quotes for phrases, `OR`, leading `-` for NOT | **Never** | **Default for every user-facing search box.** Safe with raw input. |
| `plainto_tsquery` | None — every word becomes AND | Never | Programmatic queries where the caller, not the user, supplies plain words. |
| `phraseto_tsquery` | None — every word becomes FOLLOWED-BY (`<->`) | Never | Exact-phrase lookups (e.g. "find this exact sentence in audit logs"). |
| `to_tsquery` | Full operator syntax (`&`, `|`, `!`, `<->`, `:*`, weights) | **Yes** | Internal admin tools, CLI utilities. **Never** with raw HTTP input. |

> **Rule.** All `/list` endpoints use `websearch_to_tsquery(config, search)`.
> It is parameterised, injection-safe, and forgiving — three properties any
> public endpoint requires.

### 4.3 Ranking choice — `ts_rank_cd` vs `ts_rank` (and weights)

| Function | Behaviour | Use |
|---|---|---|
| `ts_rank` | Frequency-based — ignores term proximity. | Single-field, unweighted indexes. |
| `ts_rank_cd` | Cover density — clustered matches rank higher. | **Default** for all enterprise search endpoints. |

**`setweight()` for multi-field documents.** When the `tsvector` covers several columns, assign weights so ranking favours matches in important fields (title > body):

```sql
ALTER TABLE articles ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        setweight(to_tsvector('english', coalesce(title, '')),    'A') ||
        setweight(to_tsvector('english', coalesce(summary, '')),  'B') ||
        setweight(to_tsvector('english', coalesce(body, '')),     'C')
    ) STORED;
```

Default weights are `{D=0.1, C=0.2, B=0.4, A=1.0}`. With the schema above, a
match in `title` ranks 10× a match in `body` — the standard convention for
any content where the title is the primary signal.

> **Rule.** If your `tsvector` is built from a single column or columns of
> equal importance, skip `setweight`. Use it only when one field clearly
> outranks another (title > body, name > description).

### 4.4 Optional: highlighting with `ts_headline`

For list responses that need a snippet of the matched text (search-result
excerpt with `<b>highlighted</b>` terms), use `ts_headline`. **Caveat from
PostgreSQL docs:** `ts_headline` operates on the original document, not the
`tsvector`, and is therefore expensive. Apply it **after** pagination — not
inside the count window — and only on the page being returned.

```python
headline_expr = func.ts_headline(
    'english',
    Article.body,
    func.websearch_to_tsquery('english', search),
    'MaxFragments=2, MaxWords=20, MinWords=5',
)
# Add to SELECT list, not to the search predicate.
```

---

## 5. Filter + Search Sync (Critical Rule)

**Search and filters are always AND-combined in a single WHERE clause.**  
Never run a full-table search and then post-filter in Python.

### Why this matters

```
# ❌ WRONG — search runs on full table, Python filters after
all_results = await session.execute(select(Lead))
matching = [r for r in all_results if search in r.name and r.status == 'active']

# ❌ WRONG — two queries, search on unfiltered set
count_q  = select(func.count()).where(search_condition)
items_q  = select(Lead).where(filters_condition)

# ✅ CORRECT — all predicates in one WHERE, single query
base_query = select(Lead).where(
    Lead.is_deleted.is_(False),
    Lead.status == 'active',         # filter
    Lead.department == 'cardiology', # filter
    search_condition,                # search — AND-combined
)
items, total = await paginated_select(session, base_query, ...)
```

The PostgreSQL planner can then choose:
- A GIN bitmap scan for the search predicate
- A B-tree bitmap scan for `status` and `department`
- Bitmap AND of all three results

This is far more efficient than running search on an unfiltered set.

### Rule summary

| Rule | Reason |
|---|---|
| All filters + search in one `WHERE` | Single table scan; planner can combine indexes |
| Never filter in Python after fetching | Pagination totals become incorrect |
| `escape_like()` on every `iLIKE` parameter | Prevents `%` / `_` injection |
| `is_(False)` / `is_(None)` for nullable booleans | Avoids SQLAlchemy ORM ambiguity |
| Never `search_vector @@ tsquery` outside WHERE | Window function pagination requires all predicates before OFFSET/LIMIT |

---

## 6. Indexing Strategy

### 6.1 Index type selection

| Data access pattern | Index type | Notes |
|---|---|---|
| Exact equality / range (dates, FKs, status) | **B-tree** | Default — always use for `=`, `<`, `>`, `BETWEEN` |
| `iLIKE '%term%'` on text | **GIN** `gin_trgm_ops` | Also accelerates `~*` regex |
| Trigram similarity (`%` operator) | **GIN** `gin_trgm_ops` | GiST if nearest-neighbour `ORDER BY dist` needed |
| FTS match (`@@`) | **GIN** on `tsvector` column | Always GIN, never GiST for FTS |
| Vector distance (`<->`) | **HNSW** or **IVFFlat** | pgvector extension |
| Frequently filtered subset | **Partial B-tree** `WHERE is_deleted = false` | Smaller index, faster scans |

### 6.2 GIN vs GiST — for both trigram and FTS

Per PostgreSQL §12.9 (*Preferred Index Types for Text Search*) and the
`pg_trgm` documentation, the GIN-vs-GiST trade-off applies identically to
trigram indexes and `tsvector` indexes. The trade-offs:

| Criterion | GIN | GiST |
|---|---|---|
| Read (lookup) speed | Faster | Slower (lossy — needs heap recheck) |
| Write (insert/update) speed | Slower | Faster |
| Index size | Larger | Smaller (fixed-length signatures) |
| Nearest-neighbour sort (`ORDER BY similarity()`) | ❌ Not supported | ✅ Supported |
| Stores weight labels (FTS) | ❌ No (recheck needed for weighted queries) | ✅ Yes |
| **Recommended default** | ✅ Read-heavy: catalogs, CRM, articles, leads | Write-heavy: audit logs, event streams, IoT data |

**Rule:** Default to **GIN**. Switch to **GiST** only when `ORDER BY similarity()` is required in SQL, or when write throughput on the indexed table is the measured bottleneck.

**Always use `CREATE INDEX CONCURRENTLY` in production** — plain `CREATE INDEX` takes an `ACCESS EXCLUSIVE` lock and blocks all writes for the build duration. For very large GIN builds, raise `maintenance_work_mem` temporarily:

```sql
SET maintenance_work_mem = '1GB';
CREATE INDEX CONCURRENTLY ix_leads_search_vector ON crm_leads USING GIN (search_vector);
RESET maintenance_work_mem;
```

### 6.3 Standard index set for a new module

```sql
-- 1. Soft-delete partial index on the primary table
CREATE INDEX ix_{table}_active ON {table} (created_at DESC)
    WHERE is_deleted = false;

-- 2. Foreign key indexes (PostgreSQL does NOT auto-create these)
CREATE INDEX ix_{table}_{fk_col} ON {table} ({fk_col});
-- repeat for every FK column

-- 3. Search — name/title (GIN trigram)
CREATE INDEX ix_{table}_name_trgm ON {table}
    USING GIN (lower(name) gin_trgm_ops);

-- 4. Search — phone / mobile (GIN trigram on normalized column)
CREATE INDEX ix_{table}_mobile_norm_trgm ON {table}
    USING GIN (mobile_normalized gin_trgm_ops);

-- 5. Full-text search vector (if needed)
CREATE INDEX ix_{table}_search_vector ON {table}
    USING GIN (search_vector);

-- 6. Common filter columns (B-tree)
CREATE INDEX ix_{table}_status       ON {table} (status)   WHERE is_deleted = false;
CREATE INDEX ix_{table}_created_at   ON {table} (created_at DESC);
CREATE INDEX ix_{table}_assigned_to  ON {table} (assigned_to) WHERE is_deleted = false;
```

### 6.4 Composite indexes — when and how

Use composite B-tree indexes for columns that are **always queried together**:

```sql
-- Correct: status + created_at queried together as a range + filter
CREATE INDEX ix_leads_status_created ON crm_leads (status, created_at DESC)
    WHERE is_deleted = false;

-- Wrong: don't composite-index rarely co-occurring columns
-- The planner cannot use partial key lookups on arbitrary column order
```

**Rule:** Left-most column in the composite index should be the highest-
selectivity equality predicate (usually an enum like `status`).

### 6.5 Generated columns for search targets

Prefer **stored generated columns** over application-level computation for
search targets. They are always consistent with the source column and never
stale:

```sql
-- Phone normalization
ALTER TABLE contacts ADD COLUMN mobile_normalized TEXT
    GENERATED ALWAYS AS (regexp_replace(mobile, '[^0-9]', '', 'g')) STORED;

-- Full-text vector
ALTER TABLE leads ADD COLUMN search_vector tsvector
    GENERATED ALWAYS AS (
        to_tsvector('simple',
            coalesce(first_name,'') || ' ' || coalesce(last_name,'') || ' ' ||
            coalesce(email,'')      || ' ' || coalesce(mobile,'')
        )
    ) STORED;
```

**Important:** Generated column indices are automatically maintained by
PostgreSQL on every INSERT and UPDATE — no trigger or application logic needed.

---

## 7. Implementation Patterns

### 7.1 Safe input handling

```python
from app.core.utils.text import escape_like

# Always escape user input before iLIKE
term = f"%{escape_like(search)}%"
filters.append(Column.ilike(term))

# For FTS — websearch_to_tsquery is injection-safe
# (uses parameterised query, not string interpolation)
ts_q = func.websearch_to_tsquery('simple', search)  # safe
filters.append(column('search_vector').op('@@')(ts_q))
```

### 7.2 Input routing — detect token type before routing to technique

```python
import re

def _classify_search_input(term: str) -> str:
    """Classify user input to route to the optimal search path."""
    clean = term.strip()
    if re.fullmatch(r'[A-Z]{1,3}\d+', clean.upper()):
        return 'identifier'          # C0042, INV-001, SKU123
    if re.fullmatch(r'[\d\s\-+().]+', clean) and len(re.sub(r'\D', '', clean)) >= 6:
        return 'phone'               # 9876543210, +91-98765-43210
    return 'text'                    # everything else
```

### 7.3 Hybrid search pattern (canonical) — *use only for primary, mixed-input search boxes*

```python
search_type = _classify_search_input(search)

if search_type == 'identifier':
    filters.append(Model.code.ilike(f"{escape_like(search.upper())}%"))

elif search_type == 'phone':
    digits = re.sub(r'\D', '', search)
    filters.append(column('mobile_normalized').ilike(f"%{digits}%"))

else:
    ts_q      = func.websearch_to_tsquery('simple', search)
    name_col  = func.lower(func.concat(Model.first_name, ' ', Model.last_name))
    rank_expr = (
        func.coalesce(func.ts_rank_cd(column('search_vector'), ts_q), 0.0)
        + func.similarity(name_col, search.lower())
    )
    filters.append(or_(
        column('search_vector').op('@@')(ts_q),    # FTS (GIN)
        name_col.op('%')(search.lower()),           # trigram fallback (GIN)
    ))
```

### 7.4 Relevance-ranked response

```python
# Route layer: derive sort_by from context
effective_sort_by = params.sort_by.value if params.sort_by else (
    'relevance' if params.search else 'created_at'
)

# CRUD layer: use rank_expr as primary ORDER BY
if effective_sort_by == 'relevance' and rank_expr is not None:
    order_clauses = [rank_expr.desc(), Model.created_at.desc(), Model.id.desc()]
else:
    sort_col = sort_col_map.get(effective_sort_by, Model.created_at)
    direction = sort_col.asc() if sort_order == 'asc' else sort_col.desc()
    order_clauses = [direction, Model.id.desc()]   # tiebreaker always last
```

---

## 8. When to Apply Each Technique

Use this table to match the search requirement to the correct infrastructure level.

| Requirement | Correct approach |
|---|---|
| Search by name/code on a small-to-medium table | `iLIKE '%term%'` — no index needed for small tables; add GIN trigram index as the table grows |
| Typo-tolerant name/label search | `pg_trgm` GIN index + `iLIKE` |
| Phone / digits substring lookup | Normalized column (`mobile_normalized`) + GIN trigram |
| Multi-field search (name + email + phone) | GIN trigram on each column individually |
| Long-form text with ranked results | Stored `tsvector` + GIN index + `ts_rank_cd` |
| Mixed input (name OR phone OR code in one box) | Hybrid classifier — FTS + trigram + identifier branch |
| Weighted field ranking (title ranks above body) | `setweight()` in `tsvector` generation |
| Search result excerpts / highlighted snippets | `ts_headline()` — applied after pagination on the returned page only |
| Semantic / intent search | `pgvector` — requires an embedding model at insert time |
| Write-heavy table with trigram/FTS index | GiST index over GIN to reduce write overhead |

---

## 9. Migration Checklist

When adding a new entity that has a list endpoint with search:

```
[ ] 1. Add pg_trgm extension (once per DB):
        CREATE EXTENSION IF NOT EXISTS pg_trgm;

[ ] 2. Add FTS extension dependencies if using FTS:
        (no extension needed — tsvector/tsquery are built-in)

[ ] 3. Add generated columns (mobile_normalized, search_vector) to model.
        Use GENERATED ALWAYS AS (...) STORED — not triggers.

[ ] 4. Add B-tree index on FK columns (PostgreSQL does not auto-index FKs).

[ ] 5. Add GIN trigram index on every text column used in iLIKE search.

[ ] 6. Add GIN index on search_vector if FTS is used.

[ ] 7. Add partial B-tree index for the most common non-deleted filter:
        CREATE INDEX ix_table_active ON table (created_at DESC)
            WHERE is_deleted = false;

[ ] 8. Add B-tree indexes on enum/status columns filtered in most queries.

[ ] 9. Run EXPLAIN (ANALYZE, BUFFERS) on a representative query with real data
        to verify the planner uses the indexes.

[ ] 10. Use CREATE INDEX CONCURRENTLY in production migrations on tables
         > 100 k rows. Plain CREATE INDEX takes an ACCESS EXCLUSIVE lock
         and blocks writes for the full build duration.

[ ] 11. Set pg_trgm.similarity_threshold = 0.3 (default is fine for most apps).
         Lower → more results (noisier); higher → fewer results (stricter).

[ ] 12. For FTS endpoints: explicitly choose configuration ('simple' vs
         'english' — see §4.1) and query parser (websearch_to_tsquery for
         all user-facing endpoints — see §4.2). Document the choice.
```

---

## 10. Anti-Patterns to Avoid

| Anti-pattern | Problem | Fix |
|---|---|---|
| `iLIKE '%term%'` without a GIN index on a large table | Full sequential scan on every request | Add `GIN (lower(col) gin_trgm_ops)` |
| FTS with `'english'` config on a names/codes column | Stop-word removal silently drops tokens ("The", "On") | Use `'simple'` config for proper nouns and identifiers |
| Calling `to_tsquery(user_input)` from an HTTP endpoint | Raises on bad syntax; injection-adjacent | Use `websearch_to_tsquery` — never raises, parameter-safe |
| Filtering in Python after fetching results | Pagination totals are wrong; full table loaded | Move all predicates into SQLAlchemy `where()` |
| `to_tsvector(col)` computed inline in query | Recomputed on every row, can't use index | Use stored `GENERATED ALWAYS AS` column |
| String interpolation into `tsquery` | SQL injection | Use parameterised `func.websearch_to_tsquery('simple', :q)` |
| Not escaping user input for iLIKE | `%` and `_` widen the match unexpectedly | Use `escape_like()` from `app.core.utils.text` |
| Composite GIN index on unrelated columns | Large index, partial-key GIN lookups are not useful | GIN on individual columns; composite only for B-tree |
| Using FTS for short names / codes | Stop-word removal can drop tokens; no fuzzy match | Use trigram for short strings |
| Using trigram for long documents | High false-positive rate; large index | Use FTS for long-form text |
| `ts_rank` instead of `ts_rank_cd` for multi-term queries | Ignores proximity — distant matches rank as high as clustered ones | Default to `ts_rank_cd` |
| `ORDER BY similarity(col, term)` with GIN index | GIN doesn't support distance ordering | Switch to GiST when nearest-neighbour sort is needed |
| `ts_headline` inside the `WHERE` or count window | Recomputes for every candidate row — very slow | Apply `ts_headline` only in the SELECT list, after pagination |
| Plain `CREATE INDEX` on a live table > 100 k rows | `ACCESS EXCLUSIVE` lock blocks writes for the entire build | Use `CREATE INDEX CONCURRENTLY` |
| Skipping tiebreaker in ORDER BY | Non-deterministic pagination with OFFSET | Always append `Model.id.desc()` last |

---

## Summary — One-Line Rules

1.  **Short names / codes → GIN trigram + iLIKE.**
2.  **Long text / ranked relevance → stored tsvector + GIN + `ts_rank_cd`.**
3.  **FTS config: `'simple'` for names/codes, `'english'` for prose.**
4.  **FTS query parser: `websearch_to_tsquery` for every user-facing endpoint.**
5.  **Mixed input (name + phone + code) → classify input, route to correct path.**
6.  **All filters + search in one WHERE clause — never post-filter in Python.**
7.  **Generated columns for search targets — never computed inline.**
8.  **GIN for reads; GiST only when `ORDER BY similarity()` or write throughput demands it.**
9.  **Every FK column gets a B-tree index — PostgreSQL never auto-creates them.**
10. **Partial indexes on `WHERE is_deleted = false` — smaller and faster for soft-delete tables.**
11. **`CREATE INDEX CONCURRENTLY` on live tables.**
12. **Escape all iLIKE input. `websearch_to_tsquery` is already safe.**
13. **Always end ORDER BY with `model.id.desc()` — deterministic pagination.**
