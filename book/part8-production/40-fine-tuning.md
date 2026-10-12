# Chapter 40 — Fine-tuning

> Fine-tuning changes the model's **weights** using your examples. It's powerful for **behaviour**
> (format, style, a narrow task, tool-call reliability, a smaller cheaper model) — and the wrong tool
> for **knowledge** (use retrieval) or for fixing a bad prompt. Never fine-tune without an eval set
> that proves it helped.

**You will learn:** the prompt → RAG/tools → fine-tune decision; SFT, preference tuning (DPO and
friends, RLHF), RL with verifiable rewards (RLVR, GRPO), continued pretraining and **distillation**;
**LoRA** and **QLoRA** vs full fine-tuning; data (quality, format, synthetic data, PII, splits);
training basics and the toolchain (TRL, PEFT, Unsloth, Axolotl, hosted APIs); catastrophic forgetting
and regression evals; serving adapters; embedding and reranker fine-tuning; and RL for agents.

**Where this fits:** builds on training stages (Ch 01), model choice (Ch 08), evals (Ch 33 — mandatory),
the data flywheel and traces (Ch 33–34), and multi-LoRA serving (Ch 39). Distillation is a cost lever from
Ch 37; poisoned training data is a security risk from Ch 36.

> **Checked against:** the Hugging Face TRL README and source (TRL 1.15 on PyPI, October 2026; `SFTTrainer`,
> `GRPOTrainer`, `DPOTrainer`) and PEFT's `LoraConfig` (PEFT 0.21). Training code below needs a GPU and was
> not executed here; the data-preparation and LoRA-math code was run.

---

## 1. The idea in plain words

| Your problem | Best first fix |
|---|---|
| Model doesn't know your facts / documents / live data | **RAG and tools** (Part 4, Ch 11) — not fine-tuning |
| Model misunderstands the task | **Better prompt and examples** (Ch 09) |
| Output format or style inconsistent at scale | Structured output (Ch 10) → then **SFT** if still inconsistent |
| A narrow, high-volume task (classify, extract, route) is too slow/expensive on a big model | **Distill** into a small fine-tuned model |
| Small/open model calls your tools unreliably | **SFT on tool-call traces** |
| Quality needs judgement aligned with your preferences | **Preference tuning (DPO etc.)** |
| A checkable task (code, math, SQL, agent task success) needs to improve | **RL with verifiable rewards** |
| Domain language the base model barely knows (rare jargon, a minority language) | **Continued pretraining** + SFT |

Order of attack: **prompt → retrieval/tools → evals prove a gap → fine-tune**. Fine-tuning first is usually
expensive and premature.

---

## 2. Analogy

**Training a new employee.** Giving them the handbook to look things up is RAG. Writing them a clear brief is
prompting. *Fine-tuning* is weeks of practice on real cases until habits change — great for *how* they work
(format, judgement, speed), poor for memorizing a handbook that changes every month.

---

## 3. How it works

### 3.1 Kinds of fine-tuning

| Method | Data | What it teaches |
|---|---|---|
| **SFT (supervised fine-tuning)** | (prompt → ideal response) pairs, in the model's chat format | Format, style, task behaviour, tool-call patterns |
| **Preference tuning: DPO** (and ORPO, KTO, …) | (prompt, preferred, rejected) | Choose better answers; tone; policy adherence — no separate reward model |
| **RLHF (PPO)** | Preferences → a reward model → RL | Same goal, more complex; classic approach |
| **RLVR / GRPO** | Prompts + a **programmatic reward** (tests pass, answer correct, task completed) | Reasoning and agent skills on checkable tasks; GRPO compares a group of samples per prompt (no value network) |
| **Continued pretraining** | Large unlabelled domain text | Domain vocabulary and knowledge priors |
| **Distillation** | A strong "teacher" model's outputs (+ human corrections) | A small "student" that imitates the teacher on a narrow task |
| **Embedding / reranker fine-tuning** | (query, relevant passage, hard negatives) | Better retrieval for your domain (Ch 17, 23) |

### 3.2 LoRA, QLoRA and full fine-tuning

**Full fine-tuning** updates every weight: best ceiling, highest cost, highest risk of **catastrophic
forgetting** (losing general abilities).

**LoRA (Low-Rank Adaptation)** freezes the original weights `W` and learns a small low-rank update:

```
W_adapted = W + (alpha / r) · B·A        W: d×k (frozen)   B: d×r, A: r×k (trainable)   r ≪ d, k
d = k = 4096, r = 16  →  131,072 trainable params instead of 16,777,216 (0.78%) per matrix
```

