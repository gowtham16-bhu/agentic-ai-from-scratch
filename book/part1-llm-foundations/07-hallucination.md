# Chapter 07 — Hallucination

> A **hallucination** is output that sounds right but isn't supported — by the facts of
> the world, or by the documents and tool results the model was given. You cannot remove
> hallucination completely. You can **reduce** it, **detect** it, **contain** it, and
> **measure** it. That is the job.

**You will learn:** why models hallucinate, the types (factual, faithfulness, tool,
citation, package, action…), how to detect each one, a mitigation ladder you can apply
in any project, and how to measure a hallucination rate so you can prove improvement.

**Where this fits:** builds on [Ch 01](01-what-is-an-llm.md) (pretraining rewards
plausible text), [Ch 04](04-sampling-and-determinism.md) (logprobs) and
[Ch 06](06-embeddings.md) (similar ≠ true). Mitigations come from structured output
(Ch 10), tools (Ch 11), RAG and its variants (Ch 17–21), verifier-guided reasoning
(Ch 24); multi-agent hallucination cascades in Ch 25; measurement in evals (Ch 33);
package hallucination as a security attack in Ch 36.

---

## 1. The idea in plain words

The model's goal is to produce **likely** text (Ch 01). Usually likely text is also true.
When the model doesn't have the information — or has it but doesn't use it — the likely
text can still be **wrong, invented, or unsupported**, and it is delivered with exactly the
same confident tone as a correct answer.

Two different questions to ask about any output:

| Question | Name |
|---|---|
| Is it true **in the world**? | **Factuality** |
| Is it supported **by the context I gave** (documents, tool results)? | **Faithfulness** / **groundedness** |

In business systems, **faithfulness** is usually what matters most: you want answers based on
*the customer's* policy, not on what the model guesses a typical policy says.

---

## 2. Analogy

**A student in an exam who never leaves a question blank.** The grading only gives points
for answers, never for "I don't know", so guessing is always the best strategy. When they
know, they're right. When they don't, they write something plausible, confidently.

That is close to how models are trained and evaluated — and the fix is the same as for the
student: **give them the textbook (grounding), reward "I don't know" (abstention), and check
the work (verification).**

Where it breaks: the student *knows* when they're guessing. A model has no reliable internal
sense of that; its confidence signals (logprobs) are only loosely related to correctness.

---

## 3. How it works

### 3.1 Why models hallucinate

| Cause | Example |
|---|---|
| **Training objective** — plausible, not true | Invents a realistic-looking court case citation |
| **Guessing is rewarded** — training/benchmarks that score only right answers make guessing better than abstaining | Answers a question it should refuse |
| **Rare (long-tail) facts** — seen only a few times in training | Wrong birth year of a minor public figure |
| **Knowledge cutoff** | Describes an API that changed last month |
| **Missing context** | Retrieval found nothing relevant, model answers anyway |
| **Conflicting or noisy context** | Two policy versions retrieved; model blends them |
| **Lost in the middle / context rot** (Ch 02) | Ignores the right paragraph buried in a long prompt |
| **Leading questions / sycophancy** | "Since your 30-day return policy…" → model accepts the false premise |
| **Snowballing** | One wrong early token; the model stays consistent with its own mistake |
| **Forced output shape** | A required JSON field `"order_date"` with no date available → invents one |
| **Pressure to complete** (agents) | Says "I've updated the record" when the tool call failed |

### 3.2 Types of hallucination

| Type | What it looks like | Typical in |
|---|---|---|
| **Factual** | Wrong world fact | Open Q&A |
| **Intrinsic (faithfulness)** | **Contradicts** the provided source | RAG, summarization |
| **Extrinsic (faithfulness)** | **Adds** details not in the source ("please send a photo of the damage" when the policy says nothing about photos) | RAG, support bots |
| **Citation** | Fake reference, or a real source that doesn't support the claim | Research, legal, RAG with citations |
| **Tool-argument** | Invented order IDs, emails, parameters | Agents (Ch 11) |
| **Tool-result / action** | Claims a tool returned X or an action succeeded, when it didn't | Agents |
| **Code / API** | Calls a function or parameter that doesn't exist | Coding assistants |
| **Package** | Recommends a library that doesn't exist — attackers register those names (**slopsquatting**, Ch 36) | Coding assistants |
| **Reasoning** | Each step looks fine, the logic is wrong | Math, planning |
| **Self-capability** | "I checked the website" — it has no browsing tool | Chatbots |
| **Multimodal** | Describes objects or text not in the image | Vision (Ch 41) |

