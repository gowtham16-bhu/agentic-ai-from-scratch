# Chapter 25 — Multi-agent systems

> Several agents, each with its own instructions, tools and context, working together.
> The rule that prevents most bad designs: **sub-agents are for isolation, not
> concurrency.** If one agent can do it with parallel tool calls, don't add agents.

**You will learn:** the valid reasons for multiple agents (context isolation, specialization,
separation of duties, parallel exploration, organizational boundaries), their real costs,
the architectures (supervisor, hierarchical, handoffs/swarm, pipeline, debate/critic,
blackboard, agents-as-tools), shared state vs message passing, the **worker contract**,
fan-out + synthesizer, **shared budgets**, depth limits, and the failure modes — especially the
**hallucination cascade**.

**Where this fits:** grows from orchestrator–workers (Ch 13) and the agent loop (Ch 14); "isolate"
from context engineering (Ch 15). State, reducers and checkpoints for multi-agent graphs are
Ch 26; frameworks that implement these patterns are Ch 27; agent-to-agent protocols across
organizations are Ch 30 (A2A); security between agents is Ch 36.

---

## 1. The idea in plain words

### Good reasons for more than one agent

| Reason | Example |
|---|---|
| **Context isolation** | A research worker reads 50 pages and returns 5 sourced lines — the parent's context stays small and focused |
| **Specialization** | Different prompts, tools, or models per job (a SQL agent, a writing agent, a cheap triage agent) |
| **Separation of duties (security)** | The agent that reads untrusted web pages has **no** write tools; a separate agent with write access never sees raw web content (Ch 36) |
| **Independent checking** | A reviewer agent with a fresh context checks the maker's output (maker–checker) |
| **Parallel exploration** | Breadth-first research over independent directions, each needing lots of reading |
| **Organizational boundaries** | Agents owned by different teams or vendors, talking over a protocol (A2A, Ch 30) |

### Bad reasons

- "It's faster" — **parallel tool calls in one agent** are faster and cheaper (Ch 11).
- "Each agent should have one tool" — that's just tools with extra steps.
- "It mirrors our org chart" — architecture should follow information flow, not job titles.

### Real costs

- **Tokens:** every agent has its own context; published reports from production multi-agent
  research systems describe using many times (on the order of 10×+) the tokens of a single chat.
- **Availability multiplies down:** five components at 99% each ≈ 95% for the chain (Ch 38).
- **Debugging:** failures hide in hand-offs between agents.
- **Coordination overhead** can exceed the benefit.

---

## 2. Analogy

**A newsroom.** An editor (orchestrator) assigns stories to reporters (workers) who go out, read,
interview, and return **short, sourced drafts** — the editor never reads every interview
transcript (context isolation). A fact-checker (checker) verifies claims independently. A reporter
who files a claim without a source gets sent back. And nobody hires five reporters to read one press
release.

---

## 3. How it works

### 3.1 Architectures

```
SUPERVISOR / ORCHESTRATOR–WORKER         HIERARCHICAL
        [orchestrator]                         [director]
       /      |       \                       /          \
   [w1]     [w2]     [w3]             [lead A]          [lead B]
                                     /     \            /      \
                                  [w]      [w]       [w]       [w]

HANDOFFS / SWARM                       PIPELINE (assembly line)
[triage] ──handoff──► [billing]        [extract] ─► [analyze] ─► [write] ─► [review]
    └────handoff──► [shipping] ──handoff──► [refunds]

DEBATE / CRITIC                        BLACKBOARD
[agent A] ⇄ [agent B]                  agents read/write a shared workspace;
      ↘      ↙                         a controller picks who acts next
       [judge]

AGENTS-AS-TOOLS: a sub-agent is exposed to its parent as one tool: research(question) -> report
```

