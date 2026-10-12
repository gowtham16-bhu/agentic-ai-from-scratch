# Chapter 05 — Inside the transformer

> You don't need to train a transformer to build agents. But knowing a few internals —
> **attention, the KV cache, prefill vs decode, memory math** — explains why long context
> is expensive, why prompt caching works, and why GPUs run out of memory.

**You will learn:** the transformer's building blocks, attention (queries, keys, values)
with a tiny implementation, causal masking, multi-head attention, positional encoding
(RoPE), the n² cost, the KV cache and its memory formula, MQA/GQA, Mixture-of-Experts,
FlashAttention, and how to turn parameter counts into GPU memory and speed limits.

**Where this fits:** builds on [Ch 02](02-tokens-and-context-window.md) (tokens, context
window) and [Ch 03](03-cost-and-latency.md) (prefill vs decode). Explains *why* prompt
caching works (Ch 12), why context engineering matters (Ch 15), and is the foundation for
serving models yourself with vLLM (Ch 39) and fine-tuning (Ch 40).

---

## 1. The idea in plain words

A transformer turns a list of tokens into a probability for the next token. Inside, it's a
**stack of identical layers** (dozens of them). Each layer does two things:

1. **Attention** — every token looks at the earlier tokens and pulls in information from
   the ones that matter to it. ("it" looks back and finds "the cat".)
2. **Feed-forward network (MLP)** — each token's information is processed on its own,
   applying what the model learned in training (facts, patterns).

```
token IDs → embeddings (vectors) → [ attention → feed-forward ] × N layers → logits → next token
```

Each token is represented as a **vector** (a list of thousands of numbers) that gets
refined layer by layer.

---

## 2. Analogy

**Attention is a soft dictionary lookup.** A normal hash map: you give a key, you get
exactly one value. Attention: each token sends a **query** ("what am I looking for?"), every
earlier token offers a **key** ("what I contain") and a **value** ("what I'll give you").
The query is compared with all keys; instead of returning one value, it returns a
**weighted mix** of all values — mostly from the best-matching keys.

Where it breaks: a dictionary lookup is one comparison. Attention compares the query with
*every* key, which is why cost grows with the square of the length.

---

## 3. How it works

### 3.1 Attention in one formula

```
Attention(Q, K, V) = softmax( Q · Kᵀ / √d ) · V
```

- `Q · Kᵀ` — compare each query with each key (dot products = similarity scores).
- `/ √d` — scale down so softmax doesn't become too peaky (d = vector size).
- `softmax` — turn scores into weights that sum to 1 (same softmax as Ch 04).
- `· V` — weighted mix of the values.

**Causal mask:** when generating, a token may only look at **earlier** tokens (it can't see
the future). Scores for later positions are set to −∞ before softmax, so their weight is 0.

### 3.2 Multi-head attention

Instead of one attention, each layer runs many in parallel (**heads**), each with its own
Q/K/V projections. Different heads learn different patterns: one tracks grammar, one tracks
which noun a pronoun refers to, one tracks formatting. Their outputs are concatenated.

### 3.3 Position: RoPE

Attention by itself has no sense of order ("cat bites dog" = "dog bites cat"). Models add
position information. Most modern LLMs use **RoPE (rotary position embeddings)**: queries and
keys are rotated by an angle that depends on their position, so the dot product naturally
encodes *relative* distance. Context-extension techniques stretch these rotations so a model
trained on shorter sequences can handle longer ones (with some quality loss — one reason for
context rot, Ch 02).

### 3.4 The n² problem

With `n` tokens, attention computes an `n × n` score matrix in every layer and every head.

```
 n = 1,000   →     1,000,000 scores
 n = 10,000  →   100,000,000 scores   (10× longer → 100× more)
```

Double the context → **4×** the attention work. This is why long prompts raise TTFT and cost
and why "just use a 1M-token window" is not free.

### 3.5 The KV cache — the most important serving idea

During **decode** (writing output), each new token needs to attend to all previous tokens.
Recomputing every previous token's keys and values at every step would be wasteful. So the
server **stores** each token's K and V vectors once, in the **KV cache**, and reuses them:

```
step 1 (prefill): compute K,V for all prompt tokens ───────► store in KV cache
step 2: new token → compute its own Q,K,V → attend over cached K,V → append its K,V
step 3: new token → compute its own Q,K,V → attend over cached K,V → append its K,V
...
```

This turns each decode step from "recompute everything" into "compute one token, look up
the rest". The price is **memory**:

```
KV cache bytes per token = 2 (K and V) × layers × kv_heads × head_dim × bytes_per_value
```

Example — a typical 8B model (32 layers, 8 KV heads, head_dim 128, 16-bit = 2 bytes):
`2 × 32 × 8 × 128 × 2 = 131,072 bytes ≈ 128 KB per token`.
A 32K-token conversation → **~4 GB** of KV cache, for **one** user. Fifty concurrent users with
long contexts need more memory for KV cache than for the model weights. **GPU memory, not
compute, is usually what limits how many users one GPU can serve** (Ch 39).

