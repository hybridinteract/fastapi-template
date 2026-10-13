# Documentation Map

> Start here. This file lists every document, what it owns, and when to read it.
> Last verified against the code: 13 October 2026.

**One owner per rule.** A rule is stated in full in exactly one place. Everywhere else summarises it
in a sentence and links here. Copies drift, and then they disagree — see
[`WRITING_DOCS.md`](WRITING_DOCS.md) before you write or move any `.md` in this repo.

## The four homes

| Home | Answers | When it reaches an agent |
|---|---|---|
| [`../CLAUDE.md`](../CLAUDE.md) | "What must I never get wrong?" | Loaded in full at the start of every session |
| [`../.claude/rules/`](../.claude/rules/) | "What are the rules for *this* file I'm editing?" | Loaded automatically when a matching file is read — never otherwise |
| `docs/` (this folder) | "What is the house spec? How do I do X? What are we building? Which option wins?" | On demand, by link |
| `app/<module>/README.md` | "How does this one module work?" | On demand, when working in that module |

Nothing else gets a folder. If a document does not fit one of these, it is probably two documents.

## The specs

| File | Owns | Read it when |
|---|---|---|
| [`PROJECT_CONVENTIONS.md`](PROJECT_CONVENTIONS.md) | **How** backend code is built — layering, DI, naming, models, list endpoints, streaming, Docker | Before your first change, then as reference by section number |
| [`MODULE_CONVENTIONS.md`](MODULE_CONVENTIONS.md) | **Where** code goes — the `core/` gate, the bar for a new module, split-vs-keep-together | Before creating any module or folder |
| [`FRONTEND_CONVENTIONS.md`](FRONTEND_CONVENTIONS.md) | The API contract a frontend relies on. Frontend conventions live in the frontend repo | When changing anything a client consumes |
| [`WRITING_DOCS.md`](WRITING_DOCS.md) | The doc-ownership contract, the naming convention, the freshness stamp | Before writing or moving any `.md` |
| [`DECISIONS.md`](DECISIONS.md) | **Why** — an append-only log of decisions and reversals | When a convention looks wrong, before changing it |

`CLAUDE.md` and the rules files link to `PROJECT_CONVENTIONS.md` **by section number**, so renumbering
its sections is expensive. Add sections at the end rather than renumbering.

## The working folders

| Folder | Holds | Lifecycle |
|---|---|---|
| [`guides/`](guides/) | How-to, task-oriented: set it up, run it, deploy it | Long-lived, updated in place |
| [`planning/`](planning/README.md) | The spec for a feature **before** it is built | Written once, then tracked to its exit criteria |
| [`research/`](research/README.md) | Evaluate options, end with a recommendation | Ends in `ADOPTED` / `REJECTED` / `STILL A PROPOSAL`; the durable part is promoted out |

## Naming

- **Root of `docs/`: `SCREAMING_SNAKE.md`** — reserved for the specs above. If it is not a spec that
  owns a whole subject, it does not belong at the root.
- **Inside any folder: `kebab-case.md`.**
- **`_TEMPLATE.md`** marks a copy-me file. It carries no stamp.

## Every file here carries a stamp

`Last verified against the code: <DD Month YYYY>`. Verify a claim while working → move the date. Find
a doc wrong → fix it **in the same change**. An unstamped or silently-stale doc is worse than none,
because nobody can tell July-true from today-true.

```bash
python3 scripts/check_docs.py
```

Dead links, missing stamps, and a rules file without `paths:` are errors. Stamps older than 30 days
are warnings; `--strict` promotes them.
