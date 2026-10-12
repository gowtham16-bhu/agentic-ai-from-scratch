# Chapter 34 — Observability

> You can't fix what you can't see. An agent run is dozens of model calls, tool calls, retries
> and decisions; **traces** turn that into a readable story, and **metrics** turn many stories
> into trends. "No traces" is "no logs" — the first thing a customer's on-call engineer will ask for.

**You will learn:** logs vs metrics vs traces; spans for model calls, tool calls and agent runs;
the **OpenTelemetry GenAI semantic conventions** (span names, `gen_ai.*` attributes — and their
"development" status); the extra fields every agent span needs (run, tenant, **model resolved**,
**prompt version**, config version, decision reason, cost, retries); cost metering; the **four core
dashboards**; SLOs and alerts; reading a trace **top-down**; sampling; privacy (PII in logs); and
the tools (Langfuse, Arize Phoenix, LangSmith, Datadog and others).

**Where this fits:** builds on the event stream idea (Ch 27), cost/latency (Ch 03), retries and
fallbacks (Ch 12), the agent loop (Ch 14) and gateways (Ch 32 — a natural place to emit spans).
Traces feed evals and the data flywheel (Ch 33), incident response (Ch 35), cost work (Ch 37) and
SLOs at scale (Ch 38).

> **Verified against:** the OpenTelemetry GenAI semantic conventions repository
> (`open-telemetry/semantic-conventions-genai`), whose GenAI documents are marked **Status:
> Development** as of October 2026 — names can still change. Code run with `opentelemetry-sdk` 1.45.

---

## 1. The idea in plain words

| Signal | What it is | Agent example | Answers |
|---|---|---|---|
| **Logs** | Timestamped events/messages | "tool get_order failed: timeout" | What happened at this moment? |
| **Metrics** | Numbers aggregated over time | p95 latency, cost/hour, error rate, fallback rate | Is the system healthy? Is it getting worse? |
| **Traces** | A tree of **spans** (timed operations) for one request, linked by a trace ID | `invoke_agent` → `chat` → `execute_tool` → `chat` | Why was *this* run slow, expensive or wrong? |

For agents, **traces are the primary debugging tool**: one user request becomes a tree of model calls,
tool calls and sub-agents, and you need to see the whole tree with inputs, outputs, tokens and timing.

---

## 2. Analogy

**A flight data recorder plus air-traffic statistics.** The recorder (trace) reconstructs exactly what
happened on one flight: every control input, reading and decision, in order. The statistics (metrics)
tell you whether flights in general are getting delayed or which aircraft type has more incidents. You
need both — and you read the recorder from takeoff, not from the crash.

---

## 3. How it works

### 3.1 The span tree of an agent run

```
invoke_agent support-agent                 [run_id, tenant, decision_reason, iterations, total cost]
├── chat llama3.2                          [model role + resolved model, tokens in/out, finish reason]
├── execute_tool get_order                 [tool name, call id, args (redacted), result size, error?]
├── chat llama3.2
├── invoke_agent refund-worker (sub-agent) [its own subtree: chats, tools]
└── chat llama3.2                          [final answer]
        trace context propagates across services: agent → gateway → MCP server (W3C traceparent)
```

### 3.2 OpenTelemetry GenAI semantic conventions

OpenTelemetry (OTel) is the vendor-neutral standard for traces/metrics/logs. Its **GenAI conventions**
standardize names so any backend understands agent telemetry:

