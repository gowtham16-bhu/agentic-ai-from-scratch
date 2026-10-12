# Chapter 39 — Serving open models: vLLM and inference engineering

> When you run open-weight models yourself — for privacy, cost at volume, latency, or custom
> fine-tunes — you become the model provider. The job is to squeeze maximum useful tokens out of
> expensive GPUs: **batch continuously, manage the KV cache like virtual memory, reuse prefixes,
> quantize, parallelize, and speculate**. vLLM is the most widely used open-source engine for this.

**You will learn:** GPU basics (VRAM, HBM bandwidth, compute, interconnect); memory math and how many
sequences fit; prefill vs decode and the metrics (TTFT, TPOT/ITL, throughput, **goodput**); static vs
**continuous batching** and chunked prefill; **PagedAttention**; **prefix caching** (and SGLang's RadixAttention);
**speculative decoding** (draft models, n-gram, EAGLE/Medusa-style heads); **quantization** (FP8, INT8, INT4,
GPTQ, AWQ, GGUF, newer FP4 formats; KV-cache quantization); **tensor, pipeline, data, expert and context
parallelism**; **disaggregated prefill/decode**; **multi-LoRA** serving; structured outputs and tool calling in
engines; the engines (**vLLM, SGLang, TensorRT-LLM, TGI, llama.cpp, Ollama**) and Kubernetes serving layers;
GPU autoscaling and cold starts; benchmarking; and self-hosting vs API cost.

**Where this fits:** builds directly on transformer internals (Ch 05: KV cache, prefill/decode, memory math),
cost/latency (Ch 03, 37), structured output (Ch 10), prompt caching (Ch 12), model choice (Ch 08) and deployment
(Ch 38). Fine-tuned adapters you serve here come from Ch 40.

> **Verified against:** the vLLM README (vLLM 0.31.0 on PyPI, October 2026), and the READMEs of SGLang,
> TensorRT-LLM, llama.cpp and Hugging Face TGI (which states it is now in **maintenance mode**).

---

## 1. The idea in plain words

A GPU serving an LLM has three limits:

| Resource | What it limits | Rule of thumb |
|---|---|---|
| **VRAM (GPU memory) capacity** | Model weights + **KV cache** for all active sequences | Weights fit ≠ service fits (Ch 05) |
| **Memory bandwidth (HBM)** | **Decode speed** — every new token re-reads the weights | Single-stream tokens/s ≈ bandwidth ÷ model bytes |
| **Compute (FLOPs)** | **Prefill speed**, large batches | Prefill is compute-bound |
| **Interconnect** (NVLink, PCIe, network) | Multi-GPU scaling | Tensor parallelism needs fast links |

**Serving engines** win by **batching many users together** so each expensive read of the weights produces
tokens for many sequences at once — while keeping latency acceptable for each user.

Metrics:

| Metric | Meaning |
|---|---|
| **TTFT** | Time to first token (queueing + prefill) |
| **TPOT / ITL** | Time per output token / inter-token latency (decode speed per user) |
| **Throughput** | Total tokens/s across all users |
| **Goodput** | Requests per second that **meet their latency SLO** — the number that matters for a product |

---

## 2. Analogy

**A city bus vs taxis.** A taxi (one request at a time) is fast for one passenger but wastes capacity. A bus
(batch) carries many people per trip. *Static* batching is a bus that waits until the passenger going furthest
gets off before anyone new can board. **Continuous batching** lets people get on and off at every stop — the bus is
always nearly full. **PagedAttention** is assigning seats flexibly instead of reserving a whole row per passenger
"in case their family comes".

---

## 3. How it works

### 3.1 Memory math: how many users fit?

```
VRAM budget = GPU memory × utilization target − model weights − runtime overhead
KV cache per sequence = 2 × layers × KV heads × head dim × bytes × tokens in that sequence (Ch 05)
max concurrent sequences ≈ VRAM budget ÷ KV per sequence
```

Levers: fewer bytes per weight (**quantization**), fewer bytes per KV value (**KV-cache quantization**), models
with fewer KV heads (**GQA/MQA**), shorter max context, and **paging** so sequences only use what they need.

### 3.2 Continuous batching and chunked prefill

- **Static batching:** collect a batch, run it until *every* sequence finishes; short answers wait for the longest.
  GPU slots sit idle.
- **Continuous (in-flight, iteration-level) batching:** after **each decode step**, finished sequences leave and
  waiting requests join. Utilization goes way up — the single biggest throughput win.
- **Chunked prefill:** a huge prompt's prefill is split into chunks interleaved with other users' decode steps, so
  one long prompt doesn't freeze everyone's token stream (protects ITL).

### 3.3 PagedAttention

Naively, each sequence reserves one **contiguous** KV-cache region for its maximum length — most of it unused, and
fragmented. **PagedAttention** (introduced with vLLM) stores the KV cache in fixed-size **blocks**, like OS virtual
memory pages, with a per-sequence block table:

```
sequence A: logical blocks [0][1][2]   → physical blocks 7, 2, 9
sequence B: logical blocks [0][1]      → physical blocks 4, 11
shared prefix? both point to the SAME physical blocks (copy-on-write when they diverge)
```

Result: near-zero waste, many more concurrent sequences, and cheap **sharing** (common prefixes, parallel sampling).

### 3.4 Prefix caching

If many requests start with the same tokens (system prompt, tools, a shared document), keep their KV blocks and
**reuse them** — the self-hosted version of provider prompt caching (Ch 12). vLLM supports automatic prefix
caching; **SGLang**'s **RadixAttention** organizes cached prefixes in a radix tree, which works especially well for
agent workloads with many calls sharing long prefixes. Everything in Ch 12 about stable, append-only prompts
applies here too.

### 3.5 Speculative decoding

Decode is slow because it's one token per weight-read. Speculative decoding guesses ahead:

```
a cheap DRAFTER proposes k tokens (a small draft model, n-gram lookup from the prompt, or extra
"heads" trained on the big model — EAGLE / Medusa-style)
→ the big model VERIFIES all k in ONE forward pass
→ accept the longest matching prefix (+1 token from the big model) → repeat
```

Output follows the **same distribution** as the big model alone (it's an exact acceleration technique when using
standard verification), and speedups depend on the **acceptance rate** — highest for predictable text (code, JSON,
repeating the input) and at **low batch sizes** (at high load the GPU is already busy).

### 3.6 Quantization

| Format | Bytes/param | Notes |
|---|---|---|
| FP16 / BF16 | 2 | Baseline quality |
| **FP8** | 1 | Good quality on GPUs that support it; common production choice |
| **INT8** | 1 | Weights (and sometimes activations) |
| **INT4** (**GPTQ**, **AWQ**) | ~0.5 | Big memory savings; measure quality on your evals |
| **GGUF** (llama.cpp formats, 1.5–8 bit) | 0.2–1 | CPU / Apple Silicon / edge |
| Newer 4-bit floating formats (MXFP4, NVFP4) | ~0.5 | Supported on recent hardware/engines |
| **KV-cache quantization** (e.g. FP8 KV) | — | Doubles concurrent context vs 16-bit KV |

Quantization trades a little quality for memory and speed. **Always re-run your eval suite** on the quantized
model — degradations often hit specific skills (math, tool-call formatting, non-English).

### 3.7 Parallelism

| Type | Splits | Use when |
|---|---|---|
| **Tensor parallelism (TP)** | Each layer's matrices across GPUs | Model doesn't fit one GPU; needs fast interconnect (within a node) |
| **Pipeline parallelism (PP)** | Layers across GPUs/nodes | Very large models across nodes |
| **Data parallelism (DP)** | Full replicas | More throughput; simplest scaling |
| **Expert parallelism (EP)** | MoE experts across GPUs | Mixture-of-Experts models (Ch 05) |
| **Context / sequence parallelism** | The sequence across GPUs | Very long contexts |

### 3.8 Disaggregated prefill and decode

Prefill (compute-bound) and decode (bandwidth-bound) interfere when they share GPUs. **Disaggregated serving** runs
them on **separate GPU pools** and transfers the KV cache between them, tuning each pool for its job — better
goodput at scale. vLLM and SGLang support it, and orchestration layers (for example llm-d, NVIDIA Dynamo) build
on it for large deployments.

### 3.9 Multi-LoRA serving

Serve **many fine-tuned LoRA adapters** (Ch 40) on **one base model**, choosing the adapter per request — e.g. one
adapter per tenant or per task — at little extra memory cost.

### 3.10 Structured output and tool calling

Engines implement constrained decoding (vLLM: **xgrammar** or **guidance**) so JSON schemas and regexes are
enforced at sampling time (Ch 10), and include **tool-calling and reasoning parsers** that turn model-specific
output formats into OpenAI-style `tool_calls`. Check the parser for your exact model — tool calling quality on
self-hosted models depends heavily on it.

### 3.11 The engines

| Engine | Strengths | Use for |
|---|---|---|
| **vLLM** | Most popular OSS engine; PagedAttention, continuous batching, prefix caching, speculative decoding, broad quantization, all parallelism types, multi-LoRA; **OpenAI-compatible** server (also Anthropic Messages API and gRPC) | Default choice for GPU serving |
| **SGLang** | RadixAttention prefix caching, fast structured generation, strong for agentic multi-call programs | High-throughput agent workloads |
| **TensorRT-LLM** | NVIDIA-optimized kernels and compilation; top performance on NVIDIA GPUs | Max performance, NVIDIA-only, more complexity |
| **TGI** (Hugging Face) | Was popular; **now in maintenance mode** | Existing deployments; prefer others for new projects |
| **llama.cpp** | C/C++, GGUF, CPU and Apple Silicon first-class, CPU+GPU offload; OpenAI-compatible server | Laptops, edge, on-prem without big GPUs |
| **Ollama** | Developer-friendly wrapper around local models (this book's default) | Local development and prototypes |

Kubernetes-level serving and routing: **KServe**, **Ray Serve**, **llm-d**, **NVIDIA Dynamo/Triton**, plus
gateway routing that's aware of KV-cache locality (send requests sharing a prefix to the same replica).

### 3.12 Autoscaling GPUs and cold starts

- A cold start = schedule a GPU node + pull a big image + download/load tens of GB of weights → **minutes**.
- Keep **warm pools**, pre-pull images, cache weights on local NVMe or shared volumes, and scale on **queue depth /
  KV-cache utilization / pending requests**, not CPU.
- Scale-to-zero saves money but costs minutes of latency on the first request — fine for batch, bad for chat.

### 3.13 Benchmarking

Measure at **your** prompt/output length distribution and **target concurrency**: TTFT and ITL percentiles,
throughput, and **goodput at your SLO**. Sweep concurrency to find the knee where latency explodes. Engines ship
benchmark scripts, and dedicated tools exist (e.g. GuideLLM).

### 3.14 Self-hosting vs API: do the math

```
cost per 1M tokens (self-hosted) = GPU $/hour × GPUs ÷ (tokens/s × 3600 × utilization) × 1,000,000
```

Utilization is everything: an idle GPU still costs money. Add engineers, on-call, redundancy (N+1), upgrades and
evals. Self-hosting usually wins only with **large, steady volume**, **strict data requirements**, **custom
fine-tunes**, or **latency/edge** needs — and only after caching and routing (Ch 37).

---

## 4. Code

### 4.1 Batching, capacity and cost — simulations you can run anywhere

```python
# serving_math.py — continuous vs static batching, GPU capacity, self-host cost (offline simulations)
import random

# 1) STATIC vs CONTINUOUS BATCHING: a batch slot is wasted while waiting for the longest sequence
rng = random.Random(0)
requests = [rng.choice([20, 40, 80, 400]) for _ in range(400)]    # output lengths (tokens), very uneven
SLOTS = 16                                                         # sequences decoded together per step

def static_batching(reqs):
    steps = 0
    for i in range(0, len(reqs), SLOTS):
        steps += max(reqs[i:i + SLOTS])                            # whole batch waits for its longest member
    return steps

def continuous_batching(reqs):
    queue, active, steps = list(reqs), [], 0
    while queue or active:
        while queue and len(active) < SLOTS:                       # refill free slots EVERY decode step
            active.append(queue.pop(0))
        active = [r - 1 for r in active if r > 1]
        steps += 1
    return steps

tokens = sum(requests)
for name, fn in [("static", static_batching), ("continuous", continuous_batching)]:
    steps = fn(requests)
    print(f"{name:10s} batching: {steps:6d} decode steps, slot utilization {tokens / (steps * SLOTS):.0%}")

# 2) HOW MANY CONCURRENT SEQUENCES FIT ON ONE GPU?
def max_sequences(vram_gb, params_b, bytes_per_param, layers, kv_heads, head_dim, context, kv_bytes=2,
                  utilization=0.9, overhead_gb=2):
    weights = params_b * bytes_per_param
    kv_per_seq_gb = 2 * layers * kv_heads * head_dim * kv_bytes * context / 1e9
    free = vram_gb * utilization - weights - overhead_gb
    return max(0, int(free / kv_per_seq_gb)), weights, kv_per_seq_gb

for label, bpp, kvb in [("8B @16-bit, KV 16-bit", 2, 2), ("8B @8-bit (FP8), KV 8-bit", 1, 1)]:
    n, w, kv = max_sequences(80, 8, bpp, layers=32, kv_heads=8, head_dim=128, context=16_000, kv_bytes=kvb)
    print(f"{label:28s}: weights {w:.0f} GB, KV/seq {kv:.2f} GB -> ~{n} sequences of 16K tokens on an 80 GB GPU")

# 3) SELF-HOSTED COST PER 1M OUTPUT TOKENS vs AN API PRICE (example numbers — use real quotes)
def self_host_cost_per_m(gpu_hour_usd, gpus, tokens_per_s_aggregate, utilization):
    tokens_per_hour = tokens_per_s_aggregate * 3600 * utilization
    return gpu_hour_usd * gpus / tokens_per_hour * 1e6

for util in (0.8, 0.3):
    c = self_host_cost_per_m(gpu_hour_usd=4.0, gpus=1, tokens_per_s_aggregate=2500, utilization=util)
    print(f"self-hosted at {util:.0%} utilization: ${c:.2f} per 1M tokens (vs e.g. $0.50-$10 API list prices; "
          f"add ops/people costs)")
```

Verified output:

```
static     batching:  10000 decode steps, slot utilization 33%
continuous batching:   3480 decode steps, slot utilization 94%
8B @16-bit, KV 16-bit       : weights 16 GB, KV/seq 2.10 GB -> ~25 sequences of 16K tokens on an 80 GB GPU
8B @8-bit (FP8), KV 8-bit   : weights 8 GB, KV/seq 1.05 GB -> ~59 sequences of 16K tokens on an 80 GB GPU
self-hosted at 80% utilization: $0.56 per 1M tokens (...)
self-hosted at 30% utilization: $1.48 per 1M tokens (...)
```

The capacity numbers assume every sequence fills its full 16K context; with PagedAttention, sequences only hold
the blocks they actually use, so real concurrency is usually higher.

### 4.2 Run vLLM and call it like any OpenAI-compatible API

```bash
pip install vllm                                    # needs a supported GPU (NVIDIA or others vLLM supports)
vllm serve Qwen/Qwen2.5-7B-Instruct \
    --max-model-len 16384 \
    --gpu-memory-utilization 0.90                   # add --tensor-parallel-size 2 to split across 2 GPUs
# serves an OpenAI-compatible API at http://localhost:8000/v1
```

```python
# vllm_client.py — the same client code works against vLLM, SGLang, llama.cpp's server, or a gateway
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="not-needed-locally")
r = client.chat.completions.create(
    model="Qwen/Qwen2.5-7B-Instruct",
    messages=[{"role": "system", "content": "You are a concise support assistant."},   # stable prefix -> prefix cache
              {"role": "user", "content": "Where is order A-1043?"}],
    max_tokens=200, temperature=0)
print(r.choices[0].message.content, r.usage)
```

Point your gateway's `smart`/`fast` roles (Ch 32) at this endpoint and the rest of your system doesn't change.
(Check each engine's docs for model-specific flags such as tool-call parsers, quantization and speculative
decoding settings — they evolve quickly.)

---

## 5. Production view

| Watch | Why |
|---|---|
| Goodput at SLO, TTFT/ITL p95 | Throughput alone hides user pain |
| KV-cache utilization and preemptions | Near 100% → requests get preempted/recomputed; add capacity or shorten contexts |
| Prefix-cache hit rate | Prompt design matters as much as with APIs |
| Speculative acceptance rate | Low acceptance = wasted compute; tune or disable |
| GPU utilization and idle cost | Self-hosting economics live or die here |
| Quantized-model eval deltas | Quality regressions hide in specific skills |
| Cold-start time | Plan warm capacity for interactive routes |

---

## 6. Common mistakes

- Sizing GPUs by weights only, forgetting the KV cache.
- Benchmarking with one user and short prompts, then deploying for hundreds of users with long contexts.
- Quantizing to 4-bit without re-running evals.
- Tensor parallelism across nodes with slow interconnect.
- Scale-to-zero for interactive chat.
- Choosing self-hosting for cost before doing utilization math.
- Starting new projects on engines in maintenance mode.

---

## 7. Practice

**Level 1**
1. Run `serving_math.py`. Change `SLOTS` to 64 and make output lengths uniform (all 80). How much does continuous
   batching help now — and why?
2. Use `max_sequences` for a 70B model at FP8 on 2×80 GB GPUs (tensor parallel) with 8K contexts (assume 80 layers,
   8 KV heads, head dim 128).

**Level 2**
3. If you have any GPU (or a cloud GPU for an hour), run `vllm serve` with a small model, then load-test it at 1, 8,
   32 and 64 concurrent requests. Plot TTFT p95 and total throughput vs concurrency and find the knee.
4. Without a GPU: run a GGUF model with llama.cpp's server on your laptop and point `vllm_client.py` at it. Compare
   a 4-bit and an 8-bit version on 20 of your eval cases.

**Level 3**
5. Write a **self-hosting decision memo** for a customer: workload (requests/day, tokens per request, SLOs), engine
   choice, GPU type/count from your capacity math, expected utilization, $/1M tokens vs their current API bill,
   operational costs, risks (cold starts, upgrades), and a recommendation.

---

## 8. Check yourself

1. Why is decode memory-bandwidth-bound and prefill compute-bound?
2. What does continuous batching change compared with static batching?
3. Explain PagedAttention with the virtual-memory analogy.
4. How can speculative decoding speed up generation without changing output quality?
5. What is goodput and why does it matter more than throughput?
6. Name the engines you'd consider for (a) a GPU cluster, (b) a MacBook, (c) maximum NVIDIA performance.
7. Why is GPU utilization the key variable in self-hosting cost?

<details>
<summary>Answers</summary>

1. Decode produces one token per step but must read all weights each step (little math per byte read); prefill
   processes many tokens at once, doing lots of math per weight read.
2. Requests join and leave the batch at every decode step instead of waiting for the whole batch to finish, keeping
   GPU slots busy.
3. The KV cache is split into fixed-size blocks mapped through a per-sequence block table, like virtual memory pages;
   sequences use only the blocks they need, fragmentation disappears, and identical prefixes can share physical blocks.
4. A cheap drafter proposes several tokens, the big model verifies them in one pass and accepts the matching prefix;
   with standard verification the output distribution equals the big model's.
5. Requests per second that meet the latency SLO; high throughput with blown latency is useless to users.
6. (a) vLLM or SGLang; (b) llama.cpp (or Ollama); (c) TensorRT-LLM.
7. You pay for GPU hours whether or not they produce tokens; cost per token = hourly cost ÷ tokens actually produced.

</details>

---

## 9. Key terms

**VRAM / HBM bandwidth / FLOPs / interconnect** · **TTFT / TPOT / ITL / throughput / goodput** · **static vs
continuous batching** · **chunked prefill** · **PagedAttention** · **block table** · **prefix caching** ·
**RadixAttention** · **speculative decoding** · **draft model / EAGLE / Medusa** · **acceptance rate** ·
**quantization (FP8, INT8, INT4, GPTQ, AWQ, GGUF)** · **KV-cache quantization** · **tensor / pipeline / data /
expert / context parallelism** · **disaggregated prefill/decode** · **multi-LoRA** · **vLLM / SGLang /
TensorRT-LLM / TGI / llama.cpp / Ollama** · **cold start** · **warm pool**

Next: [Chapter 40 — Fine-tuning →](40-fine-tuning.md)
