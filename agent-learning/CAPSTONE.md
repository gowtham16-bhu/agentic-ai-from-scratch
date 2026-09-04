# Multi-Agent Math/Writing Router

## What it does

A single question comes in. An **orchestrator** decides whether it's a math
question or a writing question, then hands it to one of two **isolated
workers** who never see each other's tools or context:

- **math_worker** — has a real `calculator` tool (safe AST-based evaluator,
  not `eval()`). Runs its own tool-call loop.
- **writing_worker** — no tools, answers in prose directly.

```
question -> orchestrator (picks worker via a tool-call, not free text)
              -> math_worker    (isolated, has calculator)
              -> writing_worker (isolated, no tools)
```

## Why isolation, not one agent with two tools

A single agent with both a calculator and no other constraint would still
have to *reason* about which tool fits, using a bigger tool list, in one
context. Splitting into workers means each one only ever sees what it needs
-- smaller context per step, and a routing mistake is visible (wrong worker
picked) instead of buried in a longer, tool-cluttered reasoning trace.

## Known failure mode (real, not hypothetical)

The orchestrator routes via a "fake tool" (`route`, constrained by
`enum: ["math", "writing"]`) so the decision is structured, not free text.
On the local model used here (`llama3.2` via Ollama), the model
occasionally answers the routing question directly instead of calling
`route` at all -- observed directly during eval runs, not a theoretical
risk.

**Mitigation:** bounded retry (`max_routing_attempts=2`). If it still
doesn't route after one retry, the orchestrator returns an explicit
`"ERROR: orchestrator failed to route after retry"` instead of silently
returning a bad answer. The failure is visible, not hidden.

**Not fixed:** this is a model reliability limit, not a code bug. A larger
hosted model would likely route more reliably. This system was built to
learn the pattern, not for unattended production use.

## How it's tested

`step5_eval.py` -- 5 hand-written cases checking two things per case:
1. did it route to the expected worker
2. was the answer correct (exact substring match for math, non-empty for writing)

Current: 5/5 passing after the retry fix. Before the fix, the same
tagline question intermittently failed depending on model routing
behavior on that run -- this is expected given the known failure mode
above, not a regression.

## What's deliberately NOT here (scope, not oversight)

- No tracing/observability (would need this before running unattended)
- No kill switch (only matters once it's running continuously, not one-shot)
- No memory/retrieval (neither worker needs external data)
- No MCP (single local script, no need to expose tools across processes yet)
- LLM-as-judge grading of writing quality (writing worker output is only
  checked for "non-empty," not correctness -- grading prose needs a
  different technique)

These were cut deliberately to hit a 1-month timeline for a first
multi-agent build, not because they don't matter.