| Span | Name format | Key attributes |
|---|---|---|
| Model call | `{gen_ai.operation.name} {gen_ai.request.model}` e.g. `chat llama3.2` | `gen_ai.operation.name` (`chat`, `embeddings`, `generate_content`…), `gen_ai.provider.name`, `gen_ai.request.model`, `gen_ai.response.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `gen_ai.response.finish_reasons`, `gen_ai.conversation.id` |
| Tool call | `execute_tool {gen_ai.tool.name}` | `gen_ai.tool.name`, `gen_ai.tool.call.id`, `gen_ai.tool.type` |
| Agent | `invoke_agent {gen_ai.agent.name}` (also `create_agent`) | `gen_ai.agent.name`, `gen_ai.agent.id`, `gen_ai.agent.version` |
| Others | well-known operations include `retrieval`, `invoke_workflow`, `plan`, memory operations (`search_memory`, `create_memory`…) | |

Token detail attributes include `gen_ai.usage.cache_read.input_tokens`,
`gen_ai.usage.cache_write.input_tokens` and `gen_ai.usage.reasoning.output_tokens` — so you can track
prompt-cache hit rate (Ch 12) and thinking-token spend (Ch 24) per span. Message content
(`gen_ai.input.messages`, `gen_ai.output.messages`) is **opt-in** because it may contain sensitive data.
There are also conventions for MCP spans. Because the status is *Development*, pin the conventions
version you emit and expect renames (older code used `gen_ai.system` where newer uses
`gen_ai.provider.name`).

### 3.3 The fields people forget

Standard attributes aren't enough to debug agents. Add your own (namespaced, e.g. `app.*`):

```
run_id · trace_id · tenant_id · user/actor (pseudonymous) · agent_path (parent→child agents)
model_role AND model_id_resolved · prompt_version · config_version · decision_reason (why this route/tool)
tokens (in/out/cached/reasoning) · cost_usd · retries · fallback_used · iteration number · budget remaining
```

> `model_id_resolved` and `prompt_version` are the two people forget. "It worked last week" is almost
> always one of those two changing.

**Put identifiers in attributes, not inside log message strings.** `tenant_id` buried in a message text
can't be filtered, aggregated or protected — and makes cross-tenant data mistakes harder to detect.

### 3.4 Read the trace top-down

The root cause is usually a **routing or configuration decision near the top** (wrong route, wrong model
resolved, missing context, wrong prompt version), not the error at the bottom. Read from the root span
down: what was decided, with which inputs, and only then the failing leaf.

### 3.5 The four core dashboards

| Dashboard | Shape to watch | Usually means |
|---|---|---|
| **Cost outliers** (top runs by cost, p99 cost) | A few runs 10–100× the median | Loops, giant tool outputs, retry storms |
| **Iteration histogram** | **Bimodal**: most runs at 3–5, a bump at the cap | A loop/stuck-agent bug for some inputs (Ch 14) |
| **Fallback rate** (per provider/alias) | Rising | A provider degrading — act before it fails |
| **Human override rate** | Rising | Quality regression your offline evals missed (Ch 33) |

Plus the standard ones: request rate, error rate, p50/p95/p99 latency (TTFT and total), tokens and cost
per tenant, cache hit ratio, tool error rates.

### 3.6 SLOs and alerts

Define **SLOs** (service level objectives) for what users feel: e.g. "99% of support answers in < 8 s",
"95% task success on weekly sampled evals", "fallback rate < 5%". Alert on **SLO burn rate** (how fast
you're using the error budget), not on every blip. Page humans for user-facing breakage; ticket the rest.

### 3.7 Sampling and cost of telemetry

Agent traces are big (prompts, tool outputs). Typical policy:
- Keep **100% of metadata** (span names, timings, tokens, cost, IDs) — cheap and needed for dashboards.
- **Sample content** (prompts/outputs), but **always keep** errors, high-cost runs, low-score runs,
  negative feedback and runs flagged by guardrails (**tail-based sampling**).
- Set retention by data class; content logs often need shorter retention.

### 3.8 Privacy and security of telemetry

- **Redact PII** before export (gateway, Ch 32); opt-in content capture; separate access control for raw
  content.
- Telemetry is a **data store**: tenant isolation, encryption, retention and deletion requests (Ch 16) apply.
- Never put secrets in span attributes.

### 3.9 Tools

LLM-focused tracing platforms (often OTel-compatible): **Langfuse** (open source, self-hostable;
traces, prompt management, evals), **Arize Phoenix** (open source; OpenInference instrumentation),
**LangSmith** (LangChain ecosystem), **Braintrust**, **Helicone**; plus general APM vendors (Datadog,
New Relic, Grafana, Honeycomb…) that ingest OTel GenAI spans. Pick one that accepts **OTel** so you're not
locked into a vendor's SDK.

---

## 4. Code

```bash
pip install opentelemetry-sdk        # + an OTLP exporter to send to your backend
```

### 4.1 Spans with GenAI convention names

```python
# tracing.py — OpenTelemetry spans for an agent run using GenAI semantic-convention names
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

exporter = InMemorySpanExporter()                 # production: OTLP exporter -> Langfuse/Phoenix/Datadog/...
provider = TracerProvider()
provider.add_span_processor(SimpleSpanProcessor(exporter))
trace.set_tracer_provider(provider)
tracer = trace.get_tracer("support-agent")

APP = {"app.tenant_id": "acme", "app.prompt_version": "support_answer@v3", "app.config_version": "2026-10-12.1"}

