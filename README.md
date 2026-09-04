# Agentic AI From Scratch

A hands-on, zero-to-multi-agent build log — no framework, no black box. Every
concept (the tool-calling loop, orchestration, isolation, memory, MCP) is
implemented from first principles in plain Python against a **local LLM**
(Ollama + `llama3.2`), then progressively hardened toward something closer to
production shape.

This isn't a tutorial copy-paste — it's a real, working multi-agent system
with a documented failure mode, a small eval suite, and an honest "what's
deliberately not here yet" list. See [`agent-learning/CAPSTONE.md`](agent-learning/CAPSTONE.md)
for the full write-up.

## Why this exists

Most agent frameworks (LangChain, LangGraph, CrewAI...) hide the actual
mechanics behind abstractions. Before reaching for those, this project builds
the underlying primitives by hand once, so the framework layer later reads as
"a helper for what I already understand," not magic:

- the raw LLM tool-calling loop
- why tool *descriptions* (not just names) drive correct behavior
- context engineering — feeding an agent only what it needs, not everything
- orchestrator/worker isolation — routing to specialized sub-agents with
  disjoint context and tools
- per-worker episodic memory (file-based, no vector DB — deliberately, since
  a vector DB is unjustified overhead at this data scale)
- production-adjacent hardening: tracing, a kill switch, bounded retries
- the Model Context Protocol (MCP) — both **stdio** (local subprocess) and
  **HTTP/SSE** (networked) transports, built from the official SDK, not just
  described

## Concepts covered

| Concept | Where |
|---|---|
| LLM without tools (baseline, shows confidently wrong arithmetic) | [`step0_no_tool.py`](agent-learning/step0_no_tool.py) |
| The tool-calling loop, `max_iterations` guard | [`step1_loop.py`](agent-learning/step1_loop.py) |
| Tool design: safe `ast`-based eval (no `eval()`), actionable error messages | [`step2_tool_design.py`](agent-learning/step2_tool_design.py) |
| Why tool descriptions matter more than tool names under ambiguity | [`step2_broken_ids.py`](agent-learning/step2_broken_ids.py) |
| Context engineering — orchestrator selects a relevant slice instead of dumping everything | [`step3_context_slice.py`](agent-learning/step3_context_slice.py) |
| Multi-agent orchestrator + 2 isolated workers, "fake tool" pattern for structured routing output | [`step4_orchestrator.py`](agent-learning/step4_orchestrator.py) |
| Eval suite — routing correctness + answer correctness, catches silent misrouting | [`step5_eval.py`](agent-learning/step5_eval.py) |
| Hardening: JSONL tracing, file-based kill switch, bounded routing retries | [`step6_hardened.py`](agent-learning/step6_hardened.py) |
| Per-worker episodic memory, and why naive memory injection corrupts routing decisions | [`step7_memory.py`](agent-learning/step7_memory.py) |
| MCP server + client over stdio (local subprocess) | [`mcp_calculator_server.py`](agent-learning/mcp_calculator_server.py), [`mcp_client_test.py`](agent-learning/mcp_client_test.py) |
| MCP server + client over HTTP/SSE (networked) | [`mcp_http_server.py`](agent-learning/mcp_http_server.py), [`mcp_http_client_test.py`](agent-learning/mcp_http_client_test.py) |

Full narrative log of what was built, what broke, and what was learned from
each break: [`agent-learning/PROGRESS.md`](agent-learning/PROGRESS.md).

## Architecture (capstone)

```
question -> orchestrator (routes via a structured "fake tool" call, not free text)
              -> math_worker    (isolated: only has a calculator tool, own context)
              -> writing_worker (isolated: no tools, prose only, own context)
```

Isolation here means **context/memory isolation**, not concurrency —
workers run one at a time, sequentially. Each worker only ever sees its own
tools and its own memory file; a routing mistake shows up as a visibly wrong
worker instead of being buried inside one agent's long, tool-cluttered
reasoning trace.

**Known, documented failure mode:** the local model occasionally skips the
routing tool call and answers directly. Mitigated with a bounded retry
(`max_routing_attempts=2`); if both attempts fail, the system fails loudly
with an explicit error instead of silently returning an unrouted answer.

## Setup

Requires Python 3.10+ and [Ollama](https://ollama.com) running locally.

```bash
# 1. Install and start Ollama, then pull the model used throughout
ollama pull llama3.2

# 2. Clone and set up the virtualenv
git clone https://github.com/<your-username>/agentic-ai-from-scratch.git
cd agentic-ai-from-scratch/agent-learning
python3 -m venv venv
source venv/bin/activate
pip install ollama mcp
```

## Running the examples

Each file is runnable standalone and prints its own output:

```bash
python step0_no_tool.py        # baseline: LLM gets arithmetic wrong without a tool
python step1_loop.py           # tool-calling loop fixes it
python step2_tool_design.py    # safer tool + better errors
python step4_orchestrator.py   # full orchestrator + isolated workers
python step5_eval.py           # eval suite: routing + answer correctness
python step6_hardened.py       # adds tracing (traces.jsonl) + kill switch
python step7_memory.py         # per-worker memory across runs
```

Try the kill switch:

```bash
touch agent-learning/STOP
python step6_hardened.py       # refuses to run, no wasted model call
rm agent-learning/STOP
```

MCP examples need the server running in one terminal and the client in
another:

```bash
# stdio transport (client spawns the server itself, no separate step needed)
python mcp_client_test.py

# HTTP/SSE transport (server must be started first, separately)
python mcp_http_server.py &
python mcp_http_client_test.py
```

## What's deliberately not here

This is a learning build with an honest scope boundary, not an oversight:

- No concurrency/parallel subagent execution — workers run sequentially by
  design; parallel fan-out + a synthesizer/aggregator step is a real,
  tracked next step (planned alongside LangGraph, which has native
  primitives for it)
- No vector DB / RAG — memory is small enough that file-based episodic notes
  are sufficient; adding a vector store here would be unjustified complexity
- No LLM-as-judge grading — writing-worker output is checked for
  non-emptiness only, not quality
- No real observability stack (OpenTelemetry, dashboards, cost tracking) —
  tracing here is a JSONL file, intentionally simplified to teach the
  concept first
- No MCP gateway (multiple MCP servers behind one aggregator) — a real,
  named pattern, understood conceptually, deferred until a single-server
  understanding was solid

See [`agent-learning/CAPSTONE.md`](agent-learning/CAPSTONE.md) for the full
rationale behind each of these calls.
