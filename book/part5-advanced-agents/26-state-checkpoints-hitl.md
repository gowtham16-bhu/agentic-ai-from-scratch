# Chapter 26 — State, checkpoints, human-in-the-loop

> Real agent work pauses: for a human approval, for a slow system, for tomorrow morning.
> Real servers crash. **State + checkpoints + durable execution** let a run stop and continue
> exactly where it left off — minutes, hours or days later — without redoing (or double-doing)
> anything.

**You will learn:** explicit state and state machines, graphs with nodes/edges/conditional
edges, **reducers**, **checkpointers** and thread IDs, resume and **time travel**, human-in-the-
loop patterns (approve, edit, review, ask, escalate) with static and dynamic **interrupts**, the
re-execution gotcha, long-running agent harnesses, **durable execution** (Temporal, Restate,
DBOS, cloud workflows), the duration ladder, and **scheduled/proactive agents** with a relevance
gate.

**Where this fits:** builds on the agent loop's checkpoint dict (Ch 14), multi-agent shared state
(Ch 25) and idempotent tools (Ch 11–12). LangGraph is surveyed among frameworks in Ch 27;
approval UX is Ch 44; deployment of async jobs and queues is Ch 38; approval gates as a safety
pattern are Ch 35.

---

## 1. The idea in plain words

- **State:** everything needed to continue a run — messages, intermediate results, decisions,
  counters, budgets. Make it an explicit, typed object (not scattered variables).
- **Checkpoint:** a saved snapshot of the state after each step, stored durably and keyed by a
  **thread/run ID**.
- **Resume:** load the latest checkpoint for that ID and continue.
- **Human-in-the-loop (HITL):** the run *pauses* at a defined point, a human acts (approve, edit,
  answer), and the run resumes with their input.
- **Durable execution:** the platform guarantees your workflow runs to completion despite crashes,
  deploys and long waits — by recording every completed step.

---

## 2. Analogy

**Save points in a video game.** Without them, a crash sends you back to the start. With them, you
reload and continue. **Time travel** is loading an *older* save to try a different choice. A human
approval is a level where the game waits for a second player to press a button — and the console can
be switched off while it waits.

---

## 3. How it works

### 3.1 Graphs: control flow you can see

Model the workflow as a **graph**:

```
START → lookup_order → (amount > 100?) ──yes──► approve (HUMAN) ──► refund → END
                                    └──no──────────────────────────► refund
```

- **Nodes:** functions that read state and return **updates**.
- **Edges:** what runs next; **conditional edges** pick the next node from state (routing made
  explicit and testable).
- **State schema:** a typed definition of the state.
- **Reducers:** how updates to the same field are **combined** (append to a list, add numbers, merge
  dicts). With parallel branches (fan-out), a reducer is required: LangGraph raises an error if two
  branches write the same key in one step without one — and hand-rolled shared state would silently
  keep only the last write.

LangGraph is the best-known library for this model; the ideas apply to any graph/state-machine engine.

### 3.2 Checkpointers, threads and time travel

```
thread_id = "refund-A-1043"
step 0: {order_id}                         → checkpoint 0
step 1: {order_id, amount}                 → checkpoint 1
step 2: PAUSED at approve (interrupt)      → checkpoint 2   ← process can exit; state is in the DB
...hours later, any server...
resume with "yes" → step 3 → step 4 → END  → checkpoints 3, 4
```

- Use an in-memory checkpointer for tests and a **database checkpointer** (SQLite, Postgres, etc.)
  in production.
- **Time travel:** list a thread's checkpoint history, load an earlier one, optionally modify state,
  and re-run from there.
- **The debugging workflow:** *reproduce → rewind → patch → re-run* from the failing step, instead of
  re-running a 20-minute agent from the start.

### 3.3 Human-in-the-loop patterns

