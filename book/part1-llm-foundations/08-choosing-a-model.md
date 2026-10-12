# Chapter 08 — Choosing a model

> There is no "best model". There is the **cheapest, fastest model that passes your
> quality bar on your task** — measured on your data, not on a leaderboard.

**You will learn:** the model landscape (frontier APIs, open-weight, small language
models, reasoning models), the dimensions that matter (quality, cost, latency, context,
tool reliability, modality, license, data residency), why benchmarks mislead, how to
compare models with your own mini-eval, and how to reference models by **role** so you can
swap them without code changes.

**Where this fits:** builds on Ch 01–07 (what models are, what they cost, how they fail).
Model roles are implemented in the API client (Ch 12) and the LLM gateway (Ch 32); the
comparison harness grows into full evals (Ch 33); cascades and routing in Ch 37;
self-hosting open-weight models in Ch 39; making a small model better with fine-tuning in
Ch 40.

---

## 1. The idea in plain words

Choosing a model is an engineering trade-off, like choosing a database. You compare options
on several dimensions and pick per **task**, not per company. One product often uses several
models: a small fast one for routing, a strong one for hard reasoning, an embedding model for
search, and a different-family model as a judge.

---

## 2. Analogy

**Hiring for a team.** You don't hire a senior architect to sort the mail. You hire a fast
junior for routine work, a senior for hard problems, and an outside reviewer who wasn't
involved in the work to check quality. And you check references on *your kind of work*, not
just their CV.

---

## 3. How it works

### 3.1 The landscape (concepts — names change fast)

| Category | What it is | Pros | Cons |
|---|---|---|---|
| **Frontier closed models** (e.g. Anthropic Claude, OpenAI GPT, Google Gemini) | Best-quality models, accessed via API or cloud platforms (AWS Bedrock, Google Vertex AI, Azure) | Highest quality, best tool use, no infra | Per-token cost, data leaves your network (unless via your cloud tenancy/agreements), rate limits, deprecations |
| **Open-weight models** (e.g. Llama, Qwen, Mistral, DeepSeek, Gemma families) | Weights downloadable; run them yourself or via inference providers | Control, privacy, on-prem, fine-tuning, no per-token fee when self-hosted | You run GPUs (Ch 39); usually behind the frontier on hard agent tasks |
| **Small language models (SLMs)** (~1–10B params) | Small open or closed models | Very fast, cheap, can run on laptop/phone/edge | Weaker reasoning and instruction following; great when fine-tuned for one narrow job |
| **Reasoning models** | Think before answering (Ch 01, Ch 24); often configurable thinking budget/effort | Much better at hard multi-step problems | Slower, costlier (thinking tokens billed as output) |
| **Embedding / reranker models** | Specialized for search (Ch 06, 17) | Cheap, fast | Not for generation |

Most providers sell **tiers** — a large, a mid and a small model (for example Anthropic's
Opus / Sonnet / Haiku naming). The mid tier is the usual default; large for the hardest steps;
small for high-volume simple steps.

**"Open-weight" is not always "open-source".** Licenses differ: some are permissive (e.g.
Apache-2.0, MIT), some have usage restrictions or user-count limits. **Read the license before
a customer deploys it commercially.**

### 3.2 The dimensions that matter

| Dimension | Question to ask | How to measure |
|---|---|---|
| **Task quality** | Does it pass *our* eval cases? | Your mini-eval (below), later Ch 33 |
| **Tool-use reliability** | Does it call the right tool with valid arguments? | Trajectory evals (Ch 33) |
| **Instruction following / format** | Does it respect JSON schemas and constraints? | Parse-failure rate |
| **Cost per successful task** | Not per token! | Ch 03 cost meter × success rate |
| **Latency** | TTFT and p95 total | Ch 03 latency measurement |
| **Context window (effective)** | Does quality hold at our document lengths? | Needle tests at your sizes (Ch 02) |
| **Modalities** | Images, PDFs, audio needed? | Ch 41 |
| **Language coverage + tokenizer efficiency** | Tamil, Hindi, Arabic users? | Token counts + eval in that language (Ch 02) |
| **Data residency & privacy** | Where is data processed and stored? Retention? Training on data? | Provider terms, regional endpoints, DPAs, "zero data retention" options |
| **Deployment constraints** | Must it run on-prem / air-gapped? | → open-weight self-hosted |
| **Rate limits & availability** | Can we get the throughput we need? | Provider tier limits, SLAs (Ch 38) |
| **License** | Can the customer use it commercially? | License text |
| **Lifecycle** | When will this version be deprecated? | Provider deprecation pages |

