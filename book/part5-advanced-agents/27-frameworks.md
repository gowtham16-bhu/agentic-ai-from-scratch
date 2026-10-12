# Chapter 27 — Frameworks

> Frameworks package the loop, tools, state, multi-agent patterns and tracing you've built by
> hand. Because you built them by hand first, a framework is now **a helper for what you
> already understand**, not magic — and you can judge which one fits, and how to avoid being
> locked in.

**You will learn:** what every agent framework is underneath (a small "universal runtime"),
the current landscape (LangGraph, OpenAI Agents SDK, Claude Agent SDK, Google ADK, Microsoft
Agent Framework, CrewAI, Pydantic AI, LlamaIndex, smolagents, DSPy, Haystack, Strands and
others), build-vs-buy, a framework evaluation checklist, and how to stay portable.

**Where this fits:** everything in Parts 2–5 is what frameworks implement: tool calling (Ch 11),
the loop (Ch 14), context and memory (Ch 15–16), RAG (Ch 17–23), planning (Ch 24), multi-agent
(Ch 25), state and HITL (Ch 26). Protocol support (MCP Ch 29, A2A Ch 30), gateways (Ch 32) and
tracing (Ch 34) are key selection criteria.

---

## 1. The idea in plain words

An agent framework gives you, in some combination:

| Capability | You built it in |
|---|---|
| Model abstraction (many providers) | Ch 12 `llm.py` |
| Tools from plain functions (schemas from type hints/docstrings) | Ch 11 |
| The agent loop with stop conditions | Ch 14 |
| Structured output | Ch 10 |
| Memory / sessions | Ch 16 |
| Workflows, graphs, state, reducers, checkpoints, interrupts | Ch 13, 26 |
| Multi-agent: handoffs, sub-agents, agents-as-tools | Ch 25 |
| Guardrails hooks | Ch 35 |
| Streaming + tracing integrations | Ch 12, 34 |
| Deployment helpers | Ch 38 |

Frameworks differ in **how much control** they give you (low-level graph vs high-level "crew"),
**which ecosystem** they're tied to, and **what they optimize for** (data/RAG, coding agents,
enterprise, type safety, quick prototypes).

---

## 2. Analogy

**Web frameworks.** Once you understand HTTP, routing, sessions and databases, Django, FastAPI or
Spring are productivity tools, and you can debug them because you know what they do underneath.
Developers who only know the framework are stuck when it misbehaves. Same with agent frameworks.

---

## 3. How it works

### 3.1 What every framework is underneath: a universal runtime

Strip away branding and most frameworks share this core:

```
Executable (anything that can run):
    execute(context) -> stream of EVENTS        # model tokens, tool calls, results, state updates, errors
    as_tool() -> Tool                           # ANY executable can be used as a tool by another

Primitives:
    LlmAgent    — the only non-deterministic one (model + tools + loop)
    Sequential  — run children in order
    Parallel    — run children at the same time
    Loop        — repeat until a condition
    Router      — choose a child
```

`as_tool()` is the entire composability story: an agent, a workflow, or a whole multi-agent team
can be a tool for another agent.

Two design decisions worth arguing about:
1. **Children get empty state, not a copy** — anything they need is passed explicitly. Visible data
   flow, no context bloat, and it's the isolation boundary (Ch 25).
2. **Budget is shared by reference** — one budget object for the whole tree (Ch 25).

**The event stream is the highest-leverage decision.** Build it once and UI streaming, tracing,
cost metering, checkpointing, eval capture and safety monitors all read from the same stream.
Frameworks that bolt observability on afterwards never fully recover.

**Never hardcode a model ID** inside agents: reference a role (Ch 08), resolved by config or a
gateway (Ch 32).

### 3.2 The landscape (October 2026 — check current docs; this space moves monthly)

