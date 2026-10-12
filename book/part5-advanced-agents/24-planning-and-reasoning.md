# Chapter 24 — Planning and reasoning

> Hard tasks need more than one quick answer: room to think, a plan, and — above all — a way
> to **check the work**. Reasoning is cheap; **verification is the bottleneck**. Whenever you
> can replace "ask the model if it's right" with "run a program that checks", do it.

**You will learn:** chain-of-thought, self-consistency, plan-and-execute (with replanning),
ReWOO, LLMCompiler-style parallel plans, Reflexion, self-refine, Tree/Graph-of-Thoughts,
verifier-guided generation (best-of-N), test-time compute, reasoning models (effort and
thinking budgets, interleaved thinking), and how to price each strategy.

**Where this fits:** builds on the agent loop (Ch 14), workflow patterns (Ch 13 — evaluator-
optimizer is self-refine), sampling (Ch 04 — self-consistency needs variety) and model choice
(Ch 08 — reasoning models). Verifiers are the bridge to evals (Ch 33) and RL fine-tuning
(Ch 40). Code execution for verification needs sandboxing (Ch 36, 43).

---

## 1. The idea in plain words

| Strategy | One-line idea | Cost | Worth it when |
|---|---|---|---|
| **Chain-of-thought (CoT)** | Think step by step before answering | ~1× (+ thinking tokens) | Almost always for multi-step problems; built into reasoning models |
| **Self-consistency** | Sample N reasoning paths, take the majority answer | N× | Single verifiable answers, high stakes |
| **Plan-and-execute** | Write a plan, then execute steps, replan on surprises | 1 plan + steps | Long tasks with clear structure |
| **ReWOO** | Plan all tool calls up front with placeholders, run them, then solve | Fewer LLM calls | Predictable tasks; cost-sensitive; brittle under surprise |
| **LLMCompiler-style** | Plan as a dependency graph; run independent steps in parallel | Lower latency | Many independent lookups |
| **ReAct** | Think → act → observe loop | ~1× per step | The default agent loop (Ch 14) |
| **Reflexion** | After a failure *with a real signal*, write a lesson and retry with it | 2–4× | Failing tests, eval scores, error messages |
| **Self-refine** | Draft → critique → revise | 2–3× | Writing quality with clear criteria (Ch 13) |
| **Tree / Graph of Thoughts** | Explore and score many branches of reasoning | 10–100× | Rarely pays off in production now; puzzles/research |
| **Verifier-guided (best-of-N)** | Generate N candidates, keep the ones a program verifies | N× gen + cheap check | Anything checkable: code, SQL, JSON, math |

---

## 2. Analogy

**How a careful engineer solves a hard bug.** Think it through (CoT), make a plan (plan-and-
execute), try several hypotheses (self-consistency / ToT), run the tests to see which fix
actually works (verifier), and when a fix fails, write down *why* before trying again
(Reflexion). Thinking harder helps; **running the tests** is what makes it reliable.

---

## 3. How it works

### 3.1 Chain-of-thought and reasoning models

For standard models, asking for reasoning first (`<thinking>…</thinking>` then `<answer>`, Ch 09)
improves multi-step accuracy. **Reasoning models** do this internally — trained with RL on
verifiable tasks (Ch 01) to think longer and check themselves.

Working with reasoning models:
- Control depth with the provider's **effort** level or **thinking budget** instead of prompts
  ("think step by step" adds little).
- Give **clear goals and success criteria**; avoid over-prescribing *how* to think.
- Thinking tokens are **billed as output** (Ch 03) and add latency; use lower effort for easy,
  high-volume routes and higher effort for hard ones (Ch 37).
- **Interleaved thinking:** in agent loops, modern models reason *between* tool calls (after
  each result) — much better than planning once at the start. Some APIs require you to pass
  thinking blocks back unchanged in later requests; follow your provider's rules.

### 3.2 Self-consistency

```
same question ──► sample 5 reasoning paths (temperature ~0.7)
                   → answers: 42, 42, 38, 42, 42  → majority: 42 (agreement 80%)
```

