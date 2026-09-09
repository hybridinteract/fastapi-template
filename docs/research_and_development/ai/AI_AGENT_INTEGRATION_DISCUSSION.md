# AI Agent Integration — Discussion Notes & Draft Direction

> Working document from an architecture discussion on integrating agentic AI into the `fastapi-template`
> (used across 7+ production ERP/CRM/Ecom projects). Not yet a finalized convention — captures research,
> decisions made, and open points to resolve before writing `docs/AI_AGENT_CONVENTIONS.md`.
>
> Status: **Draft for evaluation** · Continue this thread in Claude Code against the real codebase.

---

## 1. Context

The template is a modular monolith: FastAPI (async) + SQLAlchemy 2.0 + Postgres + Celery/Redis + RBAC,
with a strict layered architecture (`Route → Service → CRUD → Model`), DI only via `dependencies.py`,
and an append-only audit log (`app/activity`). Full conventions in `docs/PROJECT_CONVENTIONS.md`.

Goal: define **how agentic AI gets built and wired into this stack**, so every future project built on
the template inherits the same conventions the rest of the stack already enforces (naming, layering,
DI, permissions, audit, testing) — instead of every project inventing its own ad hoc AI integration.

The person is a software engineer, academic-level understanding of GenAI/ML, general understanding of
agents/terminology, but no production agentic-AI-building experience yet. This doc assumes that level.

---

## 2. Existing template — relevant primitives already in place

These matter because the AI conventions should **reuse** them, not duplicate them:

| Primitive | Where | Why it matters for agents |
|---|---|---|
| Layered architecture, service owns transactions | `docs/PROJECT_CONVENTIONS.md` §4 | Agent tools must call **services**, never CRUD directly — same rule as human-facing routes |
| DI wiring | `<module>/dependencies.py` | Agent/tool factories follow the same `Annotated` + `Depends()` pattern |
| Celery + retry/circuit-breaker | `app/core/background/internals/` | Long-running agent workflows reuse this instead of a new orchestration engine |
| Redis cache abstraction | `app/core/cache/` | Reuse for rate limiting / usage caps on agent calls |
| Append-only audit log | `app/activity/` (`ActivityLog`: actor_id, action, resource_type/id, details JSONB) | Agent actions should log here too — see open question in §7 |
| RBAC, `resource:action[:scope]` permissions | `app/user/permission_management/` | Extend with an agent-specific permission namespace |
| SSE / JSON-lines streaming | `docs/PROJECT_CONVENTIONS.md` §15 | Already the right primitive for streaming agent tokens — no new infra needed |
| Pydantic v2 everywhere, `ty` type checking | whole stack | Strong argument for a typed-agent framework over a loosely-typed one |
| `pytest-asyncio` test setup | `pyproject.toml` | Framework choice should offer a way to test agents without live LLM calls |

---

## 3. Research summary (as of mid-2026)

### Framework landscape
- **Pydantic AI** — typed agents, Pydantic-v2-native, multi-provider model support, built-in usage/cost
  limits, `TestModel`/`FunctionModel` for testing without live API calls. Philosophically closest fit to
  this codebase (minimal abstraction, typed, DI-friendly).
- **LangGraph** — most mature for durable, checkpointed, multi-step graph workflows with human-in-the-loop
  pauses that must survive across sessions. Heaviest of the options; large enterprise deployment base
  (Klarna, Uber, JPMorgan, etc.) but introduces a second orchestration paradigm alongside Celery.
- **Vendor-native SDKs** (Claude Agent SDK, OpenAI Agents SDK) — tight integration with one provider's
  tracing/tooling, at the cost of portability.
- **MCP (Model Context Protocol)** — now the standard way to expose tools/APIs to agents over JSON-RPC.
  `fastapi-mcp` can expose existing FastAPI routes as MCP tools with auth. Relevant if/when third-party
  agents or tools need to call into this stack in a standardized way — not required for the first pilot.

### Model cost tiering
- 2026 list pricing (input tokens, illustrative): DeepSeek V4 ~$0.44/M, Haiku-class ~$1/M, Sonnet-class
  ~$3/M, GPT-5.5-class ~$5/M, Opus-class ~$25/M.
- Routing the bulk of calls to a cheap/fast model and reserving an expensive model for hard cases cuts
  token spend 40–85% with reportedly no visible quality drop, because agent loops make far more LLM calls
  per task (10–100x a chatbot) — not every step needs a frontier model.

### Human-in-the-loop (HITL) for mutating actions
- Standard pattern: proposal contains the action, parameters, agent's reasoning, estimated impact, and an
  **expiry** — nothing executes until a human accepts.
- Escalation triggers worth encoding explicitly: action reversibility/magnitude, low model confidence,
  behavioral anomalies, regulatory classification.
- Audit trail must answer: what did the agent try to do, who approved it, what context did the reviewer
  see, did it actually happen.

### Observability
- Langfuse is the current open-source standard (tracing, cost, evals) but self-hosting requires
  ClickHouse in addition to Postgres — a real new-infra cost.
- Extending existing Prometheus metrics + structured logging gets most of the value with zero new infra;
  treat Langfuse as a phase-2 option.

### RAG / data
- pgvector on the existing Postgres instance covers retrieval-augmented generation over CRM/ERP data
  without introducing a dedicated vector database.

---

## 4. Decisions made in discussion so far

