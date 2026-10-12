# Chapter 14 — The agent loop

> An agent is a loop: the model thinks, calls a tool, reads the result, and repeats until
> it's done — or until **you** stop it. The loop is ten lines. The guards around it (when
> to stop, budgets, loop detection, checkpoints) are what make it safe to run.

**You will learn:** the ReAct loop, the four termination conditions, iteration/token/time
budgets (and the "first turn is free" bug), loop detection, an explicit `finish` tool,
checkpoint-and-resume, provider stop reasons, a kill switch, and the classic agent
vocabulary (ReAct, OODA, BDI, reactive vs proactive).

**Where this fits:** builds on tool calling (Ch 11), the reliable client (Ch 12) and the
workflow-vs-agent decision (Ch 13). Context grows every iteration → context engineering
(Ch 15) and memory (Ch 16). Planning variants of the loop are in Ch 24; durable checkpoints
and human approval pauses in Ch 26; trajectory evals in Ch 33; the kill switch and safety
patterns in Ch 35.

---

## 1. The idea in plain words

```
messages = [system, user request]
loop:
    response = model(messages, tools)
    if response has no tool calls:  → done, return the answer
    run each tool call, append results to messages
    check: too many steps? too many tokens? too long? → stop safely
```

The **message list is the agent's working memory**. Every iteration sends the whole list
again (Ch 03), so it gets longer, slower and more expensive each step.

The pattern is called **ReAct** (Reason + Act): the model reasons about what to do, acts with
a tool, observes the result, and reasons again.

---

## 2. Analogy

**A detective on a case.** Look at the evidence, decide on the next lead, go check it, come
back with new information, decide again — until the case is solved. A good detective also has
limits: a deadline, a budget, and the sense to stop following the same dead-end lead.

Where it breaks: a detective remembers yesterday without re-reading the whole case file. The
agent re-reads the *entire* file on every step.

---

## 3. How it works

### 3.1 The four termination conditions

Every agent loop needs all four. Missing one is a production incident waiting to happen.

| # | Condition | Meaning | Outcome |
|---|---|---|---|
| 1 | **Task complete** | Model calls an explicit `finish` tool (or signals end of turn with a final answer) | ✅ success — return the answer |
| 2 | **No tool wanted** | Model replied with text and no tool calls | Usually success — but check it's a real answer, not a question or a give-up |
| 3 | **Max iterations** | Hit the step cap (e.g. 10–25) | ⚠️ stop, checkpoint, report "couldn't finish" |
| 4 | **Budget exhausted** | Token, cost or wall-clock limit reached | ⚠️ stop, checkpoint, report |

Plus **external stops**: a user cancel or an operator **kill switch** (Ch 35).

### 3.2 Budgets: check *before* you spend

A common bug: the budget check runs at the top of the loop using tokens counted *after*
each call. On the first iteration the counter is 0, so the first call can never be blocked —
however large it is. And the check always lets you go one call over.

Fix: **estimate the next call's cost before making it** (current context tokens + expected
output) and refuse if `used + estimate > budget`. Use the provider's token-count endpoint or
your own estimate (Ch 02).

**Budgets must survive restarts.** If you resume a stopped run and reset the counters, a
4,000-token budget resumed three times spends 12,000. Store `tokens_used` and `iterations` in
the checkpoint.

### 3.3 Loop detection

Signs an agent is stuck:
- **Same tool, same arguments**, called again and again.
- **Oscillation**: A → B → A → B.
- **No progress**: iterations go by with no new information.

Two classic causes of "the last tool result was correct, but the agent called the same tool
five more times":
1. **The tool result never made it into the messages** (an append bug), so the model never
   sees it and asks again.
2. **The result has no closure signal**: a bare `"4736"` doesn't tell the model the question
   is answered. Results like `"Order A-1043 found: shipped on Oct 3 (lookup complete)"` give the
   model a clear reason to move on.

