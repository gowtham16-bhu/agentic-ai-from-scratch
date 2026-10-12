# Chapter 33 — Evals

> **Evals are tests for behaviour.** LLM systems are non-deterministic, and every prompt edit,
> tool change or model upgrade can silently change behaviour. "Shipping without evals" is
> "shipping without tests". At the end of a pilot, the deliverable is **a number** — and the
> evals produce it.

**You will learn:** the testing pyramid for agents, golden datasets (sources, size, structure,
absence/contradiction cases), the three assertion types (**final state, trajectory, LLM-as-judge**),
judge biases and **calibration** (agreement, Cohen's kappa), **pass@k vs pass^k**, variance and
confidence intervals, regression gates in CI and recorded fixtures, online evals (feedback, A/B,
canaries, shadow mode), human evaluation, red-teaming, public benchmarks, eval tools, the **data
flywheel**, and why the **human override rate** is the most honest metric.

**Where this fits:** you've been building evals since Ch 07 (hallucination), Ch 08 (model
comparison), Ch 14 (agent regression tests), Ch 23 (retrieval metrics), Ch 24 (verifiers). This
chapter makes them a system. Traces feed evals (Ch 34); guardrail and security evals (Ch 35–36);
eval-gated deployments (Ch 38); fine-tuning needs evals first (Ch 40); pilot reports quote them (Ch 45).

---

## 1. The idea in plain words

An eval = **a set of cases** + **a way to run the system on them** + **assertions that score the
results** + **metrics you track over time**.

```
cases (inputs + expectations) ──► run the agent (several times each) ──► assertions ──► metrics
                                                                                        ├─ pass rate (+ CI)
                                                                                        ├─ pass^k (reliability)
                                                                                        ├─ mean iterations
                                                                                        ├─ p95 latency
                                                                                        └─ cost per task
```

Track **all four** of pass rate, iterations, p95 latency and cost per task — improving one often
worsens another.

---

## 2. Analogy

**A driving test, not a written quiz.** You don't just ask the learner "how do you parallel park?"
(the model saying it did something). You put them in the car (run the agent), on several routes
(cases), several times (repeats), and check the outcome — is the car actually parked, did they
check mirrors (trajectory), would an experienced examiner approve the style (judge). And you test on
the roads where people actually crash (production failures), not just the easy ones.

---

## 3. How it works

### 3.1 The testing pyramid for agents

```
         ╱ E2E ╲          few; on RECORDED fixtures (deterministic, no API bill)
       ╱  Evals  ╲        20–200 cases in CI; measure BEHAVIOUR (non-deterministic → repeats)
     ╱  Contract  ╲       the schema the model sees matches what the tool function accepts;
   ╱               ╲       tool error messages are actionable (they are prompts!)
 ╱   Integration    ╲     tools actually reach their backends (auth, network, timeouts)
╱       Unit         ╲    tools are ordinary functions: test them like any code
```

Evals alone don't catch a broken tool; unit tests alone don't catch a confused agent. You need both.

### 3.2 Golden datasets

- **Start with 20 cases, not 2,000.** Grow with every bug.
- **Sources:** real user requests (logs, tickets), past failures, edge cases you fear, the customer's
  "must never happen" list.
- **Include the cases everyone skips:** **absence** (answer not available → must abstain),
  **contradiction** (conflicting sources), **adversarial** (injection, jailbreak), **multi-step**,
  **other languages**, **permission boundaries**.
- **Structure:** `id`, `input`, `expect` (assertions), `tags` (category, difficulty, risk), source,
  date added. Store in version control next to the code.
- **Splits:** if you optimize prompts against the evals (Ch 09), keep a held-out test set you don't
  tune on — otherwise you overfit to your own eval.

### 3.3 The three assertion types

| Type | Checks | Example | Strength |
|---|---|---|---|
| **Final state** | The world after the run | Refund row exists in DB; ticket closed; file written; JSON validates | **Strongest** — checks outcomes, not words |
| **Trajectory** | How it got there | Called `get_order` before `create_refund`; never called `delete_*`; ≤ 5 iterations; ≤ 20K tokens | Catches "right answer, wrong path" and waste |
| **Output checks** | The final answer | Contains the right number; matches schema; regex; semantic similarity to a reference | Cheap, deterministic |
| **LLM-as-judge** | Subjective quality | Helpful? Polite? Grounded? Follows policy? | Flexible — but biased; calibrate it |

Grade trajectories by **checkpoints** (key tools called, forbidden tools avoided, budgets respected),
not exact step-by-step matching — there are often several valid paths.

