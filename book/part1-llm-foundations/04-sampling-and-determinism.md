# Chapter 04 — Sampling and determinism

> The model gives a probability for every possible next token. **Sampling** is how one
> token gets picked. The settings you choose decide whether output is focused or
> creative — and why "the same input" can give different answers.

**You will learn:** logits and softmax, temperature, top-k, top-p (nucleus), min-p,
repetition/frequency/presence penalties, seeds, greedy vs beam search, logprobs, and why
temperature 0 is still not fully deterministic.

**Where this fits:** builds on [Ch 01](01-what-is-an-llm.md) (one token at a time) and
[Ch 02](02-tokens-and-context-window.md). Used in structured output (Ch 10), hallucination
detection with logprobs (Ch 07), self-consistency voting (Ch 24), and eval reliability
(pass^k, Ch 33).

---

## 1. The idea in plain words

At every step the model outputs a score for every token in its vocabulary. These raw
scores are called **logits**. **Softmax** turns them into probabilities that add up to 1.
Then a token is **sampled** — picked at random, weighted by probability.

The **sampling parameters** change the probabilities before the pick:

| Parameter | What it does | Low value | High value |
|---|---|---|---|
| **temperature** | Sharpens or flattens the whole distribution | Focused, repetitive, "safe" | Varied, creative, more mistakes |
| **top-k** | Keep only the k most likely tokens | Very constrained | Almost no effect |
| **top-p** (nucleus) | Keep the smallest set of tokens whose probabilities add up to p | Only the most likely few | Almost all tokens allowed |
| **min-p** | Keep tokens with probability ≥ min_p × (top token's probability) | Many tokens allowed | Only near-top tokens |
| **repetition / frequency / presence penalty** | Lower the score of tokens already used | — | Less repetition (but can hurt code/data that *should* repeat) |
| **seed** | Fixes the random draw | — | Same seed + same setup → usually same output |
| **max tokens** | Hard cap on output length | — | — |

**Temperature 0** (or "greedy decoding") means: always pick the single most likely token.

---

## 2. Analogy

**Choosing a restaurant.** You have a ranked list of places you like.
- *Temperature 0:* always go to your #1 favourite.
- *Temperature 1:* usually #1, sometimes #2 or #3, occasionally something odd.
- *Temperature 2:* almost random — you might end up somewhere terrible.
- *Top-k = 3:* only ever consider your top 3.
- *Top-p = 0.9:* consider the places that together make up 90% of your preference.

Where it breaks: you pick a restaurant once. The model picks **hundreds of times in a row**,
and one odd early pick changes everything after it.

---

## 3. How it works

```
 logits (raw scores)        temperature T            softmax              truncation            pick
 " Paris"   9.1        ┐                       ┐  " Paris"  0.90   ┐  top-k / top-p /     ┐
 " Lyon"    6.8        ├──►  divide by T  ─────┼─► " Lyon"   0.09   ├─► min-p removes the  ├─► random draw
 " the"     4.0        │                       │  " the"    0.005  │  unlikely tail,      │   weighted by
 " banana" -2.0        ┘                       ┘  " banana" ~0     ┘  renormalize         ┘   probability
```

**The math of temperature** (just one line): `p_i = exp(z_i / T) / Σ exp(z_j / T)`.
- `T < 1` divides by a small number → big gaps get bigger → the top token dominates.
- `T > 1` shrinks the gaps → the distribution flattens.
- `T → 0` → all probability on the top token (greedy).

**Greedy vs beam search.** Greedy picks the best token each step. **Beam search** keeps the
best *k* partial sequences and extends all of them, choosing the best full sequence at the
end. It's used in translation and some structured tasks, but chat LLM APIs generally use
sampling, not beam search.

**Logprobs.** Many APIs can return the **log-probability** of each chosen token and the
top alternatives. `logprob = -0.01` means ~99% probable; `-2.3` means ~10%. Useful for
confidence scores and classification (Ch 07, Ch 10).

### Why temperature 0 is not perfectly deterministic

You'd expect "always pick the top token" to give identical output every time. In practice,
small differences happen because:

1. **Floating-point math isn't associative.** `(a + b) + c` can differ slightly from
   `a + (b + c)`. GPUs add numbers in parallel, in orders that can change.
2. **Batching.** Hosted providers batch your request with other users' requests. The batch
   size and shape change the kernel execution and therefore tiny numeric results. When two
   tokens are nearly tied, a tiny difference flips the choice — and everything after it changes.
3. **Infrastructure and model updates** (different hardware, different serving engine,
   mixture-of-experts routing differences).

So: **temperature 0 makes output *much more* consistent, not *guaranteed* identical.**
Design your system and tests to tolerate variation (Ch 33: run evals several times).

> **Hosted reasoning models increasingly don't let you set sampling at all.** For example,
> several current Claude models reject non-default `temperature` / `top_p` / `top_k` with an
> error and expose an **effort** level (low → max) as the control instead. Everything in
> this chapter still explains what happens inside, and it applies fully to models you run
> yourself (Ollama, vLLM — Ch 39). Check your provider's docs before relying on temperature.

### Recommended starting points

| Task | Temperature | Why |
|---|---|---|
| Extraction, classification, routing, tool arguments, JSON | 0 – 0.2 | You want the single most likely correct answer |
| Q&A, support chat | 0.2 – 0.7 | Natural phrasing, still focused |
| Brainstorming, creative writing, generating test data variety | 0.8 – 1.2 | Variety is the goal |
| Self-consistency voting (sample N, take majority, Ch 24) | 0.5 – 1.0 | You need *different* reasoning paths to vote on |

Change **temperature or top-p, not both** at once (they interact; tune one).

---

## 4. Code

### 4.1 Build a sampler from scratch (no model needed)

```python
# ch04_sampler.py — temperature, top-k, top-p, min-p on a toy vocabulary
import math
import random

logits = {" Paris": 9.1, " Lyon": 6.8, " Marseille": 6.0, " the": 4.0, " banana": -2.0}

def softmax(scores, temperature=1.0):
    t = max(temperature, 1e-6)                    # avoid divide-by-zero; ~greedy as t→0
    exps = {tok: math.exp(s / t) for tok, s in scores.items()}
    total = sum(exps.values())
    return {tok: e / total for tok, e in exps.items()}

def top_k(probs, k):
    kept = dict(sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:k])
    total = sum(kept.values())
    return {t: p / total for t, p in kept.items()}

def top_p(probs, p):
    kept, cumulative = {}, 0.0
    for tok, prob in sorted(probs.items(), key=lambda kv: kv[1], reverse=True):
        kept[tok] = prob
        cumulative += prob
        if cumulative >= p:
            break
    total = sum(kept.values())
    return {t: q / total for t, q in kept.items()}

def min_p(probs, m):
    threshold = m * max(probs.values())
    kept = {t: q for t, q in probs.items() if q >= threshold}
    total = sum(kept.values())
    return {t: q / total for t, q in kept.items()}

def show(name, probs):
    print(f"{name:22s}", {t.strip(): round(p, 3) for t, p in probs.items()})

for T in [0.1, 0.5, 1.0, 2.0]:
    show(f"temperature={T}", softmax(logits, T))
show("T=1, top_k=2", top_k(softmax(logits), 2))
show("T=1, top_p=0.95", top_p(softmax(logits), 0.95))
show("T=1, min_p=0.05", min_p(softmax(logits), 0.05))

probs = softmax(logits, 1.0)
draws = random.choices(list(probs), weights=list(probs.values()), k=1000)
print({t.strip(): draws.count(t) for t in probs})          # how often each token got picked
```

### 4.2 Measure variation with a real model

```python
# ch04_variation.py — same prompt, many runs, count distinct answers
import ollama
from collections import Counter

PROMPT = "Give one creative name for a coffee shop. Reply with the name only."

def run(n, **options):
    answers = []
    for _ in range(n):
        r = ollama.chat(model="llama3.2", messages=[{"role": "user", "content": PROMPT}],
                        options=options)
        answers.append(r["message"]["content"].strip())
    return Counter(answers)

for opts in [{"temperature": 0}, {"temperature": 0.7}, {"temperature": 1.3},
             {"temperature": 0.7, "seed": 42}]:
    counts = run(8, **opts)
    print(f"{opts}: {len(counts)} distinct -> {counts.most_common(3)}")
```

Then run the `seed: 42` case twice. On a local model the two runs usually match exactly;
on hosted APIs, seeds (where supported) are "best effort".

### 4.3 Look at logprobs (the model's confidence)

```python
# ch04_logprobs.py — needs a recent Ollama server that supports logprobs
import math
import ollama

r = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content":
               "Is this review positive or negative? 'The food was cold and late.' "
               "Answer with one word: positive or negative."}],
    options={"temperature": 0},
    logprobs=True,
    top_logprobs=3,
)
for item in r["logprobs"][:5]:                     # first few generated tokens
    alts = {a["token"]: round(math.exp(a["logprob"]), 3) for a in item["top_logprobs"]}
    print(repr(item["token"]), round(math.exp(item["logprob"]), 3), "alternatives:", alts)
```

A first token with probability 0.99 = confident. 0.55 vs 0.40 = the model is unsure — a
useful signal to route the case to a stronger model or a human (Ch 07, Ch 37).

---

## 5. Production view

| Problem | Detect | Fix |
|---|---|---|
| Flaky routing / tool choice | Run the same eval case 5–10×; measure pass rate per case (Ch 33) | Temperature 0–0.2 for decisions; structured output (Ch 10); clearer tool descriptions (Ch 11) |
| Repetitive, looping text | Repeated n-grams in output; max_tokens hit | Slightly higher temperature, a light repetition penalty, better stop conditions |
| Broken JSON or code at high temperature | Parse-failure rate | Low temperature for structured tasks; constrained decoding (Ch 10) |
| "Can't reproduce the bug" | Missing sampling params in logs | Log temperature, top_p, seed, model ID with every call (Ch 34) |
| Treating temperature 0 as a hallucination fix | Wrong answers stay wrong, just consistently | Grounding, tools and verification (Ch 07) — not sampling |

---

## 6. Common mistakes

- **Using temperature 0 for creative or voting tasks.** You get the same bland answer N times.
- **Tuning temperature and top-p together**, then not knowing which one helped.
- **Assuming temperature 0 = deterministic tests.** Design tests to tolerate variation, or
  assert on structure/meaning rather than exact strings.
- **Heavy repetition penalties on code or data**, where tokens *must* repeat (`}` `)` keys).
- **Thinking low temperature makes the model more truthful.** It makes it more *consistent*.

---

## 7. Practice

**Level 1**
1. Run `ch04_sampler.py`. At which temperature does " banana" ever get picked in 1,000 draws?
2. Run `ch04_variation.py`. Write a 3-row table: temperature → number of distinct answers.

**Level 2**
3. Take any classification prompt (e.g., "is this email spam? yes/no") and 20 example
   inputs. Run each 5× at temperature 0 and 5× at 0.8. Report: per-input agreement rate for
   each temperature. This is how you measure flakiness.
4. Add `top_k` and `min_p` to the real model call via `options={...}` and repeat 4.2.
   Which knob changed variety the most?

**Level 3**
5. Build a "confidence router": classify sentiment with logprobs; if the top answer's
   probability is < 0.8, mark the case "needs review". Hand-label 30 examples and measure:
   how many wrong answers did the router catch? How many correct answers did it send to
   review unnecessarily? (You just built a precision/recall trade-off — Ch 33.)

---

## 8. Check yourself

1. What does dividing logits by a temperature below 1 do to the distribution?
2. What's the difference between top-k and top-p?
3. Why can temperature 0 give different outputs on a hosted API?
4. Which temperature would you use for (a) extracting an invoice total into JSON, (b)
   generating 50 varied test questions?
5. A colleague says "set temperature to 0 to stop hallucinations." What do you reply?

<details>
<summary>Answers</summary>

1. It makes it sharper: the most likely token gets even more probability, unlikely ones less.
2. Top-k keeps a fixed *number* of tokens. Top-p keeps a variable number: the smallest set
   whose probabilities add up to p, so it adapts to how confident the model is.
3. Floating-point non-associativity in parallel GPU kernels plus changing batch composition
   produce tiny numeric differences; near-ties flip and the rest of the output diverges.
   Infrastructure/model updates also change results.
4. (a) 0 or near 0. (b) high, around 0.9–1.2, to get variety.
5. Temperature 0 makes output consistent, not correct. A model that doesn't know a fact will
   confidently produce the same wrong answer. Fix with grounding (RAG), tools, citations and
   verification.

</details>

---

## 9. Key terms

**logits** · **softmax** · **sampling** · **temperature** · **greedy decoding** · **top-k** ·
**top-p / nucleus sampling** · **min-p** · **repetition / frequency / presence penalty** ·
**seed** · **beam search** · **logprobs** · **floating-point non-associativity** ·
**batch invariance**

Next: [Chapter 05 — Inside the transformer →](05-inside-the-transformer.md)
