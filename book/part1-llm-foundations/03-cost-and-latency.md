# Chapter 03 — Cost and latency

> Every token costs money and time. In agents, the money hides in **input** tokens
> (history re-sent every turn) and the time hides in **output** tokens and **iterations**.

**You will learn:** how LLM pricing works (input, output, cached, thinking tokens), why
multi-turn and agent costs grow *quadratically*, the parts of latency (TTFT, TPOT,
tokens/sec), how to measure all of them, and how to think in **cost per task** instead of
cost per call.

**Where this fits:** builds on [Ch 02](02-tokens-and-context-window.md) (tokens). Why
prefill is fast and decode is slow is explained in Ch 05. Caching (Ch 12), context
engineering (Ch 15), the cost playbook (Ch 37) and serving your own models (Ch 39) are all
answers to the numbers you learn to measure here.

---

## 1. The idea in plain words

Hosted LLM APIs charge **per token**, priced per million tokens (often written **/MTok**):

| Token type | What it is | Relative price (typical pattern) |
|---|---|---|
| **Input tokens** | Everything you send: system prompt, tools, documents, history, new message | 1× |
| **Output tokens** | Everything the model writes | **several times** the input price (often 3–5×) |
| **Cached input tokens** | Input the provider already processed recently (Ch 12) | a **fraction** of input (often ~10%) |
| **Cache write** | Storing a prefix in the cache (some providers) | a small premium over input |
| **Thinking / reasoning tokens** | Hidden "thinking" of reasoning models | **billed as output**, even if you don't see them |

> Prices change often. Always take numbers from the provider's pricing page on the day you
> estimate. The *ratios* above are stable enough to reason with.

**Latency** (how long you wait) has two main parts:

- **TTFT — time to first token.** The model must read (process) your whole input first. This
  is called **prefill**. More input → longer TTFT. Plus network and queueing time.
- **Generation time.** The model writes output one token at a time. This is called
  **decode**. Measured as **TPOT** (time per output token) or its inverse, **tokens/second**.

```
total latency ≈ network + queue + TTFT (prefill) + output_tokens × TPOT (decode)
```

---

## 2. Analogy

**A translator paid by the word.** Reading your document (input) is quick and cheap per
word. Writing the translation (output) is slow and expensive per word. If every time you
ask a follow-up question you hand them **the whole conversation again**, you pay for them
to re-read everything, every time. That is exactly how chat APIs work.

Where it breaks: a real translator remembers. The model doesn't (Ch 01) — which is why
re-reading happens and why caching (paying less for re-reading) matters so much.

---

## 3. How it works

### 3.1 Why multi-turn cost grows quadratically

Each turn re-sends all previous turns. Suppose every turn adds 500 tokens (user + reply),
and your system prompt + tools are 2,000 tokens:

```
turn 1 input:  2,000 + 500           =  2,500
turn 2 input:  2,000 + 500 × 2       =  3,000
turn 3 input:  2,000 + 500 × 3       =  3,500
...
turn 10 input: 2,000 + 500 × 10      =  7,000

total input over 10 turns = 2,000 × 10 + 500 × (1+2+...+10) = 20,000 + 27,500 = 47,500 tokens
```

The history part grows like **n²/2**. Double the conversation length → roughly **4×** the
history tokens. Output tokens stay flat (each reply is about the same size).

```
input tokens per turn
   ▲                                     ▲ cumulative input (what you pay)
   │                  ╱                  │                       ╱
   │              ╱                      │                   ╱╱
   │          ╱                          │              ╱╱╱
   │      ╱                              │        ╱╱╱╱
   │  ╱                                  │ ╱╱╱╱╱
   └──────────────► turn                 └──────────────► turn
       linear per turn                     quadratic in total
```

### 3.2 Agents multiply this

An agent (Ch 14) calls the model in a **loop**: think → call tool → read result → think
again. Every **iteration** is a full model call that re-sends everything so far, *including
every tool result*. A 15-iteration agent run with big tool outputs can easily send hundreds
of thousands of input tokens for one user request.

```
agent latency ≈ (network + queue + TTFT + generation + tool time) × ITERATIONS + orchestration
```

**The iteration count is the term people forget.** Cutting iterations from 12 to 4 (better
tools, Ch 11) beats every micro-optimization.

### 3.3 Prefill vs decode (preview of Ch 05)

