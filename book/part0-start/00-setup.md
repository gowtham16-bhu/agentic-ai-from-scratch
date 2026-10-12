# Chapter 00 — Setup and how to study

> Get a working lab on your laptop in one evening, and learn the study method that makes
> the rest of the book stick.

**You will learn:** what to install, how to keep costs at zero while learning, how to
organize your code, and how to study so you can *explain and build*, not just recognize.

---

## 1. The idea in plain words

You need three things to learn agent engineering:

1. **A model you can call** — locally (free, private) and later a hosted one (more capable).
2. **A place to write and run Python** — a project folder with a virtual environment.
3. **A habit** — read a concept, type the code, break it on purpose, explain it back.

That is all. No GPU is needed. A normal laptop with 8–16 GB RAM can run a small local model.

---

## 2. Install the lab

### 2.1 Python

Use Python 3.11 or newer.

```bash
python3 --version          # should print 3.11+ 
```

Create a project and a virtual environment (an isolated box for this project's packages):

```bash
mkdir agent-lab && cd agent-lab
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install ollama pydantic httpx tiktoken rank_bm25 python-dotenv
```

> **Faster option:** [`uv`](https://docs.astral.sh/uv/) is a much faster package manager.
> `uv venv && uv pip install ollama pydantic ...` does the same thing.

### 2.2 Ollama (your free local model server)

Install from [ollama.com](https://ollama.com), then pull two models:

```bash
ollama pull llama3.2            # a small chat model with tool calling (~2 GB)
ollama pull nomic-embed-text    # an embedding model (for search / RAG)
ollama list                     # check they are there
```

Test it:

```bash
ollama run llama3.2 "Say hello in one short sentence."
```

Ollama runs a server at `http://localhost:11434`. The Python `ollama` package talks to it.

### 2.3 A hosted model (optional now, needed by Part 2)

Local small models are great for learning the *mechanics*, but they are weaker at
following instructions and calling tools. Real FDE work uses frontier hosted models
(Anthropic Claude, OpenAI GPT, Google Gemini) and you must know their APIs.

1. Create an account with one provider and get an API key.
2. **Set a monthly spend limit in the provider console before you write any code.**
   Agents in loops can burn money fast. Start with something small (e.g. $10–20).
3. Put the key in a `.env` file, **never in your code**:

```bash
# .env   (add .env to .gitignore!)
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

```bash
echo ".env" >> .gitignore
echo ".venv/" >> .gitignore
```

Load it in Python:

```python
from dotenv import load_dotenv
import os

load_dotenv()                      # reads .env into environment variables
key = os.environ["ANTHROPIC_API_KEY"]
```

### 2.4 Docker (needed from Part 3)

Install Docker Desktop (or Docker Engine on Linux). You will use it for Postgres
(pgvector), Redis, Langfuse, and to package your agent as a container.

```bash
docker run --rm hello-world
```

---

## 3. Your first call — check everything works

```python
# hello.py
import time
import ollama

start = time.time()
response = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "Name three planets. One line."}],
)
elapsed = time.time() - start

print("Answer:       ", response["message"]["content"])
print("Input tokens: ", response["prompt_eval_count"])
print("Output tokens:", response["eval_count"])
print(f"Latency:       {elapsed:.2f}s")
```

```bash
python hello.py
```

If you see an answer plus token counts, your lab works. Notice: **every response tells
you how many tokens went in and out.** You will measure this in every chapter, because
tokens are money and time.

---

## 4. Project layout for the book

Keep one folder per part. Keep notes next to code.

```
agent-lab/
├── .env                  # secrets (never committed)
├── .gitignore
├── part1/                # one file per experiment: ch02_tokens.py, ch04_sampling.py ...
├── part2/
├── ...
├── capstone/             # the one system you grow across the whole book
└── notes/                # one short .md per chapter: what I built, what broke, what I learned
```

### The notes file (this is important)

After each chapter, write 5–10 lines in `notes/chXX.md`:

```markdown
# Ch 04 — Sampling
What I built: ran the same prompt 10x at temp 0 and temp 1, counted distinct answers.
What surprised me: temp 0 still gave 2 different answers on a long prompt.
What I broke on purpose: top_p=0.01 → answers became repetitive.
One sentence I can now say to a customer: "..."
```

These notes become your interview stories later. Interviewers ask "tell me about a time
something broke" — you will have 40 real examples.

---

## 5. How to study (the method)

For every chapter:

```
READ  ──►  TYPE the code  ──►  RUN it  ──►  BREAK it on purpose  ──►  EXPLAIN it back
                                                 │
                                                 └─ change ONE thing, predict the result
                                                    first, then run, then compare