| Framework | Style / focus | Good for |
|---|---|---|
| **LangGraph** (LangChain ecosystem) | Low-level **graphs/state machines**: state, reducers, checkpointers, interrupts, time travel, `Send` fan-out; v1.x stable | Production agents needing explicit control flow, durability and HITL (Ch 26) |
| **OpenAI Agents SDK** | Lightweight primitives: agents, tools, **handoffs**, guardrails, sessions, built-in tracing | Quick multi-agent apps, especially on OpenAI models |
| **Claude Agent SDK** | The Claude Code agent harness as a library: built-in file/bash/search tools, subagents, hooks, permissions, MCP | Coding and filesystem/automation agents you host yourself |
| **Google ADK** (Agent Development Kit) | Agents + workflow agents (sequential, parallel, loop), multi-agent, evaluation, deployment to Google Cloud; A2A support | Google Cloud / Gemini-centric teams; multi-agent systems |
| **Microsoft Agent Framework** | Successor that merges **AutoGen** and **Semantic Kernel** ideas: agents, workflows, multi-agent; Python and .NET | Microsoft/Azure enterprises (AutoGen itself is now mostly in maintenance) |
| **CrewAI** | High-level **role-based crews** (agents with roles/goals) plus flows | Fast multi-agent prototypes; business-process automation |
| **Pydantic AI** | **Type-safe** agents: Pydantic-validated outputs, dependency injection, graphs | Python teams who want typed, testable agents |
| **LlamaIndex** | **Data/RAG** framework: connectors, indexing, retrieval, workflows, agents | RAG-heavy applications (Part 4) |
| **Haystack** | Composable **pipelines** for search/RAG in production | Search and RAG pipelines with clear components |
| **smolagents** (Hugging Face) | Minimal; **code agents** that write Python to call tools | Learning, research, code-as-action agents |
| **DSPy** | "Programming, not prompting": signatures + **optimizers** that tune prompts/examples against a metric | Pipelines with good eval sets (Ch 09, 33) |
| **Strands Agents** (AWS), **Agno**, others | Model-driven agent loops with tools and integrations | Teams in those ecosystems |
| **Mastra**, **Vercel AI SDK** (TypeScript) | Agents and AI features for TypeScript/Node apps | JS/TS stacks |
| **LiteLLM** (not an agent framework) | One API for 100+ model providers; proxy/gateway | The model-access layer under any framework (Ch 32) |

Hosted "managed agents" products (the provider runs the loop and a sandbox for you) are another
option when you don't want to host the runtime.

### 3.3 Build vs buy

