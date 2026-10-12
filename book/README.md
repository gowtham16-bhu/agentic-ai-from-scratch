# The Agentic AI Engineer & FDE Book

From your first LLM call to a multi-tenant agent platform running at scale.

This book teaches you everything you need to work as an **AI agent developer** and a
**Forward Deployed Engineer (FDE)**: how LLMs work, how to build agents, every way to give
them knowledge (vector RAG, vectorless retrieval, PageIndex, knowledge graphs,
personalization), the protocols (MCP, A2A), the platform pieces (registries, gateways),
quality (evals, tracing), production (security, cost, deployment, vLLM serving), and the
customer-facing craft.

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
   ([Chapter 47](part11-capstone/47-capstone.md)). By the end you have a portfolio project.

**Time:** about 400–450 hours total. At ~3 hrs on weekdays + weekends, that is
18–22 weeks. See the [week-by-week roadmap](appendix/B-roadmap.md).

---

## The four levels

| Level | You can… | Chapters |
|---|---|---|
| **L1 — Build** | call models, use tools, write an agent loop, manage context and memory | 0–16 |
| **L2 — Production** | every retrieval style, knowledge graphs, multi-agent, state, protocols, evals, tracing | 17–34 |
| **L3 — Scale** | secure it, control cost, deploy on K8s, serve open models with vLLM, fine-tune | 35–40 |
| **L4 — Expert / FDE** | multimodal and voice, ship it for a customer, design systems under interview pressure | 41–47 |

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
- [07 · Hallucination](part1-llm-foundations/07-hallucination.md) — why it happens, types (factual, faithfulness, tool-argument, citation, package), detection, mitigation, measuring hallucination rate
- [08 · Choosing a model](part1-llm-foundations/08-choosing-a-model.md) — frontier vs open-weight, reasoning/thinking budgets, small language models, licenses, data residency, benchmark limits, model roles, deprecations

### Part 2 — Talking to models
- [09 · Prompt engineering](part2-talking-to-models/09-prompt-engineering.md) — roles, structure, XML delimiters, few-shot, CoT prompting, prefill, templates, versioning, prompts-as-code, DSPy
- [10 · Structured output](part2-talking-to-models/10-structured-output.md) — JSON mode, JSON Schema, native structured outputs, constrained decoding, Pydantic, the repair ladder
- [11 · Tool calling](part2-talking-to-models/11-tool-calling.md) — schemas, tool_choice, parallel calls, errors-as-prompts, 5 tool-design rules, pagination, dry_run, idempotency, tool search
- [12 · API reliability and caching](part2-talking-to-models/12-api-reliability-and-caching.md) — streaming, timeouts, backoff + jitter, rate limits, idempotency keys, circuit breakers, fallbacks, batch APIs, prompt caching

### Part 3 — Building agents
- [13 · Workflows vs agents](part3-building-agents/13-workflows-vs-agents.md) — chain, router, parallel, orchestrator-worker, evaluator-optimizer, autonomous agent, when NOT to build an agent
- [14 · The agent loop](part3-building-agents/14-the-agent-loop.md) — ReAct, 4 termination conditions, budgets, loop detection, checkpoints, OODA/BDI/reactive/proactive
- [15 · Context engineering](part3-building-agents/15-context-engineering.md) — write/select/compress/isolate, compaction, tool-result clearing, just-in-time retrieval, cache-friendly ordering, Skills, AGENTS.md
- [16 · Agent memory](part3-building-agents/16-memory.md) — working/episodic/semantic/procedural, write/read policies, consolidation, decay, bi-temporal facts, memory as a tool, poisoning, memory evals