### 3.4 LLM-as-judge done properly

Known biases: **position** (prefers the first/second option), **length** (prefers longer answers),
**self-preference** (prefers outputs from its own model family), **sycophancy** (agrees with claims in
the input).

Mitigations:
- **Binary or small categorical verdicts** with an explicit rubric beat 1–10 scores.
- Require **evidence** (a quote from sources) with each verdict; check the quote exists in code.
- **Swap positions** in pairwise comparisons and count only consistent wins.
- Use a **different model family** from the one being judged.
- **Calibrate**: label 50+ cases yourself (or with domain experts); measure agreement and **Cohen's
  kappa** (agreement beyond chance). Don't gate releases on a judge you haven't calibrated, and re-check
  after changing the judge model or rubric.

### 3.5 pass@k vs pass^k — capability vs reliability

Run each case **n** times; **c** runs pass.

```
pass@k = P(at least ONE of k attempts succeeds)   = 1 − C(n−c, k) / C(n, k)    ← "can it ever do it?"
pass^k = P(ALL k attempts succeed)                = C(c, k) / C(n, k)          ← "can I rely on it?"
```

A case that passes 7 of 8 times has pass@3 = 1.00 but pass^3 ≈ 0.62. **Users experience pass^k**:
the same customer asks similar things many times, and every failure is visible. Agent benchmarks
built around tool-using customer-service tasks (the τ-bench family) popularized pass^k because
single-run scores hid how unreliable agents were.

### 3.6 Variance, sample size and significance

- LLM results vary run to run → **repeat** each case (3–10×).
- Small eval sets have **wide confidence intervals**: on 50 cases, ±5–10 points is noise. Report a
  **bootstrap 95% CI**.
- Compare versions on the **same cases** (paired comparison); look at which cases flipped, not only the
  average.
- Don't celebrate "+2%" on 40 cases.

### 3.7 Evals in CI — "a prompt edit is a code change"

| When | What runs |
|---|---|
| Every PR | Unit + contract tests; E2E on **recorded fixtures** (deterministic replays of model/tool responses) |
| PRs touching prompts, tools, tool code, model config | The live eval suite (or a fast subset) with repeats |
| Nightly | Full suite, all models in fallback chains, cost/latency trend |
| Before release / model upgrade | Full suite + gate against the last released baseline |

**Gate:** fail the build if pass rate < floor **or** drops more than X vs baseline **or** cost/latency
regress beyond budget. And actually **refuse to ship** when it fails — an ignored gate is worse than none.

### 3.8 Online evaluation (production)

| Method | What it tells you |
|---|---|
| **Sampled judge scoring** of live traffic | Quality drift on real inputs |
| **Explicit feedback** (thumbs, reasons) | Biased (angry users vote) but valuable |
| **Implicit signals**: retries, rephrases, abandonment, escalations | Hidden dissatisfaction |
| **Human override rate**: how often people edit/reject the agent's output | **The most honest quality metric.** If people keep editing the output, your offline evals are lying to you |
| **Shadow mode**: the new version runs on live traffic, output not shown | Safe comparison on real inputs |
| **Canary / A/B**: a % of traffic gets the new version | Real impact with limited blast radius (Ch 38) |

Note: rising **handoff to humans** with *falling* override rate can be good — the agent correctly
recognizes its limits.

### 3.9 Red-teaming

Deliberately attack your system: prompt injection (direct and via documents/tool results), jailbreaks,
data exfiltration attempts, cross-tenant probes, PII extraction, harmful-content requests, tool misuse,
denial-of-wallet (huge inputs, loops). Automate generation of attack variants; keep every successful
attack as a regression case (Ch 35–36).

### 3.10 Benchmarks and tools

**Public benchmarks** (for shortlisting models, Ch 08): coding (e.g. SWE-bench family), tool-agent-user
interaction (τ-bench family), general assistants (GAIA), web/computer use (WebArena, OSWorld),
function calling (BFCL), knowledge/reasoning (MMLU-style, GPQA, HLE). They are **not** your eval.