### 3.3 Why benchmarks mislead

Public benchmarks (general knowledge, graduate-level science, coding, agent tool-use suites,
human-preference arenas) are useful for a **shortlist**, never for a **decision**:

- **Not your task.** A top coding score says little about extracting fields from your invoices.
- **Contamination.** Test questions leak into training data.
- **Vendor-reported** numbers use favourable settings.
- **Saturation.** When every model scores 90%+, differences are noise.
- **Single-run.** Agents vary run to run; you need pass^k (Ch 33).

**Build a 30–50 case eval from the customer's real data before choosing.** That is one of
the most valuable things an FDE does in week one.

### 3.4 Reference models by role, not by name

```
code:   llm.complete(role="fast", ...)            ← never llm.complete(model="some-model-2026-05-01")

config: roles:
          fast:      [provider-A/small-model, provider-B/small-model]       ← fallback chain
          reasoning: [provider-A/large-model, provider-B/large-model]
          judge:     [provider-B/mid-model]          ← different family from the one being judged
          embed:     [local/nomic-embed-text]
```

Benefits: swap models by editing config; per-environment and per-tenant overrides; fall back
to a **different provider** when one has an outage (provider-wide outages are exactly what a
same-provider fallback can't protect against); log `model_role` **and** the resolved
`model_id` on every call (Ch 34).

### 3.5 A selection process you can repeat

```
1. Define the task and the quality bar ("≥ 90% correct on extraction; p95 < 3s")
2. Build 30–50 eval cases from real data (include hard and "absence" cases, Ch 07)
3. Shortlist 3–5 models across tiers (small, mid, large; one open-weight if relevant)
4. Run the eval 3× per model; record pass rate, cost/task, p50/p95 latency, parse failures
5. Pick the cheapest model that passes the bar
6. Consider a cascade: cheap model first, escalate hard cases (Ch 37)
7. Pin the exact version; re-run the eval before any model upgrade
```

---

## 4. Code

### 4.1 Roles in config, resolved at runtime

```python
# model_roles.py
ROLES = {
    "fast":      ["ollama/llama3.2", "ollama/qwen2.5:3b"],     # first = preferred
    "reasoning": ["ollama/qwen2.5:7b", "ollama/llama3.2"],
    "judge":     ["ollama/qwen2.5:3b"],                         # different family from "fast"
    "embed":     ["ollama/nomic-embed-text"],
}

def resolve(role, unavailable=()):
    """Return the first model in the role's chain that isn't known to be down."""
    for model in ROLES[role]:
        if model not in unavailable:
            return model
    raise RuntimeError(f"no available model for role '{role}'")

print(resolve("fast"))
print(resolve("fast", unavailable={"ollama/llama3.2"}))   # falls back
```

(In Ch 12 this grows into a real client with retries and cross-provider fallback; in Ch 32
into a gateway.)

### 4.2 A model comparison harness

```python
# ch08_compare.py — same eval, several models: accuracy, latency, tokens
import time
import statistics
import ollama

CASES = [   # (input, expected label) — replace with 30-50 cases from real data
    ("I want my money back for the broken lamp", "refund"),
    ("Where is my parcel? It's been 10 days", "shipping"),
    ("I forgot my password", "account"),
    ("Can I return shoes I wore once?", "refund"),
    ("Do you deliver to Sri Lanka?", "shipping"),
    ("Change the email on my profile", "account"),
]
LABELS = ["refund", "shipping", "account"]
SCHEMA = {"type": "object", "properties": {"label": {"type": "string", "enum": LABELS}},
          "required": ["label"]}

def run(model):
    correct, latencies, tokens = 0, [], 0
    for text, expected in CASES:
        start = time.perf_counter()
        r = ollama.chat(model=model, format=SCHEMA, options={"temperature": 0}, messages=[
            {"role": "system", "content": f"Classify the customer message into one of {LABELS}."},
            {"role": "user", "content": text}])
        latencies.append(time.perf_counter() - start)
        tokens += r["prompt_eval_count"] + r["eval_count"]
        correct += expected in r["message"]["content"]
    return {"model": model, "accuracy": correct / len(CASES),
            "p50_s": round(statistics.median(latencies), 2),
            "max_s": round(max(latencies), 2), "tokens": tokens}

for m in ["llama3.2", "qwen2.5:3b"]:        # `ollama pull qwen2.5:3b` first
    print(run(m))
```

Extend it with hosted models later (same cases, same scoring). The output table is your
model-selection evidence.

---

## 5. Production view

| Risk | Detect | Mitigate |
|---|---|---|
| Provider deprecates your model | Track deprecation notices; inventory of model IDs in use (Ch 31 registry) | Roles + config; eval-gated migration well before the date |
| "It worked last week" — silent alias update | `model_id_resolved` changes in traces | Pin exact version IDs, not floating aliases |
| Provider outage | Error rate per provider | Cross-provider fallback chain at the gateway (Ch 32) |
| Cost spike after "upgrading" to a reasoning model | Output tokens per task jump | Reasoning only on steps that need it; set thinking budget/effort |
| Data-residency violation | Audit where each role's provider processes data | Regional endpoints, cloud-tenancy deployments, or self-hosting |
| Judge bias | Judge and judged from same family inflate scores | Cross-family judge, calibrate against human labels (Ch 33) |

---

## 6. Common mistakes

- **Choosing by leaderboard.** Choose by your eval.
- **Using the biggest model everywhere** "to be safe". It's slower and often unnecessary.
- **Hardcoding model IDs** in many files.
- **Comparing price per token** instead of cost per *successful* task.
- **Forgetting license and data terms** until the customer's security review (Ch 45).
- **Same-provider fallback only.** When a provider has an outage, all its models usually do.

---

## 7. Practice

**Level 1**
1. Pull `qwen2.5:3b` and run `ch08_compare.py`. Which model wins on accuracy? On latency?
2. Write down the 5 most important dimensions for: (a) a hospital's internal document
   assistant, (b) a high-volume e-commerce intent classifier. Explain the difference.

**Level 2**
3. Grow the eval to 30 cases using messages you write in your own words (include 5 tricky,
   ambiguous ones). Run each model 3×. Report mean accuracy and the worst run.
4. Add a cost column using example prices from Ch 03 as if each model were hosted. Which is
   the cheapest model that reaches 90%?

**Level 3**
5. Write a one-page **model selection memo** for a fictional customer (a bank's support team,
   data must stay in India, 50K conversations/day): requirements, shortlist, eval results
   (yours), decision, fallback plan, risks. This is a real FDE deliverable (Ch 45).

---

## 8. Check yourself

1. Why should code reference a model *role* instead of a model *name*?
2. When would you choose an open-weight model over a frontier API?
3. Give two reasons leaderboard scores can mislead.
4. Why should a fallback chain include a different provider?
5. What is the difference between "open-weight" and "open-source" in practice?

<details>
<summary>Answers</summary>

1. To swap models via config (upgrades, per-tenant overrides, fallbacks) without code
   changes, and to make every call's role and resolved model visible in traces.
2. When data must stay on-prem/air-gapped, when volume makes self-hosting cheaper, when you
   need to fine-tune deeply, or when latency/control requirements demand your own serving.
3. Any two: not your task; contamination; vendor-reported settings; saturation; single runs
   hide variance.
4. Provider-wide outages and rate limits affect all of that provider's models at once.
5. Open-weight means the weights are downloadable; the license may still restrict commercial
   use or impose conditions. Open-source (in the strict sense) also allows broad reuse, and
   ideally the training code/data are open too. Always read the license.

</details>

---

## 9. Key terms

**frontier model** · **open-weight model** · **small language model (SLM)** · **reasoning
model** · **thinking budget / effort** · **model tier** · **model role** · **fallback chain** ·
**pinned version vs alias** · **deprecation** · **data residency** · **zero data retention** ·
**license** · **benchmark contamination** · **cost per successful task**

Next: [Part 2 — Chapter 09: Prompt engineering →](../part2-talking-to-models/09-prompt-engineering.md)
