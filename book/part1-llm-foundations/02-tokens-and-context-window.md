# Chapter 02 — Tokens and the context window

> Models don't read letters or words. They read **tokens**. Tokens decide what you pay,
> how fast you get an answer, how much fits in one request, and some strange failures.

**You will learn:** what tokens are, how tokenizers (BPE) are built, why different models
count differently, why non-English text costs more, what chat templates and special tokens
are, what the context window is, and why quality drops in long contexts (**context rot**,
**lost in the middle**).

**Where this fits:** builds on [Ch 01](01-what-is-an-llm.md) (the model reads tokens, one
step at a time). Tokens are the unit of cost and latency (Ch 03), the n² attention cost
explains long-context pain (Ch 05), and the context window is the budget that context
engineering (Ch 15) and retrieval (Ch 17–19) manage.

---

## 1. The idea in plain words

Before the model sees your text, a **tokenizer** cuts it into pieces called **tokens** and
turns each piece into a number (a **token ID**). The model only ever sees the list of numbers.

```
"Unbelievable results!"  →  ["Un", "believ", "able", " results", "!"]  →  [1844, 33567, 481, 3135, 0]
```

Common words are usually one token. Rare words are split into several. Spaces are often
part of the token (`" results"` with a leading space is a different token from `"results"`).

The **context window** is the maximum number of tokens the model can handle in one
request — **your input plus its output, together**. Everything the model knows about your
task must fit in that window.

Rough rules for English:

| Unit | ≈ Tokens |
|---|---|
| 1 token | ~4 characters, ~¾ of a word |
| 100 words | ~130–150 tokens |
| 1 page of text | ~500–800 tokens |
| 1 page as an **image** | ~1,500–2,500 tokens (Ch 21, Ch 41) |
| Code | more tokens per line than prose (symbols, indentation) |

---

## 2. Analogy

**Shipping containers.** You don't ship loose items; you pack them into standard
containers. The tokenizer packs text into standard pieces. The **context window** is the
size of the ship: input cargo + output cargo must both fit. You pay per container (token),
not per item (word).

Where it breaks: containers are all the same size. Tokens are not — one token can be one
letter or a whole word.

---

## 3. How it works

### 3.1 How a tokenizer is built: Byte-Pair Encoding (BPE)

Most modern tokenizers use **BPE** (or close variants like SentencePiece/Unigram):

```
1. Start: every byte/character is its own token.        l o w e s t   n e w e s t
2. Count every adjacent pair in a big training text.    "e s" is most common
3. Merge the most common pair into a new token.         l o w es t    n e w es t
4. Repeat thousands of times.                           l o w est     n e w est
5. Stop at a target vocabulary size (e.g. 32K–200K+).
```

Result: frequent text (common English words, common code) becomes single tokens. Rare text
(unusual names, many non-English scripts) stays split into many small tokens.

### 3.2 Chat messages become one long token list

You send structured messages. The model receives **one flat sequence** with **special
tokens** marking roles. This formatting is called the **chat template**. For a Llama-style
model it looks roughly like:

```
<|begin_of_text|><|start_header_id|>system<|end_header_id|>
You are a helpful assistant.<|eot_id|><|start_header_id|>user<|end_header_id|>
What is 2+2?<|eot_id|><|start_header_id|>assistant<|end_header_id|>
```

The model then generates the assistant's tokens and ends with a special stop token.
Important consequences:
- **Roles are just text with markers.** A "system prompt" is not magic — it's tokens at the start.
- **The template adds overhead tokens** to every message.
- **Tool definitions are also turned into tokens** and inserted into this sequence. Tools
  cost tokens on every call (Ch 11).

### 3.3 The context window

```
┌──────────────────────── context window (e.g. 128K or 200K tokens) ──────────────────────┐
│ system prompt │ tool definitions │ documents │ conversation history │ new message │ OUTPUT │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                   input tokens                                 ↑ max_tokens
```

- **max_tokens / max output tokens**: a separate, smaller cap on how much the model may
  write. If it's hit, the answer is cut off mid-sentence (the response says why — e.g.
  `stop_reason: "max_tokens"` or `done_reason: "length"`). Always check this field.
- If **input + max output > window**, the API returns an error — or, on some local servers,
  **silently drops the oldest tokens**. (Ollama does this when you exceed its `num_ctx`
  setting, whose default is small. Set it explicitly.)

