# Chapter 37 — Cost and performance

> Most agent cost and latency problems are not solved by a faster GPU or a cheaper model. They're
> solved by **sending fewer tokens, fewer times**: cache the stable prefix, cut iterations with better
> tools, route easy work to cheaper models, and only then optimize the rest. **Never optimize before
> you decompose.**

**You will learn:** latency decomposition (and the iterations multiplier), cost per successful task, the
**optimization order** (caching → fewer iterations → routing/cascades → compaction → shorter outputs → batch
→ self-hosting), effort/thinking tuning, all the caching layers, model routing and cascades with confidence
signals, streaming and parallelism for perceived latency, distillation, and FinOps (attribution, budgets,
unit economics, pricing).

**Where this fits:** builds on cost/latency basics (Ch 03), KV/prompt caching (Ch 05, 12), tool design
(Ch 11), the agent loop (Ch 14), context engineering (Ch 15), model choice (Ch 08), reasoning effort (Ch 24),
gateways (Ch 32) and observability (Ch 34). Scale and capacity planning are Ch 38; self-hosting economics
are Ch 39; distillation by fine-tuning is Ch 40.

---

## 1. The idea in plain words

**Latency decomposes:**

```
agent latency ≈ (network + queue + TTFT + output_tokens / speed + tool time + orchestration) × ITERATIONS
```

The multiplier at the end is the term everyone forgets. Going from 8 iterations to 4 halves latency *and*
roughly halves cost — far more than shaving output tokens.

**Cost decomposes:**

```
cost per task = Σ calls (uncached input × p_in + cached input × p_cached + output × p_out)
cost per SUCCESSFUL task = cost per task ÷ success rate          ← the number that matters
```

A cheaper model that fails more (or needs more iterations/retries) can cost *more* per successful task.

---

## 2. Analogy

**Reducing a delivery company's costs.** You don't start by buying slightly cheaper fuel. You first stop
driving the same route twice (caching), plan routes so each driver makes fewer trips (fewer iterations),
send small parcels by bicycle instead of truck (routing), and only then negotiate fuel prices (cheaper
tokens). And you measure cost per *delivered* parcel, not per kilometre.

---

## 3. How it works

### 3.1 The optimization order

| # | Lever | Typical impact | Notes |
|---|---|---|---|
| 1 | **Prompt caching** (Ch 12) | Large cut on input cost (often 50–90%) and TTFT | Free if your prompt is cache-friendly; verify hit rate |
| 2 | **Fewer iterations** via better tools (Ch 11, 14) | 30–60% on cost and latency | Clear descriptions, actionable errors, returning the useful slice, closure signals |
| 3 | **Effort / reasoning tuning** (Ch 24) | Large on reasoning models | Lower effort for easy routes; measure before building a cascade |
| 4 | **Model routing / cascades** | 30–70% | Cheap model for easy cases, escalate the rest |
| 5 | **Context compaction / clearing** (Ch 15) | Grows with conversation length | Rare, big compactions — they reset the cache |
| 6 | **Shorter outputs** | Output is expensive and slow | Concise formats, structured output, `max_tokens` sized right |
| 7 | **Batch APIs** (Ch 12) | Often ~50% for async work | Evals, backfills, nightly jobs |
| 8 | **Self-hosting** (Ch 39) | Can win at large, steady volume | Only after the above; include GPU, ops and people costs |

A pragmatic note from provider guidance: before building a multi-model cascade, try the **most capable
model at a lower effort setting** — it often matches older models at high effort, and one model keeps one
prompt cache (caches are per model, so cascades lose cache reuse across models).

### 3.2 Caching layers

| Cache | Key | Saves | Risk |
|---|---|---|---|
| **Prompt (prefix) cache** | Exact prompt prefix (provider-side) | Input cost, TTFT | Silent invalidators (Ch 12) |
| **Exact response cache** | Tenant + model + normalized request (deterministic settings) | Whole calls | Stale answers; tenant leaks if not namespaced |
| **Semantic response cache** | Embedding similarity of the request | Whole calls for paraphrases | Wrong answers for subtly different questions (Ch 32) |
| **Embedding cache** | Text hash + embedding model | Embedding calls | Model change → invalidate (Ch 23) |
| **Tool result cache** | Tool + args (+ TTL) | Slow/expensive tool calls | Staleness; per-user data must be scoped |
| **Retrieval cache** | Query + tenant + ACL scope + index version (Ch 23) | Search latency | Permission leaks if scope missing |

### 3.3 Routing and cascades

- **Rule routing:** obvious cases by rules (order-status questions → small model + `get_order`).
- **Classifier routing:** a small model or trained classifier picks the model (Ch 13).
- **Cascade:** run the cheap model first; check a **confidence signal**; escalate to the strong model if low.
  Confidence signals: verifier passes (best, Ch 24), self-consistency agreement, logprobs (Ch 04), a
  calibrated judge.
- **Learned routers** (research such as RouteLLM) predict which model a query needs from data.

