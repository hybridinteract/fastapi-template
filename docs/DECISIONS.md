# Decisions

> Why things are the way they are. **Append-only, newest first.**
> Last verified against the code: 12 October 2026.

A decision earns an entry here when reversing it would be expensive, or when someone six months from
now would otherwise look at the code and assume it was an accident.

**Never rewrite an entry.** A reversal is a *new* entry that references the old one — the record of
having changed our mind is the useful part. Keep entries short; the long version belongs in
`docs/research/` or a rule file, linked from here.

Shape:

```markdown
## <DD Month YYYY> — <short title>

**Decided:** <what we do now, in one sentence.>
**Why:** <the reason, and the tiebreaker if it was close.>
**Rejected:** <what we did not do, and what it would have cost.>
**Owner:** <file or section that now states this rule in full.>
```

---

## 12 October 2026 — SQLAlchemy stays on 2.0.x; capped below 2.1

**Decided:** `sqlalchemy[asyncio]>=2.0.54,<2.1`. The cap is what stops `uv lock --upgrade` crossing
to 2.1 without anyone choosing to.
**Why:** 2.1.0 went GA on 24 September 2026 and shipped four patch releases in thirteen days, each
fixing regressions — 2.1.4 fixed one in the asyncpg dialect we run on. Our code is *not* the
obstacle: it was audited against every item in the official `migration_21` guide (Python 3.11
floor, greenlet extra, psycopg 3 default driver, unconditional autoflush, `filter_by()` ambiguity,
named types bound to `MetaData`, `Computed`, dataclass and loader-option changes) and none applies,
and our enum migrations render byte-identical DDL under 2.0.52 and 2.1.4. This is a maturity call.
**Lift it when** a 2.1 release ships with no regression fixes in its changelog; then raise the floor,
run the suite, the migration up/down/up cycle and `alembic check`, and record it here.
**Rejected:** Moving now — the template would be where 2.1's regressions get found, in every
project built from it. Leaving the floor uncapped — the next routine relock would take 2.1 silently.
**Owner:** the comment on the `sqlalchemy` line in `pyproject.toml`.

## 12 October 2026 — Enums subclass `StrEnum

**Decided:** `UserStatus`, `ActivityAction` and `ChangeType` moved from `(str, Enum)` to `StrEnum`,
and new enums use it.
**Why:** On Python 3.11+, `str()` of a `(str, Enum)` member is `"ActivityAction.CREATE"`, not
`"CREATE"`. `GET /activity?action=CREATE` upper-cased that and compared against
`"ACTIVITYACTION.CREATE"`, so the filter matched nothing and returned an empty page with no error.
**Rejected:** `.value` at the one call site — it fixes that site and leaves the trap armed for the
next `str()` or f-string. Leaving the mixin for consistency — consistency with a latent bug.
**Owner:** [`PROJECT_CONVENTIONS.md`](PROJECT_CONVENTIONS.md) §6.

## 10 September 2026 — Layer folders from the first commit; a module's shape is chosen, not grown

**Decided:** A domain module lays each layer out as a folder — `models/`, `schemas/`, `crud/`,
`services/`, `routes/` — **from its first commit**. Four shapes exist and one is chosen deliberately
before any file is written: **flat**, **layered** (the default), **composite**, **shared kernel**.
The procedure is [`MODULE_CONVENTIONS.md`](MODULE_CONVENTIONS.md) §6.1; the shape and the step that
chose it go in the module's `how-it-works.md`.

**Reverses:** yesterday's rule, which said *"a file becomes a folder when it outgrows itself"*
(`CLAUDE.md` §1) and *"write the concrete thing twice, abstract on the third"*
(`MODULE_CONVENTIONS.md` §6). **That rule was never recorded here as a decision** — it arrived with
the Phase 1 docs as inherited wording and was never examined, which is most of why it survived a day.

**Why:** two reasons, one borrowed and one our own.

