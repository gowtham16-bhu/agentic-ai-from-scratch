# Chapter 46 — AI system design and interviews

> AI engineer and FDE interviews test whether you can **design a system that works for a real customer**, **write
> working code under time pressure**, and **show judgement and ownership** in your stories. This chapter gives you
> a 7-step design framework, five worked designs that reuse the whole book, back-of-envelope maths, behavioural
> stories in STAR form, and live coding drills.

**You will learn:** the interview formats; a **7-step AI system design framework**; back-of-envelope numbers
(load, concurrency, tokens, cost, storage); **five worked designs** (bank support agent, enterprise knowledge
assistant, document extraction pipeline, analytics agent over a warehouse, an internal agent platform with
gateway and registry); the **case/decomposition** interview; **STAR** stories for FDE roles; **live coding
drills** with a solved example and a "find the bugs" exercise; and the red flags interviewers watch for.

**Where this fits:** a review of the whole book under pressure. Each design step points back to its chapters.
Use it after Part 8 (or alongside the capstone, Ch 47). Appendix C has more practice questions.

> **About this chapter:** interview formats vary by company; this describes common patterns, not any specific
> company's process. The code in section 4 was run.

---

## 1. The idea in plain words

| Format | What they test | How to prepare |
|---|---|---|
| **AI system design** | Turning a vague problem into a sound, measurable, safe architecture | The 7 steps (3.1) and the five designs (3.3) |
| **Practical coding** | Building something real in 45–90 minutes (a RAG function, a tool loop, a rate limiter) or debugging code | Drills (section 4); type fast, test as you go |
| **Case / decomposition** | Structured thinking about a messy customer situation | 3.4: clarify → measure → hypothesize → prioritize |
| **Behavioural** | Ownership, ambiguity, customer handling, judgement | 5–8 STAR stories (3.5) |
| **Project deep-dive / demo** | Whether you really built what's on your CV | Your capstone (Ch 47): know every decision and number |
| **Customer role-play** (FDE) | Discovery, pushing back, explaining trade-offs to non-engineers | Ch 45's question bank |

---

## 2. Analogy

**An architect's site visit, not an exam.** Nobody expects a finished blueprint in 45 minutes. They watch how
you ask about the land, the budget and the people who'll live there; whether you choose the simplest building
that works; whether you think about fire exits; and whether you can explain the trade-offs to the client.

---

## 3. How it works

### 3.1 The 7-step AI system design framework

| Step | Questions to cover | Book |
|---|---|---|
| **1. Clarify** | Who are the users? What job? What volume, latency, languages? Constraints: privacy, residency, budget, regulation? What exists today? | Ch 45 |
| **2. Define success and evals** | Business metric, quality metric, severe-error definition, eval set and grading method, baseline. *Do this early.* | Ch 33 |
| **3. Simplest architecture that works** | Single call → workflow → agent → multi-agent, and why. Draw it. | Ch 13–14, 25 |
| **4. Data and knowledge** | Sources, ingestion, freshness, permissions. RAG vs vectorless vs graph vs SQL. Chunking, hybrid search, reranking | Ch 17–23 |
| **5. Models and tools** | Model roles (router, worker, judge), structured output, tool design, MCP, memory | Ch 08–11, 16, 29 |
| **6. Safety and reliability** | Guardrails, injection, permissions, approvals/HITL, fallbacks, retries, idempotency | Ch 12, 26, 35–36, 44 |
| **7. Production** | Scale and cost maths, latency budget, caching, serving, observability, rollout (shadow → canary), feedback loop | Ch 34, 37–39 |

Close with **trade-offs** ("I chose X over Y because…; if the volume grew 10×, I'd change…") and **what you'd
do in the first two weeks**. Timebox: about 5 minutes for step 1, 5 for step 2, 10 for steps 3–4, 10 for steps
5–6, 10 for step 7 and the wrap-up. Interviewers will steer you; follow them.

### 3.2 Back-of-envelope numbers