**Tools** (pick one, don't build everything): promptfoo (config-driven evals + red-teaming), DeepEval
(pytest-style), Ragas (RAG metrics, Ch 23), Inspect (an open evaluation framework from the UK AI
Security Institute), plus platforms with tracing+evals such as Langfuse, LangSmith, Braintrust, Arize
Phoenix.

### 3.11 The data flywheel

```
capture: trajectory + outcome + user corrections (Ch 34)
   ↓
mine: overrides · halted runs · cost outliers · immediate retries · novel inputs · negative feedback
   ↓
triage: label the failure (retrieval? tool? prompt? model? policy?)
   ↓
EVERY production failure becomes an eval case BEFORE it becomes a fix
   ↓
fix → eval suite passes (old + new case) → ship behind a canary → capture …
```

### 3.12 Evals are verifiers

Everything that makes a good eval — deterministic, hard to game, checks the real outcome rather than a
proxy — is also what makes a good verifier for verifier-guided generation (Ch 24) and a good reward for
RL fine-tuning (Ch 40). Invest here; it pays three times.

---

## 4. Code

### 4.1 An eval harness: repeats, three assertion types, pass@k, pass^k, CI, gate

```python
# eval_harness.py — run cases N times; final-state, trajectory and output assertions; pass@k, pass^k, CIs
import json
import random
import statistics
from math import comb

def pass_at_k(n, c, k):
    """P(at least one of k attempts succeeds), unbiased estimate from n runs with c successes."""
    return 1.0 if n - c < k else 1 - comb(n - c, k) / comb(n, k)

def pass_hat_k(n, c, k):
    """pass^k: P(ALL k attempts succeed) — reliability as users experience it."""
    return comb(c, k) / comb(n, k) if c >= k else 0.0

def bootstrap_ci(values, iters=2000, alpha=0.05, seed=0):
    rng = random.Random(seed)
    means = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(iters))
    return means[int(alpha / 2 * iters)], means[int((1 - alpha / 2) * iters) - 1]

def check(case, run):
    """Return list of failed assertion names (empty = pass). run = {answer, tools, iterations, state, ...}."""
    failures = []
    exp = case["expect"]
    if "final_state" in exp:                                          # strongest: did the world change correctly?
        for k, v in exp["final_state"].items():
            if run["state"].get(k) != v:
                failures.append(f"final_state.{k}")
    if "must_call" in exp and not set(exp["must_call"]) <= set(run["tools"]):
        failures.append("trajectory.must_call")
    if any(t in run["tools"] for t in exp.get("must_not_call", [])):
        failures.append("trajectory.must_not_call")
    if run["iterations"] > exp.get("max_iterations", 99):
        failures.append("trajectory.max_iterations")
    for s in exp.get("answer_contains", []):
        if s.lower() not in run["answer"].lower():
            failures.append(f"answer_contains:{s}")
    if exp.get("must_abstain") and "don't know" not in run["answer"].lower():
        failures.append("abstention")
    return failures

def evaluate(cases, agent, repeats=5, k=3):
    rows = []
    for case in cases:
        results = []
        for _ in range(repeats):
            run = agent(case["input"])
            fails = check(case, run)
            results.append({"ok": not fails, "fails": fails, **run})
        c = sum(r["ok"] for r in results)
        rows.append({"id": case["id"], "tags": case.get("tags", []), "passes": c, "runs": repeats,
                     "pass@k": pass_at_k(repeats, c, k), "pass^k": pass_hat_k(repeats, c, k),
                     "iterations": statistics.mean(r["iterations"] for r in results),
                     "latency_p95": sorted(r["latency_s"] for r in results)[int(0.95 * (repeats - 1))],
                     "cost": statistics.mean(r["cost"] for r in results),
                     "failures": sorted({f for r in results for f in r["fails"]})})
    per_run = [r["passes"] / r["runs"] for r in rows]
    summary = {"pass_rate": statistics.mean(per_run), "pass_rate_95ci": bootstrap_ci(per_run),
               f"pass@{k}": statistics.mean(r["pass@k"] for r in rows),
               f"pass^{k}": statistics.mean(r["pass^k"] for r in rows),
               "mean_iterations": statistics.mean(r["iterations"] for r in rows),
               "p95_latency_s": max(r["latency_p95"] for r in rows),
               "cost_per_task": statistics.mean(r["cost"] for r in rows)}
    return summary, rows

def gate(summary, baseline, min_pass=0.85, max_drop=0.03):
    """CI gate: refuse to ship on an absolute floor or a regression vs the last released baseline."""
    problems = []
    if summary["pass_rate"] < min_pass:
        problems.append(f"pass_rate {summary['pass_rate']:.2f} < {min_pass}")
    if baseline and summary["pass_rate"] < baseline["pass_rate"] - max_drop:
        problems.append(f"regression {baseline['pass_rate']:.2f} -> {summary['pass_rate']:.2f}")
    return problems

if __name__ == "__main__":
    CASES = [
        {"id": "refund-small", "input": "refund A-1043, it arrived damaged", "tags": ["refund"],
         "expect": {"final_state": {"refund_A-1043": "created"}, "must_call": ["get_order", "create_refund"],
                    "max_iterations": 5}},
        {"id": "status", "input": "where is A-1043?", "tags": ["status"],
         "expect": {"must_call": ["get_order"], "must_not_call": ["create_refund"], "answer_contains": ["DHL"]}},
        {"id": "absence", "input": "do you sell gift cards?", "tags": ["absence"],
         "expect": {"must_abstain": True, "must_not_call": ["create_refund"]}},
    ]
    rng = random.Random(42)
    def fake_agent(text):            # stands in for the Ch 14 agent; flaky on purpose
        flaky = rng.random() < 0.2
        if "refund" in text:
            state = {} if flaky else {"refund_A-1043": "created"}
            return {"answer": "Refund created.", "tools": ["get_order", "create_refund"], "iterations": 3,
                    "state": state, "latency_s": rng.uniform(1, 4), "cost": 0.004}
        if "gift" in text:
            return {"answer": "I don't know based on our documents.", "tools": [], "iterations": 1,
                    "state": {}, "latency_s": 0.8, "cost": 0.001}
        return {"answer": "Shipped via UPS." if flaky else "Shipped via DHL, ETA Oct 15.", "tools": ["get_order"],
                "iterations": 2, "state": {}, "latency_s": rng.uniform(1, 2), "cost": 0.002}

    summary, rows = evaluate(CASES, fake_agent, repeats=8, k=3)
    for r in rows:
        print(f"{r['id']:14s} {r['passes']}/{r['runs']}  pass@3={r['pass@k']:.2f}  pass^3={r['pass^k']:.2f}  fails={r['failures']}")
    print({k: (tuple(round(x, 3) for x in v) if isinstance(v, tuple) else round(v, 3)) for k, v in summary.items()})
    problems = gate(summary, baseline={"pass_rate": 0.95})
    print("GATE:", "FAIL -> " + "; ".join(problems) if problems else "PASS")
```

Verified output (with the flaky fake agent):

```
refund-small   7/8  pass@3=1.00  pass^3=0.62  fails=['final_state.refund_A-1043']
status         7/8  pass@3=1.00  pass^3=0.62  fails=['answer_contains:DHL']
absence        8/8  pass@3=1.00  pass^3=1.00  fails=[]
{'pass_rate': 0.917, 'pass_rate_95ci': (0.875, 1.0), 'pass@3': 1.0, 'pass^3': 0.75, ...}
GATE: FAIL -> regression 0.95 -> 0.92
```

Read it like a release manager: pass@3 says "it *can* do everything"; pass^3 = 0.75 says "one in four
customers who ask three times will see a failure"; the gate blocks the release because it regressed
against the last baseline.

Replace `fake_agent` with a wrapper around the Ch 14 agent that returns `answer`, `tools`
(names called), `iterations`, `state` (read back from your test database), `latency_s` and `cost`.

### 4.2 An LLM judge with a binary rubric, and calibrating it

```python
# judge_calibration.py — an LLM judge with a binary rubric, and how to check it against human labels
import json

RUBRIC = """You grade a customer-support answer. Answer PASS only if ALL are true:
1. It answers the customer's actual question.
2. Every factual claim is supported by the SOURCES (quote one).
3. It does not promise anything the policy doesn't allow.
Return JSON: {"verdict": "PASS" | "FAIL", "evidence": "<quote from sources or empty>", "reason": "<one sentence>"}"""

def judge(question, answer, sources, model="qwen2.5:3b"):      # use a DIFFERENT family than the agent's model
    import ollama
    r = ollama.chat(model=model, format="json", options={"temperature": 0}, messages=[
        {"role": "system", "content": RUBRIC},
        {"role": "user", "content": f"QUESTION: {question}\nSOURCES: {sources}\nANSWER: {answer}"}])
    return json.loads(r["message"]["content"])

def cohen_kappa(a, b):
    """Agreement between two raters beyond chance (1 = perfect, 0 = chance level)."""
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    labels = set(a) | set(b)
    expected = sum((a.count(l) / n) * (b.count(l) / n) for l in labels)
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0

if __name__ == "__main__":
    human = ["PASS", "FAIL", "PASS", "PASS", "FAIL", "PASS", "FAIL", "PASS", "PASS", "FAIL"]
    judge_labels = ["PASS", "FAIL", "PASS", "FAIL", "FAIL", "PASS", "PASS", "PASS", "PASS", "FAIL"]
    agreement = sum(h == j for h, j in zip(human, judge_labels)) / len(human)
    print(f"raw agreement {agreement:.0%}, Cohen's kappa {cohen_kappa(human, judge_labels):.2f}")
    # rule of thumb: don't gate releases on a judge until agreement with expert labels is high
    # (e.g. kappa >= 0.6-0.7 on 50+ labelled cases) — and re-check after changing judge model or rubric
```

Output: `raw agreement 80%, Cohen's kappa 0.58` — 80% sounds good, but kappa shows much of that is what
you'd expect by chance. Improve the rubric (or the judge model) before trusting it as a gate.

---

## 5. Production view

| Practice | Why |
|---|---|
| Eval suite lives in the repo, runs in CI, has an owner | Evals rot without ownership |
| Every incident adds a case | The suite encodes your production lessons |
| Report pass rate **with CI**, pass^k, iterations, p95 latency, cost/task | One number hides trade-offs |
| Separate dashboards for offline evals and online signals | When they diverge, offline evals are stale |
| Recorded fixtures for deterministic E2E | Fast, free, stable PR checks |
| Budget for eval cost | Live evals cost tokens; sample smartly, cache, use smaller judges where calibrated |

---

## 6. Common mistakes

- A handful of happy-path cases, no absence/adversarial cases.
- Single run per case (variance hidden).
- Checking only the final text, never the final state or trajectory.
- Uncalibrated LLM judges, same model family as the agent, 1–10 scales.
- Tuning prompts on the test set.
- A CI gate that people routinely override.
- Ignoring the human override rate because offline evals look green.

---

## 7. Practice

**Level 1**
1. Run `eval_harness.py`. Change the flakiness from 0.2 to 0.05 and to 0.4. How do pass@3 and pass^3 move?
2. Run `judge_calibration.py`, then change two judge labels to agree with the human labels. What happens to kappa?

**Level 2**
3. Write 20 cases for your support agent (from Ch 14/29) including 4 absence, 2 contradiction, 2 injection and
   2 multi-step cases. Wire the real agent into the harness with a test database for final-state checks.
4. Label 30 agent answers yourself (PASS/FAIL with the rubric), run the judge, compute kappa. Iterate the
   rubric until kappa ≥ 0.6.

**Level 3**
5. Put the harness in **CI** (e.g. a GitHub Actions workflow): unit/contract tests on every push; the live eval
   subset when files under `prompts/`, `tools/` or `config/models*` change; the gate compares against a
   `baseline.json` committed on each release. Then make a change that drops the pass rate and watch the
   pipeline **refuse to ship** it.

---

## 8. Check yourself

1. Name the five levels of the agent testing pyramid.
2. Why is a final-state assertion stronger than checking the answer text?
3. Name three LLM-judge biases and a mitigation for each.
4. A case passes 6 of 8 runs. Is pass@3 or pass^3 higher? Which matters to users and why?
5. Your new prompt scores 86% vs 84% on 40 cases. What do you conclude?
6. What is the data-flywheel rule about production failures?
7. Why is the human override rate the most honest metric?

<details>
<summary>Answers</summary>

1. Unit, integration, contract, eval, end-to-end (on recorded fixtures).
2. It checks the actual outcome in the world (DB row, closed ticket), so an agent can't pass by *claiming*
   success; action hallucinations are caught.
3. Position bias → swap positions and require consistent wins; length bias → rubric criteria independent of
   length, binary verdicts; self-preference → use a different model family; sycophancy → require evidence
   quotes checked by code.
4. pass@3 is higher (1 − C(2,3)/C(8,3) = 1.0; pass^3 = C(6,3)/C(8,3) = 20/56 ≈ 0.36). pass^3 matters to users:
   it's the chance that repeated interactions all succeed.
5. Nothing yet — that difference is within noise for 40 cases. Look at confidence intervals, paired case-level
   flips, repeats, and more cases before deciding.
6. Every production failure becomes an eval case before it becomes a fix.
7. It measures real users' judgement on real tasks: if they keep editing or rejecting outputs, quality is
   lacking regardless of what offline evals say.

</details>

---

## 9. Key terms

**eval** · **testing pyramid** · **contract test** · **recorded fixtures** · **golden dataset** ·
**absence / contradiction cases** · **final-state assertion** · **trajectory assertion** · **LLM-as-judge** ·
**rubric** · **judge bias** · **calibration** · **Cohen's kappa** · **pass@k** · **pass^k** · **bootstrap
confidence interval** · **paired comparison** · **regression gate** · **online eval** · **shadow mode** ·
**canary / A/B test** · **human override rate** · **red-teaming** · **benchmark** · **data flywheel**

Next: [Chapter 34 — Observability →](34-observability.md)