### Part 4 — Retrieval and knowledge (every way to give an agent knowledge)
- [17 · RAG fundamentals: classic vector RAG](part4-retrieval-knowledge/17-rag-fundamentals.md) — when NOT to use RAG, the pipeline, chunking basics, embedding models, vector databases (pgvector, Qdrant, Weaviate, Milvus, Pinecone, Chroma, LanceDB, OpenSearch), ANN indexes (flat, HNSW, IVF, PQ, DiskANN), metadata filters, hybrid BM25 + vector with RRF, rerankers, groundedness, citations
- [18 · Advanced RAG](part4-retrieval-knowledge/18-advanced-rag.md) — query rewriting, multi-query/RAG-Fusion, HyDE, decomposition, step-back, query routing; semantic, parent-child (small-to-big), sentence-window, proposition, contextual-retrieval and late chunking; multi-vector/ColBERT, SPLADE sparse, binary/Matryoshka embeddings; Self-RAG, Corrective RAG (CRAG), Adaptive RAG, Speculative RAG; multi-hop and iterative retrieval; agentic RAG; deep-research agents
- [19 · Vectorless and reasoning-based retrieval](part4-retrieval-knowledge/19-vectorless-retrieval.md) — agentic search with grep/glob/read tools (how coding agents retrieve), keyword-first BM25 agents, **PageIndex** (tree index + LLM tree search), agentic document navigation, long-context stuffing, **CAG (cache-augmented generation)**, text-to-SQL and API retrieval for structured data, when vectors still win
- [20 · Knowledge graphs and GraphRAG](part4-retrieval-knowledge/20-knowledge-graphs-graphrag.md) — entities, relations, triples, ontologies; property graphs vs RDF (Neo4j/Cypher, SPARQL); building a KG with an LLM (extraction, entity resolution); text-to-Cypher; Microsoft GraphRAG (communities, local vs global search), LazyGraphRAG, LightRAG, HippoRAG, KAG, RAPTOR; temporal knowledge graphs (Graphiti/Zep); KG + vector hybrid; when a graph is worth it; keeping a graph correct
- [21 · Document and multimodal RAG](part4-retrieval-knowledge/21-document-multimodal-rag.md) — PDF/Office parsing (PyMuPDF, Docling, Unstructured), layout, OCR, tables, charts, per-page routing, visual retrieval (ColPali/ColQwen), metadata extraction
- [22 · Personalization and personal knowledge](part4-retrieval-knowledge/22-personalization.md) — user profiles (explicit vs implicit), the `corrections` field, confidence that rises slowly and decays fast, personal knowledge graphs, personal memory stores (Mem0, Zep, Letta, LangMem), personalized retrieval and reranking, recommendation basics, the 8 personalization failure modes, consent, privacy, right to be forgotten, on-device personal agents, evaluating personalization
- [23 · Retrieval in production](part4-retrieval-knowledge/23-retrieval-in-production.md) — ingestion at scale (queues, idempotency, content hashing, incremental re-embed, CDC), freshness and deletion, embedding-model migration, permission-aware retrieval, multi-tenant indexes, vector DB ops (sharding, replication, quantization, backups, cost), retrieval evals (recall@k, precision@k, MRR, nDCG, Ragas metrics), debugging retrieval vs generation

### Part 5 — Advanced agents
- [24 · Planning and reasoning](part5-advanced-agents/24-planning-and-reasoning.md) — CoT, self-consistency, plan-and-execute, ReWOO, Reflexion, self-refine, ToT, verifier-guided generation, test-time compute, reasoning models, interleaved thinking
- [25 · Multi-agent systems](part5-advanced-agents/25-multi-agent-systems.md) — supervisor, hierarchical, swarm/handoffs, pipeline, debate, blackboard, shared state vs messages, worker contract, fan-out + synthesizer, failure modes, shared budgets
- [26 · State, checkpoints, human-in-the-loop](part5-advanced-agents/26-state-checkpoints-hitl.md) — state machines, graphs and reducers, checkpointers, resume, time travel, interrupts, long-running agents, durable execution (Temporal/Restate/DBOS), scheduled and proactive agents
- [27 · Frameworks](part5-advanced-agents/27-frameworks.md) — LangGraph, OpenAI Agents SDK, Claude Agent SDK, Google ADK, Microsoft Agent Framework, CrewAI, Pydantic AI, LlamaIndex, smolagents, DSPy, build vs buy, avoiding lock-in

### Part 6 — The platform layer: protocols, registries, gateways
- [28 · Specs and standards map](part6-platform/28-specs-and-standards.md) — JSON-RPC, JSON Schema, OpenAPI, OAuth 2.1/OIDC, RFC 8693, SPIFFE/mTLS, MCP, A2A, agent-UI protocols (AG-UI, A2UI, MCP Apps), agentic-commerce protocols, AGNTCY/OASF, AGENTS.md, Agent Skills, OTel GenAI, llms.txt, who governs them
- [29 · MCP deep dive](part6-platform/29-mcp.md) — host/client/server, tools/resources/prompts, sampling/elicitation/roots, transports (stdio, Streamable HTTP, legacy SSE), spec revisions incl. the 2026-07-28 stateless revision, OAuth, structured output, tasks, Inspector, security, scaling remote servers
- [30 · A2A deep dive](part6-platform/30-a2a.md) — Agent Card, skills, task lifecycle, messages/parts/artifacts, streaming and push, signed cards, multi-tenancy, MCP vs A2A, server and client in code
- [31 · Registries (agent resource registry)](part6-platform/31-registries.md) — model, prompt, tool/MCP-server, agent, skill and dataset registries; metadata schema, semver, ownership, lifecycle, signing (anti-shadowing), capability discovery, health, policy, audit; build a mini registry
- [32 · LLM gateway and MCP gateway](part6-platform/32-llm-gateway.md) — unified API, routing, cross-provider fallback, per-tenant limits, budgets, virtual keys, exact and semantic cache, guardrail hooks, PII redaction, cost attribution, LiteLLM/Portkey/Kong/Envoy/Cloudflare/OpenRouter, avoiding a single point of failure; build a mini gateway