Say assumptions out loud; round aggressively; check orders of magnitude.

| Quantity | Rule of thumb |
|---|---|
| Tokens | ~0.75 English words per token; a page ≈ 500–700 tokens; an image ≈ 1–5K tokens (Ch 02, 41) |
| Requests per second | daily requests ÷ 86,400 × a peak factor (2–5×) |
| **Concurrency** (Little's law) | peak requests/s × seconds each request takes |
| LLM cost per day | (input tokens × input price + output tokens × output price), with a cache discount on stable prefixes (Ch 12, 37) |
| Latency | time-to-first-token + output tokens ÷ tokens per second, plus tool calls (Ch 03) |
| Vector storage | chunks × dimensions × bytes per dimension (4 float32, 1 int8, 1/8 binary) + index overhead (Ch 18) |
| Self-hosting | GPU memory = weights + KV cache; throughput from continuous batching (Ch 05, 39) |

Section 4.1 computes these for two of the designs below.

### 3.3 Five worked designs

Each is a condensed answer: what you'd say in an interview, with pointers to depth.

#### Design 1 — A customer-support agent for a retail bank

1. **Clarify**: web and app chat; 200K daily active users; account questions, card issues, disputes; EU data
   residency; regulator scrutiny; existing human team of 300.
2. **Success**: containment of tier-1 intents ≥ 40% with CSAT ≥ human baseline; **severe errors** (wrong
   account data, unauthorized action, bad financial advice) ≈ 0; p95 first token < 2 s. Eval set from 1,000
   historical chats per intent, graded by code checks plus a calibrated judge (Ch 33).
3. **Architecture**: a *workflow* with an agent inside it. Authenticate → classify intent (small model) → route:
   FAQ answer (RAG over policies), account lookups (read tools), actions (card freeze, dispute) as tools behind
   approvals or step-up authentication → human handoff for complaints, vulnerable customers and low confidence.
4. **Data**: policy documents with versions and effective dates (Ch 23), product terms; no training on customer
   data; account data only via tools scoped to *the authenticated customer* (never through retrieval).
5. **Models/tools**: a mid-size model for conversation, a small router, structured outputs for actions; tools
   with idempotency keys; the customer's identity bound in the tool layer, not the prompt (Ch 36).
6. **Safety**: input/output guardrails (PII, advice disclaimers), injection-resistant tool design, card freeze
   allowed automatically (safe, reversible) but disputes need confirmation; handoff object with `attempted`
   and `confidence_flags` (Ch 44); audit log of every action; kill switch.
7. **Production**: about 360K turns/day, about 12 rps at peak, about 50 concurrent requests (4.1); prompt
   caching cuts input cost substantially; EU region only through the gateway (Ch 32); tracing with PII
   redaction; shadow mode → 5% canary → ramp by intent; weekly failure triage. Model risk documentation for the
   bank's reviewers (Ch 45).

Trade-off to mention: *a single big agent vs intent-routed specialists*. Routing gives tighter tools per
intent and easier evals; the cost is the router's error rate, so measure it.

#### Design 2 — An enterprise knowledge assistant over 10M documents

1. **Clarify**: 30K employees; Confluence, SharePoint, Drive, tickets; answers with citations; strict
   permissions; 12 languages.
2. **Success**: answer correctness and **citation faithfulness** on 500 real questions; **zero permission
   leaks**; recall@10 of retrieval ≥ 0.9; p95 < 6 s.
3. **Architecture**: ingestion pipeline (connectors → parse → chunk by structure → embed → index with ACLs) +
   a query path (rewrite → hybrid search → rerank → grounded answer with citations). Agentic RAG only for
   multi-hop questions (Ch 18).
4. **Data**: incremental sync with content hashing and deletes (Ch 23); **ACLs stored per chunk and enforced
   as a filter at query time** for the asking user (Ch 23 `secure_search`); multilingual embeddings; tables
   and scanned PDFs need special parsing (Ch 21).
5. **Models**: embedding + reranker + a mid-size generator; a small model for query rewriting.
6. **Safety**: documents are untrusted (indirect injection: Ch 35); answers only from retrieved text;
   "not found" is allowed; sensitive collections excluded or restricted.
7. **Production**: ~200M chunks → ~820 GB of float32 vectors at 1024 dimensions; int8 quantization brings it to
   ~205 GB, binary to ~26 GB with a rescoring step (Ch 18, 4.1). Shard by collection or tenant; re-embed on
   model change as a planned migration; freshness SLO (e.g. 95% of edits searchable within 15 minutes).

Trade-off: *vector RAG vs vectorless / tree search (PageIndex-style)*. Vectors scale to millions of documents;
tree search shines on long, structured documents (contracts, filings). Combine: vector search to find the
documents, tree navigation inside them (Ch 19).

#### Design 3 — Invoice and claims extraction at volume

1. **Clarify**: 500K documents/month, PDFs and phone photos, 40 vendors' layouts, extraction into the ERP;
   errors cost money.
2. **Success**: field-level accuracy per field (amount, date, vendor, line items), **straight-through
   processing rate** (no human touch) at a fixed error budget, cost per document.
3. **Architecture**: a *pipeline, not an agent*: classify → page routing (text layer vs VLM, Ch 21) → extract
   with a schema (Ch 10) → **validate with invariants** (line items sum to total, vendor in master data, PO
   matches; Ch 41) → auto-post or human review queue.
4. **Data**: vendor master data and PO system as ground truth; human corrections feed the eval set and
   possibly a fine-tune later (Ch 40).
5. **Models**: a small model for the common layouts, a bigger VLM for hard pages (a cascade, Ch 37); batch API
   pricing where latency doesn't matter.
6. **Safety**: invariant checks are the guardrail; duplicates detected (the same invoice twice); fraud signals
   to humans; no auto-posting above an amount threshold.
7. **Production**: a queue with workers and autoscaling on queue depth (KEDA, Ch 38), idempotent posting,
   per-vendor accuracy dashboards; review UI showing the cropped source region next to each field (Ch 44).

Trade-off: *accuracy vs straight-through rate*. Tune per-field confidence thresholds on the eval set to hit the
customer's error budget.

#### Design 4 — A natural-language analytics agent over a data warehouse

1. **Clarify**: business users ask questions of a warehouse with 2,000 tables; answers as numbers and charts;
   must match the finance team's official definitions.
2. **Success**: execution accuracy (results match a gold query's results) on 300 real questions; zero
   unauthorized data access; "I can't answer that reliably" when unsure.
3. **Architecture**: question → retrieve relevant tables and **certified metric definitions** (a semantic
   layer) → generate SQL → validate (read-only, allowed tables, row limits, cost estimate) → execute → answer
   + chart rendered *by code* (Ch 41) + the SQL shown for transparency.
4. **Data**: schema descriptions, sample values, a glossary of business terms, a library of verified queries
   used as few-shot examples (Ch 19 text-to-SQL).
5. **Models**: a strong model for SQL generation; a self-check that re-reads the question and the result.
6. **Safety**: a read-only role, row-level security enforced by the database for the asking user, query
   timeouts, a cost cap; no DDL/DML ever (Ch 19 validator).
7. **Production**: cache frequent questions; log every query with the user; usage by team; a feedback button
   that sends wrong answers to the analytics team to fix definitions.

Trade-off: *free-form SQL vs a semantic layer*. Free-form covers more questions but drifts from official
numbers; the semantic layer is safer and consistent. Use the semantic layer for metrics and free-form for
exploration, with a visible warning.

#### Design 5 — An internal agent platform for a 20-team company

1. **Clarify**: 20 teams are building agents separately: duplicated integrations, no cost control, security is
   worried, nobody knows which agents exist.
2. **Success**: time to ship a new agent; % of LLM traffic through the platform; cost visibility per team;
   security incidents; reuse of tools.
3. **Architecture**: an **LLM gateway** (virtual keys, model aliases, budgets, rate limits, fallbacks, logging;
   Ch 32), an **MCP gateway** in front of approved tool servers (allowlists, approvals, audit), an **agent and
   tool registry** (owners, versions, signatures, lifecycle, dependents; Ch 31), shared **evals and tracing**
   (Ch 33–34), and templates with guardrails built in.
4. **Data**: shared retrieval services with per-team ACLs; a memory service with tenant isolation (Ch 16).
5. **Models**: a catalogue of approved models by role; changes rolled out through gateway aliases after evals.
6. **Safety**: central policy (PII redaction, egress allowlists, prompt-injection defences), per-agent
   permissions as the intersection of user and agent permissions (Ch 36), kill switches per agent.
7. **Production**: the gateway is critical infrastructure: HA, multi-region, latency overhead < 20 ms;
   chargeback per team; deprecation policy for models and tools; A2A for agent-to-agent calls where teams need
   them (Ch 30).

Trade-off: *platform control vs team speed*. Make the paved road the easiest path (templates, SDKs, free
evals) rather than mandating it.

### 3.4 The case / decomposition interview

Prompt: *"A logistics customer says the agent you deployed 'stopped working' last week. Go."*

1. **Clarify the symptom**: what exactly? (wrong answers, slow, errors, low usage). Since when? For whom
   (all users, one region, one intent)?
2. **Check what changed**: deploys, prompt versions, model alias changes (Ch 32), data source changes, traffic
   mix, upstream APIs.
3. **Measure**: dashboards (Ch 34) for errors, latency, tool failures and eval scores on live samples; compare
   before and after.
4. **Hypothesize and test the most likely, cheapest first**: e.g. the carrier API changed its date format →
   the tool returns errors → the agent apologises.
5. **Mitigate, then fix**: roll back or fall back; communicate status to the customer; add a regression eval and
   an alert so it can't recur silently.
6. **Write it up**: a short blameless post-incident note (incident response: Ch 35).

Structure beats speed: interviewers want to see you narrow the space, not guess.

### 3.5 Behavioural interviews: STAR stories

**STAR** = **S**ituation (2 sentences), **T**ask (your responsibility), **A**ction (what *you* did, the
largest part), **R**esult (numbers, plus what you learned). Two minutes per story.

Prepare 6–8 stories that cover the themes FDE and AI-engineer interviews probe:

| Theme | Prompt you'll hear |
|---|---|
| Ownership | "Tell me about something that went wrong that you fixed, even though it wasn't your job." |
| Ambiguity | "A time requirements were unclear." |
| Customer conflict | "A time a customer wanted something you thought was wrong." |
| Failure | "A project that failed. What would you do differently?" |
| Influence | "Convincing people without authority." |
| Speed vs quality | "When did you ship something imperfect, and how did you manage the risk?" |
| Learning fast | "A technology you had to learn quickly." |
| Saying no | "When did you push back on scope?" |

Example (built from the capstone, so it's true for you):

> **S**: My support-agent capstone answered return questions well in demos, but on a 300-case eval it scored
> 71%, and most failures were gift returns. **T**: I owned getting it to the 85% bar I had set. **A**: I traced
> the failures and found two policy documents that contradicted each other, so retrieval returned both. I
> wrote down which source wins (newest effective date), added effective-date metadata and filtering, and added
> 20 gift-return cases to the eval set. I also stopped the agent from answering when sources conflicted and had
> it hand off with a confidence flag instead. **R**: 71% → 87%, with zero severe errors on the new cases.
> Learned: most "model problems" are data problems; read the traces first.

Rules: say "I" for your actions; use numbers; include what you learned; never invent stories, because deep
follow-up questions find out quickly.

### 3.6 Red flags interviewers watch for

- Jumping to multi-agent or fine-tuning before a single call or workflow is tried.
- No eval plan, or "we'll test it manually".
- Ignoring cost and latency until asked.
- No failure modes, no human fallback, no security.
- Buzzwords without mechanisms ("we'll use RAG" without chunking, retrieval quality or permissions).
- Not asking a single clarifying question.
- Arguing with the interviewer's constraints instead of designing within them.

---

## 4. Code

### 4.1 Back-of-envelope calculator (runs anywhere)

```python
# envelope.py — back-of-envelope numbers for an AI system design interview (say assumptions out loud)
def llm_load(daily_users, convs_per_user, turns_per_conv, input_tokens_per_turn, output_tokens_per_turn,
             peak_factor=3.0, latency_s=4.0, price_in=1.0, price_out=5.0, cache_hit=0.7, cache_read_mult=0.1):
    turns_per_day = daily_users * convs_per_user * turns_per_conv
    avg_rps = turns_per_day / 86_400
    peak_rps = avg_rps * peak_factor
    concurrency = peak_rps * latency_s                          # Little's law: in-flight = arrival rate x time in system
    tin, tout = turns_per_day * input_tokens_per_turn, turns_per_day * output_tokens_per_turn
    effective_in = tin * (1 - cache_hit) + tin * cache_hit * cache_read_mult   # cached prefix billed at ~10%
    cost_day = effective_in / 1e6 * price_in + tout / 1e6 * price_out
    return {"turns/day": f"{turns_per_day:,.0f}", "avg rps": round(avg_rps, 1), "peak rps": round(peak_rps, 1),
            "peak concurrency": round(concurrency), "input Mtok/day": round(tin / 1e6),
            "output Mtok/day": round(tout / 1e6), "$ per day": round(cost_day), "$ per turn": round(cost_day / turns_per_day, 4)}

def vector_storage(chunks, dims, bytes_per_dim):
    return chunks * dims * bytes_per_dim / 1e9                  # GB, vectors only (no index overhead, no text)

if __name__ == "__main__":
    print("Bank support agent: 200k daily users, 0.3 convs each, 6 turns, 6k in / 300 out tokens per turn")
    for k, v in llm_load(200_000, 0.3, 6, 6_000, 300).items():
        print(f"  {k:<18}{v}")
    print("Knowledge assistant: 10M docs x 20 chunks = 200M chunks")
    for name, dims, b in [("float32, 1024 dims", 1024, 4), ("int8, 1024 dims", 1024, 1), ("binary, 1024 dims", 1024, 1 / 8)]:
        print(f"  {name:<20}{vector_storage(200e6, dims, b):>8,.0f} GB")
```

Output:

```text
Bank support agent: 200k daily users, 0.3 convs each, 6 turns, 6k in / 300 out tokens per turn
  turns/day         360,000
  avg rps           4.2
  peak rps          12.5
  peak concurrency  50
  input Mtok/day    2160
  output Mtok/day   108
  $ per day         1339
  $ per turn        0.0037
Knowledge assistant: 10M docs x 20 chunks = 200M chunks
  float32, 1024 dims       819 GB
  int8, 1024 dims          205 GB
  binary, 1024 dims         26 GB
```

Prices are example values (Ch 03). The point is the *shape*: input tokens dominate (the context is re-sent every
turn), so caching and context size are the big cost levers.

### 4.2 Live coding drill (solved): a per-tenant rate limiter

Time yourself: 25 minutes, including tests. Then compare.

```python
# token_bucket.py — drill: a per-tenant rate limiter (asked in gateway / platform interviews, Ch 32)
import time

class TokenBucket:
    def __init__(self, rate_per_s, capacity, clock=time.monotonic):
        self.rate, self.capacity, self.clock = rate_per_s, capacity, clock
        self.tokens, self.last = float(capacity), clock()

    def allow(self, cost=1.0):
        now = self.clock()
        self.tokens = min(self.capacity, self.tokens + (now - self.last) * self.rate)   # refill since last call
        self.last = now
        if self.tokens >= cost:
            self.tokens -= cost
            return True
        return False

class Limiter:
    """One bucket per tenant; cost can be 'tokens' instead of requests (LLM gateways limit both)."""
    def __init__(self, rate_per_s, capacity, clock=time.monotonic):
        self.args, self.buckets = (rate_per_s, capacity, clock), {}

    def allow(self, tenant, cost=1.0):
        bucket = self.buckets.setdefault(tenant, TokenBucket(*self.args))
        return bucket.allow(cost)

if __name__ == "__main__":
    t = [0.0]
    lim = Limiter(rate_per_s=2, capacity=5, clock=lambda: t[0])           # fake clock = deterministic test
    burst = [lim.allow("acme") for _ in range(7)]
    assert burst == [True] * 5 + [False] * 2, burst                        # burst up to capacity, then throttled
    assert lim.allow("globex")                                             # tenants are isolated
    t[0] += 1.0                                                            # one second later: 2 tokens refilled
    assert [lim.allow("acme") for _ in range(3)] == [True, True, False]
    t[0] += 100
    assert sum(lim.allow("acme") for _ in range(10)) == 5                  # refill is capped at capacity
    assert not lim.allow("acme", cost=6)                                   # a request bigger than the bucket never fits
    print("all token-bucket tests passed")
```

Output:

```text
all token-bucket tests passed
```

What interviewers notice: an injectable clock (so tests are deterministic), isolation between tenants, a
capped refill, and the edge case of a request larger than the bucket.

### 4.3 Drill: find the bugs

Find at least six problems in this agent loop before reading the answers in section 8 (question 8).

```python
# buggy_agent.py — drill: find at least 6 problems in this agent loop (answers in section 8 of the chapter)
import json
import ollama

TOOLS = {"refund": lambda order, amount: f"refunded {amount} on {order}",
         "lookup": lambda order: json.dumps({"order": order, "status": "delivered"})}

def run(task):
    messages = [{"role": "user", "content": task}]
    while True:
        r = ollama.chat(model="llama3.2", messages=messages, tools=list(TOOLS.values()))
        if not r.message.tool_calls:
            return r.message.content
        for call in r.message.tool_calls:
            fn = TOOLS[call.function.name]
            for attempt in range(3):
                try:
                    result = fn(**call.function.arguments)
                    break
                except Exception:
                    continue
            messages.append({"role": "user", "content": result})
```

### 4.4 More drills (45–60 minutes each)

1. Hybrid retrieval: BM25 + embeddings + RRF over 50 documents, with recall@5 on 10 questions (Ch 17).
2. A structure-aware chunker for Markdown that keeps headings as metadata (Ch 17).
3. `with_retries(fn)`: exponential backoff with full jitter, a deadline, and retrying only retryable errors
   (Ch 12).
4. A tool-calling loop with max steps, tool errors returned to the model, and a cost budget (Ch 11, 14).
5. JSON-output repair: validate with Pydantic, re-ask with the error once, then fail cleanly (Ch 10).
6. `pass_at_k` and `pass_hat_k` from n samples with c successes, plus a bootstrap CI (Ch 33).
7. An SSE stream parser that yields text deltas and tool-call events (Ch 12, 44).
8. A groundedness checker: every quoted span must appear in the sources (Ch 07).
9. A safe SQL validator: SELECT only, allowed tables, a LIMIT added (Ch 19).
10. An LRU cache for embeddings keyed by (model, text hash) with hit-rate stats (Ch 37).

All ten are built somewhere in this book. Do them **from a blank file**, then compare with the chapter.

---

## 5. Production view (how interviews map to the job)

| Interview signal | Why it matters on the job |
|---|---|
| Clarifying questions first | Discovery is half of FDE work (Ch 45) |
| Evals defined early | Pilots are won and lost on agreed metrics |
| Simplest architecture | Agents are costly to run and debug; workflows ship |
| Cost and latency maths | Customers' finance teams will do it if you don't |
| Security and HITL by default | Security reviews gate every enterprise deployment |
| Clear trade-off language | Customers make decisions from your memos |
| Working, tested code fast | MVPs in two weeks |
| Honest stories with numbers | Trust with customers is built the same way |

---

## 6. Common mistakes

- Starting to draw boxes before asking who the users are.
- Designing the happy path only.
- Naming tools and vendors instead of explaining mechanisms.
- Over-engineering: multi-agent, fine-tuning and a knowledge graph for a FAQ bot.
- Running out of time before production concerns (cost, latency, rollout).
- Coding without tests or without running the code.
- STAR stories where "we" did everything and the result has no number.

---

## 7. Practice

**Level 1**
1. Use `envelope.py` for Design 3: 500K documents/month, 3 pages each, ~1,500 tokens per page image, 400 output
   tokens per document. What does a month cost at the example prices, and what does a 50% batch discount
   change?
2. Write three STAR stories from your own work (any field) using the template.

**Level 2**
3. Do drills 1, 3 and 4 from a blank file, 45 minutes each, then compare with Ch 17, 12 and 14.
4. Design a **voice appointment-booking agent for a chain of 200 clinics** using the 7 steps (Ch 42 for voice,
   Ch 36 for health data). Record yourself explaining it in 30 minutes.

**Level 3**
5. Run three mock interviews with a friend or an LLM acting as the interviewer: one design (pick from 3.3 but
   change a constraint, e.g. on-prem only), one case (3.4) and one behavioural. Ask for written feedback against
   the red-flag list.

---

## 8. Check yourself

1. List the 7 steps of the design framework.
2. Why define evals in step 2, before the architecture?
3. What is Little's law, and how do you use it in an AI design?
4. In Design 2, where are permissions enforced and why there?
5. Why is Design 3 a pipeline and not an agent?
6. What does the semantic layer protect against in Design 4?
7. What does STAR stand for, and which part should be longest?
8. Name at least six problems in `buggy_agent.py`.

<details>
<summary>Answers</summary>

1. Clarify → success and evals → simplest architecture → data and knowledge → models and tools → safety and
   reliability → production (scale, cost, latency, observability, rollout).
2. Success criteria shape every later choice (model size, retrieval design, human review), and they're what the
   customer will judge the system by.
3. Concurrency = arrival rate × time in system. Peak requests/s × request latency gives how many requests are
   in flight, which sizes workers, connection pools, rate limits and GPU batches.
4. As a filter at query time, using ACLs stored with each chunk and the identity of the asking user, so no
   unauthorized text ever reaches the model. The model can't be trusted to enforce permissions.
5. The steps are known and fixed (classify → extract → validate → post), so a deterministic pipeline is cheaper,
   faster, easier to test and to audit; LLMs are used inside steps, not to decide the flow.
6. Numbers that differ from the official definitions (e.g. two ways to compute "revenue"), keeping answers
   consistent with finance.
7. Situation, Task, Action, Result. The Action, because it shows what you did.
8. Any six: (1) `while True` with no step or cost limit; (2) the assistant message with the tool calls is
   never appended to history; (3) tool results are added with role `user` instead of `tool`, which also
   gives tool output user-level authority; (4) an unknown tool name raises `KeyError` instead of returning an
   error to the model; (5) the non-idempotent `refund` is retried up to 3 times on any exception (double
   refunds); (6) if all attempts fail, `result` is undefined or stale from a previous call; (7) no approval or
   limits on the refund (a write tool runs directly); (8) tool arguments aren't validated; (9) lambdas as
   tools have no names or docstrings, so the SDK can't build useful schemas and every tool looks like
   `<lambda>`; (10) no system prompt, timeout or tracing.

</details>

---

## 9. Key terms

**AI system design** · **7-step framework** · **back-of-envelope** · **Little's law** · **peak factor** ·
**containment rate** · **straight-through processing** · **semantic layer** · **execution accuracy** · **paved
road (platform)** · **case interview** · **STAR** · **live coding drill** · **red flags**

Next: [Part 11 — Chapter 47: Capstone →](../part11-capstone/47-capstone.md)