| Pattern | Example | Implementation |
|---|---|---|
| **Approve / reject** | "Refund $249 to order A-1043?" | Interrupt before the side-effecting node |
| **Edit** | Human changes the refund to $200 or edits a draft email | Interrupt returns the edited value; resume with it |
| **Review output** | Check a generated contract clause before sending | Interrupt after generation |
| **Ask for missing info** | "Which address — home or work?" | Agent requests input; resume with the answer |
| **Escalate** | Low confidence or policy says a human must handle it | Hand off with context (Ch 44) |

**Static interrupts** pause before/after named nodes (configured at compile time). **Dynamic
interrupts** call `interrupt(payload)` inside a node when a condition is met (e.g. only for large
amounts).

**The re-execution gotcha:** when resumed, a node that called `interrupt()` runs again **from the
top**. Anything before the `interrupt()` call executes twice. Put `interrupt()` first, or make
whatever comes before it idempotent.

### 3.4 Long-running agents

Agents that work for hours (coding, research, data migrations) can't keep everything in one context.
Common harness ideas:
- A **progress file / todo list** the agent updates and re-reads (Ch 15 note-taking).
- **Frequent checkpoints** (in code: commits; in data: saved state) so a fresh context can resume.
- **Context resets** between sessions: start each session by reading the progress notes and the
  current state, not the old transcript.
- An **initializer** step that sets up the environment and plan, then repeated worker sessions that
  each make bounded progress and leave the system in a clean, testable state.

### 3.5 Durable execution

For workflows that must not be lost — payments, onboarding, multi-day processes — use a durable
execution engine:

| Engine | Model |
|---|---|
| **Temporal** | **Workflows** (deterministic code) + **activities** (side effects, retried). Every event is recorded; after a crash the workflow **replays** its history, reusing recorded activity results instead of re-running them. **Signals** send data in (approvals), **queries** read state, durable **timers** wait for days |
| **Restate** | Durable functions/handlers with journaled steps and durable state |
| **DBOS** | Durable workflows as decorated functions, with state in Postgres |
| **Cloud workflows** | AWS Step Functions, Google Cloud Workflows, Azure Durable Functions |
| **LangGraph + DB checkpointer** | Durable at the graph-step level; good for agent graphs |

**Determinism rule (Temporal-style engines):** workflow code must be deterministic — no direct
random numbers, current time, network or file I/O; use the engine's APIs (activities, workflow time,
timers). Otherwise replay diverges from history.

### 3.6 The duration ladder

Pick the execution model from the task's **p99** duration (Ch 38):

```
< 2 s           synchronous request/response
2–30 s          synchronous + streaming
30 s – 5 min    async job + polling (or server-sent events)
5 min – 1 h     queue + worker + checkpointing
1 h +           durable workflow (Temporal/DBOS/…) with human/timer waits
```

### 3.7 Scheduled and proactive agents

The difference between a chatbot and an assistant: it does things **later**, on its own.

```
1 INTENT CAPTURE    "remind me if the price drops" → store intent + context + expiry
2 TRIGGER           time (cron), event (webhook/queue), or condition (price < X)
3 DURABLE SCHEDULER survives restarts: cron → DB/Redis sorted set → Temporal timer → cloud scheduler
4 RELEVANCE GATE    the difference between an assistant and spam (below)
5 DELIVERY          right channel, respect quiet hours
6 FEEDBACK          track ignore rate; stop nagging
```