- **Prefill** processes all input tokens **in parallel** → fast per token. 10K input tokens
  might take well under a second on a hosted API.
- **Decode** produces output **one token at a time** → slow per token. 1,000 output tokens
  at 50 tokens/s = 20 seconds.

So: **input dominates cost, output dominates latency.** Keep this sentence.

### 3.4 Think in cost per task

A "task" is what the user actually wanted: "resolve this support ticket", "summarize this
contract". One task may need 1 call or 30.

```
cost per task = Σ over all calls in the task ( input × p_in + cached × p_cached + output × p_out )
```

Then compare to the value: if a human handles a ticket for $4 and your agent costs $0.30 per
ticket at 80% resolution, the business case works. FDEs present this math to customers.

---

## 4. Code

### 4.1 A cost meter you'll reuse all book long

```python
# cost_meter.py
from dataclasses import dataclass, field

# EXAMPLE prices in USD per million tokens. Replace with your provider's current prices.
PRICES = {
    "example-large": {"input": 3.00, "output": 15.00, "cached_input": 0.30},
    "example-small": {"input": 0.80, "output": 4.00, "cached_input": 0.08},
    "llama3.2-local": {"input": 0.0, "output": 0.0, "cached_input": 0.0},   # local = free per token
}

@dataclass
class CostMeter:
    model: str
    calls: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    per_call: list = field(default_factory=list)

    def record(self, input_tokens, output_tokens, cached_tokens=0):
        p = PRICES[self.model]
        uncached = input_tokens - cached_tokens
        cost = (uncached * p["input"] + cached_tokens * p["cached_input"]
                + output_tokens * p["output"]) / 1_000_000
        self.calls += 1
        self.input_tokens += input_tokens
        self.cached_tokens += cached_tokens
        self.output_tokens += output_tokens
        self.per_call.append(cost)
        return cost

    @property
    def total_cost(self):
        return sum(self.per_call)

    def report(self):
        return (f"{self.calls} calls | in={self.input_tokens} (cached {self.cached_tokens}) "
                f"out={self.output_tokens} | ${self.total_cost:.4f}")
```

### 4.2 See the quadratic growth (no model needed)

```python
# ch03_quadratic.py
from cost_meter import CostMeter

def simulate(turns, system_tokens=2000, tokens_per_turn=500, reply_tokens=250, cached=False):
    meter = CostMeter("example-large")
    history = 0
    for _ in range(turns):
        input_tokens = system_tokens + history + (tokens_per_turn - reply_tokens)
        # with caching, everything except the newest message was seen before
        cached_tokens = system_tokens + history if cached else 0
        meter.record(input_tokens, reply_tokens, cached_tokens)
        history += tokens_per_turn
    return meter

for turns in [5, 10, 20, 40]:
    plain, cache = simulate(turns), simulate(turns, cached=True)
    print(f"{turns:3d} turns: no cache ${plain.total_cost:.3f} | with cache ${cache.total_cost:.3f}")
```

Run it. Doubling turns from 20 → 40 roughly quadruples the history part of the cost. Caching
cuts it dramatically — that's why Ch 12 exists.

### 4.3 Measure TTFT and tokens/second for real

```python
# ch03_latency.py
import time
import ollama

def measure(prompt, model="llama3.2"):
    start = time.perf_counter()
    first_token_at = None
    pieces = 0
    final = None
    for chunk in ollama.chat(model=model, stream=True,
                             messages=[{"role": "user", "content": prompt}]):
        if first_token_at is None and chunk["message"]["content"]:
            first_token_at = time.perf_counter()
        pieces += 1
        final = chunk                       # the last chunk carries the counts and durations
    end = time.perf_counter()

    out_tokens = final["eval_count"]
    decode_s = final["eval_duration"] / 1e9          # Ollama durations are in nanoseconds
    print(f"input tokens:   {final['prompt_eval_count']}")
    print(f"output tokens:  {out_tokens}")
    print(f"TTFT:           {first_token_at - start:.2f}s  (includes model load if cold)")
    print(f"decode speed:   {out_tokens / decode_s:.1f} tokens/s")
    print(f"total:          {end - start:.2f}s")

measure("Write one sentence about the sea.")
measure("Write a 300-word story about the sea.")       # more output → much longer total
measure("Summarize this: " + "The sea is large and blue. " * 400 + " One sentence.")  # more input → longer TTFT
```

