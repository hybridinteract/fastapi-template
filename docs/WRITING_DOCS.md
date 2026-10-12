# Writing Docs — one owner per rule

> Read this before you write or move any `.md` in this repo.
> Last verified against the code: 9 September 2026.

**A rule is stated in full in exactly one place.** Everywhere else summarises it in a sentence and
links. Never paste a rule into a second file — copies drift, then they disagree, and nobody can tell
which one is current.

## The four owners

| Owner | Holds | Loaded |
|---|---|---|
| [`CLAUDE.md`](../CLAUDE.md) | The guardrail — one line per rule, nothing longer | Every session, in full |
| [`.claude/rules/<topic>.md`](../.claude/rules/) | One cross-cutting rule, in full, for the files it governs | Only when a matching file is read |
| `docs/` | The house spec, how-tos, plans, research, decisions | On demand, by link |
| `app/<module>/<module>_doc/` | Everything written about one module | On demand |

## Where does this document go?

| It is… | It goes in |
|---|---|
| A rule that spans modules and is checkable in a diff | `.claude/rules/<topic>.md` |
| A rule about how code is written | `PROJECT_CONVENTIONS.md`, as a numbered section |
| A rule about where code is placed | `MODULE_CONVENTIONS.md` |
| A procedure someone follows step by step | `.claude/skills/<name>/SKILL.md` |
| A how-to for a human (set up, run, deploy) | `docs/guides/<topic>.md` |
| A spec for something not built yet | `docs/planning/<feature>.md` |
| An evaluation of options | `docs/research/<topic>.md` |
| Why a decision was made, or reversed | `docs/DECISIONS.md` — append, never rewrite |
| How one module works | `app/<module>/<module>_doc/how-it-works.md` |

**If it does not fit a row, it is probably two documents.**

## Naming

- **Root of `docs/`: `SCREAMING_SNAKE.md`** — reserved for the specs that own a whole subject.
- **Inside any folder: `kebab-case.md`.**
- **`_TEMPLATE.md`** marks a copy-me file, and carries no stamp.
- Folder names are plain English a new hire understands without being taught.

## The stamp

**Every file under `docs/` carries `Last verified against the code: <DD Month YYYY>`** near the top.
Verify a claim while working → move the date. Find a doc wrong → fix it in the same change.
`scripts/check_docs.py` fails on a missing stamp and warns past 30 days.

Module notes under `app/**/<module>_doc/` carry the stamp too. They live outside `docs/`, so the
checker validates their links but not their stamps — keeping those honest is on you.

## Writing a rule file

Rules live in `.claude/rules/` because Claude Code loads them **automatically when a matching file is
read**, and not otherwise. That is the whole point: the rule reaches the agent editing the code it
governs, and costs nothing on every other task.

> **Every rule file must carry `paths:`.** A rule with no `paths:` loads unconditionally on every
> session — the exact cost this design avoids. `scripts/check_docs.py` fails the build if one is
> missing. This is also why there is no `_TEMPLATE.md` in `.claude/rules/`; the template is below.

Keep a rule under ~120 lines. Copy this shape:

````markdown
---
paths:
  - "app/*/services*/**"
---
# <Topic>

> Last verified against the code: <DD Month YYYY>.

## The rules
Hard rules as a bullet list. Each must be checkable: someone reading a diff should be able to say
"this line breaks rule 3". Name the `PROJECT_CONVENTIONS.md` section that states the long version.

## Where it IS used
One row per call site, verified by reading the code — not by reading other docs.

| Where | What | Notes |
|---|---|---|

## Where it is deliberately NOT applied
The places that look like they should use this and don't, with the reason and the consequence.
This section is why the doc is trustworthy — without it, the next person "fixes" a deliberate
omission.

## Known gaps
What is wrong, missing or unfinished right now.

## How to re-check this rule
The literal commands that rebuild the call-site table, with the counts they should produce.
If a count disagrees with the table, the table is stale — fix it before relying on it.
````

The last two sections are what make a rule worth reading. Do not drop them.

## Promote what stays true

A `docs/research/` note is dated and ends in a status line. When one is adopted, copy the durable
part into `DECISIONS.md` or a rule file **in the same change**. Without that step, `research/` becomes
an archive nobody reads.

## Why the split exists

The same contract restated in four places becomes four contracts that disagree. `CLAUDE.md` is read
on **every** task, so anything longer than a line there costs attention on work it has nothing to do
with. The long version is not less important — it is just not read every time.

**Before you add a paragraph to `CLAUDE.md`, delete one.**