def traced_llm_call(model_role, model_resolved, messages, conversation_id):
    with tracer.start_as_current_span(f"chat {model_resolved}") as span:      # "{operation} {model}"
        span.set_attributes({"gen_ai.operation.name": "chat", "gen_ai.provider.name": "ollama",
                             "gen_ai.request.model": model_resolved, "gen_ai.conversation.id": conversation_id,
                             "app.model_role": model_role, **APP})
        reply, tokens_in, tokens_out = "calling get_order", 812, 41          # pretend model call
        span.set_attributes({"gen_ai.response.model": model_resolved, "gen_ai.usage.input_tokens": tokens_in,
                             "gen_ai.usage.output_tokens": tokens_out,
                             "gen_ai.response.finish_reasons": ["tool_calls"], "app.cost_usd": 0.0})
        return reply

def traced_tool(name, call_id, args):
    with tracer.start_as_current_span(f"execute_tool {name}") as span:
        span.set_attributes({"gen_ai.operation.name": "execute_tool", "gen_ai.tool.name": name,
                             "gen_ai.tool.call.id": call_id, **APP})
        try:
            return {"status": "shipped"}
        except Exception as e:                                               # record errors on the span
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            raise

def run_agent(run_id, question):
    with tracer.start_as_current_span("invoke_agent support-agent") as span:
        span.set_attributes({"gen_ai.operation.name": "invoke_agent", "gen_ai.agent.name": "support-agent",
                             "gen_ai.conversation.id": run_id, "app.run_id": run_id,
                             "app.decision_reason": "route=order_status", **APP})
        traced_llm_call("fast", "llama3.2", [{"role": "user", "content": question}], run_id)
        traced_tool("get_order", "call_1", {"order_id": "A-1043"})
        traced_llm_call("fast", "llama3.2", [], run_id)
        span.set_attribute("app.iterations", 2)

if __name__ == "__main__":
    run_agent("run-7f3a", "Where is A-1043?")
    for s in exporter.get_finished_spans():
        parent = s.parent.span_id if s.parent else None
        print(f"{s.name:28s} trace={s.context.trace_id:032x}"[:70], "parent" if parent else "ROOT",
              {k: v for k, v in s.attributes.items() if k.startswith(("gen_ai.usage", "gen_ai.tool.name", "app.run_id"))})
```

Verified output (trace ID shortened):

```
chat llama3.2                trace=5558e60d... parent {'gen_ai.usage.input_tokens': 812, 'gen_ai.usage.output_tokens': 41}
execute_tool get_order       trace=5558e60d... parent {'gen_ai.tool.name': 'get_order'}
chat llama3.2                trace=5558e60d... parent {...}
invoke_agent support-agent   trace=5558e60d... ROOT   {'app.run_id': 'run-7f3a'}
```

All four spans share one trace ID; the agent span is the root. To ship them, swap the in-memory exporter
for an **OTLP exporter** pointed at your backend (e.g. a self-hosted Langfuse or Phoenix).

### 4.2 The four dashboards from run records

```python
# dashboards.py — the four core agent dashboards, computed from run records (offline)
import random
import statistics
from collections import Counter

rng = random.Random(7)
runs = []                                   # one record per agent run, derived from root spans
for i in range(500):
    looping = rng.random() < 0.06           # a hidden loop bug in 6% of runs
    iterations = 12 if looping else rng.choice([2, 3, 3, 3, 4, 4, 5])
    runs.append({"run_id": f"r{i}", "iterations": iterations,
                 "cost_usd": iterations * rng.uniform(0.002, 0.004) + (0.4 if rng.random() < 0.01 else 0),
                 "fallback": rng.random() < (0.02 if i < 400 else 0.15),     # a provider degrading recently
                 "human_override": rng.random() < 0.08})

print("1) ITERATIONS PER TASK (histogram) — a bump at the cap = loop bug in the tail")
for it, n in sorted(Counter(r["iterations"] for r in runs).items()):
    print(f"   {it:2d} | {'#' * (n // 5)} {n}")

costs = sorted(r["cost_usd"] for r in runs)
p99 = costs[int(0.99 * len(costs))]
print(f"\n2) COST OUTLIERS — p50 ${statistics.median(costs):.4f}, p99 ${p99:.4f}; runs above p99:",
      [r["run_id"] for r in runs if r["cost_usd"] > p99])

early, recent = runs[:400], runs[400:]
rate = lambda rs: sum(r["fallback"] for r in rs) / len(rs)
print(f"\n3) FALLBACK RATE — earlier {rate(early):.1%}, last 100 runs {rate(recent):.1%}  -> alert if rising")