| Go raw / thin (your own loop) | Use a framework |
|---|---|
| Simple single-agent tools loop | Durable state, checkpoints, HITL across days |
| You need full control of every token and request | Multi-agent patterns you'd otherwise rebuild |
| Few dependencies; strict security review | Team productivity, shared conventions |
| Unusual runtime (edge, embedded) | Ecosystem integrations (tracing, evals, connectors) |
| Learning (this book's Parts 2–4) | You'd otherwise re-implement the framework badly |

A common, healthy pattern: **thin custom loop for simple agents, LangGraph-style graphs for the
complex durable ones, a gateway underneath both.**

### 3.4 Framework evaluation checklist

```
□ Maturity: release cadence, breaking-change history, stable 1.x API?
□ Control: can I see/override prompts, the loop, tool-call handling, retries?
□ State: typed state, checkpointing to a real DB, resume, time travel?
□ HITL: interrupts/approvals with durable waits?
□ Observability: OpenTelemetry/trace export; token and cost metering (Ch 34)?
□ Models: multi-provider, roles, fallbacks — or locked to one vendor?
□ Protocols: MCP client/server support (Ch 29)? A2A (Ch 30)?
□ Testing: can I unit-test nodes/tools and replay recorded runs (Ch 33)?
□ Deployment: how does it run in my infra (containers, serverless, managed)?
□ Security: tool permissions, sandboxing hooks, secrets handling (Ch 36)?
□ License, community, docs, commercial support
□ Exit cost: how hard to move off it in a year?
```

### 3.5 Staying portable (avoid lock-in)

- **Tools are plain functions** with your own schemas/docstrings; wrap them per framework.
- **Prompts live in your prompt registry** (Ch 31), not scattered in framework config.
- **Your eval harness is framework-independent** (Ch 33): same cases, any implementation.
- **Model access through your gateway/roles** (Ch 32), not hardcoded per framework.
- **You own the state schema and the trace format** (OTel, Ch 34).
- Put the framework behind a thin interface (`run_agent(task) -> result + events`).

---

## 4. Code

### 4.1 A tiny universal runtime (runs offline with a fake model)

```python
# runtime.py — the core shared by most frameworks: executables, events, as_tool, shared budget
import asyncio
from dataclasses import dataclass, field

@dataclass
class Event:
    source: str
    kind: str            # "start" | "llm" | "tool" | "result" | "error"
    data: dict = field(default_factory=dict)

@dataclass
class Budget:            # shared BY REFERENCE across the whole tree
    max_tokens: int
    used: int = 0

@dataclass
class Context:
    input: str
    budget: Budget
    events: list = field(default_factory=list)       # one stream for UI, tracing, metering, evals

    def emit(self, source, kind, **data):
        self.events.append(Event(source, kind, data))

class Executable:
    name = "executable"
    async def execute(self, ctx: Context) -> str:
        raise NotImplementedError
    def as_tool(self):
        async def tool(arg: str, parent: Context):
            child = Context(input=arg, budget=parent.budget, events=parent.events)  # empty state, shared budget
            return await self.execute(child)
        return self.name, tool

class LlmAgent(Executable):
    def __init__(self, name, llm, tools=()):
        self.name, self.llm, self.tools = name, llm, dict(t.as_tool() for t in tools)
    async def execute(self, ctx):
        ctx.emit(self.name, "start", input=ctx.input)
        decision, tokens = await self.llm(ctx.input, list(self.tools))
        ctx.budget.used += tokens
        ctx.emit(self.name, "llm", tokens=tokens, decision=decision)
        if ctx.budget.used > ctx.budget.max_tokens:
            ctx.emit(self.name, "error", reason="budget exhausted")
            return "stopped: budget exhausted"
        if decision.get("tool"):
            result = await self.tools[decision["tool"]](decision["arg"], ctx)
            ctx.emit(self.name, "tool", tool=decision["tool"], result=result)
            return f"{self.name} used {decision['tool']}: {result}"
        return decision["answer"]

class Sequential(Executable):
    def __init__(self, name, children):
        self.name, self.children = name, children
    async def execute(self, ctx):
        out = ctx.input
        for child in self.children:
            out = await child.execute(Context(out, ctx.budget, ctx.events))
        return out

class Parallel(Executable):
    def __init__(self, name, children):
        self.name, self.children = name, children
    async def execute(self, ctx):
        results = await asyncio.gather(*(c.execute(Context(ctx.input, ctx.budget, ctx.events))
                                         for c in self.children))
        return " | ".join(results)

async def fake_llm(prompt, tool_names):        # stands in for a real model call
    if tool_names and "research" in prompt:
        return {"tool": tool_names[0], "arg": prompt}, 120
    return {"answer": f"answer({prompt[:30]})"}, 80

if __name__ == "__main__":
    researcher = LlmAgent("researcher", fake_llm)
    lead = LlmAgent("lead", fake_llm, tools=[Parallel("team", [researcher, LlmAgent("checker", fake_llm)])])
    ctx = Context("research shoe market in Sri Lanka", Budget(max_tokens=1000))
    print(asyncio.run(lead.execute(ctx)))
    for e in ctx.events:
        print(f"{e.source:10s} {e.kind:6s} {e.data}")
    print("budget used:", ctx.budget.used)
```

Look at what you get for free from the event list: a trace, a cost meter, and eval data — all from
one stream.

### 4.2 Keep tools portable

```python
# portable_tools.py — one plain function, adapted to any framework
def get_order(order_id: str) -> str:
    """Look up shipping status for ONE order ID like 'A-1043'. Use for 'where is my order' questions."""
    return f"Order {order_id}: shipped (lookup complete)"

def to_openai_style(fn):
    import inspect
    params = {name: {"type": "string"} for name in inspect.signature(fn).parameters}
    return {"type": "function", "function": {"name": fn.__name__, "description": inspect.getdoc(fn),
            "parameters": {"type": "object", "properties": params, "required": list(params)}}}

def to_anthropic_style(fn):
    spec = to_openai_style(fn)["function"]
    return {"name": spec["name"], "description": spec["description"], "input_schema": spec["parameters"]}

print(to_openai_style(get_order))
print(to_anthropic_style(get_order))
```

Most frameworks also accept plain functions directly and build the schema from type hints and the
docstring — which is exactly why writing good docstrings (Ch 11) pays off everywhere.

---

## 5. Production view

| Risk | Mitigation |
|---|---|
| Breaking changes on upgrade | Pin versions; upgrade behind your eval suite (Ch 33) |
| Hidden prompts/behaviour inside the framework | Read the source; log the final requests; override defaults |
| Framework-specific tracing only | Export OpenTelemetry to your own backend (Ch 34) |
| Vendor lock-in | Portable tools, prompts, evals, gateway; thin adapter layer |
| Abandoned projects | Prefer active, well-funded projects; check release cadence (e.g. PyPI dates) |
| Abstraction leaks under load | Load-test the framework path, not just your code (Ch 38) |

---

## 6. Common mistakes

- Choosing a framework before writing the eval set.
- Using a high-level multi-agent framework for a single-call problem.
- Not reading what prompts the framework sends.
- Mixing three frameworks in one service.
- Framework-specific tools that can't be reused elsewhere.
- Believing a framework makes an agent "production-ready" — evals, security, tracing and ops are
  still your job.

---

## 7. Practice

**Level 1**
1. Run `runtime.py`. Lower the budget to 150. Which events show the stop?
2. Run `portable_tools.py`. Add an `order_count: int` parameter and make the converter emit
   `"integer"` for it (hint: inspect annotations).

**Level 2**
3. Build the same small support agent (two tools: `get_order`, `search_policies`) in **two**
   frameworks of your choice, using their quickstarts. Run the same 10 eval cases. Compare: lines of
   code, accuracy, tokens, how easy it was to see the actual prompts and to add an approval step.

**Level 3**
4. Write a one-page **framework decision record** (ADR) for a fictional customer: requirements
   (durability, HITL, Azure-only, Python, MCP needed), options considered, evaluation against the
   3.4 checklist, decision, and exit plan.

---

## 8. Check yourself

1. What does `as_tool()` give you, and why is it powerful?
2. Why is the event stream "the highest-leverage decision" in a runtime?
3. Name three situations where you'd skip a framework.
4. Give four items from the framework evaluation checklist.
5. List four practices that keep you portable across frameworks.

<details>
<summary>Answers</summary>

1. Any executable (agent, workflow, team) can be used as a tool by another agent — composition
   without special cases.
2. Streaming UI, tracing, cost metering, checkpointing, eval capture and safety monitoring can all be
   built on one stream instead of separate, inconsistent mechanisms.
3. A simple single-agent loop; need for full control over requests/tokens or minimal dependencies;
   unusual runtimes; learning the mechanics.
4. Any four: maturity/stability; control over prompts and loop; state/checkpointing; HITL;
   observability/OTel; multi-provider models; MCP/A2A support; testability; deployment; security;
   license/community; exit cost.
5. Plain-function tools; prompts in your own registry; framework-independent evals; model access via
   gateway/roles; own state schema and trace format; thin adapter interface.

</details>

---

## 9. Key terms

**agent framework** · **universal runtime** · **executable** · **as_tool / composability** ·
**event stream** · **LangGraph** · **OpenAI Agents SDK** · **Claude Agent SDK** · **Google ADK** ·
**Microsoft Agent Framework** · **CrewAI** · **Pydantic AI** · **LlamaIndex** · **Haystack** ·
**smolagents** · **DSPy** · **build vs buy** · **lock-in** · **ADR (architecture decision record)**

Next: [Part 6 — Chapter 28: Specs and standards map →](../part6-platform/28-specs-and-standards.md)