```

**Change one thing at a time.** If you change the prompt *and* the temperature *and* the
model, and the result changes, you learned nothing — you can't tell which change mattered.
This "isolate the variable" habit is the single most important engineering skill in AI
work, because model behavior is noisy.

**Predict before you run.** Write down what you think will happen. Being wrong is where
learning happens.

**Explain it simply.** If you can't explain a concept to a non-engineer in two sentences,
you don't understand it yet. FDEs explain things to customers all day.

### The mastery bar

Mark a chapter "done" only when:

- [ ] You did the Level 1 practice tasks yourself (no copy-paste).
- [ ] You answered every "Check yourself" question correctly *before* opening the answer.
- [ ] You can explain the main idea in 2 sentences to a non-engineer.
- [ ] You wrote your notes file.

---

## 6. Production view (yes, even for setup)

| Habit you start now | Why it matters later |
|---|---|
| Secrets in `.env`, never in code | Leaked keys in git are the #1 beginner security incident |
| Spend limit set in the console | A loop bug can cost hundreds of dollars overnight |
| Pin package versions (`pip freeze > requirements.txt`) | SDKs change fast; your code breaks silently on upgrade |
| Record tokens + latency on every call | You can't optimize what you never measured |
| One experiment per file | You can re-run and compare later |

---

## 7. Common mistakes

- **Committing `.env`.** Add it to `.gitignore` *before* the first commit. If you leaked a
  key, revoke it in the console immediately — deleting the commit is not enough.
- **Installing packages globally.** Always activate the venv first.
- **Using a huge local model.** A 70B model will not fit on a laptop. Stay with 1B–8B.
- **Skipping the notes.** You will forget 80% of what broke and why within two weeks.

---

## 8. Practice

**Level 1**
1. Install everything and run `hello.py`. Record the latency of the first and second run.
   (The first is slower — the model loads into memory. This is called a *cold start*.)
2. Ask the model "What is 47 × 89?" five times. Write down every answer. Is it always right?
   (Correct: 4183.) Keep this — you will fix it with tools in Chapter 11.

**Level 2**
3. Write `compare.py` that sends the same question to two local models (e.g. `llama3.2`
   and `qwen2.5:3b` — pull it first) and prints answer, tokens and latency side by side.

**Level 3**
4. Set up a hosted provider with a spend limit. Send one message, print the usage object.
   Compare the field names to Ollama's (`prompt_eval_count` vs `input_tokens`). Different
   names, same idea — this is why later we build one wrapper for all providers.

---

## 9. Check yourself

1. Why should API keys live in `.env` and not in your code?
2. Why is the first local model call slower than the second?
3. What does "change one thing at a time" protect you from?

<details>
<summary>Answers</summary>

1. Code gets committed, shared and pasted. Anyone with the key can spend your money or
   read your data. `.env` stays on your machine and is git-ignored.
2. The model has to be loaded from disk into memory (RAM/VRAM) the first time — a cold
   start. Later calls reuse the loaded model.
3. From false conclusions. With several changes at once, you can't know which one caused
   the result, and LLM output is noisy enough that you'll often blame the wrong thing.

</details>

---

## 10. Key terms

**Virtual environment (venv)** · **Ollama** · **API key** · **spend limit** · **cold start** ·
**tokens** · **latency** · **isolate the variable**

Next: [Chapter 01 — What an LLM is →](../part1-llm-foundations/01-what-is-an-llm.md)
