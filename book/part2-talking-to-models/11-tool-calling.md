# Chapter 11 — Tool calling

> Tools are how a model **looks things up** and **does things**. The model never runs
> anything itself: it *asks* for a tool call, your code runs it, and you hand back the
> result. Tool design is the single biggest lever on agent quality.

**You will learn:** the tool-calling flow end to end, tool schemas, `tool_choice`,
parallel tool calls, provider format differences, the **five tool-design rules**, errors
as prompts, pagination, `dry_run` and idempotency for writes, read vs write tools, what to
do when you have too many tools (tool search), and the security basics.

**Where this fits:** builds on structured output (Ch 10 — tool arguments are schema-shaped
output) and hallucination (Ch 07 — tools replace recall with lookup). The agent loop (Ch 14)
is this flow repeated. MCP (Ch 29) is a standard way to *publish* tools; the MCP gateway
(Ch 32) governs them; tool security is Ch 36; tool trajectory evals are Ch 33.

---

## 1. The idea in plain words

You send the model a list of **tool definitions**: a name, a description, and a JSON Schema
for the arguments. When the model decides a tool would help, instead of answering in text it
returns a **tool call**: "call `get_order` with `{"order_id": "A-1043"}`". Your code runs the
real function, sends the **tool result** back, and the model continues — maybe calling more
tools, maybe answering.

---

## 2. Analogy

**A manager who can't touch the computer.** They're smart, but every lookup or action has to
be written on a request slip ("look up order A-1043"). An assistant (your code) does it and
hands back the printout. The quality of the work depends heavily on how clearly the request
slips are designed — and on whether the printouts are useful or a 200-page dump.

Where it breaks: a human manager would notice the assistant is doing something dangerous.
The model will happily ask for a destructive action if the tool allows it — **safety lives in
your code, not in the model** (Ch 35–36).

---

## 3. How it works

### 3.1 The flow

```
 YOUR APP                                      MODEL
 ───────                                       ─────
 messages + tool definitions  ───────────────► decides: answer in text, or call tools?
                              ◄─────────────── tool_calls: [get_order({"order_id": "A-1043"})]
 run get_order("A-1043")  (your code!)
 append assistant msg (with the tool call)
 append tool result {"status": "shipped", ...}
 messages + tool definitions  ───────────────► reads the result
                              ◄─────────────── final text: "Your order shipped on Oct 3..."
```

Run this flow in a loop until the model stops asking for tools and you have an **agent**
(Ch 14).

### 3.2 Provider formats differ (same idea)

| | Tool definition | Model's call | Your result message |
|---|---|---|---|
| **OpenAI-style** (also Ollama) | `{"type":"function","function":{name, description, parameters}}` | `message.tool_calls[i].function.{name, arguments}` (+ `id`) | `{"role":"tool","tool_call_id":id,"content":...}` (Ollama: `tool_name`) |
| **Anthropic-style** | `{name, description, input_schema}` | content block `{"type":"tool_use", id, name, input}` | user message with block `{"type":"tool_result","tool_use_id":id,"content":...}` |

Normalize these in **one client layer** (Ch 12) so the rest of your code doesn't care.

### 3.3 tool_choice

| Value | Meaning | Use for |
|---|---|---|
| `auto` (default) | Model decides | Normal agent turns |
| `required` / `any` | Must call *some* tool | Forcing action in a step |
| a specific tool | Must call *this* tool | Structured output via a "fake" tool (Ch 10), routing decisions |
| `none` | No tools this turn | Forcing a final answer (e.g. budget exhausted) |

> Provider check: some current models (e.g. recent Claude models) **reject** `required/any`
> and specific-tool forcing with an error. The portable pattern is `auto` + a clear
> instruction naming the tool + **strict** tool schemas (`strict: true`, so arguments always
> validate) — or schema-constrained output (Ch 10) when you only wanted JSON.

### 3.4 Parallel tool calls

A model can request **several tool calls in one turn** ("get_order A-1 and get_order A-2").
Run them **concurrently** and return all results. This is parallelism in **one** context — much
cheaper than spawning sub-agents for the same work (Ch 25: sub-agents are for *isolation*, not
concurrency).