Works when answers are **comparable** (a number, a label, a choice). Agreement rate doubles as a
confidence signal (Ch 07). Costs N calls — use for high-stakes, low-volume decisions.

### 3.3 Planning

**Plan-and-execute**

```
PLANNER (strong model):  goal → numbered steps (structured output)
EXECUTOR (cheaper model or tools): run step 1, 2, ... recording results
REPLANNER: after each step (or on failure) — continue, modify remaining steps, or finish
```

Benefits: the user (or a reviewer) can see and approve the plan (Ch 26); cheaper models can
execute; progress is visible. Risk: rigid plans when the world surprises you — always allow
replanning.

**ReWOO (Reasoning WithOut Observation):** the planner writes the whole tool plan with
placeholders (`#E1 = search("return policy")`, `#E2 = get_order(#E1.order)`), tools run without
LLM calls in between, then a solver writes the answer. Very few LLM calls, but no adaptation
mid-way.

**LLMCompiler-style DAGs:** the planner outputs tasks with **dependencies**; independent tasks run
**in parallel** (Ch 11 parallel tool calls), dependent ones wait. Latency drops for wide tasks
("look up these 6 orders, then summarize").

**Goal decomposition (BDI-style):** for long-lived goals, keep a task tree — goal → sub-goals →
tasks — and persist it (Ch 26). The agent works until the goal state is reached, not just until
one answer is written.

### 3.4 Reflexion and self-refine

**Reflexion** needs a **real feedback signal** — a failing test, a compiler error, an eval score,
a user rejection:

```
attempt → run verifier → FAIL ("test_refund_limit failed: expected 400, got 200")
       → model writes a reflection: "I didn't validate the amount before calling the API"
       → store the reflection; retry with it in context → verifier → PASS
```

Without a real signal, "reflect on your answer" often just rephrases the same mistake.
**Self-refine** (critique-revise with the same model) works for style and completeness against
explicit criteria; for correctness, prefer a verifier.

### 3.5 Tree / Graph of Thoughts

Explore many partial reasoning paths, score them (with the model or a heuristic), expand the best,
backtrack from dead ends. Powerful for search-like puzzles; expensive (10–100× calls). With strong
reasoning models, simpler methods usually match it at a fraction of the cost.

### 3.6 Verifier-guided generation (best-of-N)

```
generate N candidates (diverse: temperature > 0) ──► VERIFY each with a program ──► return a passing one
   code   → run unit tests in a sandbox
   SQL    → execute on a read-only replica; check columns/row counts; compare with expected samples
   JSON   → schema validation + business rules (Ch 10)
   math   → recompute with a calculator / symbolic check
   claims → check against sources (Ch 07)
```

This is the most reliable pattern for checkable outputs. It's also exactly the idea behind
RL with verifiable rewards (Ch 01, 40) and good evals (Ch 33): **a good verifier is deterministic,
hard to game, and checks the real outcome, not a proxy.**

### 3.7 Test-time compute

Spending more compute **at inference** — longer thinking, more samples, search over candidates —
improves accuracy on hard problems, with diminishing returns. Reasoning models made this a dial:
effort/budget. Your job is to set the dial per route based on measured accuracy vs cost (Ch 37).

---

## 4. Code

### 4.1 Self-consistency

```python
# self_consistency.py
import json
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import ollama

SCHEMA = {"type": "object", "properties": {"reasoning": {"type": "string"}, "answer": {"type": "number"}},
          "required": ["reasoning", "answer"]}
QUESTION = ("A store sold 23 pairs of shoes on Monday, twice as many on Tuesday, and 15 fewer than "
            "Tuesday on Wednesday. How many pairs in total?")

def sample(_):
    r = ollama.chat(model="llama3.2", format=SCHEMA, options={"temperature": 0.8},
                    messages=[{"role": "user", "content": QUESTION + " Reason step by step, then answer."}])
    return json.loads(r["message"]["content"])["answer"]

with ThreadPoolExecutor(max_workers=5) as pool:
    answers = list(pool.map(sample, range(5)))
best, votes = Counter(answers).most_common(1)[0]
print(answers, "->", best, f"agreement {votes}/5", "(correct: 23 + 46 + 31 = 100)")
```

