# Agentic AI, from scratch

A working agent system built module by module, by hand, before reaching for any
framework — the agent loop, tool design, context engineering, and RAG, each written
and debugged from real evidence (not tutorials copy-pasted and assumed correct).

Runs entirely local via [Ollama](https://ollama.com) (`llama3.2` + `nomic-embed-text`)
— no API keys, no cloud cost to experiment.

## Why build this by hand instead of using LangChain/LlamaIndex

Frameworks like LangChain and LlamaIndex already implement everything here (tool-calling
loops, RAG retrievers, hybrid search) behind a single function call. That's the right
choice for shipping fast in production. It is the wrong choice for *learning* — when a
framework's retriever silently returns the wrong document, you need to know what's
actually happening underneath to debug it. This repo is that underneath, built once by
hand so the framework version is later an API lookup, not a black box.

## What's here

| Module | File | Status |
|---|---|---|
| The agent loop, tool design | `step0_no_tool.py` → `step2_tool_design.py` | Done |
| Context slicing | `step3_context_slice.py` | Done |
| Multi-agent orchestrator + isolated workers | `step4_orchestrator.py` (see `CAPSTONE.md`) | Done |
| Eval suite | `step5_eval.py` | 5/5 cases passing |
| Production hardening (tracing, kill switch) | `step6_hardened.py` | Partial — no cost/token tracking, no approval gate yet |
| Session memory, per-worker isolation | `step7_memory.py` | Done |
| Context budgeting + RAG (chunking, groundedness, top-k, hybrid search) | `step8_context_budget.py` | See below |

Full concept-by-concept status against the entire curriculum: `CONCEPT-MAP.md`.

## RAG module — what it does and what broke building it

`step8_context_budget.py` grounds an ecommerce support chatbot in real documents
instead of letting the model guess. Corpus: 6 policy/FAQ files, ~62 chunks after
paragraph-splitting the multi-topic ones.

**Built, in this order, each with real before/after evidence:**

1. **Naive grounding** — inject the one relevant doc into the system prompt.
   Fixed a real hallucination: asked "what's your return policy?" with no
   grounding, the model invented a fake 30-day window and a fake link. Grounded,
   it answered from the real 14-day policy.
2. **Chunking** — split multi-topic files (FAQ, product catalog) into per-topic
   paragraphs before embedding. Without it, a 6-topic FAQ file's single embedding
   blurred all 6 topics together and lost a real query ("international return
   window") to a wrong, more topically-focused document.
3. **Top-k retrieval** — a hardcoded top-1 result dropped real information on a
   cross-topic query (a damaged-item warranty question that also had a relevant
   answer in the return policy). Moved to top-3.
4. **Groundedness (faithfulness)** — even with the right document retrieved, the
   model invented a detail not in the source text ("send a photo of the damage").
   Added an explicit system-prompt constraint: answer only from the provided
   document, say so if it's not covered. RAG reduces hallucination; it does not
   remove it by itself.
5. **Hybrid search (BM25 + vector, Reciprocal Rank Fusion)** — built for learning
   purposes after four separate real attempts to find a case where vector-only
   search actually fails (a nonsense promo code, near-duplicate error codes, a
   50-document near-duplicate product catalog) all succeeded on vector search
   alone. Honest finding: `nomic-embed-text` is more robust than assumed, and
   hybrid search is not empirically justified at this corpus size — it's here as
   a working, understood mechanism, not because the data needed it.
6. **Re-ranking** — a second, more expensive pass over the top-10 RRF candidates:
   an LLM scores each candidate's relevance 1-10, re-sorted to the final top-3.
   Standing in for a real cross-encoder (`ms-marco-MiniLM`, Cohere Rerank), which
   is what production actually uses at scale — an LLM call per candidate does
   not scale to real traffic, it's the prototyping version of the mechanic.
7. **Query expansion** — generate 2 alternate phrasings of the question, retrieve
   for all 3 (never replacing the original), union the results, rerank against
   the original question. Attacks recall, not ranking: catches cases where the
   right document never made the shortlist under one specific phrasing.
8. **Citations** — every retrieved chunk is labeled with its own key
   (`[products.txt#25]`) before being handed to the model, with an explicit
   system-prompt instruction to cite sources. Verified the model's citations
   are accurate, not decorative.

**A real bug worth naming**, because it's the kind that's genuinely hard to catch:
passing a *list* of tokens into `ollama.embed(input=...)` doesn't error — Ollama
treats a list as a batch and embeds each token separately, silently returning the
embedding of just the first word. Every cosine score collapsed to a near-identical
band with no error message. Found by comparing scores before/after a change, not by
reading the code.

## Known gaps (logged, not hidden)

- `model = "llama3.2"` is hardcoded in `step8_context_budget.py` — should be a
  config-resolved role (`fast`/`reasoning`), not a literal string. Flagged, not
  yet fixed.
- `retrieve()` re-embeds every document on every call — doc embeddings should be
  cached once; only the question needs embedding per call.
- Reranking uses a full LLM call per candidate — real production would swap in a
  dedicated cross-encoder model for this to work at scale.
- Citations expose the internal chunk ID (`products.txt#25`) directly to the
  user — meaningless to a real customer. Needs a lookup mapping each chunk key
  to a human-readable label before it reaches the final answer.
- No CI, no automated eval gate on this file yet (eval work deliberately pushed
  to the end of the curriculum sequence).

See `PROGRESS.md` for the full, dated build log — including wrong predictions,
what broke, and what was learned from each, not just what worked.

## Running it

```bash
python -m venv venv && source venv/bin/activate
pip install ollama tiktoken rank_bm25
ollama pull llama3.2
ollama pull nomic-embed-text
python step8_context_budget.py
```

## License

Not yet chosen — add one (MIT is the common default for a learning repo like this)
before treating any of this as reusable by others.
