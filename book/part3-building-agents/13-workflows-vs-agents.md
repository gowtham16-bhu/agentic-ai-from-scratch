# Chapter 13 — Workflows vs agents

> The most important architecture question: **who owns the control flow?** In a
> **workflow**, your code decides the steps. In an **agent**, the model decides at runtime.
> If you can write the path down, write it down. Agents earn their cost only when the path
> genuinely can't be known in advance.

**You will learn:** the spectrum from a single augmented LLM call to an autonomous agent,
the six standard patterns (prompt chaining, routing, parallelization, orchestrator-workers,
evaluator-optimizer, autonomous agent), each one's cost and failure mode, and a checklist
for deciding whether you need an agent at all.

**Where this fits:** builds on tools (Ch 11) and the reliable client (Ch 12). The agent loop
(Ch 14) is the "autonomous agent" box in detail; multi-agent systems (Ch 25) are
orchestrator-workers grown up; state machines and graphs (Ch 26) are how workflows are
implemented in production; reasoning patterns (Ch 24) refine the evaluator-optimizer.

---

## 1. The idea in plain words

| | **Workflow** | **Agent** |
|---|---|---|
| Who decides the next step | Your code | The model |
| Path | Fixed (maybe with branches you wrote) | Discovered at runtime |
| Cost / latency | Predictable | Variable, often higher |
| Testing | Like normal software — step by step | Harder: many possible paths (Ch 33) |
| Fails when | Input doesn't fit the paths you wrote | It loops, wanders, or picks wrong tools |
| Best for | Known processes: extract → validate → file | Open-ended tasks: "investigate why this order failed" |

Both use LLMs. The difference is only **control flow ownership**.

Most real systems are **hybrids**: a workflow skeleton with one agentic step inside
("research this part freely"), or an agent wrapped in deterministic guardrails.

---

## 2. Analogy

**A recipe vs a chef.** A recipe (workflow) lists exact steps; anyone following it gets
consistent results, and it fails when an ingredient is missing. A chef (agent) looks at what's
in the fridge and decides what to cook; brilliant for new situations, but slower, more
expensive, and occasionally makes something strange. Restaurants use recipes for 95% of
dishes and let the chef improvise the specials.

---

## 3. How it works

### 3.1 The building block: the augmented LLM

One LLM call enhanced with **retrieval** (Ch 17), **tools** (Ch 11) and **memory** (Ch 16).
Many problems are solved right here, with **one well-designed call**. Start here.

### 3.2 The six patterns

```
1. PROMPT CHAINING — fixed sequence, each step's output feeds the next
   input → [LLM: extract] → (code check) → [LLM: draft] → [LLM: polish] → output

2. ROUTING — classify, then send to a specialized handler
                    ┌→ [refund handler]
   input → [router] ┼→ [shipping handler]
                    └→ [general handler]

3. PARALLELIZATION — independent work at the same time
   sectioning:  input → [LLM: part A] [LLM: part B] [LLM: part C] → combine
   voting:      input → [LLM] [LLM] [LLM] (same task) → majority / best

4. ORCHESTRATOR–WORKERS — an LLM decides the subtasks at runtime
   input → [orchestrator: plan subtasks] → [worker 1] [worker 2] ... → [synthesizer] → output

5. EVALUATOR–OPTIMIZER — generate, critique, revise, until good enough
   input → [generator] → draft → [evaluator] → pass? ──yes──► output
                            ▲                      │no + feedback
                            └──────────────────────┘   (max N rounds)

6. AUTONOMOUS AGENT — the model loops: think → call tools → observe → ... → done (Ch 14)
```

### 3.3 Priced comparison

| Pattern | Use when | Relative cost | Typical failure |
|---|---|---|---|
| Single augmented call | One step, enough context | lowest | Hallucination (Ch 07) |
| Prompt chain | Fixed steps known upfront | low | Error propagates down the chain → add code checks ("gates") between steps |
| Router | Input types need different handling | low | Wrong route → silent wrong answer (log routing decisions; eval them) |
| Parallelization | Independent subtasks, or N-vote for reliability | medium | Merging conflicting outputs |
| Orchestrator–workers | Subtasks can't be known in advance | high | Bad return contract; workers' unsourced claims treated as facts (Ch 25) |
| Evaluator–optimizer | Quality improves with critique, and you can state criteria | high | Judge bias; endless polishing → cap rounds |
| Autonomous agent | Path genuinely unknown; many tools; recovery needed | highest | Loops, cost overruns, wandering (Ch 14 guards) |

### 3.4 Should this be an agent? (checklist)

Say **yes to all four** before choosing an agent:

1. **Complexity** — multi-step and hard to specify in advance? ("Fix this failing test" yes;
   "extract the invoice total" no.)