**The relevance gate checks all five before sending anything:**
1. Already done elsewhere? (the user reordered yesterday)
2. Still actionable? (the sale ended)
3. Under the follow-up cap? (max 2 nudges, then stop forever)
4. Genuinely new information?
5. Appropriate time? (quiet hours → **reschedule**, don't drop)

Design rules: **silence is the default**; always include an off switch; an ignore rate above ~50%
means your triggers are wrong. Never use `sleep()` in a process as a scheduler — it dies with the
process.

---

## 4. Code

```bash
pip install langgraph        # checked against langgraph 1.2.x
```

### 4.1 A refund graph with a reducer, a checkpointer and a human approval

```python
# lg_refund.py — a refund workflow with state, a reducer, a checkpointer and a human approval interrupt
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command

class State(TypedDict):
    order_id: str
    amount: float
    decision: str
    log: Annotated[list[str], operator.add]      # REDUCER: updates are appended, not overwritten

def lookup_order(state: State):
    return {"amount": 249.0, "log": [f"looked up {state['order_id']}: amount 249.0"]}

def route(state: State):
    return "approve" if state["amount"] > 100 else "refund"     # conditional edge: explicit, inspectable

def approve(state: State):
    # interrupt() pauses the graph and saves state; put it FIRST in the node, because the
    # node re-runs from the top on resume (side effects before it would happen twice)
    answer = interrupt({"question": f"Approve refund of {state['amount']} for {state['order_id']}?"})
    return {"decision": "approved" if answer == "yes" else "rejected", "log": [f"human said {answer}"]}

def refund(state: State):
    if state.get("decision") == "rejected":
        return {"log": ["refund skipped (rejected)"]}
    return {"log": [f"refund issued: {state['amount']} (idempotency key {state['order_id']}-refund)"]}

graph = StateGraph(State)
graph.add_node("lookup_order", lookup_order)
graph.add_node("approve", approve)
graph.add_node("refund", refund)
graph.add_edge(START, "lookup_order")
graph.add_conditional_edges("lookup_order", route, {"approve": "approve", "refund": "refund"})
graph.add_edge("approve", "refund")
graph.add_edge("refund", END)
app = graph.compile(checkpointer=InMemorySaver())     # production: a Postgres/SQLite checkpointer

if __name__ == "__main__":
    config = {"configurable": {"thread_id": "refund-A-1043"}}       # one thread = one durable run
    result = app.invoke({"order_id": "A-1043", "log": []}, config)
    print("paused with:", result.get("__interrupt__"))
    print("saved state:", app.get_state(config).values)
    # ... hours later, a different process with the same checkpointer + thread_id ...
    result = app.invoke(Command(resume="yes"), config)
    print("final log:", result["log"])
    print("history (time travel):", [s.next for s in app.get_state_history(config)])
```

Output (verified):

```
paused with: [Interrupt(value={'question': 'Approve refund of 249.0 for A-1043?'}, ...)]
saved state: {'order_id': 'A-1043', 'amount': 249.0, 'log': ['looked up A-1043: amount 249.0']}
final log: ['looked up A-1043: amount 249.0', 'human said yes', 'refund issued: 249.0 (idempotency key A-1043-refund)']
history (time travel): [(), ('refund',), ('approve',), ('lookup_order',), ('__start__',)]
```

### 4.2 Fan-out with `Send` — and why the reducer matters

```python
# lg_fanout.py — map-reduce with Send; the reducer is what makes parallel writes safe
import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send

class State(TypedDict):
    order_ids: list[str]
    statuses: Annotated[list[str], operator.add]     # remove the reducer and parallel writes collide

def fan_out(state: State):
    return [Send("check_order", {"order_id": oid}) for oid in state["order_ids"]]   # one branch per order

def check_order(item: dict):
    return {"statuses": [f"{item['order_id']}: shipped"]}

def summarize(state: State):
    return {"statuses": [f"SUMMARY: {len(state['statuses'])} orders checked"]}

g = StateGraph(State)
g.add_node("check_order", check_order)
g.add_node("summarize", summarize)
g.add_conditional_edges(START, fan_out, ["check_order"])
g.add_edge("check_order", "summarize")
g.add_edge("summarize", END)
print(g.compile().invoke({"order_ids": ["A-1", "A-2", "A-3"], "statuses": []})["statuses"])
```

With the reducer: all three statuses plus the summary. Change the field to a plain `list[str]` and
LangGraph raises `InvalidUpdateError: At key 'statuses': Can receive only one value per step` — the
framework protecting you from a silent overwrite.

### 4.3 A durable workflow with Temporal (approval can take days)

```bash
pip install temporalio       # plus a Temporal server (e.g. the temporal CLI's dev server) to run it
```

```python
# temporal_refund.py — a durable refund workflow: survives crashes, waits days for approval
from datetime import timedelta
from temporalio import activity, workflow
from temporalio.common import RetryPolicy

@activity.defn
async def issue_refund(order_id: str, amount: float) -> str:
    # side effects live in ACTIVITIES (retried, results recorded); make them idempotent
    return f"refund {order_id}-refund issued for {amount}"

@workflow.defn
class RefundWorkflow:
    def __init__(self) -> None:
        self.decision: str | None = None

    @workflow.signal
    def human_decision(self, decision: str) -> None:       # sent later by an approval UI
        self.decision = decision

    @workflow.query
    def status(self) -> str:
        return self.decision or "waiting for approval"

    @workflow.run
    async def run(self, order_id: str, amount: float) -> str:
        if amount > 100:
            # durable wait: no process sits idle; the timer and state live in Temporal
            await workflow.wait_condition(lambda: self.decision is not None, timeout=timedelta(days=3))
            if self.decision != "approve":
                return "rejected"
        return await workflow.execute_activity(
            issue_refund, args=[order_id, amount],
            start_to_close_timeout=timedelta(seconds=30),
            retry_policy=RetryPolicy(maximum_attempts=5))
```

A worker process registers the workflow and activity; your API starts a workflow per refund and an
approval UI sends the `human_decision` signal. If the worker crashes mid-wait, another worker replays
the history and continues. (If the 3-day timeout passes, `wait_condition` raises a timeout error —
decide whether that means escalate or auto-reject.)

### 4.4 A durable scheduler with a relevance gate (offline)

```python
# proactive.py — follow-ups that survive restarts, claimed once, and gated for relevance
import sqlite3
from datetime import datetime, timedelta

db = sqlite3.connect(":memory:")
db.execute("""CREATE TABLE followups (id INTEGER PRIMARY KEY, user_id TEXT, intent TEXT, due_at TEXT,
              status TEXT DEFAULT 'pending', attempts INTEGER DEFAULT 0, expires_at TEXT)""")

def schedule(user_id, intent, due_at, expires_at):
    db.execute("INSERT INTO followups (user_id, intent, due_at, expires_at) VALUES (?,?,?,?)",
               (user_id, intent, due_at.isoformat(), expires_at.isoformat()))

def claim_due(now):
    """Atomically mark due items as 'processing' so two workers never send the same follow-up."""
    with db:
        rows = db.execute("SELECT id, user_id, intent, attempts, expires_at FROM followups "
                          "WHERE status='pending' AND due_at<=?", (now.isoformat(),)).fetchall()
        for row in rows:
            db.execute("UPDATE followups SET status='processing' WHERE id=? AND status='pending'", (row[0],))
    return rows

def relevance_gate(item, now, already_done, has_new_info, quiet_hours=(22, 7), max_attempts=2):
    _id, user, intent, attempts, expires_at = item
    if already_done(user, intent):
        return "drop:done_elsewhere"
    if now >= datetime.fromisoformat(expires_at):
        return "drop:no_longer_actionable"
    if attempts >= max_attempts:
        return "drop:follow_up_cap"
    if not has_new_info(user, intent):
        return "drop:nothing_new"
    if now.hour >= quiet_hours[0] or now.hour < quiet_hours[1]:
        return "reschedule:quiet_hours"
    return "send"

now = datetime(2026, 10, 12, 23, 30)
schedule("u1", "price_drop:trail-runner", now - timedelta(minutes=1), now + timedelta(days=7))
schedule("u2", "reorder:socks", now - timedelta(minutes=1), now + timedelta(days=7))
for item in claim_due(now):
    decision = relevance_gate(item, now,
                              already_done=lambda u, i: u == "u2",     # u2 already reordered
                              has_new_info=lambda u, i: True)
    print(item[1], item[2], "->", decision)
print("second claim (another worker):", claim_due(now))     # nothing: already claimed
```

In production the claim step is the same idea with a database row lock, a Redis sorted set
(`ZADD` by due time + atomic pop), or a Temporal timer.

---

## 5. Production view

| Concern | Do |
|---|---|
| Lost runs on deploy/crash | Database checkpointer or durable execution engine; never in-memory state in prod |
| Double side effects on resume/replay | Idempotency keys on every write; side effects in activities/tools, not in replayed code |
| Stuck interrupts | Dashboard of runs waiting on humans, age, and SLA; reminders and escalation |
| State schema changes | Version your state; migrate or drain old threads before incompatible changes |
| Checkpoint storage growth | Retention policy; prune old checkpoints of finished threads |
| Proactive spam | Track send rate, ignore rate, opt-outs per trigger; cap and gate |
| Scheduler duplicates | Atomic claim; at-least-once delivery + idempotent handlers |

---

## 6. Common mistakes

- Keeping run state in process memory ("it's fine until the pod restarts").
- Side effects before `interrupt()` in the same node.
- Parallel branches writing the same state key without a reducer.
- Non-deterministic code inside durable workflows (time, random, network calls).
- Approvals with no timeout or escalation path.
- `asyncio.sleep` / `time.sleep` as a scheduler.
- Proactive messages without a relevance gate, cap or off switch.

---

## 7. Practice

**Level 1**
1. Run `lg_refund.py`. Change the amount in `lookup_order` to 50 — does it skip approval? Then resume
   with `"no"` for the 249 case.
2. Run `lg_fanout.py`, then remove the reducer and read the error.

**Level 2**
3. Replace `InMemorySaver` with a SQLite checkpointer (`langgraph-checkpoint-sqlite`). Start the run,
   **kill the process** at the interrupt, start a new process, and resume with the same `thread_id`.
4. Use `get_state_history` to load the checkpoint before `approve`, change `amount` with
   `update_state`, and re-run from there (time travel + fork).

**Level 3**
5. Port the Ch 14 agent to a LangGraph graph: an `agent` node (LLM call), a `tools` node, a conditional
   edge on "tool calls present?", an approval interrupt before any write tool, a budget in state, and a
   database checkpointer. Write 3 tests: normal completion, approval rejected, crash-and-resume.

---

## 8. Check yourself

1. What's the difference between state and a checkpoint?
2. Why do parallel branches need reducers?
3. Explain the `interrupt()` re-execution gotcha and two ways to handle it.
4. How does Temporal recover a workflow after a crash without repeating side effects?
5. Which execution model fits a task whose p99 is 20 minutes?
6. Name the five checks of a relevance gate.

<details>
<summary>Answers</summary>

1. State is the current data a run needs; a checkpoint is a saved snapshot of that state at a step,
   stored durably under a thread/run ID.
2. Two branches may update the same field in the same step; a reducer defines how to combine them
   (e.g. append). Without one, LangGraph raises an error; hand-rolled state silently keeps one write.
3. On resume, the node containing `interrupt()` re-runs from its first line, so code before the
   interrupt runs twice. Put the interrupt first, or make preceding code idempotent (or move it to a
   separate node).
4. It records every event; on recovery it replays the deterministic workflow code, and completed
   activities return their recorded results instead of executing again.
5. Queue + worker + checkpointing (5 min – 1 h band); consider durable execution if it involves waits
   or must never be lost.
6. Already done elsewhere? Still actionable? Under the follow-up cap? Genuinely new information?
   Appropriate time (reschedule during quiet hours)?

</details>

---

## 9. Key terms

**state** · **state machine / graph** · **node / edge / conditional edge** · **reducer** ·
**checkpointer** · **thread ID** · **resume** · **time travel / fork** · **human-in-the-loop** ·
**static vs dynamic interrupt** · **re-execution gotcha** · **long-running agent harness** ·
**durable execution** · **workflow vs activity** · **deterministic replay** · **signal / query /
timer** · **duration ladder** · **proactive agent** · **relevance gate** · **atomic claim**

Next: [Chapter 27 — Frameworks →](27-frameworks.md)