Two details that matter in practice:
- Return **all** results of one turn together (Anthropic-style: all `tool_result` blocks in a
  **single** user message). Splitting them across messages teaches the model to stop making
  parallel calls.
- A failed tool still gets a result — mark it as an error (e.g. `is_error: true`) with an
  actionable message. Never silently drop a call.

### 3.5 The five tool-design rules

```
1. The description says WHEN to use it AND when NOT to use it
2. Few required fields; enums over free text
3. Return the useful slice, not the whole record
4. Errors are recovery instructions, not log lines
5. One good tool beats five overlapping ones
```

**Rule 1 — descriptions drive behavior.** The model chooses tools from names and
descriptions. Compare:

```
BAD:  "search: searches stuff"
GOOD: "search_help_articles: Search the public help-center articles by keywords.
       Use for how-to and policy questions. Do NOT use for a specific customer's order —
       use get_order for that. Returns up to 5 article titles with IDs."
```

**Rule 2 — easy arguments.** Every required field is a chance to hallucinate. Use enums
(`status: "open" | "closed"`), defaults, and clear formats in descriptions ("ISO date
YYYY-MM-DD").

**Rule 3 — return the slice.** A raw CRM record can be 5,000 tokens; the model needs 5 fields.
Big tool results cost tokens on **every later iteration** (Ch 03) and push important context
into the middle (Ch 02). Offer a `detail: "summary" | "full"` option if needed.

**Rule 4 — errors are prompts.** The model reads your error and decides what to do next.

```
BAD:  "Error 404"
GOOD: "No order found with id 'A1043'. Order IDs look like 'A-1043' (with a dash).
       If the customer doesn't know the ID, call find_orders_by_email instead."
```

A good error turns a dead end into a correct next step. In practice, improving descriptions
and error messages can cut the number of iterations on the same task several-fold — measure
it on your own tasks.

**Rule 5 — no overlap.** `search_orders`, `find_order`, `lookup_order`, `get_order_details`
→ the model guesses. One tool with a clear contract is better.

### 3.6 More design patterns

| Pattern | Why |
|---|---|
| **Names: `verb_noun`, namespaced** (`crm_get_contact`, `kb_search`) | Clear, no collisions when tools come from many MCP servers |
| **Pagination**: return a page + "N more results; call again with page=2" | Never return 10K tokens at once |
| **Truncate large outputs** with a note ("…truncated, 340 more lines; use `grep` to narrow") | Protects the context window |
| **Return IDs** the model can use in follow-up calls | Enables multi-step work without guessing |
| **Separate read and write tools** | Reads can be auto-approved; writes need gates |
| **`dry_run=True` as the default on writes** | The model sees what *would* happen; a human/rule approves the real run |
| **Idempotency keys on writes** | A retried "create refund" doesn't refund twice (Ch 12) |
| **Timeouts on every tool** | One hanging API shouldn't hang the agent |
| **Validate arguments in code** | Never pass model output straight into SQL, shell or file paths (Ch 36) |

### 3.7 Too many tools

Every tool definition costs tokens on every call, and tool-choice accuracy drops as the list
grows (especially with similar tools). Options:

1. **Merge and prune** tools (rule 5).
2. **Tool search / deferred loading**: give the model a `search_tools(query)` tool; load full
   definitions only for the tools it finds. Some providers offer this natively (e.g.
   Anthropic's tool-search tool, where other tools are marked `defer_loading: true`).
3. **Route to specialists**: a router picks a sub-agent that has only 5–8 relevant tools
   (Ch 13, 25).
4. **Skills**: load task-specific instructions + tools only when needed (Ch 15).

Note the caching trade-off (Ch 12): changing the tool list per request breaks prompt-cache
reuse. Prefer a stable list, or a stable list plus deferred loading.

---

## 4. Code

### 4.1 A complete tool-calling loop

```python
# ch11_tools.py
import json
import ollama

ORDERS = {"A-1043": {"status": "shipped", "carrier": "DHL", "eta": "2026-10-15",
                     "items": ["running shoes"], "internal_notes": "VIP, warehouse 3"}}

def get_order(order_id: str) -> str:
    order = ORDERS.get(order_id)
    if order is None:
        return (f"No order found with id '{order_id}'. Order IDs look like 'A-1043'. "
                "Ask the customer to check their confirmation email.")
    useful = {k: order[k] for k in ("status", "carrier", "eta", "items")}   # rule 3: the slice
    return json.dumps(useful)

TOOLS = [{
    "type": "function",
    "function": {
        "name": "get_order",
        "description": ("Look up the status, carrier and delivery estimate of ONE order by its ID. "
                        "Use when the customer asks where their order is. Do not use for "
                        "general policy questions."),
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "string", "description": "Like 'A-1043'"}},
            "required": ["order_id"],
        },
    },
}]
REGISTRY = {"get_order": get_order}

def run(user_message, max_iterations=5):
    messages = [{"role": "user", "content": user_message}]
    for i in range(max_iterations):
        r = ollama.chat(model="llama3.2", messages=messages, tools=TOOLS,
                        options={"temperature": 0})
        msg = r["message"]
        if not msg.get("tool_calls"):
            return msg["content"], i + 1
        messages.append(msg)                              # the assistant's tool request
        for call in msg["tool_calls"]:
            name, args = call["function"]["name"], call["function"]["arguments"]
            fn = REGISTRY.get(name)
            result = fn(**args) if fn else f"Unknown tool '{name}'. Available: {list(REGISTRY)}"
            print(f"  tool {name}({args}) -> {result[:80]}")
            messages.append({"role": "tool", "tool_name": name, "content": result})
    return "Stopped: too many steps.", max_iterations

for q in ["Where is my order A-1043?", "Where is order A1043?", "What's your return policy?"]:
    answer, iterations = run(q)
    print(f"[{iterations} iterations] {q}\n  -> {answer}\n")
```

Watch the second question: the error message tells the model the right format, so it can
recover (or ask the customer) instead of inventing a status.

### 4.2 Parallel tool calls, run concurrently

```python
# ch11_parallel.py — execute several tool calls from one turn at the same time
import time
from concurrent.futures import ThreadPoolExecutor

def slow_lookup(order_id):
    time.sleep(1)                                   # pretend this is a 1-second API call
    return f"{order_id}: shipped"

calls = [{"function": {"name": "get_order", "arguments": {"order_id": oid}}}
         for oid in ["A-1", "A-2", "A-3"]]

start = time.perf_counter()
with ThreadPoolExecutor(max_workers=8) as pool:
    results = list(pool.map(lambda c: slow_lookup(**c["function"]["arguments"]), calls))
print(results, f"{time.perf_counter() - start:.1f}s")   # ~1s, not ~3s
```

(Results must go back in a way the model can match to its calls — by call ID or tool name +
order. Your client layer handles this.)

### 4.3 A safe write tool: dry_run by default + idempotency

```python
# ch11_write_tool.py
import uuid

REFUNDS = {}                     # idempotency_key -> refund record (pretend DB)

def create_refund(order_id: str, amount: float, reason: str,
                  dry_run: bool = True, idempotency_key: str | None = None) -> str:
    if amount <= 0 or amount > 500:
        return "Refund amount must be between 0 and 500. For larger refunds, call escalate_to_human."
    plan = f"Would refund {amount:.2f} for order {order_id} (reason: {reason})."
    if dry_run:
        return plan + " This was a DRY RUN. Ask the user to confirm, then call again with dry_run=false."
    if idempotency_key is None:
        return "idempotency_key is required when dry_run=false."
    if idempotency_key in REFUNDS:                          # retry-safe
        return f"Refund already created: {REFUNDS[idempotency_key]['id']} (no duplicate made)."
    REFUNDS[idempotency_key] = {"id": f"RF-{uuid.uuid4().hex[:6]}", "order": order_id, "amount": amount}
    return f"Refund created: {REFUNDS[idempotency_key]['id']}"

print(create_refund("A-1043", 49.99, "damaged"))
key = "A-1043-refund-1"
print(create_refund("A-1043", 49.99, "damaged", dry_run=False, idempotency_key=key))
print(create_refund("A-1043", 49.99, "damaged", dry_run=False, idempotency_key=key))  # retried
```

In production the idempotency key is generated by **your code** (e.g. from conversation ID +
action), not invented by the model, and the confirmation step is an approval gate (Ch 26, 35).

---

## 5. Production view

| Metric (per tool) | Why |
|---|---|
| Call count, error rate, latency p95 | Find broken or slow tools |
| **Invalid-argument rate** | Bad schema/description, or model hallucinating args |
| Result size in tokens | Rule 3 violations; context bloat |
| **Iterations per task** | Bad tools → more loops → more cost and latency (Ch 03) |
| Wrong-tool rate (from trajectory evals, Ch 33) | Overlapping or unclear tools |

**Contract tests** (Ch 33): assert that the schema the model sees matches what the function
accepts, and that **error messages are actionable** — they are prompts and deserve tests.

---

## 6. Common mistakes

- Thinking the model *executes* tools. It only *requests*; your code is responsible.
- One-word descriptions. The description is the prompt for tool choice.
- Returning whole database rows, full HTML pages, or 10K-line logs.
- Errors like `500 Internal Server Error` with no hint about what to do.
- Write tools without `dry_run`, approval, or idempotency.
- Passing model-chosen strings directly into SQL/shell/paths.
- Adding a new tool for every small variation instead of improving one tool.

---

## 7. Practice

**Level 1**
1. Run `ch11_tools.py`. Change the error message in `get_order` to just `"not found"`. Re-run
   the second question. What does the model do now?
2. Run `ch11_parallel.py` with `max_workers=1`. How long does it take? Why?

**Level 2**
3. Add `find_orders_by_email(email)` and `search_help(query)` tools with good descriptions.
   Write 10 test questions; record for each: tools called (in order), iterations, final answer
   correct? This is a mini **trajectory eval** (Ch 33).
4. Measure the **iteration delta**: run the 10 questions with bad descriptions/errors, then
   with good ones. Report mean iterations and accuracy for both.

**Level 3**
5. Implement **tool search**: 30 tool definitions (write short fake ones across billing,
   shipping, account, catalog); the model initially sees only `search_tools(query)` which
   returns the 3 best-matching tool names + descriptions (use embeddings from Ch 06); then you
   add those tools to the next call. Compare accuracy and tokens against sending all 30 tools.

---

## 8. Check yourself

1. Who executes a tool call — the model or your application?
2. State the five tool-design rules.
3. Why is returning a 5,000-token record from a tool expensive even if it's only used once?
4. What does `dry_run=True` by default protect against?
5. Why might you *not* want to change the tool list on every request?
6. When should several tool calls be run in parallel inside one agent, versus split into
   sub-agents?

<details>
<summary>Answers</summary>

1. Your application. The model only outputs a request (name + arguments).
2. Description says when and when not; few required fields with enums; return the useful
   slice; errors are recovery instructions; one good tool beats five overlapping ones.
3. The result stays in the message history and is re-sent on every later iteration (input
   tokens are quadratic, Ch 03); it also dilutes attention.
4. Accidental or injected destructive actions: the model must first see the plan, and a
   human or rule approves the real execution.
5. It breaks prompt-cache reuse (the tool definitions are part of the cached prefix) and
   fragments the cache into many rarely-reused entries.
6. Independent lookups that fit in one context → parallel tool calls in one agent. Split into
   sub-agents only when you need **isolation** (protect context, different permissions).

</details>

---

## 9. Key terms

**tool / function calling** · **tool definition** · **tool call** · **tool result** ·
**tool_choice** · **parallel tool calls** · **errors as prompts** · **pagination** ·
**dry_run** · **idempotency key** · **read vs write tools** · **tool search / deferred
loading** · **contract test** · **iteration count**

Next: [Chapter 12 — API reliability and caching →](12-api-reliability-and-caching.md)