- *Borrowed.* `influen-backend` ran the size rule for three weeks and reversed it on 1 September
  2026: *"Every Influen domain module ends up split — `organization` and `influencer` both did within
  days — so the flat file is a stage nobody stays in, and converting later is a churn commit that
  touches every layer at once and buries the real diff underneath it. Start where you are going to
  end up."*
- *Ours.* The size rule implies a threshold around 600 lines. **The largest file in this repo is 354
  lines** (`app/iam/user/services.py`). A rule that never fires does not make the decision — it means
  the decision gets made by accident, differently each time.

**Cost:** one extra folder on day one for a module that turns out to stay small. Bounded, and
reversible by the §8 procedure. The cost of the old rule was a restructure commit landing on a branch
that was also doing something else.

**Rejected:** keeping the size rule with a lower threshold. It still measures the wrong thing —
whether a module holds a second entity is a fact about the domain, knowable before the code exists;
line count is a fact about a Tuesday.

**Owner:** [`MODULE_CONVENTIONS.md`](MODULE_CONVENTIONS.md) §6 · [`../CLAUDE.md`](../CLAUDE.md) §1.

## 10 September 2026 — "Composite module" for a module made of sub-modules

**Decided:** A module holding two or more sub-domains is a **composite module**; its parts are
**sub-modules**; the act is **sub-modularising**. It declares a **rank order** in its root
`__init__.py`, and a sub-module may import only lower ranks — enforced by
`tests/test_module_boundary.py`, not by review.

**Why the name:** it says *made of parts* without implying size, which matters because size is the
criterion the entry above removes. It collides with nothing already in use here — DDD's **Aggregate**
is a consistency boundary, **Bounded Context** is the module itself, **Shared Kernel** is the fourth
shape. Rejected: `submodular` (an established maths/ML term — search-hostile), `aggregate module`
(collides with Aggregate), `multi-context` (it is *one* context; the name would invite the wrong
split), `nested`/`parent` (describe the filesystem, not the intent), and `subpackages` — which is
what `influen-backend` calls the same thing — because every layer folder is also a subpackage, so the
word distinguishes nothing.

**Why the rank is a test:** [`app/iam`](../app/iam) is this shape with neither, and its boundary has
already dissolved — `auth/` imports `user/` in 8 places, `user/services.py` imports `auth/` in 4, and
one function-local import at `app/iam/auth/current_user.py:44` is what stops startup deadlocking.
Nobody decided that; each import passed review on its own. A convention produces a cycle; a rank plus
a test produces a chain. `app/iam` is **not** being fixed in this change — it is documented as the
cautionary tale.

**Note:** this is our own term, not standard vocabulary. There is no established industry name for
this file shape. `MODULE_CONVENTIONS.md` §7 says so and names influen's word, so nobody moving
between the two repos thinks they are two different ideas.

**Owner:** [`MODULE_CONVENTIONS.md`](MODULE_CONVENTIONS.md) §6.2, §7.

## 9 September 2026 — Lint is reported, not gated; tests and docs are gated

**Decided:** CI blocks on `pytest` and `scripts/check_docs.py`. `ruff` and `ty` run
`continue-on-error` and are reported only. `.pre-commit-config.yaml` runs ruff on **changed
files**, so new code is held clean while the baseline is worked down separately.

**Why:** The template carries several hundred inherited ruff findings and an untriaged `ty`
baseline. Making either a hard gate means CI is red on the first commit, and a gate that is
always red teaches everyone to ignore every gate — including the two that are meaningful.

**Rejected:** Bulk-fixing the baseline as part of this change. It would bury the
documentation work in a several-hundred-file diff, and `UP042` (replace-str-enum) in
particular can change runtime behaviour in a SQLAlchemy codebase.

**Owner:** [`../.github/workflows/ci.yml`](../.github/workflows/ci.yml) — the comment there
says to delete `continue-on-error` once the baseline reaches zero. Tracked in
[`planning/modernization.md`](planning/modernization.md).

## 9 September 2026 — `fcube.py` deleted, replaced by the `/new-module` skill

**Decided:** Removed the `fcube.py` stub. Module scaffolding is
[`.claude/skills/new-module/SKILL.md`](../.claude/skills/new-module/SKILL.md).

