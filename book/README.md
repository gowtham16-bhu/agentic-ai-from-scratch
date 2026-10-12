# The Agentic AI Engineer & FDE Book

From your first LLM call to a multi-tenant agent platform running at scale.

This book teaches you everything you need to work as an **AI agent developer** and a
**Forward Deployed Engineer (FDE)**: how LLMs work, how to build agents, the protocols
(MCP, A2A), the platform pieces (registries, gateways), quality (evals, tracing),
production (security, cost, deployment, vLLM serving), and the customer-facing craft.

Every chapter follows the same shape, so you always know where you are:

| Section | What it gives you |
|---|---|
| **The idea in plain words** | The concept explained simply, no jargon |
| **Analogy** | Something you already know that works the same way |
| **How it works** | A diagram of the flow |
| **Code** | Small, runnable Python (local Ollama by default — free) |
| **Production view** | What breaks in real systems, how you detect it, how you fix it |
| **Common mistakes** | The traps people fall into |
| **Practice** | Level 1 (basic) → Level 2 (intermediate) → Level 3 (advanced) tasks |
| **Check yourself** | Questions with hidden answers |
| **Key terms** | The words to remember (all collected in the [Glossary](appendix/A-glossary.md)) |

---

## How to read this book

1. **Read in order the first time.** Later chapters build on earlier ones.
2. **Type the code yourself.** Do not copy-paste. Typing is how it gets into your hands.
3. **Do the Level 1 practice before moving on.** Level 2 and 3 can wait for a second pass.
4. **Answer "Check yourself" out loud before opening the answer.** If you can't explain it
   simply, you don't know it yet.
5. **Build the capstone as you go.** Each part adds one piece to one real system
   ([Chapter 41](part9-capstone/41-capstone.md)). By the end you have a portfolio project.

**Time:** about 350–400 hours total. At ~3 hrs on weekdays + weekends, that is
16–20 weeks. See the [week-by-week roadmap](appendix/B-roadmap.md).

---

## The four levels

| Level | You can… | Chapters |
|---|---|---|
| **L1 — Build** | call models, use tools, write an agent loop, do basic RAG | 0–17 |
| **L2 — Production** | add memory, multi-agent, state, protocols, evals, tracing | 18–28 |
| **L3 — Scale** | secure it, control cost, deploy on K8s, serve open models | 29–34 |
| **L4 — Expert / FDE** | ship it for a customer, design systems under interview pressure | 35–41 |

---

## Table of contents

### Part 0 — Start here
- [00 · Setup and how to study](part0-start/00-setup.md) — Python env, Ollama, hosted API keys, spend limits, project layout, Docker basics

### Part 1 — How LLMs work
- [01 · What an LLM is](part1-llm-foundations/01-what-is-an-llm.md) — next-token prediction, pretraining, SFT, RLHF/RLAIF/DPO, Constitutional AI, RLVR/GRPO, base vs instruct vs reasoning models, knowledge cutoff, statelessness
- [02 · Tokens and the context window](part1-llm-foundations/02-tokens-and-context-window.md) — BPE, tokenizer differences, non-English costs more, chat templates, special tokens, input/output limits, context rot, lost-in-the-middle
- [03 · Cost and latency](part1-llm-foundations/03-cost-and-latency.md) — input/output/cached pricing, quadratic history cost, TTFT, TPOT, tokens/sec, cost per task, measuring
- [04 · Sampling and determinism](part1-llm-foundations/04-sampling-and-determinism.md) — logits, softmax, temperature, top-p/top-k/min-p, penalties, seed, greedy vs beam, logprobs, why temp=0 isn't deterministic
- [05 · Inside the transformer](part1-llm-foundations/05-inside-the-transformer.md) — attention (Q/K/V), multi-head, RoPE, n² cost, KV cache, MQA/GQA, Mixture-of-Experts, FlashAttention, parameters → memory
- [06 · Embeddings](part1-llm-foundations/06-embeddings.md) — vectors, cosine/dot/L2, normalization, dimensions, Matryoshka, bi-encoder vs cross-encoder, search/cluster/classify/dedupe
- [07 · Hallucination](part1-llm-foundations/07-hallucination.md) — why it happens, types, detection, mitigation, measuring hallucination rate
- [08 · Choosing a model](part1-llm-foundations/08-choosing-a-model.md) — frontier vs open-weight, reasoning/thinking budgets, licenses, data residency, benchmark limits, model roles, deprecations

