# Planning

> The spec for a feature **before** it is built.
> Last verified against the code: 13 October 2026.

One file per feature or module, `kebab-case.md`. Copy [`_TEMPLATE.md`](_TEMPLATE.md) and keep the
sections in order — the shape is what makes plans comparable and scannable.

A plan is written to be **read by whoever builds it**, which is increasingly an agent. That means:
name real files and real tables, not intentions; say what is deliberately out of scope; and end with
exit criteria somebody else could check without asking you.

## The two sections people skip, and shouldn't

- **"Deliberately not built"** stops the next person building something you decided against, and
  stops a reviewer flagging its absence as an oversight.
- **"Exit criteria"** is what makes the plan finishable. A plan with no exit criteria is a wish.

## Lifecycle

A plan stays here after the feature ships — it is the record of what was intended. When the code
diverges, update the plan **or** move the durable part into the module's `app/<module>/README.md`
(or a file in `app/<module>/docs/`) and say in the plan that the module doc now owns it.

Anything decided *while* planning that outlives the feature belongs in
[`../DECISIONS.md`](../DECISIONS.md).

## What is here

| Plan | Status |
|---|---|
| [`modernization.md`](modernization.md) | Aligning the template with the official FastAPI agent skill — Tiers 1–3 done, hygiene items open |
| [`iam-fixes.md`](iam-fixes.md) | Functionality and security fixes in `app/iam` from the 13 October 2026 review — 5 of 17 done |
