# <The question>

> Status: **STILL A PROPOSAL** | ADOPTED | REJECTED | SUPERSEDED by `<file>`
> Last verified against the code: <DD Month YYYY>.

## The question

What are we actually deciding, and what forced the question now. One paragraph. If the answer would
not change what we build, this note is not needed.

## Constraints

What any answer has to satisfy — the stack, the deployment target, the team, the deadline. This is
what makes an evaluation reproducible rather than a matter of taste.

## Options considered

### Option A — <name>
What it is · what it would cost us · what it rules out.

### Option B — <name>
Same shape. Include "do nothing" whenever it is genuinely available.

## What we actually tested

Commands run, versions pinned, numbers observed. **Not** what the README claims. If nothing was run,
say so plainly — an evaluation from documentation alone is worth less and should be labelled.

```bash
<command> → <result>
```

## Recommendation

One option, stated plainly, with the tiebreaker if it was close.

## What this rules out

The doors this closes, so nobody re-opens one by accident later.

## If adopted, promote

- [ ] Decision + tiebreaker → [`../DECISIONS.md`](../DECISIONS.md)
- [ ] Any rule someone must follow → `.claude/rules/<topic>.md` or a `PROJECT_CONVENTIONS.md` section
- [ ] Any procedure → `.claude/skills/` or `docs/guides/`
- [ ] Status line above updated to `ADOPTED`