A good loop detector: hash `(tool_name, sorted arguments)`; if the same hash appears 3 times,
inject a message ("You already called X with these arguments and got Y. Use that result or try
a different approach."), and stop on the next repeat.

### 3.4 An explicit `finish` tool

Instead of guessing whether a text reply is a final answer, give the model a tool:

```
finish(answer: str, sources: list[str], confidence: "high" | "medium" | "low")
```

Benefits: a structured final answer (Ch 10), sources you can verify (Ch 07), and a clear
"done" signal separate from "I'm asking the user a question".

### 3.5 Provider stop reasons (check them every iteration)

| Provider style | Values | Meaning |
|---|---|---|
| Anthropic `stop_reason` | `end_turn`, `tool_use`, `max_tokens`, `stop_sequence`, `pause_turn`, `refusal` | `tool_use` → run tools; `max_tokens` → output truncated; `pause_turn` → server-side tool paused, re-send to continue; `refusal` → declined |
| OpenAI `finish_reason` | `stop`, `tool_calls`, `length`, `content_filter` | Same ideas |
| Ollama `done_reason` | `stop`, `length` | `length` → truncated |

A truncated tool call (`max_tokens` / `length`) has incomplete JSON arguments — never execute it.

### 3.6 Checkpoint on halt

Never stop without saving a resumable state:

```json
{"run_id": "r-123", "status": "hit_max_iterations", "step": 12,
 "tokens_used": 48210, "messages": [...], "created_at": "...", "budget": {...}}
```

Then a human or a later job can inspect it, raise the budget, and resume. A checkpoint is only
useful if (a) it includes the full messages, (b) budgets persist, and (c) tools are idempotent
— resuming may re-run the step that was in progress (Ch 11, 12). Durable checkpointing
frameworks are in Ch 26.

### 3.7 Agent vocabulary you'll hear

| Term | Meaning | Where it shows up |
|---|---|---|
| **ReAct** | Reason → Act → Observe loop | The loop in this chapter |
| **OODA** | Observe → Orient → Decide → Act, continuously, against a changing environment | Monitoring / ops agents that react to events |
| **BDI** | Beliefs (what it knows), Desires (goals), Intentions (committed plans) | Goal-driven agents that persist until a goal state is reached (Ch 24) |
| **Reactive agent** | Stimulus → response, no planning or memory | Simple handlers, routers |
| **Proactive / scheduled agent** | Triggered by time or events, not a user message | Reminders, monitors, follow-ups (Ch 26) |
| **Plan-and-execute** | Plan all steps first, then run them | Cheaper, less adaptive (Ch 24) |

---

## 4. Code

### 4.1 `agent.py` — a guarded agent loop

```python
# agent.py — ReAct loop with 4 termination conditions, budgets, loop detection, checkpoints
import hashlib
import json
import time
from pathlib import Path
import ollama

MODEL = "llama3.2"
CHECKPOINT_DIR = Path("checkpoints")
KILL_SWITCH = Path("STOP")

FINISH_TOOL = {"type": "function", "function": {
    "name": "finish",
    "description": "Call this when you have the final answer for the user. Include the facts you relied on.",
    "parameters": {"type": "object", "properties": {
        "answer": {"type": "string"},
        "sources": {"type": "array", "items": {"type": "string"},
                    "description": "Tool results or documents the answer is based on"}},
        "required": ["answer", "sources"]}}}

class Agent:
    def __init__(self, tools, registry, system, max_iterations=8, max_tokens=20_000, max_seconds=120):
        self.tools = tools + [FINISH_TOOL]
        self.registry = registry
        self.system = system
        self.limits = {"iterations": max_iterations, "tokens": max_tokens, "seconds": max_seconds}

    def run(self, user_message, run_id, state=None):
        state = state or {"run_id": run_id, "step": 0, "tokens_used": 0, "seen_calls": {},
                          "messages": [{"role": "system", "content": self.system},
                                       {"role": "user", "content": user_message}]}
        started = time.monotonic()
        while True:
            if KILL_SWITCH.exists():
                return self._halt(state, "killed")
            if state["step"] >= self.limits["iterations"]:
                return self._halt(state, "hit_max_iterations")
            if time.monotonic() - started > self.limits["seconds"]:
                return self._halt(state, "hit_time_limit")
            estimate = self._estimate_tokens(state["messages"]) + 500       # check BEFORE spending
            if state["tokens_used"] + estimate > self.limits["tokens"]:
                return self._halt(state, "hit_token_budget")

            r = ollama.chat(model=MODEL, messages=state["messages"], tools=self.tools,
                            options={"temperature": 0})
            state["step"] += 1
            state["tokens_used"] += (r["prompt_eval_count"] or 0) + (r["eval_count"] or 0)
            msg = r["message"]
            if hasattr(msg, "model_dump"):          # SDK objects -> plain dicts, so checkpoints are valid JSON
                msg = msg.model_dump(exclude_none=True)

            if r.get("done_reason") == "length":
                return self._halt(state, "output_truncated")
            if not msg.get("tool_calls"):                                  # condition 2
                return {"status": "answered_without_finish", "answer": msg["content"], **self._stats(state)}

            state["messages"].append(msg)
            for call in msg["tool_calls"]:
                name, args = call["function"]["name"], call["function"]["arguments"]
                if name == "finish":                                       # condition 1
                    return {"status": "done", **args, **self._stats(state)}
                result = self._run_tool(state, name, args)
                state["messages"].append({"role": "tool", "tool_name": name, "content": result})

    def _run_tool(self, state, name, args):
        key = hashlib.sha256(f"{name}:{json.dumps(args, sort_keys=True)}".encode()).hexdigest()
        state["seen_calls"][key] = state["seen_calls"].get(key, 0) + 1
        if state["seen_calls"][key] >= 3:                                  # loop detection
            return (f"You already called {name} with these exact arguments "
                    f"{state['seen_calls'][key] - 1} times. Use the earlier result or call finish.")
        fn = self.registry.get(name)
        if fn is None:
            return f"Unknown tool '{name}'. Available tools: {sorted(self.registry)} or finish."
        try:
            return str(fn(**args))
        except TypeError as e:
            return f"Bad arguments for {name}: {e}. Check the parameter names and types."
        except Exception as e:                                             # errors are prompts
            return f"{name} failed: {e}. Try again later or call finish explaining the problem."

    @staticmethod
    def _estimate_tokens(messages):
        return sum(len(str(m.get("content", ""))) for m in messages) // 4    # rough: ~4 chars/token

    @staticmethod
    def _stats(state):
        return {"steps": state["step"], "tokens_used": state["tokens_used"]}

    def _halt(self, state, status):
        CHECKPOINT_DIR.mkdir(exist_ok=True)
        path = CHECKPOINT_DIR / f"{state['run_id']}.json"
        state["status"] = status
        path.write_text(json.dumps(state, default=str, indent=2))
        return {"status": status, "checkpoint": str(path), **self._stats(state)}

    def resume(self, run_id, extra_iterations=5):
        state = json.loads((CHECKPOINT_DIR / f"{run_id}.json").read_text())
        self.limits["iterations"] = state["step"] + extra_iterations       # budgets persist
        return self.run(None, run_id, state=state)
```

### 4.2 Use it

```python
# ch14_run.py
from agent import Agent

ORDERS = {"A-1043": "shipped via DHL on 2026-10-03, ETA 2026-10-15"}

def get_order(order_id: str) -> str:
    if order_id in ORDERS:
        return f"Order {order_id}: {ORDERS[order_id]}. (lookup complete)"     # closure signal
    return f"No order '{order_id}'. IDs look like 'A-1043'."

TOOLS = [{"type": "function", "function": {
    "name": "get_order", "description": "Get shipping status for one order ID like 'A-1043'.",
    "parameters": {"type": "object", "properties": {"order_id": {"type": "string"}},
                   "required": ["order_id"]}}}]

agent = Agent(TOOLS, {"get_order": get_order},
              system="You are a support agent. Use tools to look up facts, then call finish.")
print(agent.run("Where is my order A-1043 and when will it arrive?", run_id="demo-1"))
print(Agent(TOOLS, {"get_order": get_order}, system="Use tools.", max_iterations=1)
      .run("Where is A-1043?", run_id="demo-2"))          # forces a halt + checkpoint
```

Open `checkpoints/demo-2.json` and read it. That file is what an on-call engineer sees when a
run stops.

---

## 5. Production view

| Metric | What it tells you |
|---|---|
| **Iterations per task — as a histogram** | Bimodal (most at 3, a bump at max) = a loop bug in the tail |
| Halt reasons (`hit_max_iterations`, `hit_token_budget`, `killed`…) | Which guard fires, how often |
| Tokens and cost per task, p95 | Budget sizing (Ch 03, 37) |
| Loop-detector triggers | Tool design problems (missing closure signals, bad errors) |
| `answered_without_finish` rate | The model skipping your finish contract |
| Resume success rate | Whether checkpoints are actually usable |

**Every halt is a data point.** Route halted runs into a review queue; the worst ones become
eval cases (Ch 33).

---

## 6. Common mistakes

- No iteration cap ("the model will figure it out").
- Budget check after the call, or counters that reset on resume.
- Executing tool calls from a truncated response.
- Treating every text reply as success (it might be "I couldn't do this").
- Not appending tool results, or appending them with the wrong role/ID.
- Tool results without a closure signal.
- Halting without saving state.
- A kill switch that's checked only once at startup.

---

## 7. Practice

**Level 1**
1. Run `ch14_run.py`. Read `checkpoints/demo-2.json`. Then call `agent.resume("demo-2")`.
2. Create a file named `STOP` and run again. Delete it.

**Level 2**
3. Remove "(lookup complete)" from the tool result and ask a question that needs two lookups
   ("Compare the ETAs of A-1043 and A-2001"). Does the loop detector fire? Record steps and
   tokens with and without the closure signal.
4. Replace `_estimate_tokens` with a real count (a 1-token call that returns `prompt_eval_count`,
   or a provider token-count API). Prove the first call can now be blocked by a tiny budget.

**Level 3**
5. Add a **cost budget** (dollars) using the `CostMeter` from Ch 03, and an **oscillation
   detector** (A→B→A→B). Write 5 adversarial test cases that trigger each halt reason and assert
   the right status is returned. These are your first agent **regression tests**.

---

## 8. Check yourself

1. Name the four termination conditions.
2. Why must the budget check happen before the model call, using an estimate?
3. An agent got a correct tool result at step 50, then called the same tool 5 more times. Give
   two likely causes.
4. Why is an explicit `finish` tool better than treating any text reply as the answer?
5. What three things must be true for a checkpoint to be safely resumable?
6. What does a bimodal iterations-per-task histogram suggest?

<details>
<summary>Answers</summary>

1. Task complete (finish/final answer), no tool wanted, max iterations, budget exhausted
   (tokens/cost/time) — plus external stops (cancel, kill switch).
2. A check after counting can't stop the first call (counter is 0) and always overshoots by
   one call. Estimating first lets you refuse the expensive call before paying.
3. (a) The tool result wasn't appended to the messages, so the model never saw it; (b) the
   result lacked a closure signal, so the model didn't know the question was answered. (Also
   possible: a confusing result format or an error-looking result.)
4. It gives a structured, verifiable answer with sources, and separates "done" from "asking a
   question" or "giving up".
5. It contains the full message history, the budgets/counters persist, and tools are
   idempotent (re-running the in-progress step is safe).
6. Most tasks finish normally but a subset hits the cap — a loop or stuck-agent bug affecting
   specific inputs.

</details>

---

## 9. Key terms

**agent loop** · **ReAct** · **working memory (message list)** · **termination conditions** ·
**max_iterations** · **token / cost / time budget** · **pre-call estimate** · **loop
detection** · **closure signal** · **finish tool** · **stop reason** · **checkpoint** ·
**resume** · **kill switch** · **OODA** · **BDI** · **reactive vs proactive agent**

Next: [Chapter 15 — Context engineering →](15-context-engineering.md)