### 3.3 Detection methods

```
                       ┌───────────────────────────────────────────────────────────┐
 answer ─────────────► │ 1. DETERMINISTIC CHECKS  (cheapest, most reliable)         │
                       │    schema valid? IDs exist in DB? code runs? tests pass?   │
                       │    cited chunk exists? package exists on PyPI?             │
                       ├───────────────────────────────────────────────────────────┤
                       │ 2. GROUNDEDNESS CHECK                                       │
                       │    split answer into claims → is each claim supported by   │
                       │    the context? (NLI model or LLM judge, separate call)    │
                       ├───────────────────────────────────────────────────────────┤
                       │ 3. CONSISTENCY / UNCERTAINTY                                │
                       │    sample N answers → disagreement = risk (self-consistency)│
                       │    low logprobs on key tokens = risk                       │
                       ├───────────────────────────────────────────────────────────┤
                       │ 4. TRACE CHECK (agents)                                     │
                       │    does the final answer match what tools actually returned?│
                       ├───────────────────────────────────────────────────────────┤
                       │ 5. HUMANS: feedback buttons, corrections, sampled review   │
                       └───────────────────────────────────────────────────────────┘
```

**Rule:** prefer checks that run a **program** over checks that ask a **model**. "Reasoning
is cheap; verification is the bottleneck." Whenever you can replace "ask the model if it's
right" with "run code that checks if it's right", do it.

Asking the *same* model, *in the same conversation*, "are you sure?" is weak — it shares the
same blind spots and tends to either double down or flip to please you. Use a **separate
call** with only the claim and the evidence, ideally a **different model family**.

### 3.4 The mitigation ladder

Apply from the top; each step is cheaper than the next.

| # | Mitigation | Why it works |
|---|---|---|
| 1 | **Don't ask the model to remember facts — give them**: tools for live data, RAG for documents | Turns recall (weak) into reading (strong) |
| 2 | **Allow and instruct abstention**: "If the answer is not in the context, say you don't know." Make "unknown" a valid value in schemas (nullable fields, an `"unknown"` enum) | Removes the incentive to guess |
| 3 | **Require citations** to chunk/tool IDs, and **verify** them | Every claim must point at evidence |
| 4 | **Narrow the task**: structured output, enums, short answers, one question at a time | Less free text → less room to invent |
| 5 | **Deterministic verification**: validate IDs, run code, check numbers against source | Catches errors with certainty |
| 6 | **Groundedness check** by a separate judge call, on high-stakes answers | Catches extrinsic additions |
| 7 | **Lower temperature** for factual tasks | Fewer random detours (consistency, not truth) |
| 8 | **Don't let agents self-report success** — check final state (did the DB row change?) | Catches action hallucinations |
| 9 | **Human review** for high-risk outputs; **show sources** in the UI | Contain what you can't prevent |
| 10 | **Stronger model / reasoning model** for hard cases (Ch 08, 24) | Better models hallucinate less, never zero |

### 3.5 Measuring it

You can't improve what you don't measure. Build an eval set (Ch 33) and track:

```
hallucination rate   = unsupported claims / total claims        (lower is better)
faithfulness score   = supported claims / total claims          (higher is better)
```

And the **abstention matrix** — the one most teams forget:

| | Answer IS in the context | Answer is NOT in the context |
|---|---|---|
| **Model answers** | ✅ correct (if right) | ❌ **hallucination** |
| **Model says "I don't know"** | ❌ over-refusal (unhelpful) | ✅ correct abstention |

Your eval set **must** include questions whose answer is *not* in the documents ("absence"
cases) and questions where documents *contradict* each other. They're the ones everyone
skips and everyone fails.

---

## 4. Code

### 4.1 Watch a hallucination happen

```python
# ch07_see_it.py
import ollama

questions = [
    "Summarize the 2019 paper 'Quantum Gravy Networks' by A. Thornbury.",   # does not exist
    "What does the Python package 'fastjsonvalidatorx' do? Show how to install it.",
    "What is the return window in Acme Shoes' return policy?",              # no context given
]
for q in questions:
    r = ollama.chat(model="llama3.2", messages=[{"role": "user", "content": q}],
                    options={"temperature": 0})
    print("Q:", q, "\nA:", r["message"]["content"][:300], "\n")
```