### 3.4 Bigger is not automatically better: context rot and lost-in-the-middle

Models advertise windows of 100K–1M+ tokens. But quality is not flat across the window:

- **Context rot:** as you add more tokens — especially irrelevant ones — accuracy on the
  task goes down, even well below the limit. More text = more distraction.
- **Lost in the middle:** models recall information at the **start** and **end** of the
  context better than information in the **middle**.

```
recall
  ▲
  │█                                  █
  │█ █                              █ █
  │█ █ █                          █ █ █
  │█ █ █ █   █   █   █   █   █  █ █ █ █
  └──────────────────────────────────────► position of the fact in the context
   start            middle              end
```

**Practical rule:** the context window is a *budget*, not a *bucket*. Put only what the
task needs; put the most important instructions at the start and the question at the end.
(This becomes **context engineering**, Ch 15.)

---

## 4. Code

### 4.1 Count tokens and see the pieces

```python
# ch02_tokens.py
import tiktoken   # OpenAI's tokenizer library; good for estimates, exact only for OpenAI models

enc = tiktoken.get_encoding("cl100k_base")

def show(text):
    ids = enc.encode(text)
    pieces = [enc.decode([i]) for i in ids]
    print(f"{len(ids):3d} tokens | {pieces}")

show("Hello world")
show("Unbelievable results!")
show("strawberry")                       # why models miscount letters: they see pieces, not letters
show("1234567 * 89")                     # numbers split in odd places → weak raw arithmetic
show("def add(a, b):\n    return a + b") # code: symbols and spaces cost tokens
```

### 4.2 Non-English text costs more

```python
# ch02_languages.py
import tiktoken
enc = tiktoken.get_encoding("cl100k_base")

samples = {
    "English": "Where is the nearest train station?",
    "Tamil":   "அருகிலுள்ள ரயில் நிலையம் எங்கே?",
    "Hindi":   "सबसे नज़दीकी रेलवे स्टेशन कहाँ है?",
}
base = len(enc.encode(samples["English"]))
for lang, text in samples.items():
    n = len(enc.encode(text))
    print(f"{lang:8s} {n:3d} tokens  ({n / base:.1f}x English)")
```

The same meaning can cost several times more tokens in some scripts. For a customer
serving users in Tamil or Hindi, this means **higher cost, higher latency, and a smaller
effective context window**. Newer tokenizers are better at this — measure for the model
you actually use.

### 4.3 Measure template overhead with the real model

```python
# ch02_overhead.py — the model's own count, including chat-template tokens
import ollama

def count(messages):
    r = ollama.chat(model="llama3.2", messages=messages, options={"num_predict": 1})
    return r["prompt_eval_count"]

just_user = [{"role": "user", "content": "Hi"}]
with_system = [{"role": "system", "content": "You are a helpful assistant."}] + just_user

print("user 'Hi' only:  ", count(just_user))
print("plus system msg: ", count(with_system))
```

"Hi" is 1 token of text, but the model counts many more — that's the template (and, in some
models, a default system prompt). Always measure with the **model's own counter**, not an
estimate, when the number matters (billing, limits).

> **Hosted APIs** give you exact counts in the response's `usage` field, and most offer a
> **token-counting endpoint** to count *before* you send. Use it for budget checks.

### 4.4 Needle in a haystack: find the lost-in-the-middle effect yourself

```python
# ch02_needle.py — hide one fact at different positions in long filler text
import ollama

NEEDLE = "The secret code for the vault is PURPLE-TIGER-42."
FILLER = "The weather report said it would be mild and cloudy with light wind. " * 300

def ask(position):                      # position between 0.0 (start) and 1.0 (end)
    cut = int(len(FILLER) * position)
    doc = FILLER[:cut] + NEEDLE + " " + FILLER[cut:]
    r = ollama.chat(
        model="llama3.2",
        messages=[{"role": "user", "content": doc + "\n\nWhat is the secret code for the vault?"}],
        options={"num_ctx": 8192, "temperature": 0},
    )
    return "PURPLE-TIGER-42" in r["message"]["content"], r["prompt_eval_count"]

for pos in [0.0, 0.25, 0.5, 0.75, 1.0]:
    found, tokens = ask(pos)
    print(f"position {pos:.2f}  tokens={tokens}  found={found}")
```