Benefits: a fraction of the memory and compute, small adapter files (MBs), many adapters on one base model
(**multi-LoRA serving**, Ch 39), easy rollback, less forgetting. Key knobs: rank `r`, `lora_alpha`, dropout,
**target modules** (which layers get adapters — typically attention and MLP projections).

**QLoRA** loads the frozen base model in **4-bit** and trains LoRA adapters on top — fine-tuning fairly large
models on a single GPU.

### 3.3 Data: the part that decides the outcome

- **Quality over quantity:** a few hundred to a few thousand excellent, diverse examples often beat 100K mediocre
  ones for behaviour tasks.
- **Exact chat format** of the target model (system/user/assistant, tool-call messages) — the trainer applies the
  model's chat template.
- **Cover the edge cases:** abstentions ("I don't know"), refusals, multi-turn, tool errors, other languages.
- **Sources:** production traces with good outcomes, **human corrections** (the most valuable data, Ch 22, 33),
  expert-written examples, and **synthetic data** from a strong model — filtered by verifiers and spot-checked by
  humans (unchecked synthetic data teaches the student the teacher's mistakes).
- **Hygiene:** scrub PII and secrets; respect licenses and customer contracts (can you train on this data?); dedupe;
  remove contradictions; keep a **held-out eval split** never used for training.
- **Poisoning risk:** training data is an attack surface (Ch 36) — provenance matters.

### 3.4 Training basics

- Typical SFT: 1–3 epochs; learning rate per the method's defaults (LoRA tolerates higher rates than full FT);
  watch training and eval loss — eval loss rising while training loss falls = **overfitting**.
- Evaluate **every checkpoint** on your task eval set (Ch 33), not just loss.
- Toolchain: **Hugging Face TRL** (`SFTTrainer`, `DPOTrainer`, `GRPOTrainer`), **PEFT** (LoRA/QLoRA), **Unsloth**
  (faster, lower-memory training), **Axolotl** and LLaMA-Factory (config-driven), plus **hosted fine-tuning** from
  model providers and cloud platforms (no GPUs to manage; check data terms).

### 3.5 Evaluate like your job depends on it

Compare on the same eval set:
1. Base model + best prompt (+ RAG) — the baseline to beat.
2. Fine-tuned model.
3. **General capability and safety evals** — catch catastrophic forgetting and safety regressions.
4. Cost and latency (the usual reason for distillation).

Ship only if the fine-tuned model wins on the task **without** unacceptable regressions. Version the adapter and
its training data in the registry (Ch 31).

### 3.6 RL fine-tuning for agents (frontier practice)

- Reward comes from a **verifier** (Ch 24, 33): unit tests pass, the database ends in the right state, the task in a
  simulated environment succeeds.
- Agentic RL scores whole **trajectories**: hard parts are **credit assignment** (which step mattered), **environment
  cost** (each rollout runs tools/sandboxes), and **reward hacking** (the agent games a weak verifier — so verifiers
  must check real outcomes, be deterministic and hard to game).
- **GRPO** samples a group of attempts per prompt and rewards those better than the group average — simpler and
  cheaper than PPO at LLM scale.

### 3.7 Serving fine-tuned models

- **Merge** the adapter into the weights for a single-model deployment, or keep adapters separate and use
  **multi-LoRA** serving (Ch 39) — one base model, many tenant/task adapters.
- Re-run evals after quantizing a fine-tuned model (Ch 39).
- Plan for **base-model upgrades**: adapters are tied to their base model; a new base means re-training and re-evaluating.

---

## 4. Code

### 4.1 Why LoRA is cheap (runs anywhere)

```python
# lora_intuition.py — why LoRA is cheap: a low-rank update instead of a full weight update (numpy)
import numpy as np

d, k, r = 4096, 4096, 16
full, lora = d * k, r * (d + k)
print(f"full update: {full:,} params | LoRA r={r}: {lora:,} params ({lora / full:.2%})")

rng = np.random.default_rng(0)
W = rng.normal(size=(64, 64))                    # a frozen pretrained weight (small, for the demo)
B = rng.normal(size=(64, 4)) * 0.1               # trainable, rank 4
A = rng.normal(size=(4, 64)) * 0.1               # trainable
alpha, rank = 8, 4
W_adapted = W + (alpha / rank) * B @ A           # what the model uses at inference (can be merged)
print("rank of the update:", np.linalg.matrix_rank(B @ A), "| shape:", W_adapted.shape)
```

Output: `full update: 16,777,216 params | LoRA r=16: 131,072 params (0.78%)` and `rank of the update: 4`.

### 4.2 Build an SFT dataset from traces and human corrections (runs anywhere)

```python
# prepare_sft_data.py — turn production traces + human corrections into a clean SFT dataset
import hashlib
import json
import random
import re

traces = [  # from your trace store (Ch 34): what the agent said, and what a human corrected it to
    {"input": "Where's order A-1043?", "output": "It shipped via DHL, arriving Oct 15.", "corrected": None, "score": 1},
    {"input": "Can I return worn shoes?", "output": "Yes, within 30 days.",
     "corrected": "Worn shoes can't be returned, but damaged items can be returned within 60 days.", "score": 0},
    {"input": "Where's order A-1043?", "output": "It shipped via DHL, arriving Oct 15.", "corrected": None, "score": 1},
    {"input": "My email is priya@example.com, refund please", "output": "I've started a refund review.",
     "corrected": None, "score": 1},
    {"input": "Do you sell gift cards?", "output": "Yes, from $10.", "corrected": "I don't know based on our policies.",
     "score": 0},
]
SYSTEM = "You are Acme's support assistant. Answer only from policy; say when you don't know."

def scrub(text):
    return re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "<email>", text)     # never train on raw PII

examples, seen = [], set()
for t in traces:
    target = t["corrected"] or (t["output"] if t["score"] == 1 else None)   # keep good outputs + corrections
    if target is None:
        continue
    record = {"messages": [{"role": "system", "content": SYSTEM},
                           {"role": "user", "content": scrub(t["input"])},
                           {"role": "assistant", "content": scrub(target)}]}
    key = hashlib.sha256(json.dumps(record, sort_keys=True).encode()).hexdigest()
    if key in seen:                                                  # dedupe
        continue
    seen.add(key)
    examples.append(record)

random.Random(0).shuffle(examples)
split = max(1, int(len(examples) * 0.8))
for name, rows in [("train.jsonl", examples[:split]), ("eval.jsonl", examples[split:])]:
    with open(name, "w") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")
    print(name, len(rows), "examples")
print(json.dumps(examples[0], indent=1)[:400])
```

Notice the policy: keep good outputs, **replace** bad ones with the human correction, drop bad uncorrected ones,
scrub PII, dedupe, and split off an eval set.

### 4.3 LoRA SFT with TRL + PEFT (needs a GPU)

```python
# train_lora_sft.py — checked against TRL 1.15 / PEFT 0.21 APIs; run on a GPU machine
from datasets import load_dataset
from peft import LoraConfig
from trl import SFTConfig, SFTTrainer

train = load_dataset("json", data_files="train.jsonl", split="train")      # {"messages": [...]} rows
evals = load_dataset("json", data_files="eval.jsonl", split="train")

trainer = SFTTrainer(
    model="Qwen/Qwen2.5-0.5B-Instruct",                     # start small; scale up only if evals demand it
    train_dataset=train,
    eval_dataset=evals,
    args=SFTConfig(output_dir="support-lora", num_train_epochs=2, learning_rate=2e-4,
                   per_device_train_batch_size=4, eval_strategy="epoch", logging_steps=10),
    peft_config=LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, target_modules="all-linear",
                           task_type="CAUSAL_LM"),
)
trainer.train()
trainer.save_model("support-lora")                           # adapter weights only — a few MB
```

### 4.4 GRPO with a programmatic reward (needs a GPU)

```python
# train_grpo.py — reinforcement learning with a VERIFIABLE reward (checked against TRL 1.15 API shape)
import json
import re
from datasets import load_dataset
from trl import GRPOConfig, GRPOTrainer

def json_tool_call_reward(completions, **kwargs):
    """+1 if the completion is a valid JSON tool call for get_order with a well-formed ID, else 0."""
    rewards = []
    for c in completions:
        text = c[-1]["content"] if isinstance(c, list) else c     # conversational or plain format
        try:
            call = json.loads(text)
            ok = call.get("tool") == "get_order" and re.fullmatch(r"A-\d{4}", call.get("order_id", ""))
            rewards.append(1.0 if ok else 0.0)
        except (json.JSONDecodeError, AttributeError):
            rewards.append(0.0)
    return rewards

dataset = load_dataset("json", data_files="prompts.jsonl", split="train")   # rows with a "prompt" field
trainer = GRPOTrainer(model="Qwen/Qwen2.5-0.5B-Instruct", reward_funcs=json_tool_call_reward,
                      args=GRPOConfig(output_dir="grpo-toolcalls"), train_dataset=dataset)
trainer.train()
```

The reward is a **program** — the same idea as verifier-guided generation (Ch 24) and final-state evals (Ch 33).

---

## 5. Production view

| Concern | Practice |
|---|---|
| Proof of value | Before/after table on the task eval + general + safety evals; cost and latency |
| Reproducibility | Version data, code, base model, hyperparameters; registry entry per adapter (Ch 31) |
| Data rights and privacy | Contracts allow training? PII scrubbed? Retention honoured? |
| Drift | Re-train cadence from the data flywheel; monitor override rates (Ch 33) |
| Base-model upgrades | Budget re-training + re-evaluation; keep the prompt-only baseline current |
| Safety | Fine-tuning can weaken safety behaviour — always include safety evals |

---

## 6. Common mistakes

- Fine-tuning to "teach facts" that change (use RAG).
- Fine-tuning before trying a good prompt, examples and structured output.
- No held-out eval set — or evaluating on training data.
- Unreviewed synthetic data; training on raw PII.
- Wrong chat template (silent quality loss).
- Ignoring general/safety regressions.
- Weak RL rewards that the model learns to game.

---

## 7. Practice

**Level 1**
1. Run `lora_intuition.py` with r = 4, 64, 256. When does LoRA stop being "cheap"?
2. Run `prepare_sft_data.py`. Add 3 traces of your own, including one with a phone number and one duplicate.

**Level 2**
3. Build a 300-example SFT set for one narrow task (e.g. ticket classification into 8 labels) using a strong model to
   label and you to review 10%. Evaluate the base small model with the best prompt on 50 held-out cases. That baseline
   number decides whether fine-tuning is even needed.
4. Write 20 DPO pairs (preferred vs rejected answers) for your support agent's tone and abstention behaviour. What
   makes a *good* rejected example?

**Level 3**
5. On a GPU (cloud is fine), run `train_lora_sft.py` for the classification task with a 0.5B–1.5B model; compare
   accuracy, latency and cost per 1K requests against the large prompted model. Serve the adapter with vLLM's LoRA
   support (Ch 39) and wire it behind a gateway alias (Ch 32). Write the go/no-go memo.

---

## 8. Check yourself

1. Why is fine-tuning a poor way to add frequently changing knowledge?
2. SFT vs DPO vs GRPO — what data does each need?
3. How does LoRA reduce trainable parameters? Give the formula.
4. What is QLoRA?
5. Name four data-hygiene steps before fine-tuning.
6. What evals must a fine-tuned model pass before shipping?
7. What is reward hacking and how do you reduce it?

<details>
<summary>Answers</summary>

1. Knowledge baked into weights goes stale, is hard to update or delete, and can't be cited; retrieval keeps facts
   current, traceable and permission-filtered.
2. SFT: prompt → ideal response pairs. DPO: prompt + preferred + rejected responses. GRPO: prompts plus a reward
   function (ideally programmatic/verifiable).
3. It freezes W and learns W + (alpha/r)·B·A with B (d×r) and A (r×k), so trainable params are r(d+k) instead of d·k.
4. Fine-tuning LoRA adapters on top of a base model loaded in 4-bit, cutting memory so larger models fit on one GPU.
5. Any four: PII/secret scrubbing, licensing/consent checks, deduplication, removing contradictions, correct chat
   format, held-out eval split, provenance checks.
6. The task eval vs the prompt/RAG baseline, general capability evals (forgetting), safety evals, and cost/latency.
7. The model finds ways to score reward without truly solving the task (gaming a weak checker); use verifiers that
   check real outcomes, are deterministic and hard to game, and audit samples of high-reward trajectories.

</details>

---

## 9. Key terms

**fine-tuning** · **SFT** · **preference tuning** · **DPO / ORPO / KTO** · **RLHF / PPO** · **RLVR** · **GRPO** ·
**continued pretraining** · **distillation (teacher/student)** · **LoRA** · **rank r / lora_alpha / target modules** ·
**QLoRA** · **full fine-tuning** · **catastrophic forgetting** · **chat template** · **synthetic data** · **held-out
split** · **adapter merge / multi-LoRA** · **reward hacking** · **TRL / PEFT / Unsloth / Axolotl**

Next: [Part 9 — Chapter 41: Multimodal →](../part9-interfaces/41-multimodal.md)