Most small models will confidently describe the fake paper, the fake package and a made-up
return window.

### 4.2 Grounding + abstention

```python
# ch07_grounded.py
import ollama

POLICY = """Acme Shoes return policy:
- Unworn shoes can be returned within 14 days of delivery.
- Damaged items can be returned within 60 days.
- Refunds go to the original payment method within 5 business days."""

SYSTEM = f"""You answer customer questions using ONLY the policy below.
If the policy does not contain the answer, reply exactly: "I don't know based on our policy."
Do not add advice, steps or details that are not written in the policy.

<policy>
{POLICY}
</policy>"""

def ask(q):
    r = ollama.chat(model="llama3.2", options={"temperature": 0}, messages=[
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": q}])
    return r["message"]["content"]

if __name__ == "__main__":
    for q in ["How long do I have to return unworn shoes?",
              "My shoes arrived damaged. Do I need to send a photo?",   # tempting extrinsic add
              "Do you offer gift wrapping?"]:                           # absence case
        print(q, "->", ask(q))
```

### 4.3 A groundedness checker (separate judge call, structured output)

```python
# ch07_groundedness.py — check each sentence of an answer against the context
import json
import re
import ollama

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {
        "supported": {"type": "boolean"},
        "evidence": {"type": "string", "description": "exact quote from context, or empty"},
    },
    "required": ["supported", "evidence"],
}

def check_claim(claim, context, model="llama3.2"):
    prompt = (f"Context:\n{context}\n\nClaim: {claim}\n\n"
              "Is the claim fully supported by the context? Quote the supporting text. "
              "If any part of the claim is not in the context, supported must be false.")
    r = ollama.chat(model=model, format=JUDGE_SCHEMA, options={"temperature": 0},
                    messages=[{"role": "user", "content": prompt}])
    verdict = json.loads(r["message"]["content"])
    # deterministic double-check: a quote that isn't really in the context doesn't count
    if verdict["supported"] and verdict["evidence"] and verdict["evidence"] not in context:
        verdict["supported"] = False
    return verdict

def groundedness(answer, context):
    claims = [s.strip() for s in re.split(r"(?<=[.!?])\s+", answer) if s.strip()]
    results = [(c, check_claim(c, context)) for c in claims]
    score = sum(v["supported"] for _, v in results) / max(len(results), 1)
    return score, results

if __name__ == "__main__":
    from ch07_grounded import POLICY
    answer = ("Damaged items can be returned within 60 days. "
              "Please attach a clear photo of the damage to your request.")
    score, results = groundedness(answer, POLICY)
    for claim, v in results:
        print("SUPPORTED " if v["supported"] else "UNSUPPORTED", "|", claim)
    print(f"groundedness = {score:.0%}")
```

Note the two layers: the **model** judges, then **code** verifies the quoted evidence really
exists in the context. Judges hallucinate too.

### 4.4 Self-consistency as a risk signal

```python
# ch07_consistency.py — ask N times; disagreement means "don't trust this"
import ollama
from collections import Counter

def consistency(question, n=5):
    answers = []
    for _ in range(n):
        r = ollama.chat(model="llama3.2", options={"temperature": 0.8},
                        messages=[{"role": "user", "content": question + " Answer in under 6 words."}])
        answers.append(r["message"]["content"].strip().lower().rstrip("."))
    top, count = Counter(answers).most_common(1)[0]
    return count / n, Counter(answers)

for q in ["What is the capital of Japan?",
          "In what year was the Thornbury Bridge in Leeds opened?"]:   # obscure/likely unknown
    agreement, dist = consistency(q)
    print(f"{agreement:.0%} agreement  {q}\n   {dict(dist)}")
```

High agreement doesn't prove truth, but **low agreement is a strong warning sign** — the
model is guessing.

### 4.5 A deterministic check: does this package exist?

```python
# ch07_package_check.py — never pip install a name an LLM suggested without checking
import httpx

def pypi_exists(name):
    r = httpx.get(f"https://pypi.org/pypi/{name}/json", timeout=10)
    return r.status_code == 200

for pkg in ["requests", "pydantic", "fastjsonvalidatorx"]:
    print(pkg, "exists" if pypi_exists(pkg) else "DOES NOT EXIST (possible hallucination)")
```

Existence isn't safety — an attacker may have registered a commonly hallucinated name.
Also check age, downloads and maintainer before installing (Ch 36).

---

## 5. Production view