### 4.2 Plan-and-execute with replanning

```python
# plan_execute.py
import json
import ollama

PLAN = {"type": "object", "properties": {"steps": {"type": "array", "maxItems": 6, "items": {"type": "string"}}},
        "required": ["steps"]}
DECIDE = {"type": "object", "properties": {
    "action": {"type": "string", "enum": ["continue", "replan", "finish"]},
    "new_steps": {"type": "array", "items": {"type": "string"}},
    "final_answer": {"type": "string"}}, "required": ["action"]}

def llm(prompt, schema=None):
    r = ollama.chat(model="llama3.2", format=schema, options={"temperature": 0},
                    messages=[{"role": "user", "content": prompt}])
    return json.loads(r["message"]["content"]) if schema else r["message"]["content"]

def plan_and_execute(goal, execute_step, max_steps=8):
    steps = llm(f"Make a short step-by-step plan for: {goal}", PLAN)["steps"]
    done = []
    while steps and len(done) < max_steps:
        step = steps.pop(0)
        result = execute_step(step)                        # a tool call or a worker agent
        done.append({"step": step, "result": result})
        d = llm(f"Goal: {goal}\nCompleted: {json.dumps(done)}\nRemaining plan: {steps}\n"
                "Decide: continue, replan (give new_steps), or finish (give final_answer).", DECIDE)
        if d["action"] == "finish":
            return d.get("final_answer", ""), done
        if d["action"] == "replan":
            steps = d.get("new_steps", [])
    return llm(f"Goal: {goal}\nResults: {json.dumps(done)}\nWrite the final answer."), done

if __name__ == "__main__":
    fake_tools = lambda step: f"(pretend result for: {step})"
    answer, trace = plan_and_execute("Find out why order A-1043 is late and draft an apology", fake_tools)
    print(json.dumps(trace, indent=1), "\n\nANSWER:", answer)
```

### 4.3 Verifier-guided code generation (best-of-N) with Reflexion

```python
# verify_code.py — generate candidates, run tests, feed failures back
import re
import subprocess
import sys
import tempfile
import ollama

TESTS = """
assert refund_amount(100.0, "damaged") == 100.0
assert refund_amount(100.0, "unworn") == 90.0      # 10% restocking fee
assert refund_amount(100.0, "worn") == 0.0
assert refund_amount(-5, "damaged") == 0.0         # never negative
"""
TASK = ("Write a Python function refund_amount(price: float, condition: str) -> float. "
        "damaged: full refund; unworn: 90%; anything else: 0. Negative prices refund 0. "
        "Return only a python code block.")

def run_tests(code, timeout=5):
    """Teaching only: real systems run untrusted code in a sandbox (Ch 36, 43)."""
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(code + "\n" + TESTS)
    try:
        p = subprocess.run([sys.executable, f.name], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, "timed out"
    return p.returncode == 0, (p.stderr.strip().splitlines() or ["ok"])[-1]

def extract_code(text):
    m = re.search(r"`{3}(?:python)?\n(.*?)`{3}", text, re.S)
    return m.group(1) if m else text

def solve(n_candidates=3, max_reflections=2):
    lessons = []
    for attempt in range(max_reflections + 1):
        prompt = TASK + ("\nLessons from failed attempts:\n- " + "\n- ".join(lessons) if lessons else "")
        for i in range(n_candidates):                              # best-of-N
            r = ollama.chat(model="llama3.2", options={"temperature": 0.7},
                            messages=[{"role": "user", "content": prompt}])
            code = extract_code(r["message"]["content"])
            ok, detail = run_tests(code)
            print(f"attempt {attempt} candidate {i}: {'PASS' if ok else 'FAIL'} {detail}")
            if ok:
                return code
        # Reflexion: turn the real failure signal into a lesson
        lessons.append(ollama.chat(model="llama3.2", messages=[{"role": "user", "content":
            f"This code failed with: {detail}\n\n{code}\n\nIn one sentence, what rule did it get wrong?"}]
        )["message"]["content"].strip())
    return None

if __name__ == "__main__":
    print(solve() or "No passing solution — escalate to a human.")
```