**Prompt caching (Ch 12) is the KV cache kept across requests.** If your next request
starts with exactly the same tokens (system prompt, tools, documents), the provider reuses
the stored K/V for that prefix instead of recomputing it — faster and cheaper. That's why
the prefix must match *exactly*: one changed token early on changes every K/V after it.

### 3.6 Shrinking the KV cache: MQA and GQA

- **Multi-head attention (MHA):** every head has its own K and V → biggest cache.
- **Multi-query attention (MQA):** all heads share one K and V → smallest cache, some quality loss.
- **Grouped-query attention (GQA):** groups of heads share K/V → the common middle ground.
  (In the example above, 32 query heads share 8 KV heads → 4× smaller cache than MHA.)

### 3.7 Prefill vs decode, again — now you know why

| | Prefill (reading input) | Decode (writing output) |
|---|---|---|
| Work | All input tokens at once (big matrix × matrix) | One token at a time |
| Bottleneck | **Compute** (GPU math units busy) | **Memory bandwidth** (all weights must be read from GPU memory for every single token) |
| Speed per token | Fast | Slow |

**A rule of thumb for one stream:** max tokens/s ≈ memory bandwidth ÷ model size in bytes.
An 8B model in 16-bit is 16 GB. On a GPU with ~1 TB/s bandwidth: ~60 tokens/s, at best, for a
single user. **Batching** many users together reads the weights once for many tokens —
that's how servers get high total throughput (continuous batching, Ch 39).

### 3.8 FlashAttention

A smarter way to *compute* the same attention: it processes Q, K, V in **tiles** inside the
GPU's small, very fast on-chip memory and never writes the full n×n matrix to the slower main
GPU memory (HBM). Same result, much less memory traffic, much faster. Nearly every serving
engine uses it.

### 3.9 Mixture-of-Experts (MoE)

The feed-forward part is split into many **experts**. A small **router** picks only a few
experts per token. So a model can have huge **total** parameters (knowledge) but use only a
small number of **active** parameters per token (speed).

| | Total params | Active params per token | Memory needed | Speed |
|---|---|---|---|---|
| Dense 70B | 70B | 70B | all 70B | slow |
| MoE "e.g. 200B total, 20B active" | 200B | 20B | **all 200B** must be loaded | close to a 20B dense model |

The trap: MoE is fast, but you still need memory for **all** experts.

### 3.10 Parameters → memory

```
weights memory ≈ parameters × bytes per parameter
  FP16/BF16 = 2 bytes · FP8/INT8 = 1 byte · INT4 = 0.5 bytes

  8B  model: 16 GB (16-bit) · 8 GB (8-bit) · ~4–5 GB (4-bit)
  70B model: 140 GB (16-bit) · 70 GB (8-bit) · ~35–40 GB (4-bit)

total GPU memory ≈ weights + KV cache (grows with users × context) + runtime overhead
```

This is why a laptop runs a 4-bit 3B–8B model, and why 70B models need large or multiple GPUs.
**Quantization** (fewer bytes per parameter) trades a little quality for a lot of memory (Ch 39).

---

## 4. Code

### 4.1 Attention from scratch

```python
# ch05_attention.py — scaled dot-product attention with a causal mask (numpy)
import numpy as np

np.random.seed(0)
tokens = ["the", "cat", "sat", "because", "it", "was", "tired"]
n, d = len(tokens), 8

X = np.random.randn(n, d)                   # pretend these are token embeddings
W_q, W_k, W_v = (np.random.randn(d, d) for _ in range(3))
Q, K, V = X @ W_q, X @ W_k, X @ W_v         # each token's query, key, value

scores = Q @ K.T / np.sqrt(d)               # n x n similarity matrix
mask = np.triu(np.ones((n, n)), k=1)        # 1s above the diagonal = "future" positions
scores = np.where(mask == 1, -np.inf, scores)

weights = np.exp(scores - scores.max(axis=1, keepdims=True))
weights = weights / weights.sum(axis=1, keepdims=True)    # softmax per row
output = weights @ V                         # weighted mix of values

np.set_printoptions(precision=2, suppress=True)
print("attention weights (row = token looking, column = token looked at):")
for tok, row in zip(tokens, weights):
    print(f"{tok:8s}", row)
```

Check: every row sums to 1, and everything above the diagonal is 0 (no looking ahead). With
random weights the pattern is meaningless — in a trained model, "it" would put high weight
on "cat".

### 4.2 Memory and speed calculators

