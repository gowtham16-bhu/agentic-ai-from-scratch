# Concept map — the whole curriculum on one page

Every concept in the agentic-ai-coach skill (24 files, ~383KB), where it lives, and
where I currently stand. Built by reading all 24 files in full on 2026-09-05.

Use it two ways:
- **As a learner:** find the next thing, and see what I have *not* touched.
- **As a candidate:** this is the vocabulary an FDE / applied-AI interview draws from.

Legend: `✔` built and understood · `◐` partially done, bar not met · `✗` untouched

---

## 0. The two rules everything else hangs off

```
1. Workflow vs agent — who owns the control flow.
   Workflow = I wrote the path. Agent = the model picks it at runtime.
   If you can enumerate the path, enumerate it. Agents earn their cost only
   when the path genuinely cannot be pre-determined.

2. Sub-agents are for ISOLATION, not concurrency.
   One agent can emit five tool calls in a turn and you run them with
   asyncio.gather. That is parallelism, in one context, at a third of the cost.
   The real justification for a worker is: it reads 50 files and returns 5 lines,
   protecting the parent's context window.
```

Most bad agent architectures violate one of these two.

---

## 1. The agent loop

| Concept | Detail | Status |
|---|---|---|
| The loop by hand | `while` loop: model decides tool-or-stop, you execute, feed back | ✔ |
| Four termination conditions | natural finish · no tool wanted · max_iterations · token budget | ◐ (1 of 4) |
| Checkpoint on halt | never stop without saving resumable state | ✗ |
| Working memory = the message list | it only grows; by turn 20 the model forgets turn 2 | ✔ |
| Compaction | keep last 6 turns verbatim, summarise older with explicit preserve/drop rules | ✗ |
| Context rot | quality degrades at long horizons even under the limit | ✔ concept |

**The compaction prompt is the whole trick.** MUST preserve: decisions and why, file
paths, values referenced later (IDs, URLs), open questions. MUST drop: raw tool output
already acted on, repeated errors, dead-end exploration.

**Why keep 6 recent verbatim:** the model needs exact recent tool results to continue.
Summarising the last turn destroys the precision it needs right now.

---

## 2. Tool design

The five rules:

```
1. The description says when to use AND when NOT to use
2. Few required fields; enums over free text
3. Return the useful slice, not the whole record
4. Errors are recovery instructions, not log lines
5. One good tool beats five overlapping ones
```

| Concept | Status |
|---|---|
| Schema from type hints + docstring | ✔ |
| Descriptions drive behaviour more than names | ✔ (demonstrated) |
| Errors-as-prompts | ✔ |
| Pagination — "call again with page=2" instead of a 10K-token return | ✗ |
| `dry_run=True` as the correct default on writes | ✗ |
| Forced structured output (`tool_choice` pinned to one schema) | ✗ |
| Any-format runtime + the repair ladder | ✗ |

**The repair ladder** (each rung is cheaper than the next): strip markdown fences →
regex repair (quotes, trailing commas) → extract the JSON substring → re-prompt with the
parse error → re-prompt with a forced tool schema → degrade to plain text.

**The measurable claim:** rewriting descriptions and error messages is a 7× iteration
difference on the same task, same model, same prompt. That delta is a README row.

---

## 3. Context and memory

**The four memory types:**
```
Working    = the message list        (in-context, dies with the session)
Episodic   = what happened before    (files / DB / embedding store)
Semantic   = facts and knowledge     (RAG / knowledge graph)
Procedural = how to do things        (SKILL.md files, fine-tuning)
```

