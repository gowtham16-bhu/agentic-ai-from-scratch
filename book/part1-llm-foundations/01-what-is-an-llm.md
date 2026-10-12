# Chapter 01 — What an LLM is

> An LLM is a program that predicts the next piece of text, one piece at a time, over and
> over. Everything else — chat, tools, agents — is built on top of that one trick.

**You will learn:** next-token prediction, how models are trained (pretraining, SFT,
RLHF, DPO, Constitutional AI, RL with verifiable rewards), the difference between base,
instruct and reasoning models, and three facts that shape every system you build:
**LLMs are stateless, have a knowledge cutoff, and are probabilistic.**

**Where this fits:** builds on [Ch 00](../part0-start/00-setup.md). The three facts above
drive the rest of the book: *stateless* → context and memory (Ch 15, 16); *knowledge
cutoff* → tools and retrieval (Ch 11, 17–23); *probabilistic* → sampling, hallucination
and evals (Ch 04, 07, 33). The training stages return in reasoning (Ch 24) and
fine-tuning (Ch 40).

---

## 1. The idea in plain words

A **Large Language Model (LLM)** reads some text and answers one question:

> "Given everything so far, what piece of text most likely comes next?"

It picks a piece (a **token** — roughly ¾ of a word), adds it to the text, and asks the
same question again. It repeats until it decides to stop. That is the whole generation
process. It is called **autoregressive generation** — each new token depends on all the
previous ones.

"Large" means two things: the model has billions of internal numbers (**parameters**,
also called **weights**), and it was trained on trillions of tokens of text.

---

## 2. Analogy

**Phone autocomplete, scaled up enormously.** Your phone keyboard suggests the next word
from what you typed. An LLM does the same thing, but it has read a large part of the
internet, books and code, so its "next word" guesses can produce essays, programs and
plans.

**A brilliant, well-read intern with no notebook and no phone.** They have read almost
everything up to a certain date. They answer fluently. But:
- they forget you the moment the conversation ends (**stateless**),
- they don't know anything that happened after their reading stopped (**knowledge cutoff**),
- they can't look things up or do anything unless you hand them tools (**tools**, Ch 11),
- if they don't know, they may still answer confidently (**hallucination**, Ch 07).

Where the analogy breaks: the intern *understands* things in a human way. An LLM has
learned statistical patterns so rich that it *behaves* as if it understands, very often —
but it fails in non-human ways (e.g. miscounting letters in a word, see Ch 02).

---

## 3. How it works

### 3.1 Generation (what happens when you call the model)

```
 "The capital of France is"          ← your prompt, split into tokens
            │
            ▼
   ┌──────────────────┐
   │   the model      │   computes a probability for EVERY token in its vocabulary
   └──────────────────┘
            │
            ▼
   " Paris"  0.92
   " a"      0.03          ← pick one (how: Chapter 04, sampling)
   " the"    0.01
            │
            ▼
 "The capital of France is Paris"    ← append and repeat
            │
            ▼
   "."  0.71  ...                    ← until a special "end" token is picked
```

### 3.2 Training (how the model got its knowledge and behavior)

```
 STAGE 1: PRETRAINING                      → BASE MODEL
 trillions of tokens of internet, books, code
 task: predict the next token, billions of times
 learns: language, facts, reasoning patterns, code
 cost: huge (thousands of GPUs, months)
            │
            ▼
 STAGE 2: SUPERVISED FINE-TUNING (SFT)      → INSTRUCT MODEL (first version)
 tens of thousands of (instruction → good answer) examples written by humans
 learns: to follow instructions, chat format, answer instead of ramble
            │
            ▼
 STAGE 3: PREFERENCE TUNING                 → HELPFUL, SAFER CHAT MODEL
 humans (or an AI) compare two answers: "A is better than B"
 methods: RLHF (train a reward model, then RL)
          DPO  (learn directly from the preference pairs, no reward model)
          RLAIF / Constitutional AI (an AI judges answers against written principles)
 learns: style, helpfulness, refusing harmful requests
            │
            ▼
 STAGE 4: RL WITH VERIFIABLE REWARDS (RLVR) → REASONING MODEL
 tasks where a PROGRAM can check the answer (math, code tests, puzzles)
 the model tries many times, gets reward when the checker says "correct"
 methods: PPO, GRPO (cheaper: compares a group of attempts, no value network)
 learns: to "think" longer, try, check, backtrack before answering
```

