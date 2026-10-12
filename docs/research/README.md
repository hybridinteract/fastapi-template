# Research

> Evaluate options before deciding. Every note ends in a recommendation.
> Last verified against the code: 9 September 2026.

One file per question, `kebab-case.md`. Copy [`_TEMPLATE.md`](_TEMPLATE.md).

This folder exists so that "we looked at that" is recoverable. A library evaluated and rejected in
March is worth as much as one adopted — without the note, someone re-evaluates it in October and
reaches a different answer for reasons nobody can reconstruct.

## Every note carries a status

`ADOPTED` · `REJECTED` · `STILL A PROPOSAL` — on its own line near the top, kept current.

**A note that reaches `ADOPTED` is not finished.** In the *same change*, promote the durable part:

- the decision and its tiebreaker → [`../DECISIONS.md`](../DECISIONS.md)
- the rule someone must now follow → `.claude/rules/<topic>.md` or a `PROJECT_CONVENTIONS.md` section
- the steps to do it → a `.claude/skills/` skill or a `docs/guides/` how-to

Without that step this folder becomes an archive nobody reads, and the decision lives only in the
place least likely to be found.

Superseded notes are **kept**, with a banner at the top saying what replaced them and when. Deleting
one loses the reasoning that made the replacement necessary.

## What is here

| Note | Status |
|---|---|
| [`ai-agent-integration.md`](ai-agent-integration.md) | STILL A PROPOSAL — direction for agentic AI features in the template |