### Part 2 — Talking to models
- [09 · Prompt engineering](part2-talking-to-models/09-prompt-engineering.md) — roles, structure, XML delimiters, few-shot, CoT prompting, prefill, templates, versioning, prompts-as-code, DSPy
- [10 · Structured output](part2-talking-to-models/10-structured-output.md) — JSON mode, JSON Schema, native structured outputs, constrained decoding, Pydantic, the repair ladder
- [11 · Tool calling](part2-talking-to-models/11-tool-calling.md) — schemas, tool_choice, parallel calls, errors-as-prompts, 5 tool-design rules, pagination, dry_run, idempotency, tool search
- [12 · API reliability and caching](part2-talking-to-models/12-api-reliability-and-caching.md) — streaming, timeouts, backoff + jitter, rate limits, idempotency keys, circuit breakers, fallbacks, batch APIs, prompt caching

### Part 3 — Building agents
- [13 · Workflows vs agents](part3-building-agents/13-workflows-vs-agents.md) — chain, router, parallel, orchestrator-worker, evaluator-optimizer, autonomous agent, when NOT to build an agent
- [14 · The agent loop](part3-building-agents/14-the-agent-loop.md) — ReAct, 4 termination conditions, budgets, loop detection, checkpoints, OODA/BDI/reactive/proactive
- [15 · Context engineering](part3-building-agents/15-context-engineering.md) — write/select/compress/isolate, compaction, tool-result clearing, just-in-time retrieval, cache-friendly ordering, Skills, AGENTS.md
- [16 · Memory](part3-building-agents/16-memory.md) — working/episodic/semantic/procedural, write/read policies, decay, bi-temporal facts, profiles, vector vs graph memory, poisoning, privacy
- [17 · RAG](part3-building-agents/17-rag.md) — chunking, vector DBs, HNSW/IVF/PQ, hybrid + RRF, filters, rerankers, HyDE, multi-hop, agentic RAG, GraphRAG, long docs, multimodal RAG, citations, ACLs, RAG evals, ingestion at scale
- [18 · Planning and reasoning](part3-building-agents/18-planning-and-reasoning.md) — CoT, self-consistency, plan-and-execute, ReWOO, Reflexion, ToT, verifier-guided, test-time compute
- [19 · Multi-agent systems](part3-building-agents/19-multi-agent-systems.md) — supervisor, hierarchical, swarm/handoffs, debate, blackboard, worker contract, fan-out + synthesizer, failure modes
- [20 · State, checkpoints, human-in-the-loop](part3-building-agents/20-state-checkpoints-hitl.md) — graphs, reducers, checkpointers, interrupts, durable execution, scheduled/proactive agents
- [21 · Frameworks](part3-building-agents/21-frameworks.md) — LangGraph, OpenAI Agents SDK, Claude Agent SDK, Google ADK, Microsoft Agent Framework, CrewAI, Pydantic AI, LlamaIndex, smolagents, DSPy

### Part 4 — The platform layer: protocols, registries, gateways
- [22 · Specs and standards map](part4-platform/22-specs-and-standards.md) — JSON-RPC, JSON Schema, OpenAPI, OAuth 2.1, RFC 8693, SPIFFE, MCP, A2A, OASF, AGENTS.md, Agent Skills, OTel GenAI
- [23 · MCP deep dive](part4-platform/23-mcp.md) — architecture, primitives, transports, spec revisions, auth, security, scaling
- [24 · A2A deep dive](part4-platform/24-a2a.md) — Agent Cards, task lifecycle, streaming, signed cards, MCP vs A2A
- [25 · Registries (agent resource registry)](part4-platform/25-registries.md) — model, prompt, tool, MCP, agent, skill registries; metadata, versioning, signing, discovery, policy
- [26 · LLM gateway and MCP gateway](part4-platform/26-llm-gateway.md) — routing, fallback, budgets, virtual keys, caching, redaction, cost attribution, build your own