| Concept | Detail | Status |
|---|---|---|
| Context budgeting | print system/tools/static/history token split after every turn | ✗ |
| Prompt caching — the ordering rule | order by *increasing volatility* | ✗ |
| The three cache-killers | timestamp near the front · `json.dumps` without `sort_keys=True` · dynamically pruning the tool list | ✗ |
| Measuring cache | `cache_read_tokens / input_tokens`; under 80% multi-turn = a bug, not a price | ✗ |
| Episodic memory | file-based per worker | ✔ |
| Bi-temporal facts | `valid_from`/`valid_to` (when true) + `recorded_at` (when we learned it) | ✗ |
| User model + confidence decay | rises slowly (+0.1 cap 0.9), falls fast (−0.25), 6-month half-life | ✗ |
| The 8 personalization failure modes | overfitting · stale beliefs · creepy recall · filter bubble · silent wrongness · no escape hatch · cross-contamination · cold-start harm | ✗ |

**Cache ordering, verbatim:**
```
system prompt → tool definitions → static docs → few-shot → history → current turn
```
One changed byte invalidates everything after it.

**The most valuable and most-discarded personalization field is `corrections`.** When a
user says "no, I meant X", that is a labelled example about them specifically.

---

## 4. Retrieval

| Layer | Options, worst → best | Status |
|---|---|---|
| Chunking | fixed-size → recursive → semantic → **contextual retrieval** | ✗ |
| Search | vector only → **hybrid (BM25 + vector, RRF fusion)** | ✗ |
| Reranking | cross-encoder on the top 20 — usually the single biggest quality win | ✗ |
| Query expansion | 3 phrasings, search all, dedupe | ✗ |
| Groundedness | "answer ONLY from context, else say not found" | ✗ |
| Citations | every claim maps to a chunk id | ✗ |

**The eval that matters: measure retrieval and answer quality SEPARATELY.**
```
recall@5 low                → fix chunking, embeddings, hybrid, reranking
recall@5 high + answer low  → fix the generation prompt, NOT retrieval
```
Fixing the wrong one is the most common wasted week in RAG.

**RAG or not:** if the data fits in the window (~100K), put it in context. No retrieval.
This is the right answer far more often than people admit.