### Part 7 — Quality
- [33 · Evals](part7-quality/33-evals.md) — the test pyramid, golden datasets, final-state/trajectory/judge assertions, LLM-judge calibration, pass@k vs pass^k, variance, CI gates, online evals, A/B and canaries, red-teaming, benchmarks, eval tools, the data flywheel
- [34 · Observability](part7-quality/34-observability.md) — logs/metrics/traces, LLM/tool/agent spans, OTel GenAI conventions, required span fields, cost metering, the 4 dashboards, SLOs and alerts, debugging top-down, trace sampling, PII in logs

### Part 8 — Production
- [35 · Guardrails and safety](part8-production/35-guardrails-and-safety.md) — input/output/tool guardrails, guard models, moderation, the 12 safety patterns, kill switch, approval gates, responsible AI
- [36 · Agent security](part8-production/36-agent-security.md) — OWASP LLM + Agentic Top 10, direct/indirect prompt injection, jailbreaks, the lethal trifecta, exfiltration, excessive agency, agent identity, 6 sandbox levels, secrets, supply chain, memory poisoning, compliance (EU AI Act, GDPR, SOC 2)
- [37 · Cost and performance](part8-production/37-cost-and-performance.md) — latency decomposition, the optimization order, prompt/semantic/response caching, cascades and routers, batch APIs, distillation, streaming UX, FinOps
- [38 · Deploying at scale](part8-production/38-deploying-at-scale.md) — script → service → pilot → scale, FastAPI + SSE, the duration ladder, queues/workers, Little's law, availability math, degradation ladder, Docker, Kubernetes (HPA, KEDA), multi-tenancy (silo/pool/bridge), CI/CD, shadow/canary, SLOs, load and chaos tests, multi-region, cloud AI platforms
- [39 · Serving open models: vLLM and inference engineering](part8-production/39-serving-open-models-vllm.md) — GPU/VRAM/HBM, memory math, prefill vs decode, continuous batching, PagedAttention, prefix caching/RadixAttention, speculative decoding, quantization (FP8/INT8/INT4, GPTQ, AWQ, GGUF), tensor/pipeline/expert parallelism, disaggregated prefill/decode, multi-LoRA, vLLM/SGLang/TensorRT-LLM/TGI/llama.cpp/Ollama, TTFT/TPOT/goodput, GPU autoscaling, self-host vs API cost
- [40 · Fine-tuning](part8-production/40-fine-tuning.md) — prompt vs RAG vs fine-tune, SFT, LoRA/QLoRA, DPO, RLVR/GRPO, distillation, synthetic data, catastrophic forgetting, TRL/Unsloth/Axolotl, embedding and reranker fine-tuning

### Part 9 — Interfaces
- [41 · Multimodal](part9-interfaces/41-multimodal.md) — image tokens and resizing, vision input, audio, video, output routing (code vs image generation), multimodal evals
- [42 · Voice agents](part9-interfaces/42-voice-agents.md) — VAD → STT → LLM → TTS vs speech-to-speech, the latency budget, barge-in, turn-taking, telephony
- [43 · Code, coding and computer-use agents](part9-interfaces/43-code-and-computer-use-agents.md) — code-interpreter sandboxes, how coding agents work, AGENTS.md, spec-driven development, browser agents (DOM vs pixels), computer use
- [44 · Human-in-the-loop UX](part9-interfaces/44-human-in-the-loop-ux.md) — approval UIs, handoff (`attempted`, `confidence_flags`), streaming UIs, showing citations, feedback capture, trust calibration

### Part 10 — FDE craft
- [45 · The FDE role](part10-fde/45-the-fde-role.md) — discovery, messy enterprise data, pilot scoping, success metrics, demo → pilot → production, customer VPC/on-prem, security reviews, writing, adoption, ROI, feedback to product
- [46 · AI system design and interviews](part10-fde/46-ai-system-design-interviews.md) — a 7-step design framework, 5 worked designs, STAR stories, live coding drills

### Part 11 — Capstone
- [47 · Capstone: a support agent from laptop to scale](part11-capstone/47-capstone.md) — 10 milestones with acceptance numbers

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