| Architecture | Use when | Watch out |
|---|---|---|
| **Supervisor / orchestrator–worker** | Subtasks discovered at runtime; results need synthesis | Return contract; orchestrator context growth |
| **Hierarchical** | Very large tasks with natural sub-areas | Deep chains multiply latency and failure |
| **Handoffs / swarm** | Conversation moves between specialists (triage → billing → refunds) | Ping-pong between agents; lost context on handoff |
| **Pipeline** | Fixed stages known in advance (it's a workflow, Ch 13) | Error propagation — add gates |
| **Debate / critic** | Quality via adversarial checking | Cost; judges have biases (Ch 33) |
| **Blackboard** | Many specialists contribute to a shared artifact | Conflicting writes; needs a controller |
| **Agents-as-tools** | Composability: any agent can be a tool of another | Hide complexity, but budgets and depth must still be tracked |

### 3.2 Shared state vs message passing

- **Shared state** (one state object all nodes read/update — the LangGraph model, Ch 26): simple
  inside one process; needs **reducers** to merge parallel writes. LangGraph raises an error when two
  parallel branches write the same key without one; hand-rolled shared state (a dict both threads
  update) usually just lets the last write win — silently.
- **Message passing** (agents send each other messages/tasks — queues, A2A, Ch 30): clean boundaries,
  works across services and companies; more plumbing.

### 3.3 The worker contract

What a worker returns is the most important interface in a multi-agent system:

```python
@dataclass
class WorkerOutput:
    task_id: str
    success: bool
    result: dict
    sources: list[str]          # claims WITHOUT sources are hypotheses, not facts
    tokens_used: int
    partial: bool = False       # finished only part of the task?
    error: str | None = None    # what went wrong, specifically
```

And what the orchestrator sends is just as important — a **task spec**:

```
objective · expected output format · which tools/sources to use (and avoid) · scope boundaries
· effort budget (e.g. "3–5 searches") · what to do if blocked
```

Vague delegation ("research the market") produces duplicated, unfocused work.

**Children get explicit inputs, not a copy of the parent's whole context.** That's the isolation
boundary: visible data flow, no context bloat, and no leaking of everything the parent knows.

### 3.4 Fan-out, fan-in and the synthesizer

```
orchestrator → [task 1] [task 2] [task 3]   (parallel workers, isolated contexts)
                  ↓        ↓        ↓
             WorkerOutput × 3 (some may be partial or failed)
                  ↓
SYNTHESIZER: merge · dedupe · resolve conflicts · keep citations · mark unsourced claims as uncertain
             · report partial failures honestly ("2 of 3 sources answered")
```

### 3.5 Budgets and limits

- **Shared budget by reference:** 20 agents each with a 10K-token budget can spend 200K. Pass one
  budget object that all agents draw from; when it's empty, everyone stops.
- **Depth limit:** an agent may create sub-agents only up to depth N.
- **No cycles:** enforce a DAG of delegation or a maximum number of handoffs per conversation, to
  prevent deadlock and ping-pong.

### 3.6 Failure modes

| Failure | What happens | Guard |
|---|---|---|
| **Hallucination cascade** | Worker A guesses; orchestrator states it as fact; worker B builds on it | Mandatory sources; unsourced = hypothesis; verify key claims (Ch 07) |
| **Coordination cost > benefit** | 5 agents to do what one could | Compare against a single-agent baseline in evals |
| **Deadlock / ping-pong** | A hands off to B, B back to A, forever | DAG, handoff caps, loop detection (Ch 14) |
| **Lost error context** | Worker failed; summary says "done" | Structured `success/partial/error` fields; never summarize errors away |
| **Context starvation** | Worker lacks a constraint the orchestrator knew | Explicit task specs with constraints |
| **Duplicate work** | Two workers search the same thing | Distinct, non-overlapping task specs |
| **Budget explosion** | Per-agent budgets add up | Shared budget object |
| **Conflicting writes** | Parallel branches write the same state field (error in LangGraph; silent overwrite in hand-rolled state) | Reducers, ownership of fields, locks (Ch 26) |
| **Injection spread** | One agent reads a malicious page and instructs others | Least privilege per agent, treat inter-agent messages as data, separation of duties (Ch 36) |

---

## 4. Code

### 4.1 Orchestrator, isolated workers, shared budget, synthesizer

```python
# multi_agent.py
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field, asdict
import ollama

@dataclass
class WorkerOutput:
    task_id: str
    success: bool
    result: dict
    sources: list = field(default_factory=list)
    tokens_used: int = 0
    partial: bool = False
    error: str | None = None

class SharedBudget:                       # one object, passed BY REFERENCE to every agent
    def __init__(self, max_tokens):
        self.max_tokens, self.used, self._lock = max_tokens, 0, threading.Lock()

    def spend(self, tokens):
        with self._lock:
            self.used += tokens
            return self.used <= self.max_tokens

    @property
    def exhausted(self):
        return self.used >= self.max_tokens

KNOWLEDGE = {   # stand-in for each worker's private tool/data source
    "shipping": "Standard delivery 3-5 days. Sri Lanka delivery 7-10 days. [shipping.md]",
    "returns": "Unworn: 14 days. Damaged: 60 days. [returns.md]",
    "payments": "Accepted: cards, UPI. PX-125 = bank declined. [payments.md]",
}

def worker(task, budget, depth):
    if depth > 1:
        return WorkerOutput(task["id"], False, {}, error="max delegation depth reached")
    if budget.exhausted:
        return WorkerOutput(task["id"], False, {}, error="shared budget exhausted")
    source = KNOWLEDGE.get(task["area"], "")
    messages = [  # ISOLATED context: only this task + this worker's data, not the parent's history
        {"role": "system", "content": "Answer ONLY from the data. Return JSON {answer, sources}. "
                                      "If the data doesn't answer it, answer 'UNKNOWN' with no sources."},
        {"role": "user", "content": f"Task: {task['question']}\nData: {source}"}]
    r = ollama.chat(model="llama3.2", messages=messages, format={"type": "object", "properties": {
        "answer": {"type": "string"}, "sources": {"type": "array", "items": {"type": "string"}}},
        "required": ["answer", "sources"]}, options={"temperature": 0})
    tokens = r["prompt_eval_count"] + r["eval_count"]
    within_budget = budget.spend(tokens)
    out = json.loads(r["message"]["content"])
    return WorkerOutput(task["id"], out["answer"] != "UNKNOWN", {"answer": out["answer"]},
                        out["sources"], tokens, partial=not within_budget)

def synthesize(question, outputs):
    facts = [o for o in outputs if o.success and o.sources]
    hypotheses = [o for o in outputs if o.success and not o.sources]      # unsourced = not facts
    failures = [o for o in outputs if not o.success]
    notes = "\n".join(f"- {o.result['answer']} (sources: {o.sources})" for o in facts)
    caveats = [f"unverified: {o.result['answer']}" for o in hypotheses] + \
              [f"missing: task {o.task_id} ({o.error or 'no answer'})" for o in failures]
    r = ollama.chat(model="llama3.2", options={"temperature": 0}, messages=[{"role": "user", "content":
        f"Question: {question}\nVerified facts:\n{notes}\n\nWrite a short answer using only the verified facts, "
        f"with their sources. Then list these caveats: {caveats}"}])
    return r["message"]["content"]

def orchestrate(question, tasks, max_tokens=6000):
    budget = SharedBudget(max_tokens)
    with ThreadPoolExecutor(max_workers=4) as pool:                       # fan-out
        outputs = list(pool.map(lambda t: worker(t, budget, depth=1), tasks))
    for o in outputs:
        print(asdict(o))
    print(f"budget used: {budget.used}/{budget.max_tokens}")
    return synthesize(question, outputs)                                   # fan-in

if __name__ == "__main__":
    q = "I'm in Sri Lanka and my shoes arrived damaged. How long until a replacement arrives, and can I return them?"
    tasks = [{"id": "t1", "area": "shipping", "question": "How long does delivery to Sri Lanka take?"},
             {"id": "t2", "area": "returns", "question": "What is the return window for damaged items?"},
             {"id": "t3", "area": "loyalty", "question": "Does the customer get loyalty points back?"}]
    print(orchestrate(q, tasks))
```

Task t3 has no data source — watch it come back as a failure or `UNKNOWN`, and watch the
synthesizer report it as missing instead of inventing an answer.

### 4.2 Handoffs between specialist agents

```python
# handoffs.py — triage hands the conversation to a specialist; cap the number of handoffs
import json
import ollama

AGENTS = {
    "triage":   "You route customers. Decide which specialist should handle the message.",
    "billing":  "You handle payments and refunds. Refund policy: damaged items fully refunded within 60 days.",
    "shipping": "You handle delivery questions. Standard delivery 3-5 days.",
}
HANDOFF = {"type": "object", "properties": {
    "handoff_to": {"type": "string", "enum": ["billing", "shipping", "none"]},
    "reply": {"type": "string"}}, "required": ["handoff_to", "reply"]}

def converse(message, max_handoffs=2):
    current, history = "triage", [{"role": "user", "content": message}]
    for _ in range(max_handoffs + 1):
        r = ollama.chat(model="llama3.2", format=HANDOFF, options={"temperature": 0},
                        messages=[{"role": "system", "content": AGENTS[current] +
                                   " If another specialist fits better, set handoff_to; otherwise reply."}] + history)
        d = json.loads(r["message"]["content"])
        if d["handoff_to"] in ("none", current):
            return current, d["reply"]
        print(f"handoff: {current} -> {d['handoff_to']}")
        history.append({"role": "assistant", "content": f"[handoff from {current}: {d['reply']}]"})  # keep context
        current = d["handoff_to"]
    return current, "Let me connect you with a human colleague."           # cap reached: escalate

print(converse("I was charged twice for order A-1043"))
```

---

## 5. Production view

| Measure | Why |
|---|---|
| Tokens and cost per task vs a single-agent baseline | Is the extra cost buying accuracy? |
| Per-agent success / partial / error rates | Find the weak link |
| Unsourced-claim rate in worker outputs | Hallucination-cascade risk |
| Handoff count distribution; handoff loops | Ping-pong detection |
| Budget-exhausted rate | Budget sizing; runaway delegation |
| End-to-end latency, critical path | Parallel fan-out should shorten it |
| Trace per agent with parent/child links (Ch 34) | Debugging hand-offs |

---

## 6. Common mistakes

- Multiple agents where parallel tool calls would do.
- Passing the parent's whole conversation to every child.
- Workers returning prose without sources or status fields.
- Synthesizers that treat every worker sentence as fact.
- Per-agent budgets only (no shared cap).
- Unlimited handoffs or delegation depth.
- Giving every agent every tool (lost separation of duties).

---

## 7. Practice

**Level 1**
1. Run `multi_agent.py`. What did task t3 return? How did the synthesizer handle it?
2. Set `max_tokens=300`. Which outputs became `partial` or failed? Is the final answer honest about it?

**Level 2**
3. Solve the same customer question with **one** agent that has all three data sources as tools
   (Ch 14). Compare tokens, latency and answer quality with the multi-agent version. Which would you ship?
4. Add a **checker agent** that receives only the final answer and the workers' sources (not their
   reasoning) and flags any claim not supported by a source.