2. **Value** — is the outcome worth higher cost and latency?
3. **Viability** — can current models actually do this task well? (Test it!)
4. **Cost of error** — can mistakes be caught and recovered (tests, review, undo, approvals)?

If any answer is no, use a workflow or a single call. This one checklist will save your
customers more money than any optimization in Part 6.

### 3.5 Choosing a router

| Router type | Speed/cost | Accuracy | Use when |
|---|---|---|---|
| Rules / regex / keywords | Free, instant | Good on clear signals | Order IDs, explicit commands |
| Embedding similarity to examples (Ch 06) | Very cheap | Good for topics | Many intents, fuzzy phrasing |
| Small LLM with structured output (Ch 10) | Cheap | Best for nuance | Ambiguous requests |
| A trained classifier | Cheapest at scale | High with good data | High volume, stable intents |

Cheap routers first, LLM as fallback when the cheap one isn't confident.

---

## 4. Code

All examples use a tiny helper so the patterns stay readable:

```python
# patterns_common.py
import json
import ollama

def ask(prompt, system="", schema=None, temperature=0):
    msgs = ([{"role": "system", "content": system}] if system else []) + \
           [{"role": "user", "content": prompt}]
    r = ollama.chat(model="llama3.2", messages=msgs, format=schema,
                    options={"temperature": temperature})
    text = r["message"]["content"]
    return json.loads(text) if schema else text
```

### 4.1 Prompt chain with a gate

```python
# ch13_chain.py
from patterns_common import ask

COMPLAINT = "Order A-1043: the lamp arrived with a cracked base. I paid 49.99. Very disappointed."

facts = ask(f"Extract order_id, product, problem and amount.\n\n{COMPLAINT}", schema={
    "type": "object",
    "properties": {"order_id": {"type": "string"}, "product": {"type": "string"},
                   "problem": {"type": "string"}, "amount": {"type": "number"}},
    "required": ["order_id", "product", "problem", "amount"]})

# GATE: deterministic check between steps — stop the chain early if extraction is wrong
assert facts["order_id"].startswith("A-"), f"bad extraction: {facts}"

draft = ask(f"Write a 3-sentence apology email offering a full refund. Facts: {facts}")
final = ask(f"Make this email warmer but keep it under 80 words:\n\n{draft}")
print(facts, "\n\n", final)
```

### 4.2 Router

```python
# ch13_router.py
from patterns_common import ask

ROUTE_SCHEMA = {"type": "object",
                "properties": {"route": {"type": "string", "enum": ["refund", "shipping", "other"]}},
                "required": ["route"]}

HANDLERS = {
    "refund":   "You handle refunds. Our policy: damaged items refunded within 60 days.",
    "shipping": "You handle delivery questions. Standard shipping takes 3-5 days.",
    "other":    "You are a general helpful assistant for Acme Shoes.",
}

def handle(message):
    route = ask(message, system="Classify the customer message.", schema=ROUTE_SCHEMA)["route"]
    answer = ask(message, system=HANDLERS[route])
    return route, answer            # log the route! routing errors are silent otherwise

for m in ["My shoes came torn, I want my money back", "When will my order arrive?", "Do you have a store in Chennai?"]:
    print(handle(m))
```

### 4.3 Parallelization: voting

```python
# ch13_voting.py
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from patterns_common import ask

SCHEMA = {"type": "object", "properties": {"is_spam": {"type": "boolean"}}, "required": ["is_spam"]}
EMAIL = "Congratulations! You were selected for a free cruise. Reply with your bank details."

with ThreadPoolExecutor(max_workers=5) as pool:
    votes = list(pool.map(lambda _: ask(f"Is this email spam?\n{EMAIL}", schema=SCHEMA,
                                        temperature=0.8)["is_spam"], range(5)))
result, count = Counter(votes).most_common(1)[0]
print(votes, "->", result, f"(agreement {count}/5)")
```

### 4.4 Evaluator–optimizer

```python
# ch13_eval_opt.py
from patterns_common import ask

CRITERIA = "under 60 words; mentions the 60-day damaged-item window; ends with a clear next step"
CRITIQUE_SCHEMA = {"type": "object",
                   "properties": {"passes": {"type": "boolean"}, "feedback": {"type": "string"}},
                   "required": ["passes", "feedback"]}

draft = ask("Write a reply to: 'my shoes arrived damaged, what can I do?'")
for round_no in range(1, 4):                                   # cap the rounds
    verdict = ask(f"Criteria: {CRITERIA}\n\nDraft:\n{draft}\n\nDoes it meet ALL criteria?",
                  schema=CRITIQUE_SCHEMA)
    print(f"round {round_no}: passes={verdict['passes']} feedback={verdict['feedback']}")
    if verdict["passes"]:
        break
    draft = ask(f"Revise the draft to fix this feedback: {verdict['feedback']}\n\nDraft:\n{draft}")
word_count = len(draft.split())                                # deterministic check too
print(f"\nFINAL ({word_count} words):\n{draft}")
```