**Why:** The stub could not work — it imported a `fcube` package that is not vendored here,
so every invocation printed "FCube CLI not found". A command that only ever fails is worse
than no command: it makes people think scaffolding is unavailable rather than that it lives
somewhere else. The skill also does the part the generator never did — the four
registrations that fail silently.

**Rejected:** Vendoring the `fcube` package. A code generator has to be maintained against
the conventions it emits; a skill is the conventions.

**Owner:** `.claude/skills/new-module/SKILL.md`.

## 9 September 2026 — Cross-cutting rules live in `.claude/rules/`, not a docs folder

**Decided:** Each cross-cutting rule is one file in `.claude/rules/` with `paths:` frontmatter naming
the code it governs. `docs/` holds specs, guides, plans, research and decisions — not rules.

**Why:** Claude Code loads a path-scoped rule automatically when it reads a matching file, and not
otherwise. A rule kept as prose in `docs/` has to be *chosen*, which means the guardrail spends lines
nagging an agent to go read it, and the rule is missed exactly when someone is moving fast. Path
scoping removes the failure mode and costs zero context on unrelated tasks.

**Rejected:** A `docs/concerns/` folder (the shape used in `influen-backend`). It is the same content
one indirection further from the code, with no mechanism behind it.

**Owner:** [`WRITING_DOCS.md`](WRITING_DOCS.md) § Writing a rule file.

## 9 September 2026 — `CLAUDE.md` is capped at 200 lines

**Decided:** The guardrail stays under 200 lines. A rule earns a place in it only if breaking the rule
is **expensive and silent**. Everything else gets a file and one line pointing at it.

**Why:** It is read in full at the start of every session, so every line costs attention on every
future task. Anthropic's own guidance is to target under 200 lines because longer files consume more
context and measurably reduce adherence.

**Rejected:** A 400–500 line guardrail holding the full rule text. It reads well to a human opening
the repo once and degrades the thing it is trying to improve.

**Owner:** [`../CLAUDE.md`](../CLAUDE.md) — the budget is stated in the file itself.

## 9 September 2026 — Conventions are enforced by tests where a test is possible

**Decided:** Rules whose violation is mechanically detectable get a test in `app/core/tests/` rather
than only a paragraph. Currently: model registration for Alembic, the layering contract, module
anatomy, and router registration order.

**Why:** Prose is advisory; a red test is not. Each of these fails **silently** in production —
an unregistered model is skipped by autogenerate, a `commit()` in CRUD breaks transaction ownership
without erroring, a router registered in the wrong order swallows sibling paths.

**Rejected:** Relying on code review. It is where all four of these got through before.

**Owner:** [`../.claude/rules/tests.md`](../.claude/rules/tests.md).

## 13 October 2026 — A module's doc is its `README.md`; more than one goes in `docs/`

**Decided:** Each module documents itself in `app/<module>/README.md`. A module that needs more than
one document adds `app/<module>/docs/`, `kebab-case.md` inside, linked from the README. This
replaces `app/<module>/<module>_doc/how-it-works.md`, and `app/core/crud/SEARCH_STRATEGY.md` moved to
`app/core/crud/docs/search-strategy.md`.

**Why:** `README.md` is the industry default for a folder's documentation — GitHub and GitLab render
it when you open the folder, and every reader and agent looks there first. `<module>_doc/` was a
convention of this codebase alone, repeated the module name the path already gives, and hid the doc
one folder down. `app/core/` already used `README.md`, so there were two patterns for one job.

**Rejected:** Keeping `<module>_doc/` (the grep-target argument does not outweigh discoverability);
a `docs/` folder for every module from the start (every module had exactly one file in it); a
per-module `CLAUDE.md` (agent-only, and the path-scoped `.claude/rules/` already cover agents).

**Owner:** [`MODULE_CONVENTIONS.md`](MODULE_CONVENTIONS.md) §6.3; enforced by
`app/core/tests/test_module_anatomy.py`.