```python
# ch05_memory.py
def weights_gb(params_billion, bytes_per_param):
    return params_billion * 1e9 * bytes_per_param / 1e9

def kv_cache_gb(tokens, layers, kv_heads, head_dim, bytes_per_value=2):
    return 2 * layers * kv_heads * head_dim * bytes_per_value * tokens / 1e9

def max_decode_tokens_per_s(model_gb, bandwidth_gb_s):
    return bandwidth_gb_s / model_gb          # single stream, ignoring KV reads

w = weights_gb(8, 2)
print(f"8B @16-bit weights: {w:.0f} GB")
print(f"8B @4-bit weights:  {weights_gb(8, 0.5):.0f} GB")
kv = kv_cache_gb(32_000, layers=32, kv_heads=8, head_dim=128)
print(f"KV cache, 1 user x 32K tokens: {kv:.1f} GB")
print(f"KV cache, 50 users x 32K:      {50 * kv:.0f} GB")
print(f"max single-stream speed @1000 GB/s: {max_decode_tokens_per_s(w, 1000):.0f} tok/s")
```

---

## 5. Production view

| Symptom | The internal reason | What you do |
|---|---|---|
| TTFT grows with prompt size | Prefill work grows with input; attention grows ~n² | Send less (Ch 15, 17); cache stable prefixes (Ch 12) |
| Prompt cache hit rate is low | KV for a prefix is reusable only if the prefix is **byte-identical** | Stable ordering, no timestamps early in the prompt (Ch 12) |
| Self-hosted server OOMs (out of memory) under load | KV cache grows with users × context length | Limit max context, use GQA models, KV-cache quantization, PagedAttention (Ch 39) |
| Output speed far below expectations on your GPU | Decode is memory-bandwidth bound | Quantize, batch requests, speculative decoding (Ch 39) |
| "This MoE model is fast, why doesn't it fit?" | All experts must be in memory | Budget memory on **total** params, speed on **active** params |

---

## 6. Common mistakes

- **Thinking attention cost is linear in context.** It's quadratic in the naive form; even
  with clever kernels, long contexts cost real time and money.
- **Forgetting the KV cache in memory planning.** Weights fit ≠ the service fits.
- **Confusing prompt caching with response caching.** Prompt caching reuses *computation of
  an identical prefix*; the model still generates a fresh answer. Response caching returns a
  stored answer (Ch 37).
- **Comparing MoE and dense models by total parameters only.**

---

## 7. Practice

**Level 1**
1. Run `ch05_attention.py`. Confirm each row sums to 1 and the upper triangle is 0. Then
   remove the mask: what changes? Why must generation use a mask?
2. Use `ch05_memory.py`: how much memory do the weights of a 70B model need at 16-bit and at
   4-bit?

**Level 2**
3. Compute the KV cache for 100 concurrent users at 8K tokens each for the 8B example. Does
   it fit next to the weights on an 80 GB GPU? What happens at 32K tokens each?
4. Change `kv_heads` from 8 to 32 (no GQA). How much bigger is the cache?

**Level 3**
5. Implement a full single **transformer block** forward pass in numpy: attention (with 2
   heads) → add residual → layer norm → 2-layer MLP with ReLU → add residual → layer norm.
   Print the output shape. (~50 lines. You now know what "a layer" is.)
6. Implement a toy **KV cache**: generate 10 "tokens" one at a time, appending K and V to
   lists, and show that each step computes attention over the cache without recomputing
   old K/V. Count the multiply operations with and without the cache.

---

## 8. Check yourself

1. Explain Q, K and V in one sentence each.
2. Why does doubling the context roughly quadruple attention work?
3. What does the KV cache store, and what does it cost?
4. Why does prompt caching require an exact prefix match?
5. Why is decode memory-bandwidth bound?
6. An MoE model has 400B total and 17B active parameters. Which number tells you memory
   needs, and which tells you speed?

<details>
<summary>Answers</summary>

1. Query: what this token is looking for. Key: what each token offers to be matched
   against. Value: the information a token passes on when it's attended to.
2. Every token compares with every other token: n × n scores. 2n → 4n².
3. The keys and values of all previous tokens, so decode doesn't recompute them. It costs
   GPU memory that grows with layers × KV heads × head size × tokens × users.
4. The cached K/V of each token depends on all tokens before it. Change one early token and
   every later K/V is different, so nothing after the change can be reused.
5. To produce each single token, the GPU must read all model weights from memory; the math
   per token is small, so reading memory is the slow part.
6. Total (400B) → memory. Active (17B) → speed per token.

</details>

---

## 9. Key terms

**transformer** · **layer** · **embedding layer** · **attention** · **query / key / value** ·
**causal mask** · **multi-head attention** · **RoPE** · **n² cost** · **KV cache** ·
**MHA / MQA / GQA** · **prefill (compute-bound)** · **decode (memory-bandwidth-bound)** ·
**FlashAttention** · **HBM** · **Mixture-of-Experts** · **active vs total parameters** ·
**quantization**

Next: [Chapter 06 — Embeddings →](06-embeddings.md)