### Part 5 — Quality
- [27 · Evals](part5-quality/27-evals.md) — the test pyramid, golden sets, trajectory evals, LLM judges, pass^k, CI gates, online evals, red-teaming, the data flywheel
- [28 · Observability](part5-quality/28-observability.md) — traces and spans, OTel GenAI, span fields, cost metering, dashboards, SLOs, debugging top-down

### Part 6 — Production
- [29 · Guardrails and safety](part6-production/29-guardrails-and-safety.md) — input/output/tool guardrails, guard models, 12 safety patterns, kill switch, responsible AI
- [30 · Agent security](part6-production/30-agent-security.md) — OWASP LLM + Agentic Top 10, prompt injection, lethal trifecta, identity, sandboxing, supply chain, compliance
- [31 · Cost and performance](part6-production/31-cost-and-performance.md) — latency decomposition, optimization order, caching, cascades, batch, distillation, FinOps
- [32 · Deploying at scale](part6-production/32-deploying-at-scale.md) — service design, duration ladder, queues, Little's law, Kubernetes, KEDA, multi-tenancy, rollouts, SLOs, load tests
- [33 · Serving open models: vLLM and inference engineering](part6-production/33-serving-open-models-vllm.md) — GPU memory math, prefill/decode, continuous batching, PagedAttention, prefix caching, speculative decoding, quantization, parallelism, vLLM/SGLang/TensorRT-LLM/TGI/llama.cpp
- [34 · Fine-tuning](part6-production/34-fine-tuning.md) — when to fine-tune, SFT, LoRA/QLoRA, DPO, RLVR/GRPO, distillation, synthetic data

### Part 7 — Interfaces
- [35 · Multimodal](part7-interfaces/35-multimodal.md) — image tokens, PDFs, OCR, tables, audio, video, output routing
- [36 · Voice agents](part7-interfaces/36-voice-agents.md) — cascade vs speech-to-speech, latency budget, barge-in, telephony
- [37 · Code, coding and computer-use agents](part7-interfaces/37-code-and-computer-use-agents.md) — sandboxes, coding agents, AGENTS.md, spec-driven development, browser and computer use
- [38 · Human-in-the-loop UX](part7-interfaces/38-human-in-the-loop-ux.md) — approvals, handoff, streaming UI, citations, feedback capture

### Part 8 — FDE craft
- [39 · The FDE role](part8-fde/39-the-fde-role.md) — discovery, pilots, success metrics, customer infra, writing, adoption, ROI
- [40 · AI system design and interviews](part8-fde/40-ai-system-design-interviews.md) — design framework, 5 worked designs, STAR stories, live coding

### Part 9 — Capstone
- [41 · Capstone: a support agent from laptop to scale](part9-capstone/41-capstone.md) — 10 milestones with acceptance numbers

### Appendices
- [A · Glossary](appendix/A-glossary.md)
- [B · Week-by-week roadmap](appendix/B-roadmap.md)
- [C · Practice bank](appendix/C-practice-bank.md)
- [D · Production checklists](appendix/D-checklists.md)
- [E · Resources](appendix/E-resources.md)

---

## A note on facts that change fast

Model names, prices, SDK method names and protocol versions change every few months.
This book teaches the **concepts**, which last for years. Wherever a fact is fast-moving,
the text says so and tells you where to check. Rule of thumb: **concepts from the book,
numbers and API names from the official docs, checked on the day you use them.**

Last reviewed: 2026-10-12.