The verifier (tests) — not the model's opinion — decides what ships.

---

## 5. Production view

| Choice | Measure | Typical decision |
|---|---|---|
| Reasoning effort per route | Accuracy vs tokens vs p95 latency on your eval | Low effort for classification/chat; high for planning/code |
| Self-consistency N | Accuracy gain vs N× cost | Only for high-stakes, checkable answers |
| Plan visibility | User trust; approval rates | Show plans for consequential tasks (Ch 26, 44) |
| Verifier coverage | % of outputs checked by a program | Push it up; it's your reliability floor |
| Reflexion loops | Pass rate by attempt number | Cap attempts; escalate to a human |

---

## 6. Common mistakes

- "Think step by step" prompts on reasoning models (wasted tokens) — use effort controls.
- Self-consistency on free-text answers that can't be compared.
- Rigid plans without replanning.
- Reflexion without a real failure signal.
- Asking the model to grade its own code instead of running tests.
- Running generated code outside a sandbox.
- Max effort everywhere "to be safe" (cost and latency explode).

---

## 7. Practice

**Level 1**
1. Run `self_consistency.py` 3 times. How often is the majority answer correct? How often is a single
   sample correct?
2. Run `plan_and_execute.py` with the fake tool. Read the trace. Did it ever replan?

**Level 2**
3. Run `verify_code.py`. Add two harder tests (rounding to 2 decimals; case-insensitive condition).
   Record passes by attempt number over 5 runs.
4. Replace the fake tools in `plan_and_execute.py` with the Ch 14 agent tools (orders + policy
   search). Compare plan-and-execute vs plain ReAct on 5 multi-step tasks: steps, tokens, success.

**Level 3**
5. Build an **LLMCompiler-style** executor: the planner returns tasks with `depends_on` lists; run
   tasks whose dependencies are done in parallel (ThreadPoolExecutor); pass results into dependent
   tasks. Measure latency vs sequential execution on a 6-lookup task.

---

## 8. Check yourself

1. Why is "verification is the bottleneck" the key idea of this chapter?
2. When does self-consistency work, and what does it cost?
3. Plan-and-execute vs ReWOO — main trade-off?
4. What does Reflexion need to work well?
5. How should you control reasoning depth with a reasoning model?
6. Give three examples of program verifiers.

<details>
<summary>Answers</summary>

1. Generating candidate reasoning is cheap and plentiful; knowing which candidate is *right* is the
   hard part. Programs that check outcomes give reliable selection; model self-assessment doesn't.
2. When answers are comparable (numbers, labels, choices); it costs N calls (and latency unless
   parallel).
3. Plan-and-execute adapts after each step (replanning) at the cost of more LLM calls; ReWOO plans
   everything up front with placeholders — fewer calls, but brittle when results are surprising.
4. A real feedback signal (failing tests, errors, scores) to reflect on, plus a cap on retries.
5. Use the provider's effort level or thinking budget, set per route by measured accuracy/cost, and
   give clear goals and success criteria instead of "think step by step".
6. Unit tests for code; executing SQL on a read-only replica and checking results; JSON schema and
   business-rule validation; recomputing math; checking quotes/claims against sources.

</details>

---

## 9. Key terms

**chain-of-thought** · **reasoning model** · **effort / thinking budget** · **interleaved thinking** ·
**self-consistency** · **plan-and-execute** · **replanning** · **ReWOO** · **LLMCompiler / task
DAG** · **goal decomposition** · **Reflexion** · **self-refine** · **Tree / Graph of Thoughts** ·
**verifier** · **best-of-N** · **test-time compute**

Next: [Chapter 25 — Multi-agent systems →](25-multi-agent-systems.md)