| Decision | Choice | Rationale |
|---|---|---|
| Primary agent framework | **Pydantic AI** | Native Pydantic v2 fit, typed, testable, multi-provider option kept open even though defaulting to one vendor |
| LangGraph | **Not adopted by default** — escalation path only | Celery + Postgres + activity log already cover durable/multi-step orchestration; avoid two orchestration paradigms |
| LLM provider strategy | **Single provider by default**, model-tiered | Simplicity as house standard; cost-sensitive tasks can drop to a cheaper model within the same provider |
| Model tiers | `FAST` (classification/extraction/routing) · `DEFAULT` (chat/general tool-calling) · `PREMIUM` (complex/high-stakes reasoning) | Matches 2026 cost-routing practice; configured in `settings.py`, not hardcoded model strings |
| Pilot use case | **Both**: natural-language query/retrieval over CRM/ERP data (copilot) **and** chat-triggered actions against existing manual functionality (write/automate) | Broadest test of the conventions — read path and write/HITL path both exercised from day one |
| Execution model | **Both**, chosen per use case | In-request + SSE streaming for chat/copilot; Celery-backed async + SSE/polling for longer workflows — reuses existing patterns, doesn't invent a third |

---

## 5. Proposed architecture (draft — not yet finalized)

### Module placement

```
app/
├── core/
│   └── ai/                          # NEW — shared AI infra, never project-specific
│       ├── models.py                 # Model tier config → provider/model resolution
│       ├── client.py                 # Pydantic AI agent/model client factory
│       ├── tools.py                  # @tool decorator/registry (mutating flag, permission tag)
│       ├── guardrails.py             # usage limits, rate limiting (reuses app/core/cache)
│       ├── streaming.py              # adapter: agent stream → EventSourceResponse
│       └── metrics.py                # Prometheus counters/histograms for agent calls
│
├── agent_actions/                     # NEW — shared HITL infra (or extend app/activity)
│   ├── models.py                      # PendingAgentAction (proposal, reasoning, status, expiry)
│   ├── crud.py / services.py / routes.py   # same layered pattern as any other module
│   └── schemas.py
│
└── <feature>/                         # e.g. app/lead/
    ├── agent.py                       # domain tools wrapping THIS module's services.py
    │                                  # (never CRUD directly — same rule as routes.py)
    └── ...                            # existing services.py, routes.py, tasks.py unchanged
```

### Tool tagging (read vs. mutating)

- Every tool declares `mutating: bool`.
- Read tools execute immediately (search, summarize, report).
- Mutating tools produce a `PendingAgentAction` instead of executing — requires explicit human
  confirmation before the underlying service method runs.
- Mutating tools call the feature's **service layer**, identical business rules/permission checks as a
  human-driven route.

### Settings additions (`app/core/settings.py`)

```python
# === AI / Agents ===
AI_PROVIDER: str = "anthropic"          # single provider by default
AI_MODEL_FAST: str = "claude-haiku-4-5-20251001"
AI_MODEL_DEFAULT: str = "claude-sonnet-5"
AI_MODEL_PREMIUM: str = "claude-opus-4-8"
AI_MAX_TOOL_CALLS_PER_RUN: int = 20
AI_PENDING_ACTION_EXPIRY_MINUTES: int = 60
```

### Observability

- Extend Prometheus with `agent_requests_total`, `agent_tokens_total{model_tier}`,
  `agent_tool_calls_total{tool,outcome}`, `agent_latency_seconds`.
- Log agent runs through the existing `app.core.logging.get_logger` pattern.
- Defer Langfuse adoption until trace-level prompt debugging becomes a real bottleneck.

### Testing

- Use Pydantic AI's `TestModel` / `FunctionModel` under the existing `pytest-asyncio` setup — no live
  API calls in CI.

---

## 6. Open questions — needs a decision before writing final conventions

1. **`activity_logs` schema change.** Add `actor_type` (`user` / `agent`) to the existing, already-deployed
   `ActivityLog` model so agent actions are distinguishable from human ones in the audit trail — or keep
   agent actions in a separate table entirely to avoid migrating a shared table across 7 live projects?
2. **Approval timing.** Does mutating-tool confirmation always happen synchronously in the same chat turn
   (user sees "confirm?" inline, decides immediately), or must approval sometimes come from a different
   actor later (e.g., a manager approves the next day)? The latter requires `PendingAgentAction` to be the
   source of truth rather than in-memory conversation state — bigger design implication.
3. **LangGraph escalation trigger.** What concretely would justify introducing LangGraph later — e.g.
   "an agent workflow needs conditional branching across more than N tool calls with mid-flow pauses"?
   Worth defining a concrete threshold now rather than deciding ad hoc per project.
4. **Permission namespace.** Exact shape of the agent permission scope — e.g. `leads:create:agent` as a
   sub-scope of `leads:create`, vs. a fully separate `agent:leads:create` namespace.
5. **MCP.** Do any pilot use cases need third-party tools/agents calling into this backend (via
   `fastapi-mcp`), or is MCP out of scope until a concrete need shows up?

---

## 7. Next steps

- [ ] Resolve open questions in §6
- [ ] Prototype `app/core/ai/` against **one** pilot feature module (candidate: `lead` or similar) — both
      a read tool and a mutating tool, end to end including the `PendingAgentAction` approval flow
- [ ] Write `docs/AI_AGENT_CONVENTIONS.md` following the same format as `docs/PROJECT_CONVENTIONS.md`
      (tech stack table, naming conventions, layered architecture rules, checklist, hard rules)
- [ ] Add `PERMISSIONS` entries for agent scopes to `app/user/seed.py`
- [ ] Decide observability rollout (Prometheus-only now vs. Langfuse from the start)