print(f"\n4) HUMAN OVERRIDE RATE — {sum(r['human_override'] for r in runs) / len(runs):.1%} of outputs edited/rejected")
```

Verified output:

```
1) ITERATIONS PER TASK (histogram) — a bump at the cap = loop bug in the tail
    2 | ############ 63
    3 | ######################################### 205
    4 | ########################## 131
    5 | ############## 71
   12 | ###### 30
2) COST OUTLIERS — p50 $0.0101, p99 $0.0472; runs above p99: ['r41', 'r279', 'r289', 'r376']
3) FALLBACK RATE — earlier 1.8%, last 100 runs 16.0%  -> alert if rising
4) HUMAN OVERRIDE RATE — 9.0% of outputs edited/rejected
```

The bump at 12 iterations is exactly the "bimodal histogram" signal of a loop bug; the fallback jump is a
degrading provider you can act on before it becomes an outage.

---

## 5. Production view

| Practice | Why |
|---|---|
| Instrument at the **event stream / gateway** once (Ch 27, 32) | Consistent spans for every agent, no per-team drift |
| Propagate trace context through MCP (`_meta`) and A2A calls | One trace across agents, tools and services |
| Link traces to eval results and user feedback by `run_id` | The data flywheel (Ch 33) |
| Version everything you log (`prompt_version`, `config_version`, conventions version) | Explain behaviour changes |
| Cost per tenant and per feature from spans | FinOps and pricing (Ch 37) |
| Runbooks link dashboards → traces → fixes | Faster incident response (Ch 35) |

---

## 6. Common mistakes

- Logging only final answers (no intermediate tool calls or decisions).
- No `model_id_resolved` / `prompt_version` → can't explain regressions.
- IDs inside log message strings instead of attributes.
- Capturing full prompts with PII into a broadly-accessible log store.
- Head-based random sampling that throws away the rare failures you need.
- Reading traces bottom-up from the stack trace.
- A proprietary tracing SDK everywhere with no OTel export.

---

## 7. Practice

**Level 1**
1. Run `tracing.py`. Add a third `chat` span that hits a fallback model and record `app.fallback_used=True`
   and `app.retries=1`.
2. Run `dashboards.py`. Change the loop rate to 0.15 — how does the histogram change?

**Level 2**
3. Instrument the Ch 14 agent with spans (agent → each LLM call → each tool call) using these conventions, and
   export to a self-hosted Langfuse or Phoenix (Docker). Find the slowest span in a 5-step run.
4. Add tail-based sampling logic: keep content for runs with errors, cost > p99, iterations ≥ cap, or negative
   feedback; keep only metadata for the rest.

**Level 3**
5. Propagate trace context from your agent through the MCP gateway (Ch 32) into the MCP server (Ch 29) using
   W3C `traceparent` in the request `_meta`, so a single trace shows agent → gateway → server spans. Then
   simulate a slow tool and find it in the trace in under a minute.

---

## 8. Check yourself

1. Logs vs metrics vs traces — what does each answer best?
2. What's the span name format for a model call and for a tool call in the GenAI conventions?
3. Which two fields do teams most often forget, and why do they matter?
4. Why read traces top-down?
5. Name the four core agent dashboards and what a bad shape means for each.
6. What should tail-based sampling always keep?

<details>
<summary>Answers</summary>

1. Logs: what happened at a moment. Metrics: health and trends over time. Traces: the full causal path and
   timing of one request.
2. Model call: `{operation} {model}`, e.g. `chat llama3.2`. Tool call: `execute_tool {tool name}`.
3. `model_id_resolved` and `prompt_version`; most "it worked last week" regressions come from a model or
   prompt change, and without these fields you can't see it.
4. Root causes are usually early decisions (routing, config, context) — the error at the bottom is often a
   symptom.
5. Cost outliers (loops, huge tool outputs, retry storms); iteration histogram (bimodal = loop bug);
   fallback rate (rising = provider degrading); human override rate (rising = quality regression).
6. Errors, high-cost runs, runs hitting iteration caps, low eval/judge scores, negative feedback and
   guardrail-flagged runs.

</details>

---

## 9. Key terms

**observability** · **logs / metrics / traces** · **span** · **trace ID** · **OpenTelemetry (OTel)** ·
**GenAI semantic conventions** · **gen_ai.operation.name / provider.name / request.model** ·
**gen_ai.usage.* tokens** · **invoke_agent / execute_tool spans** · **model_id_resolved** ·
**prompt_version** · **top-down trace reading** · **four core dashboards** · **SLO / error budget / burn
rate** · **tail-based sampling** · **OTLP exporter** · **W3C trace context**

Next: [Part 8 — Chapter 35: Guardrails and safety →](../part8-production/35-guardrails-and-safety.md)