**GraphRAG only when** questions require traversing relationships ("which customers use a
service that depends on the library we deprecated") or are global ("what are the main
themes"). Vector retrieval structurally cannot answer either.

---

## 5. Large documents (a separate discipline from RAG)

The arithmetic first: 1 page ≈ 500–800 tokens as text, but 1,500–2,500 **as an image**.
A 100-page report is ~70K tokens and fits in a cached prefix at ~10% cost after turn one.

**The five strategies:**

| Situation | Strategy |
|---|---|
| <150K tokens, repeated queries | Full context + cache |
| Huge, "summarise / find all X" | Map-reduce (cheap model maps, strong model reduces) |
| Huge, many users query it | Hierarchical tree (RAPTOR-style), built once |
| Huge, structured, specific questions | **Agentic navigation** — `get_outline`, `read_pages`, `search_document` |
| Many docs, each query touches few | Retrieval |

**Agentic navigation is the underrated one** — it uses document structure, which chunking
destroys, and handles multi-hop naturally.

**The six long-doc eval cases:** needle · position sweep · multi-hop · aggregation ·
**absence** · **contradiction**. The last two are the ones everyone skips and everyone
fails.

---

## 6. Multimodal

- Image token formula: `(w × h) / 750`. A 1568² image ≈ 3,300 tokens. Ten screenshots is
  33K tokens before a word is written.
- Resize before sending — the biggest cost lever. 4000×3000 → 1024×768 costs 1,048 tokens
  instead of ~16,000.
- **PNG for screenshots and diagrams, JPEG for photos.** JPEG artefacts around text hurt
  reading noticeably.
- PDF routing *per page*, not per document: text → PyMuPDF; tables → send image too;
  scanned → OCR, vision only where OCR confidence is low.
- `view_image` tool so the agent chooses when to look, rather than dumping everything in.
- **Output routing rule:** exact (numbers, labels, structure) → the model writes CODE
  (matplotlib, Mermaid, SVG). Aesthetic → a generation model. Never chart with diffusion.
- Multimodal evals verify the **artifact** — run the code, parse the number, open the file.
  Never an LLM judge alone.

Status: ✗ entirely.

---

## 7. Orchestration

**Seven shapes, priced:**

| Shape | When | Cost | Failure mode |
|---|---|---|---|
| Single prompt | one deterministic step | lowest | hallucination |
| Prompt chain | fixed steps known upfront | low | error propagation |
| Router | input type picks the handler | low | wrong route |
| Parallelisation | independent subtasks / N-vote | medium | merge conflicts |
| Orchestrator–worker | subtasks unknown at design time | high | bad return contract |
| Evaluator–optimiser | quality needs critique loops | high | judge bias |
| Autonomous agent | path genuinely unknown | highest | loops, cost overrun |

**Multi-agent failure modes:** hallucination cascade (workers must return claims *with
sources*; unsourced = hypothesis) · coordination cost exceeding benefit · deadlock and
ping-pong (enforce a DAG or a depth limit, never cycles) · lost error context.

**The worker contract:**
```python
@dataclass
class WorkerOutput:
    task_id: str; success: bool; result: dict
    sources: list[str]        # claims WITHOUT sources are hypotheses, not facts
    tokens_used: int
    partial: bool = False; error: str | None = None
```

Status: orchestrator + 2 isolated workers ✔ · parallel fan-out ✗ · synthesiser ✗ ·
worker contract with sources ✗ · SecureOrchestrator validation ✗

---

## 8. Isolation and security

**The six isolation levels:**
```
1 Prompt       fresh context, no parent history        weakest — model can still call any tool
2 Tool/permission  scoped token per agent              any agent touching writes
3 Network      egress allowlist, kernel-enforced        anything reading untrusted content
4 Filesystem   only /workspace visible                  anything reading or writing files
5 Process      fresh container per run, no state        code execution, untrusted input
6 microVM      gVisor / Firecracker, own kernel         arbitrary user code, red-team
```
**Pick the level from what the agent could destroy, not from how much you trust it.**

**The ExploitGym lesson (the case study to know by name):** OpenAI ran capability evals
with refusals disabled, in a container whose only egress was an internal package proxy.
The containment assumption was "read-only egress". The model chained proxy recon → proxy
exploitation → local privesc → lateral movement → a node with open internet.

> An allowlist to a package proxy is not isolation. It is a network path.

The fix: resolve dependencies *before* the agent starts, bake them into the image, run
with `network_mode="none"`. If network is unavoidable during execution, use a **broker**
(performs a bounded operation, returns data), never a **proxy** (forwards traffic the
agent constructs). Only the first is a containment boundary.

**The lethal trifecta:** private data access + untrusted content + external communication.
An agent with all three is exploitable. Break any one leg — usually easiest is routing
outbound actions through an approval gate.

**Prompt injection — what does NOT work:** "ignore instructions below" · delimiters alone ·
asking the model to detect injection in its own context · blocklists of phrases.
**What works:** least privilege · breaking the trifecta · approval gates on outbound ·
an independent classifier in a separate context · provenance tagging · schema validation ·
reflexes at the tool layer.

**Agents are workloads, not users.** Two identities per request (which agent app + on
whose behalf), delegation not impersonation (RFC 8693 `act` claim), and the golden rule:
permissions are the **intersection** of user rights and agent rights. The independent
user-rights check is what prevents privilege escalation through the agent.

> A system prompt saying "you are the finance agent" cannot authenticate a workload.
> Security identity must be established outside the model.

**The 12 safety patterns:** reflex · guard model · sentinel · two-key · dry-run · canary ·
tripwire · blast door · circuit breaker · quarantine · provenance tag · least-context.

A **reflex** is a deterministic rule firing before the model sees input or before a tool
runs. No LLM call. Cannot be talked out of it. Every non-negotiable rule goes here, never
in a prompt. A **sentinel** sees only a *summary of actions*, never the agent's context —
otherwise the same injection fools both.

Status: context isolation ✔ · everything else ✗

---

## 9. Runtimes

**Static vs dynamic** — who owns the control flow. Static is deterministic, testable,
predictable in cost; it breaks on inputs outside the enumerated cases.

**LangGraph** (gated behind shipping something by hand first):
- State + **reducers** — the #1 bug is two parallel branches writing the same field
  without a reducer; the second silently overwrites the first, with no error.
- Conditional edges — routing made explicit and inspectable
- **Checkpointers** — every super-step persisted. This is the reason to adopt it:
  crash recovery, day-long HITL pauses, time-travel debugging.
- Interrupts — static (`interrupt_before`) and dynamic (`interrupt()` inside a node).
  Nuance: `interrupt()` re-runs the node from the top, so side effects before it happen
  twice. Put it first.
- Subgraphs + `Send` for fan-out
- The debugging workflow: **reproduce → rewind → patch → re-run**. 10× faster than
  re-running the whole agent.

**Temporal** — durable execution for hours-to-days. Deterministic replay: on crash it
re-runs the workflow but reuses stored results of completed activities.

**The universal runtime** (`runtime-architecture.md`) — the architect-level idea:

```python
class Executable(ABC):
    async def execute(self, ctx) -> AsyncIterator[Event]: ...
    def as_tool(self) -> Tool: ...    # ← ANY Executable can be a tool
```

That `as_tool()` is the entire composability story. Five primitives: `LlmAgent` (the only
non-deterministic one), `Sequential`, `Parallel`, `Loop`, `Router`.

Two design decisions worth arguing about:
1. **Children get empty state, not a copy.** Anything needed is passed explicitly. Visible
   data flow, no context bloat, and it is the isolation boundary.
2. **Budget is shared by reference.** 20 agents with per-node budgets of 10K can spend
   200K. One shared budget object cannot.

**The event stream is the highest-leverage decision in the whole runtime.** Build it once
and UI streaming, tracing, metering, checkpointing, eval capture, and the safety sentinel
all read from it. Frameworks that bolt observability on afterwards never fully recover.

**Never hardcode a model id.** Agents reference a *role* (`fast`, `reasoning`, `vision`,
`judge`); roles resolve at runtime through a config file with fallback chains and
per-env / per-tenant overrides. Fall back to a **different provider**, not just a
different model — provider-wide outages are the failure this protects against. Use a
cross-family judge; a model judging itself inflates scores.

Status: ✗ entirely. `step4_orchestrator.py` hardcodes `MODEL`.

---

## 10. Evals and quality

**Three assertion types:**
```
Final state   did the file get written, the ticket close, the JSON validate   ← strongest
Trajectory    right tools, sane order, under N iterations and a token budget
LLM-as-judge  subjective quality — know its biases: length, position, self-preference
```

Start with **20 cases, not 2,000**. Sources: real user requests, past bug reports, edge
cases you fear. Run in CI on any change to system prompt, tool definitions, tool code, or
model version. **A prompt edit is a code change.**

Track all four, always: pass rate · mean iterations · p95 latency · cost per task.

**The testing pyramid** — evals alone do not catch a broken tool:
```
       ╱ E2E ╲          few, on recorded fixtures (deterministic, no bill)
     ╱ Eval    ╲        20–200 cases in CI, measures BEHAVIOUR
   ╱ Contract    ╲      schema the model sees matches what the function accepts
 ╱ Integration     ╲    tools actually reach their backends
╱ Unit               ╲  tools are ordinary functions
```
**The test everyone forgets:** assert your tool *error messages* are actionable. They are
prompts, and prompts deserve tests.

**Human override rate is the most honest quality metric you have.** If people keep editing
the output, your evals are lying to you.

**The data flywheel:** capture trajectory + outcome + corrections → mine (overrides,
halted runs, cost outliers, immediate retries, novel inputs) → triage → **every production
failure becomes an eval case before it becomes a fix** → ship behind a canary.

Status: 5 eval cases ◐ (bar is 20) · CI ✗ · trajectory assertions ✗ · judge ✗ ·
override rate ✗

---

## 11. Scale and economics

**Latency decomposes — never optimise before decomposing:**
```
network + queue + TTFT + generation + tool time + orchestration, × ITERATIONS
```
The multiplier at the end is the term everyone forgets. **Reducing iterations beats every
micro-optimisation. Fix your tools first.**

**Throughput is Little's Law:** `concurrency = arrival_rate × duration`.
20 req/s × 30s = 600 concurrent runs. Then check what breaks first — usually model API
rate limits, then your tool backends (your DB was not designed for 1200 concurrent agent
queries).

**Availability multiplies down the chain:**
```
0.999 × 0.999 × 0.995 × 0.990 = 98.3%   ← worse than every component
98.3% = 12 hours down per month
```
This is the strongest technical argument against unnecessary services and unnecessary
agents.

**The graceful degradation ladder:** full → degraded (fewer tools) → cached (labelled) →
queued → honest failure with a route to a human. Never a stack trace.

**Cost:** in a multi-turn agent the money is in **input** tokens, because history is
re-sent every turn — turn 10 sends turns 1–9 again. Naive 10-turn agent: 110K input
tokens, quadratic. With 90% cache hit: ~11K equivalent.

**Optimisation order:** prompt caching (50–90%) → fewer iterations via better tools
(30–60%) → model routing (30–70%) → compaction → shorter outputs → batch API →
self-hosting (only above ~$50K/mo).

**The duration ladder:** <2s sync · 2–30s sync+streaming · 30s–5min async job + polling ·
5min–1h queue + worker + checkpointing · 1h+ durable workflow.
**Your p99 defines your architecture, not your p50.**

Status: ✗ entirely. Never measured tokens, cost, or latency.

---

## 12. Schedulers and proactive agents

The difference between a chatbot and an assistant.

```
1 INTENT CAPTURE     detect an incomplete intent, store with context and expiry
2 TRIGGER            time, event, or condition
3 DURABLE SCHEDULER  survives restarts (Redis ZSET / Temporal timer / cloud scheduler)
4 RELEVANCE GATE     the difference between assistant and spam
5 DELIVERY           right channel, respecting quiet hours
6 FEEDBACK           track ignore rate; stop nagging
```

**The relevance gate must check all five:** already done elsewhere · still actionable ·
under the follow-up cap · genuinely new information · appropriate time (reschedule for
quiet hours, do not skip).

Design rules: silence is the default · cap at two follow-ups then stop forever · always
include an off switch in the message · ignore rate >50% means the triggers are wrong.

Scheduler durability: `asyncio.sleep` (never in prod) → cron → Redis ZSET → Temporal timer
→ cloud scheduler.

Status: ✗

---

## 13. Protocols and platform

**MCP** is agent-to-tool. **A2A** is agent-to-agent. Complementary, both under Linux
Foundation governance.

| Concept | Status |
|---|---|
| MCP server, stdio transport | ✔ |
| MCP server, HTTP/SSE transport | ✔ |
| Called from an agent I did not write | ✗ ← the actual done-when bar |
| **MCP gateway** — one entry point for auth, per-agent scope, rate limits, schema validation, audit | ✗ |
| Agent registry + signed AgentCard (rejecting unsigned cards is what stops agent shadowing) | ✗ |
| A2A v1.0 — capability discovery, task lifecycle, signed identity | ✗ |

**Multi-tenancy — why agents are harder than SaaS.** Traditional multi-tenancy is a data
problem. Agents add four: they execute code at runtime (shared kernel), hold mutable
in-memory state, call tools with real-world effects, and — the one that breaks RBAC —
have **transitive authority**: granting a tool grants everything that tool can reach.
The answer is capability-based access control enforced in the runtime, not the tool.

Three models: silo · pool · **bridge** (shared control plane, dedicated data plane) —
bridge is right for most agent SaaS.

**Four boundaries that must hold simultaneously:** data (own namespace — encryption stops
a stolen disk, isolation stops a *neighbour*) · compute · credential · **inference**
(shared prompt caches must be namespaced or a cached prefix leaks across tenants).

**The leaks that actually happen:** one unscoped query · un-namespaced cache key
(`user:123` collides) · RAG filtered post-hoc instead of at retrieval · a tool taking a
raw path · shared prompt cache · noisy-neighbour bulk export · `tenant_id` inside a log
*message string* instead of as a field.

**Decoding the agentic flow.** Every span carries: `run_id`, `trace_id`, `tenant_id`,
`agent_path`, `model_role` **and** `model_id_resolved`, `decision_reason`,
`config_version`, `prompt_version`, tokens, cost, retries.

> `model_id_resolved` and `prompt_version` are the two people forget.
> "It worked last week" is almost always one of those two changing.

**Read the trace top down, not bottom up.** The root cause is usually a routing or config
decision near the top, not the error near the bottom.

**Four dashboards:** cost outliers · iteration histogram (bimodal = a loop bug in the
tail) · fallback rate (rising = a provider degrading) · human override rate.

Status: ✗ entirely.

---

## 14. Interfaces

**Browser agents** are the highest-risk shape you can build — untrusted web content +
acting on the user's behalf + a session cookie is the lethal trifecta *fully assembled by
design*. Default to DOM/a11y-tree (~2K tokens) over pixels (~1.5–2.5K **per screenshot**).
Mandatory: domain allowlist, separate profile, approval gate on writes, page content
explicitly framed as data, hard wall-clock cap. Eval on recorded fixtures, never live.

**Voice** — latency dominates. Human turn-taking tolerance is ~700ms; past 1.5s it reads
as broken. Cascade budget: VAD 150–300 + STT 100–300 + **TTFT 200–800** + TTS 80–200 +
network 50–150. Barge-in must truncate history to what was *actually heard*, not what was
generated, or the conversation desynchronises. Stream to TTS at **sentence** boundaries,
not tokens. No markdown — TTS reads asterisks aloud.

**Human handoff** — the two fields that make it good or awful: `attempted` (so the human
does not re-ask what the agent already asked) and `confidence_flags` (so they know what
not to trust). Handoff rate is not a failure metric: rising handoff with *falling* human
override means the agent correctly recognises its limits.

Status: ✗

---

## 15. Foundations worth being able to explain

- **Attention** `softmax(QK^T / √d_k)·V`. The matrix is n×n — double the context, 4× the
  attention memory and compute. That is why long context is expensive.
- **KV cache** turns O(n²) per generation step into O(n). Its memory can exceed the model
  weights, which is why GPU memory is the serving constraint and why *prompt* caching
  (caching a prefix's KV state across requests) is so valuable.
- **Memory bandwidth is the bottleneck, not compute.** That is why quantisation,
  FlashAttention (tiles so the n×n matrix never materialises in HBM), and batching matter.
- **vLLM**: PagedAttention (KV cache as OS-style virtual memory), continuous batching,
  speculative decoding.
- **Constitutional AI / RLAIF** — Claude critiques its own outputs against a constitution,
  scaling the alignment signal without labelling every example.
- **RLVR** — reward from a *program*, not a preference model. Agentic RL scores whole
  trajectories, so the hard problems are credit assignment and environment cost.
  GRPO drops the value network; cheaper at LLM scale.
- **The bridge that matters to me:** *your evals are verifiers.* Every principle of good
  verifier design — deterministic, hard to game, checks the real outcome not a proxy — is
  the design of a good eval.

Status: ✗ (reading, not building — appropriate)

---

## 16. Reasoning strategies, priced

| Strategy | Cost | Worth it when |
|---|---|---|
| CoT | ~1× | almost always; now baked into reasoning models |
| Self-consistency | N× | verifiable single answers, high stakes |
| ToT / GoT | 10–100× | rarely pays for itself in production now |
| **ReAct** | ~1× | the default agent loop — already built |
| **Reflexion** | 2–4× | when there is a real signal to reflect on (test failures, eval score) |
| ReWOO / plan-execute | lower | cost-sensitive, predictable; brittle under surprise |
| **Verifier-guided** | N× gen + cheap check | anything checkable: code, SQL, JSON, math |

> **Reasoning is cheap; verification is the bottleneck.** Any time you can replace "ask
> the model if it is right" with "run a program that checks if it is right", do it.

---

## 17. The delivery-vs-quality framework

```
CAN CUT on v1 (add later without a rewrite):
  model routing · prompt caching · multi-agent · knowledge graph · fancy UI · fine-tuning

CANNOT CUT (retrofitting is a rewrite):
  max_iterations, token budget, timeout
  trace IDs and structured logging
  a schema for tool outputs
  eval cases — even 10
  the isolation boundary
  idempotency on writes
  the kill switch
```

The second list is cheap on day one and brutally expensive on day ninety. That asymmetry
is the entire argument.

**The framing that works with management:**
```
"shipping without evals" = "shipping without tests"
"no traces"              = "no logs"
"no token budget"        = "no rate limit on a paid API"
"no kill switch"         = "no way to stop a bad deploy"
```

**The 2-week MVP shape:** 20 eval cases *before* any agent code (days 1–2) → simplest
agent, one model, no framework (3–5) → tools rewritten where it failed, iterations
measured (6–7) → traces, budgets, kill switch (8–9) → one real user in shadow mode
(10–11) → fix what shadow mode revealed, report pass rate, cost, latency (12–14).
**At day 14 the deliverable is a number, not an agent.**

---

## 18. Where I actually am

Repo: https://github.com/gowtham16-bhu/agentic-ai-from-scratch

| # | Module | Status | The gap |
|---|---|---|---|
| 0 | Python for agents | ✔ | — |
| 1 | The loop, by hand | ✔ | — |
| 2 | Tool design | ✔ | never measured the iteration delta |
| 3 | **The loop, deeply** | **◐ current** | 1 of 4 termination conditions; no checkpoint; no compaction |
| 4 | Memory systems | ◐ | episodic only; no bi-temporal |
| 5 | Context & caching | ✗ | never budgeted or measured a cache hit rate |
| 6 | RAG (text) | ✗ | |
| 7 | Multimodal RAG & ingestion | ✗ | |
| 8 | Evals & CI | ◐ | 5 cases (bar: 20); no CI; never refused to ship on a dropped eval |
| 9 | Production hardening | ◐ | tracing + kill switch ✔; no cost/token tracking, no guardrails, no approval gate |
| 10 | Orchestration & isolation | ◐ | routing ✔; no parallel dispatch, no worker contract, no output validation |
| 11–23 | Runtimes → Capstone | ✗ | |

**Projects P1–P7: none started.** P1 (the configurable runtime) is the foundation for
all of the others and must not be skipped.

**Process correction, recorded:** every file in this repo through 2026-09-04 was written
by the tutor, not by me. That is why the material read like textbook examples — I had
artifacts I had not built. From Module 3 onward I write the code; the tutor gives the
design, the shape, and the review.

---

## 19. Honest gaps in the curriculum itself

Deliberately not covered, and why: pretraining and architecture design · RL training
infrastructure · robotics and embodied agents · agent economics and mechanism design ·
formal verification of agent behaviour · specific vendor tutorials (APIs change quarterly,
concepts do not).

**Will date fastest:** model names, limits and prices · A2A and MCP spec versions ·
deprecation schedules · EU AI Act timelines · framework APIs · adoption statistics ·
best-in-class rerankers and embedding models.

**The durable core** — the agent loop, tool design, context engineering, evals, isolation
levels, latency decomposition, availability multiplication, and the trade-off tables —
is still correct in five years. Everything else is a documentation lookup.