Tune the escalation threshold on your eval set: it's a dial between cost and accuracy.

### 3.4 Latency: what users feel

- **Stream** the answer (TTFT is what users notice first).
- **Parallel tool calls** for independent lookups (Ch 11).
- **Speculative work:** start likely retrieval or tool calls while the model is still deciding; discard if unused.
- **Prefetch** user context (profile, recent orders) at session start.
- **Smaller, stable prompts** and fewer tools → faster prefill and better caching.
- Pick the execution model by **p99** (Ch 26 duration ladder): long tasks go async with progress updates.
- Product-specific budgets: voice needs sub-second responses (Ch 42); chat tolerates a few seconds with
  streaming; back-office agents can take minutes.

### 3.5 Distillation

For a high-volume, narrow task (classify tickets, extract fields), fine-tune a **small** model on outputs of a
**large** model (plus human corrections), then serve the small one (Ch 39–40). Large cost and latency cuts —
but only with a solid eval set proving quality holds.

### 3.6 FinOps for AI

- **Attribution:** cost per tenant, feature, agent, model — from spans and gateway logs (Ch 32, 34).
- **Budgets and alerts:** per key/team/tenant; anomaly alerts on cost outliers (a loop can burn a monthly
  budget overnight).
- **Unit economics:** cost per resolved ticket / processed document vs the human or legacy cost — the slide your
  customer's VP cares about (Ch 03, 45).
- **Pricing your product:** per seat, per usage (tokens/tasks), or per **outcome** (per resolved ticket). Know your
  cost per successful task and its variance before choosing.
- **Forecasting:** expected tasks × tokens per task × prices (+ growth, + caching assumptions), validated against
  real traffic monthly.

---

## 4. Code

### 4.1 Latency decomposition, a confidence cascade, and a savings what-if

```python
# perf_cost.py — latency decomposition, a confidence-based cascade, and a savings what-if (offline)
import random

# 1) LATENCY DECOMPOSITION: where does an agent's time go?
def agent_latency(iterations, network=0.08, queue=0.05, ttft=0.6, out_tokens=150, tok_per_s=60,
                  tool_s=0.4, orchestration=0.02):
    per_iter = network + queue + ttft + out_tokens / tok_per_s + tool_s + orchestration
    return iterations * per_iter, per_iter

for iters in (8, 4):
    total, per = agent_latency(iters)
    print(f"{iters} iterations x {per:.2f}s = {total:.1f}s")
print(f"halving output tokens at 8 iterations: {agent_latency(8, out_tokens=75)[0]:.1f}s  "
      f"(fewer iterations beat micro-optimizations)\n")

# 2) CASCADE: cheap model first; escalate only when not confident
rng = random.Random(1)
CHEAP = {"cost": 0.0004, "acc_easy": 0.97, "acc_hard": 0.55}
STRONG = {"cost": 0.0060, "acc_easy": 0.99, "acc_hard": 0.90}
def run_cascade(n=10_000, hard_share=0.25, threshold=0.8):
    cost = correct = escalated = 0
    for _ in range(n):
        hard = rng.random() < hard_share
        cheap_right = rng.random() < CHEAP["acc_hard" if hard else "acc_easy"]
        # confidence signal (e.g. self-consistency agreement or logprob): lower on hard/wrong answers
        confidence = rng.uniform(0.85, 1.0) if cheap_right and not hard else rng.uniform(0.4, 0.95)
        cost += CHEAP["cost"]
        if confidence < threshold:
            escalated += 1
            cost += STRONG["cost"]
            correct += rng.random() < STRONG["acc_hard" if hard else "acc_easy"]
        else:
            correct += cheap_right
    return cost / n, correct / n, escalated / n

strong_only = (STRONG["cost"], 0.75 * STRONG["acc_easy"] + 0.25 * STRONG["acc_hard"])
print(f"strong model only: ${strong_only[0]:.4f}/task, accuracy {strong_only[1]:.1%}")
for th in (0.7, 0.8, 0.9):
    c, a, e = run_cascade(threshold=th)
    print(f"cascade threshold {th}: ${c:.4f}/task, accuracy {a:.1%}, escalated {e:.0%}")

# 3) WHAT-IF: apply levers in the recommended order to a monthly bill
bill = {"input": 18_000.0, "output": 6_000.0}            # USD/month, multi-turn agent (input-heavy)
steps = [("prompt caching (70% of input cached at ~10% price)", lambda b: {**b, "input": b["input"] * (0.3 + 0.7 * 0.1)}),
         ("better tools: 30% fewer iterations", lambda b: {k: v * 0.7 for k, v in b.items()}),
         ("route 60% of traffic to a 5x cheaper model", lambda b: {k: v * (0.4 + 0.6 / 5) for k, v in b.items()}),
         ("shorter outputs (-25% output tokens)", lambda b: {**b, "output": b["output"] * 0.75})]
print(f"\nbaseline: ${sum(bill.values()):,.0f}/month")
for name, apply in steps:
    bill = apply(bill)
    print(f"  after {name:52s} ${sum(bill.values()):,.0f}")
```

