# Curriculum: Zero to Enterprise-Ready Agentic AI

Owned and sequenced by the tutor (Claude), not assembled reactively from
learner questions. Updated as modules complete or priorities shift — see
`PROGRESS.md` for the session-by-session log of what actually happened
against this plan.

**Status key:** ✅ done · 🔜 next · ⏳ planned

## Track 0 — Foundations (done)

The mechanics everything else builds on. No framework — hand-rolled, so
frameworks later read as "a helper for what I understand," not magic.

- ✅ The raw tool-calling loop, `max_iterations`
- ✅ Tool design (safe execution, actionable error messages, description
  quality under ambiguity)
- ✅ Context engineering (feeding an agent only what it needs)
- ✅ Orchestrator + isolated worker agents (routing pattern, structured
  output via a "fake tool")
- ✅ Eval suite basics (routing correctness + answer correctness)
- ✅ Hardening basics (JSONL tracing, file-based kill switch, bounded retry)
- ✅ Episodic memory, per-agent isolation, the "shared input text corrupts
  an unrelated decision" bug class
- ✅ MCP mechanics — stdio and HTTP/SSE transports, both directions,
  built not just described

## Track 1 — Graph-Based Orchestration (🔜 next)

- 🔜 **LangGraph fundamentals** — port the existing math/writing
  orchestrator 1:1 into LangGraph nodes/edges/state, so the mapping from
  "what I already built" to "what the framework gives me" is explicit
- ⏳ **Parallel fan-out + synthesizer/reduce node** (the concept you asked
  about directly) — multi-source aggregation, latency reduction, ensemble
  voting
- ⏳ **Conditional edges / dynamic graphs** — routing that depends on
  runtime state, not just the initial question
- ⏳ **Checkpointing & persistence** — resuming a long-running graph after
  a crash or across sessions (LangGraph's built-in state persistence)
- ⏳ **Cycles / iterative refinement graphs** — agent critiques and retries
  its own output (reflection pattern) instead of one-shot

## Track 2 — Agentic Design Patterns (⏳ planned, after Track 1)

Vocabulary + concrete graph shapes for each, since abstract pattern names
mean little without an implementation to point at:

- ⏳ **OODA loop** (Observe–Orient–Decide–Act) — continuous environment
  sensing vs one-shot Q&A
- ⏳ **Goal-oriented / BDI agents** — persistent goal, task decomposition,
  keeps working until goal state satisfied (vs current workers, which
  answer once and stop)
- ⏳ **Reactive agents** — pure stimulus→response, no persistent goal
- ⏳ **Scheduler/trigger-driven agents** — cron/event/queue-triggered
  instead of human-turn-triggered; ties directly into the kill-switch
  work already done
- ⏳ **Reflection / self-critique pattern** — agent evaluates its own
  output before returning it
- ⏳ **Human-in-the-loop pattern** — agent pauses for approval on
  high-stakes actions (the enterprise-critical one — most real deployments
  need this for anything with side effects)

## Track 3 — Multi-Agent Communication at Scale (⏳ planned)

- ⏳ **MCP gateway** (already flagged) — multiple MCP servers behind one
  aggregator, tool-list merging, routing to a *server* not just a worker
- ⏳ **Agent-to-agent (A2A) protocols** — how independent agents (possibly
  different vendors/models) negotiate and hand off work, vs the
  single-process orchestrator built so far
- ⏳ **Shared vs isolated state at scale** — when isolation (current
  design) breaks down and agents legitimately need to share a blackboard/
  shared memory store

## Track 4 — Data & Memory at Scale (⏳ planned)

- ⏳ **RAG fundamentals** — when file-based notes (current approach)
  stops being sufficient, chunking, embeddings, retrieval quality
- ⏳ **Vector DB selection tradeoffs** — pgvector vs dedicated (Pinecone/
  Weaviate/Qdrant) vs in-memory, and how to justify the choice (this
  project deliberately argued *against* one — knowing when to reverse
  that call matters as much as the RAG mechanics)
- ⏳ **Long-term / cross-session memory** vs the episodic per-run memory
  already built — semantic memory, summarization/compaction of old history

## Track 5 — Evaluation & Quality at Scale (⏳ planned)

- ⏳ **LLM-as-judge grading** — flagged as a known gap already (writing
  worker only checked for non-emptiness); rubric design, judge-model bias
- ⏳ **Regression suites for agent behavior** — golden datasets, catching
  silent quality drift across model/prompt changes
- ⏳ **A/B testing prompts and routing logic** in a live system

## Track 6 — Production Hardening (Enterprise-grade) (⏳ planned)

This is the track that most separates "demo" from "safe to run
unattended at a company" — deliberately deferred until now per the
original 1-month scope, revisited properly here:

- ⏳ **Real observability** — OpenTelemetry traces/spans (vs current JSONL
  file), structured logging, dashboards
- ⏳ **Cost & token tracking** — per-request and aggregate spend, budget
  alerts/circuit breakers
- ⏳ **Guardrails** — input/output content filtering, PII redaction,
  jailbreak/prompt-injection resistance (directly relevant given this
  session's own system prompt enforces exactly this kind of boundary)
- ⏳ **Rate limiting & backpressure** — protecting both your system and
  downstream APIs
- ⏳ **Retry/backoff strategy** beyond the current bounded retry —
  exponential backoff, circuit breakers, graceful degradation
- ⏳ **Remote kill switch** — current is a local STOP file; production
  needs a centrally controllable flag (feature-flag service, DB row, etc.)
- ⏳ **Secrets management** — API keys, credentials, never in code or
  plaintext config
- ⏳ **Multi-tenancy considerations** — isolating one customer's agent
  runs/data/cost from another's

## Track 7 — Deployment & Operations (⏳ planned)

- ⏳ **Containerization** — Dockerizing an agent service
- ⏳ **Scaling** — stateless vs stateful agent processes, horizontal
  scaling, queue-based work distribution
- ⏳ **CI/CD for agents** — testing pipelines that run the eval suite
  automatically, prompt/config versioning and rollback
- ⏳ **Audit logging & compliance** — who asked what, what the agent did,
  retention — needed wherever agents take real-world actions

## Track 8 — Security (⏳ planned, threaded throughout but formalized here)

- ⏳ **Prompt injection defense** — untrusted content (web pages, docs,
  tool outputs) vs trusted instructions, the same boundary this very
  tutoring session operates under
- ⏳ **Tool-use sandboxing** — least-privilege tool access per agent,
  blast-radius containment (already the *reason* workers are isolated —
  formalizing why that pays off at scale)
- ⏳ **Output validation before side effects** — never let raw LLM output
  directly trigger an irreversible action without a check

---

## Sequencing note

Tracks 1–2 (LangGraph, design patterns) come first because they're the
direct continuation of what's built and were already promised. Tracks 3–8
are enterprise-scale concerns that matter most once a real deployment is
the goal — sequenced roughly by "what breaks first" as a system grows:
communication/data next, then quality, then hardening, then ops, with
security threaded throughout and formalized last as a dedicated review
pass over everything built.

This file is the plan; `PROGRESS.md` remains the actual history (what
happened, what broke, what was learned) — check both when picking up a
session.