| Where it shows up | Detect in production | Contain / fix |
|---|---|---|
| Support bot adds policy details | Sampled groundedness checks on live traffic; customer complaints tagged "wrong info" | Stricter grounding prompt, citations, claim-level check on high-risk intents |
| Agent says "done" but nothing happened | Compare final message with tool results and **final state** (Ch 33) | Success messages generated from tool results, not from the model's claim |
| Invented IDs in tool calls | Tool returns "not found" errors at a high rate | Validate IDs; tools return actionable errors (Ch 11); let the model look IDs up first |
| Citations that don't support claims | Automated citation verification on a sample | Cite chunk IDs; verify quotes exist; show sources in UI |
| Coding agent installs fake packages | Dependency check in CI | Allowlist, lockfiles, existence + reputation check |
| "Answers everything" bot | Abstention matrix on an eval set with absence cases | Abstention instruction + allowed "unknown" + absence cases in CI |

Track **hallucination rate** and **abstention accuracy** as first-class metrics next to
latency and cost. Report them to the customer in pilot reports (Ch 45).

---

## 6. Common mistakes

- **"We added RAG, so no more hallucinations."** RAG reduces them; models still add details
  (extrinsic) or blend conflicting chunks.
- **Asking the same model in the same context to check itself.**
- **Forcing every schema field to be filled.** Make unknowns representable.
- **An eval set with only answerable questions.** You'll never see the model invent answers
  to unanswerable ones.
- **Treating "I don't know" as failure.** A correct abstention is a success.
- **Measuring with vibes.** "It seems better" is not a number.

---

## 7. Practice

**Level 1**
1. Run `ch07_see_it.py`. For each answer, label the hallucination type from the table in 3.2.
2. Run `ch07_grounded.py`. Does the photo question get an invented step? Edit the system
   prompt to fix it. Re-run 5 times.

**Level 2**
3. Build a 20-question eval for the Acme policy: 12 answerable, 5 absence ("do you do gift
   wrapping?"), 3 false-premise ("since your 30-day window…"). Score each answer by hand:
   correct / hallucinated / correct abstention / over-refusal. Fill the abstention matrix.
4. Run `ch07_groundedness.py` on 10 answers from exercise 3. Compare its verdicts to your hand
   labels. How often does the judge agree with you? (This is *judge calibration*, Ch 33.)

**Level 3**
5. Build `verify_answer(answer, context, tool_results)` that combines: claim-level
   groundedness, quote verification, a check that every number in the answer appears in the
   context or tool results, and a self-consistency score. Output a risk level
   (low/medium/high). Route "high" to a human queue. Measure on your eval set how many
   hallucinations it catches and how many good answers it wrongly flags.

---

## 8. Check yourself

1. What's the difference between factuality and faithfulness? Which matters more for a
   company support bot?
2. Give the hallucination type: the policy says "returns within 14 days" and the bot says
   "returns within 14 days; keep the original packaging."
3. Why is asking the same model "are you sure?" a weak check?
4. Why must an eval set include questions with no answer in the documents?
5. Name three checks that run a program instead of asking a model.
6. An agent replied "Your refund has been processed." How do you know if that's true?

<details>
<summary>Answers</summary>

1. Factuality: true in the world. Faithfulness: supported by the provided context. For a
   company bot, faithfulness — it must follow *this* company's policy.
2. Extrinsic faithfulness hallucination (adds an unsupported detail).
3. It shares the same knowledge gaps and context, and tends to double down or flip to please
   the user. Use a separate call, ideally a different model, with only claim + evidence — or
   better, a program.
4. Otherwise you never measure whether the model invents answers when it should abstain —
   the most common and harmful failure.
5. Schema validation; checking IDs/values exist in the database; running code or tests;
   verifying quoted evidence exists in the source; checking a package exists on PyPI.
6. Check the trace: was the refund tool called, did it return success, and does the payment
   system show the refund (final state)? Never trust the sentence alone.

</details>

---

## 9. Key terms

**hallucination** · **factuality** · **faithfulness / groundedness** · **intrinsic vs
extrinsic hallucination** · **citation hallucination** · **tool-argument hallucination** ·
**action hallucination** · **package hallucination / slopsquatting** · **sycophancy** ·
**snowballing** · **abstention** · **self-consistency** · **NLI** · **verifier** ·
**hallucination rate** · **abstention matrix** · **absence case**

Next: [Chapter 08 — Choosing a model →](08-choosing-a-model.md)