On a small local model you will often see failures at some positions. Make the filler
longer, and you'll see more. (If `tokens` is much lower than expected, the server
truncated your input — raise `num_ctx`.)

---

## 5. Production view

| Problem | What you see | Detect | Fix |
|---|---|---|---|
| Silent truncation | Model ignores instructions or documents that you *did* send | Compare tokens you sent (estimate) vs `prompt_eval_count`/`usage` | Set context size explicitly; count before sending; trim deliberately (Ch 15) |
| Output cut off | Half a JSON object, half a sentence | Check `stop_reason`/`done_reason` == length/max_tokens on **every** call | Raise `max_tokens`, ask for shorter output, or continue generation |
| Context limit error | API 400 error on long conversations | Error rate by conversation length | Compaction (Ch 15), budget check before each call (Ch 14) |
| Wrong cost estimates | Bill is 30% above forecast | Compare estimated vs billed tokens | Use the provider's own token counter, not `tiktoken`, for non-OpenAI models |
| Multilingual cost | One country's users cost 3× more | Cost per request, grouped by language | Pick a model with a better tokenizer for that language; shorter prompts; caching |
| Long-context quality drop | Answers worse as documents are added | Evals at different context lengths (needle tests) | Retrieve less but better (Ch 17), put key info at start/end |

---

## 6. Common mistakes

- **Counting words or characters instead of tokens.** Budget in tokens.
- **Using `tiktoken` counts for Claude, Llama or Gemini.** Each has its own tokenizer; use
  it only as a rough estimate.
- **Forgetting that tools and system prompts cost tokens on every single call.**
- **Never checking the stop reason.** A truncated answer looks like a bad answer.
- **Dumping the whole knowledge base into a 1M-token window** "because it fits". It's slow,
  expensive, and quality drops.

---

## 7. Practice

**Level 1**
1. Run `ch02_tokens.py`. Add your own name, an email address and a URL. Which split into
   the most tokens?
2. Run `ch02_languages.py` with a sentence in your own language. What's the multiplier?
3. Ask the model to write a 500-word story with `options={"num_predict": 50}`. Print
   `done_reason`. What happened?

**Level 2**
4. Run `ch02_needle.py`. Then make `FILLER` 3× longer and run it again. Record a small
   table: position × length → found. Write 3 lines in your notes about what you saw.
5. Write `fits_in_context(messages, max_output, window)` that returns `True/False` using the
   model's own count (from a 1-token call) and refuses to send oversized requests.

**Level 3**
6. Implement BPE yourself: start from characters of a small text, repeatedly merge the
   most frequent adjacent pair, stop after 50 merges. Print the learned merges and tokenize
   a new sentence with them. (About 40 lines. Hint: represent words as tuples of symbols.)

---

## 8. Check yourself

1. What is inside the context window — only your prompt?
2. Why do LLMs often fail at "how many r's are in strawberry"?
3. A Tamil-language support bot costs 3× more than the English one with the same traffic.
   Give the most likely reason.
4. You put a 300-page manual in the context and the model misses a rule on page 150. Name
   the effect and two ways to fix it.
5. What field do you check to know if an answer was cut off?

<details>
<summary>Answers</summary>

1. No: system prompt, tool definitions, documents, history, the new message **and the
   output** all share it.
2. The model sees tokens like `"str" "aw" "berry"`, not individual letters, so counting
   letters requires knowledge it can't directly see.
3. The tokenizer splits Tamil script into many more tokens for the same meaning, so every
   request has more input and output tokens.
4. Lost-in-the-middle (and context rot). Fixes: retrieve only the relevant section (RAG,
   Ch 17) or agentic navigation or PageIndex-style tree search (Ch 19); put the key rule near the start or end; use a
   smaller, focused context.
5. The stop/finish reason (`stop_reason`, `finish_reason`, Ollama's `done_reason`) — e.g.
   `max_tokens` / `length` means it was truncated.

</details>

---

## 9. Key terms

**token** · **token ID** · **tokenizer** · **vocabulary** · **BPE** · **special tokens** ·
**chat template** · **context window** · **max_tokens** · **stop reason** · **truncation** ·
**context rot** · **lost in the middle** · **needle-in-a-haystack test**

Next: [Chapter 03 — Cost and latency →](03-cost-and-latency.md)