Verified output:

```
8 iterations x 3.65s = 29.2s
4 iterations x 3.65s = 14.6s
halving output tokens at 8 iterations: 19.2s  (fewer iterations beat micro-optimizations)

strong model only: $0.0060/task, accuracy 96.7%
cascade threshold 0.7: $0.0013/task, accuracy 92.1%, escalated 15%
cascade threshold 0.8: $0.0016/task, accuracy 93.9%, escalated 20%
cascade threshold 0.9: $0.0034/task, accuracy 96.5%, escalated 49%

baseline: $24,000/month
  after prompt caching (70% of input cached at ~10% price)   $12,660
  after better tools: 30% fewer iterations                   $8,862
  after route 60% of traffic to a 5x cheaper model           $4,608
  after shorter outputs (-25% output tokens)                 $4,062
```

Read the cascade rows as a menu: at threshold 0.9 you keep almost all the accuracy for ~57% of the cost; at 0.7
you save more but lose 4–5 points. Which is right depends on the cost of a wrong answer — a business decision,
informed by these numbers.

(The numbers are a simulation with made-up accuracies and prices — replace them with measurements from your own
evals and current price sheets.)

---

## 5. Production view

| Metric | Target behaviour |
|---|---|
| Cost per successful task (by route, tenant) | Flat or falling over time |
| Cache hit ratio (prompt cache) | High and stable; drops after deploys = invalidator |
| Iterations per task (p50, p95) | Falling as tools improve; no bump at the cap |
| Escalation rate in cascades | Stable; rising = traffic got harder or cheap model regressed |
| p95 TTFT and total latency | Within product SLOs |
| Cost anomalies | Alerts within minutes, not at month-end |

---

## 6. Common mistakes

- Optimizing per-token price while iterations and input tokens dominate.
- Switching to a cheaper model without measuring success rate (cost per *successful* task goes up).
- Building a cascade that destroys prompt-cache reuse and saves nothing.
- Semantic caching of personalized answers.
- Ignoring output length (and reasoning tokens) in latency budgets.
- Self-hosting to "save money" before caching and routing are done.

---

## 7. Practice

**Level 1**
1. Run `perf_cost.py`. Change `tool_s` to 2.0 seconds. Which lever matters most now?
2. In the what-if, reorder the steps. Does the final bill change? Does the *size of each step's saving* change?

**Level 2**
3. Measure your real agent (Ch 14 + tracing from Ch 34): per-iteration breakdown of TTFT, generation, tool time.
   Identify the biggest term and fix it. Report before/after p50 and p95.
4. Build a real cascade: `llama3.2` first with a self-consistency confidence (3 samples, agreement); escalate to a
   stronger local model (or hosted) when agreement < 2/3. Measure cost (tokens) and accuracy vs strong-only on 30
   cases.

**Level 3**
5. Write a one-page **cost model** for a customer pilot: traffic forecast, tokens per task (measured), prices
   (current), caching assumptions, cascade share, cost per successful task, monthly cost with ±30% sensitivity, and
   the break-even vs human handling. This is a standard FDE deliverable (Ch 45).

---

## 8. Check yourself

1. Write the latency decomposition formula and name the forgotten term.
2. Why is "cost per successful task" better than "cost per token"?
3. List the optimization order.
4. What does a cascade need to work well?
5. Why might a cascade *increase* cost compared to one model at lower effort?
6. Name four caching layers and one risk of each.

<details>
<summary>Answers</summary>

1. (network + queue + TTFT + generation + tool time + orchestration) × iterations — the iterations multiplier.
2. It includes failures, retries and extra iterations; a cheap model that fails more can be more expensive per
   success.
3. Prompt caching → fewer iterations (better tools) → effort tuning → routing/cascades → compaction → shorter
   outputs → batch APIs → self-hosting.
4. A reliable confidence signal (ideally a verifier), a threshold tuned on evals, and a cheap model that handles a
   large share of traffic well.
5. Caches are per model, so splitting traffic loses cache reuse; escalations pay for two calls; and a strong
   model at low effort may already be cheap enough.
6. Prompt cache — silent invalidators; exact response cache — staleness/tenant leaks; semantic cache — wrong
   answers to similar questions; tool/retrieval caches — stale or permission-scoped data served to the wrong user.

</details>

---

## 9. Key terms

**latency decomposition** · **iterations multiplier** · **cost per successful task** · **optimization order** ·
**prompt caching** · **exact / semantic response cache** · **embedding / tool / retrieval cache** · **effort
tuning** · **model routing** · **cascade** · **confidence signal** · **escalation threshold** · **speculative
execution** · **prefetching** · **distillation** · **FinOps** · **unit economics** · **outcome-based pricing**

Next: [Chapter 38 — Deploying at scale →](38-deploying-at-scale.md)