What to notice:
- The long story: TTFT similar, total much longer → **output drives latency**.
- The long input: TTFT grows, total grows less than you'd expect → **prefill is fast per token**.

---

## 5. Production view

| Problem | Detect | Fix |
|---|---|---|
| Bill far above forecast | **Cost per task** dashboard; top-10 most expensive runs (Ch 34) | Find the outliers: usually a loop with many iterations or one huge tool output |
| Long conversations get slow and pricey | Input tokens per turn trend | Caching (Ch 12), compaction (Ch 15), trim tool results |
| Users say "it's slow" | p50 **and** p95/p99 latency, TTFT separately | Stream output (perceived latency), fewer iterations, smaller model for easy steps (Ch 37) |
| Reasoning model cost surprise | Output tokens far above visible answer length | Set a thinking budget / effort level (Ch 08, 24); use reasoning only where needed |
| Retries double cost silently | Count retries per task | Retry only retryable errors, with backoff (Ch 12) |
| One tenant eats the budget | Cost per tenant | Per-tenant budgets and rate limits at the gateway (Ch 32) |

**Your p99 defines your architecture, not your p50.** If 1% of tasks take 3 minutes, a
synchronous HTTP request will time out for those users — you need async jobs (Ch 38).

---

## 6. Common mistakes

- **Optimizing output length when the cost is in input.** In multi-turn agents, input
  (history + tool results) usually dominates.
- **Reporting average latency.** Averages hide the slow tail. Report p50, p95, p99.
- **Forgetting the fixed cost per call:** system prompt + tool definitions are paid on
  **every** call. 20 tools × 200 tokens = 4,000 tokens before the user says anything.
- **Ignoring thinking tokens.** They're billed as output.
- **Comparing models by price per token only.** A cheaper model that needs 3× more
  iterations (or retries) costs more per task. Compare **cost per successful task**.

---

## 7. Practice

**Level 1**
1. Run `ch03_quadratic.py`. Add a column for 80 turns. How much did cost grow from 40 → 80?
2. Run `ch03_latency.py`. Fill in a table: prompt → input tokens, output tokens, TTFT, tok/s.
3. Using example prices ($3 in / $15 out per MTok): what does a call with 12,000 input and
   800 output tokens cost? (Answer below.)

**Level 2**
4. Wrap `ollama.chat` in a function `tracked_chat(meter, **kwargs)` that records tokens
   in a `CostMeter` and latency in a list. Run a 10-turn chat and print the meter report plus
   p50/p95 latency (use `statistics.quantiles`).
5. Estimate the monthly cost of a support bot: 2,000 conversations/day, 6 turns each,
   3,000-token system prompt + tools, 300 tokens per user message, 250 per reply. Do it with
   and without 90% cache hits. Show your formula.

**Level 3**
6. Build a small "unit economics" report: given cost per task, resolution rate, and human
   cost per ticket, compute cost per *resolved* ticket and savings per 1,000 tickets. Then
   find the break-even resolution rate. This is the slide an FDE shows a customer's VP.

---

## 8. Check yourself

1. Why does a 20-turn conversation cost much more than twice a 10-turn conversation?
2. Which dominates latency, input or output tokens? Which usually dominates cost in an agent?
3. A reasoning model's visible answer is 100 tokens but you're billed for 3,000 output
   tokens. Why?
4. Your agent's p50 latency is 4s but p99 is 90s. What architectural change does that
   suggest, and what would you investigate first?
5. Practice Q3 answer?

<details>
<summary>Answers</summary>

1. Every turn re-sends all prior turns, so total input grows roughly with the square of the
   number of turns.
2. Output dominates latency (decode is sequential). Input usually dominates cost in agents
   because history and tool results are re-sent on every iteration.
3. Hidden thinking/reasoning tokens are billed as output tokens.
4. Long tails need async handling (job + polling or a queue) rather than a long synchronous
   request. Investigate the slow runs' traces first: usually high iteration counts or slow
   tools, not the model.
5. 12,000 × $3 / 1M = $0.036; 800 × $15 / 1M = $0.012; total **$0.048**.

</details>

---

## 9. Key terms

**/MTok** · **input / output / cached tokens** · **thinking tokens** · **prefill** ·
**decode** · **TTFT** · **TPOT** · **tokens per second** · **p50 / p95 / p99** ·
**iterations** · **cost per task** · **unit economics**

Next: [Chapter 04 — Sampling and determinism →](04-sampling-and-determinism.md)