### 4.5 Orchestrator–workers (with a synthesizer)

```python
# ch13_orchestrator.py
from concurrent.futures import ThreadPoolExecutor
from patterns_common import ask

PLAN_SCHEMA = {"type": "object", "properties": {"subtasks": {
    "type": "array", "maxItems": 4, "items": {"type": "string"}}}, "required": ["subtasks"]}

goal = "Prepare a short briefing for opening an online shoe store in Sri Lanka."
plan = ask(f"Break this goal into 2-4 independent research subtasks:\n{goal}", schema=PLAN_SCHEMA)

def worker(subtask):
    return ask(f"In at most 4 bullet points, answer: {subtask}. Say 'UNSURE' where you are not sure.")

with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(worker, plan["subtasks"]))

notes = "\n\n".join(f"## {t}\n{r}" for t, r in zip(plan["subtasks"], results))
print(ask(f"Combine these notes into a 1-paragraph briefing. Keep any UNSURE flags.\n\n{notes}"))
```

Notice the `UNSURE` instruction: workers' outputs are **claims, not facts**. In Ch 25 you'll
make workers return sources so the synthesizer can tell evidence from guesses.

---

## 5. Production view

| Concern | Workflow | Agent |
|---|---|---|
| Testing | Unit-test each step; eval each LLM step | Trajectory + final-state evals (Ch 33) |
| Observability | One span per step (Ch 34) | One span per iteration + tool calls |
| Cost control | Known number of calls | Budgets and iteration caps are mandatory (Ch 14) |
| Debugging | Find the failing step | Read the trace top-down (Ch 34) |
| Change risk | Change one step | A prompt change can change every path |

**FDE heuristic:** in a customer pilot, start with the most constrained design that could
work (single call → chain → router), measure, and add agency only where the evals show the
fixed path fails. Customers trust predictable systems, and predictable systems ship.

---

## 6. Common mistakes

- **Building an agent for a fixed process** ("extract fields from an invoice") — slower,
  costlier, less reliable.
- **Chains without gates** — garbage from step 1 flows silently to step 5.
- **Routers nobody evaluates** — misroutes produce confident wrong answers.
- **Evaluator–optimizer without a round cap or clear criteria** — infinite polishing.
- **Orchestrators trusting worker outputs blindly.**
- **Using sub-agents just to run things in parallel** — parallel tool calls in one agent are
  cheaper (Ch 11, 25).

---

## 7. Practice

**Level 1**
1. Run each pattern. For each, write one sentence: why this pattern and not a single call?
2. Run `ch13_router.py` with 10 messages you write, including 3 ambiguous ones. How many
   routes were wrong?

**Level 2**
3. Add a cheap **embedding router** in front of the LLM router (Ch 06): route directly when
   similarity to the best example is > 0.8, otherwise ask the LLM. Measure: % of messages that
   skipped the LLM, and accuracy.
4. In `ch13_eval_opt.py`, replace the LLM's word-count judgment with a code check (count words
   in Python). Which parts of the criteria should *always* be checked by code?

**Level 3**
5. Take one task — "answer a customer's question about their order using order data and the
   return policy" — and build it **three ways**: single augmented call, router + handlers, and
   an autonomous agent with tools (preview of Ch 14). Compare accuracy on 15 cases, mean
   calls per task, tokens and latency. Write a recommendation memo: which would you ship and why?

---

## 8. Check yourself

1. What single question separates a workflow from an agent?
2. Give an example task where an agent is the wrong choice, and say why.
3. What's a "gate" in a prompt chain?
4. Sectioning vs voting — what's the difference?
5. What are the four checklist questions before building an agent?
6. Why is orchestrator–workers more expensive than routing?

<details>
<summary>Answers</summary>

1. Who decides the next step at runtime — your code (workflow) or the model (agent)?
2. Extracting fields from invoices: the steps are known; an agent adds cost, latency and
   variance without benefit.
3. A deterministic check between steps that stops or corrects the flow when a step's output
   is invalid, so errors don't propagate.
4. Sectioning splits a task into different independent parts run in parallel; voting runs the
   same task several times and aggregates (majority/best) for reliability.
5. Complexity (hard to pre-specify), value (worth the cost), viability (models can do it),
   cost of error (mistakes catchable/recoverable).
6. It needs a planning call, one or more calls per worker (often each with its own context),
   and a synthesis call; routing is one cheap classification plus one handler call.

</details>

---

## 9. Key terms

**workflow** · **agent** · **control flow** · **augmented LLM** · **prompt chaining** ·
**gate** · **routing** · **parallelization (sectioning, voting)** · **orchestrator–workers** ·
**synthesizer** · **evaluator–optimizer** · **autonomous agent** · **hybrid system**

Next: [Chapter 14 — The agent loop →](14-the-agent-loop.md)