**Why you, an engineer, care about training stages:**

| Stage | What it explains in your daily work |
|---|---|
| Pretraining on next-token prediction | The model's goal is *plausible* text, not *true* text → hallucination |
| SFT on human-written answers | The model follows the chat format; it needs clear instructions |
| Preference tuning | The model wants to please → **sycophancy** (agreeing with you when you're wrong) |
| RLVR | Reasoning models are great when the answer is checkable (code, math, SQL) |
| Training data has a date | **Knowledge cutoff** → you must supply fresh facts via tools/RAG |

### 3.3 Three model families you will meet

| Family | What it is | Use it for |
|---|---|---|
| **Base model** | Only pretrained. Continues text; does not follow instructions well. | Fine-tuning starting point, research. Rarely used directly in products. |
| **Instruct / chat model** | Base + SFT + preference tuning. | Most product work: chat, extraction, tools, agents. |
| **Reasoning model** | Instruct + RL on verifiable tasks; produces "thinking" tokens before the answer. | Hard multi-step problems: planning, math, code, complex analysis. More expensive and slower. |

Many current models are **hybrid**: one model where you turn thinking on/off or set a
thinking **budget** / **effort** level per request (Ch 08, Ch 24).

---

## 4. Code

### 4.1 Watch autoregressive generation happen (streaming)

```python
# ch01_stream.py — see the model produce one small piece at a time
import ollama

stream = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Explain gravity in two sentences."}],
    stream=True,                       # give me pieces as they are generated
)
for chunk in stream:
    piece = chunk["message"]["content"]
    print(repr(piece), end=" ", flush=True)   # repr shows exact pieces, incl. spaces
print()
```

You'll see output like `'Gravity' ' is' ' a' ' force' ...` — the model really does write one
small piece at a time.

### 4.2 Prove the model is stateless

```python
# ch01_stateless.py
import ollama

MODEL = "llama3.2"

# Call 1: tell it your name
r1 = ollama.chat(model=MODEL, messages=[
    {"role": "user", "content": "My name is Gowtham. Remember it."}])
print("Call 1:", r1["message"]["content"])

# Call 2: a NEW request with no history
r2 = ollama.chat(model=MODEL, messages=[
    {"role": "user", "content": "What is my name?"}])
print("Call 2 (no history):", r2["message"]["content"])      # it does not know

# Call 3: send the history yourself
history = [
    {"role": "user", "content": "My name is Gowtham. Remember it."},
    r1["message"],                                            # the model's own reply
    {"role": "user", "content": "What is my name?"},
]
r3 = ollama.chat(model=MODEL, messages=history)
print("Call 3 (with history):", r3["message"]["content"])    # now it knows
```

**The lesson:** the model has no memory between calls. A "conversation" is an illusion
**you** create by re-sending the whole history every time. This has a cost: turn 10 sends
turns 1–9 again (Ch 03). It also means *you* own the state — which is why memory
(Ch 16) and checkpoints (Ch 26) are your job, not the model's.

### 4.3 Next-token prediction by hand: a tiny language model

This is not a neural network, but it does the *same job* in the simplest way: count which
word follows which, then generate by picking likely next words.

```python
# ch01_bigram.py — a toy "language model" in 25 lines
import random
from collections import defaultdict, Counter

text = """the cat sat on the mat . the dog sat on the rug .
the cat ate the fish . the dog ate the bone . the cat saw the dog ."""

words = text.split()
next_counts = defaultdict(Counter)            # word -> Counter of following words
for current, following in zip(words, words[1:]):
    next_counts[current][following] += 1

def next_word_probs(word):
    counts = next_counts[word]
    total = sum(counts.values())
    return {w: c / total for w, c in counts.items()}

print("After 'the':", next_word_probs("the"))
print("After 'sat':", next_word_probs("sat"))

def generate(start, n=8):
    out = [start]
    for _ in range(n):
        probs = next_word_probs(out[-1])
        if not probs:
            break
        out.append(random.choices(list(probs), weights=list(probs.values()))[0])
    return " ".join(out)

for _ in range(3):
    print(generate("the"))
```

A real LLM replaces "count the previous 1 word" with "a neural network that looks at the
previous *hundreds of thousands* of tokens" — but the generation loop is the same.

---

## 5. Production view

| Property | What breaks | How you detect it | What you do |
|---|---|---|---|
| **Stateless** | Long chats get slow and expensive; the model "forgets" early turns when history is trimmed | Token count per turn keeps growing (Ch 03) | Context engineering (Ch 15), memory (Ch 16), caching (Ch 12) |
| **Knowledge cutoff** | Confident answers about outdated prices, policies, APIs | Evals with questions about recent facts | Give fresh data via tools (Ch 11) and RAG (Ch 17); put today's date in the prompt when relevant |
| **Probabilistic** | Same input → different outputs; flaky tests | Run the same eval case several times (pass^k, Ch 33) | Lower temperature for deterministic tasks (Ch 04), structured output (Ch 10), verification |
| **Trained to please** | Agrees with a wrong user claim (sycophancy) | Eval cases where the user is confidently wrong | Prompt: "correct the user if they are wrong"; verify with tools |
| **The model changes under you** | Provider updates a model alias; behavior shifts; "it worked last week" | Record the exact model ID on every call (Ch 34) | Pin exact model versions; re-run evals before switching |

---

## 6. Common mistakes

- **Treating the LLM like a database.** It stores patterns, not records. Ask it for an
  exact fact it rarely saw, and it may invent one. Facts come from tools and documents.
- **Thinking the model remembers.** It doesn't. Every call starts blank.
- **Expecting the same answer twice.** Without care (Ch 04), outputs vary.
- **Using a reasoning model for everything.** It's slower and costlier. Many tasks
  (classification, extraction, simple chat) don't need it (Ch 08).
- **Thinking "AI" means one thing.** Base, instruct and reasoning models behave very
  differently. Always know which one you're calling.

---

## 7. Practice

**Level 1**
1. Run `ch01_stream.py`. Count roughly how many pieces were produced for a 2-sentence answer.
2. Run `ch01_stateless.py`. Then change Call 3 to remove `r1["message"]` from history. Does
   it still work? Why?
3. Ask the model: "What is today's date?" and "Who won the most recent football World Cup?"
   Explain the answers using "stateless" and "knowledge cutoff".

**Level 2**
4. Extend `ch01_bigram.py` to use **two** previous words (a trigram). Generate text. Is it
   more or less sensible? Why? (More context → better predictions — the same reason LLMs
   use long contexts.)
5. Build a 5-turn chat loop in the terminal (`input()` → append → call → append). Print the
   input token count each turn. Watch it grow.

**Level 3**
6. Train the bigram model on a larger text (any public-domain book from Project Gutenberg).
   Add a `temperature` parameter: raise each probability to the power `1/temperature` and
   re-normalize. Generate at temperature 0.5, 1.0 and 2.0. Describe the difference. You just
   implemented sampling temperature (Ch 04).

---

## 8. Check yourself

1. In one sentence, what does an LLM do at each generation step?
2. Why does an LLM sometimes state wrong facts confidently? Connect it to pretraining.
3. A customer says, "Your chatbot remembered me yesterday, so the model has memory." What
   is actually happening?
4. When would you choose a reasoning model over a standard instruct model?
5. What does RLVR need that RLHF doesn't?

<details>
<summary>Answers</summary>

1. It computes probabilities for every possible next token given all text so far, picks
   one, appends it, and repeats.
2. Pretraining rewards producing *plausible* continuations, not *true* ones. When the model
   lacks a fact, the most plausible-sounding continuation is still produced — fluently.
3. The application stored the history (or a summary / memory record) and sent it back with
   the new request. The model itself is stateless; the app provides the memory.
4. When the task is multi-step and hard (planning, math, complex code, careful analysis),
   and the extra latency and cost are acceptable. Not for simple extraction or chat.
5. A program that can automatically check whether an answer is correct (a *verifier*:
   unit tests, a math checker). RLHF uses human (or AI) preferences instead.

</details>

---

## 9. Key terms

**LLM** · **token** · **parameters / weights** · **autoregressive generation** ·
**pretraining** · **base model** · **SFT (supervised fine-tuning)** · **instruct model** ·
**RLHF** · **reward model** · **DPO** · **RLAIF** · **Constitutional AI** · **RLVR** ·
**GRPO** · **reasoning model** · **thinking budget** · **stateless** · **knowledge cutoff** ·
**sycophancy**

Next: [Chapter 02 — Tokens and the context window →](02-tokens-and-context-window.md)