**Level 3**
5. Build a mini **deep-research** system (Ch 18): a planner creates 3–5 sub-questions; workers each run
   the Ch 14 agent with a search tool over a document folder and return `WorkerOutput` with sources;
   a synthesizer writes a cited report; a verifier checks every citation. Measure cost, latency and
   citation accuracy.

---

## 8. Check yourself

1. State the isolation-not-concurrency rule and explain it.
2. Give three valid reasons for a multi-agent design.
3. What fields should a worker return, and why `sources` in particular?
4. Why pass a shared budget by reference?
5. What is a hallucination cascade, and how do you prevent it?
6. How do you prevent handoff ping-pong?

<details>
<summary>Answers</summary>

1. Use sub-agents when you need separate contexts (isolation) — e.g. a worker that reads a lot and
   returns a little, or separate permissions. If you just need things done at the same time, one
   agent with parallel tool calls is cheaper and simpler.
2. Any three: context isolation; specialization (tools/prompts/models); separation of duties for
   security; independent checking; parallel exploration of independent branches; organizational
   boundaries.
3. task_id, success, result, sources, tokens_used, partial, error. Sources let the orchestrator
   distinguish facts from guesses and let checkers verify claims.
4. So the total spend across all agents is capped; per-agent budgets add up across many agents.
5. One agent's unsourced guess is treated as fact by others and built upon. Prevent with mandatory
   sources, treating unsourced claims as hypotheses, and verifying key claims.
6. Cap handoffs per conversation, enforce a DAG (no returning to a previous agent without a new
   reason), and detect loops; escalate to a human when the cap is hit.

</details>

---

## 9. Key terms

**multi-agent system** · **isolation vs concurrency** · **supervisor / orchestrator–worker** ·
**hierarchical agents** · **handoff / swarm** · **pipeline** · **debate / critic / maker–checker** ·
**blackboard** · **agents-as-tools** · **shared state vs message passing** · **worker contract** ·
**task spec** · **fan-out / fan-in** · **synthesizer** · **shared budget** · **delegation depth** ·
**hallucination cascade** · **ping-pong** · **separation of duties**

Next: [Chapter 26 — State, checkpoints, human-in-the-loop →](26-state-checkpoints-hitl.md)
