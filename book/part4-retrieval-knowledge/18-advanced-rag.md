# Chapter 18 — Advanced RAG

> Classic RAG fails in predictable places: bad queries, bad chunks, weak matching, and no
> second chance when retrieval misses. Advanced RAG fixes each one: **transform the query,
> enrich the chunks, upgrade the retriever, and let the system check and correct itself.**

**You will learn:** query rewriting, multi-query / RAG-Fusion, HyDE, decomposition, step-back,
query routing and self-query filters; semantic, parent-child (small-to-big), sentence-window,
proposition, **contextual retrieval** and **late chunking**; ColBERT (multi-vector / late
interaction), SPLADE (learned sparse), Matryoshka and binary quantization; **Self-RAG,
Corrective RAG (CRAG), Adaptive RAG, Speculative RAG**, FLARE; multi-hop and iterative
retrieval; **agentic RAG**; and how **deep-research agents** are built.

**Where this fits:** builds on Ch 17 (classic pipeline), Ch 06 (embeddings), Ch 13 (patterns)
and Ch 14 (agent loop). Ch 19 asks whether you need vectors at all; Ch 20 adds graphs for
multi-hop questions; Ch 23 shows how to measure whether any technique here actually helped.

---

## 1. The idea in plain words

Each technique targets one failure:

| Failure | Example | Fix family |
|---|---|---|
| The **query** is bad for search | "what about that one?" (follow-up); vague wording; two questions in one | Query transformation |
| The **chunks** lost context | A chunk says "the limit is 60 days" but not *which* limit | Chunk enrichment / better chunking |
| The **matching** is too coarse | Single-vector similarity misses fine details | Better retrievers (ColBERT, SPLADE, hybrid, rerank) |
| **No second chance** | Retrieval returned junk; the model answered anyway | Self-correcting / adaptive RAG |
| **Needs several hops** | "Who manages the team that owns the payments service?" | Iterative / multi-hop / agentic RAG, graphs (Ch 20) |

**Rule:** add a technique only when your eval shows the failure it fixes (Ch 23). Each one
adds latency, cost and complexity.

---

## 2. Analogy

**A skilled research librarian vs a search box.** The search box takes your words literally
once. The librarian rephrases your question, splits it into parts, knows which shelf (source)
to check, notices when the books found don't really answer it, and goes back for more.
Advanced RAG is teaching the pipeline to behave like the librarian.

---

## 3. How it works

### 3.1 Query transformation

| Technique | What it does | When |
|---|---|---|
| **Query rewriting (condensing)** | Turn a follow-up into a standalone query using chat history ("and for damaged ones?" → "return window for damaged items") | Every conversational RAG — essential |
| **Multi-query / RAG-Fusion** | Generate 3–5 phrasings, retrieve for each, fuse with RRF (Ch 17) | Vocabulary mismatch; improves recall |
| **HyDE** (hypothetical document embeddings) | LLM writes a *fake answer*; embed that and search (answer-like text matches answer-like chunks) | Short or vague queries vs long documents |
| **Decomposition** | Split a complex question into sub-questions; retrieve for each; combine | "Compare X and Y", multi-part questions |
| **Step-back** | Ask a more general question first ("what are the return rules?") then the specific one | Questions that need principles before details |
| **Query routing** | Pick the source: policy KB, SQL, product catalog, web | Multiple knowledge sources (Ch 13 router) |
| **Self-query (metadata extraction)** | Extract filters from the query: "India returns policy updated this year" → `{country: India, updated_after: 2026-01-01}` | Metadata-rich corpora |

Always keep the **original** query in the mix — rewrites can drift.

### 3.2 Better chunks and indexes

| Technique | Idea | Trade-off |
|---|---|---|
| **Semantic chunking** | Split where the embedding similarity between neighbouring sentences drops (topic change) | More compute at indexing; better topical chunks |
| **Parent–child (small-to-big)** | Index **small** chunks (precise matching), but return their **parent** section (enough context) | Two levels to store; usually a strong win |
| **Sentence-window** | Match single sentences; return ±N surrounding sentences | Precise for fact lookup |
| **Proposition chunking** | LLM rewrites text into atomic, self-contained facts ("Damaged items can be returned within 60 days.") and you index those | Expensive indexing; very precise retrieval |
| **Contextual retrieval** | For each chunk, an LLM writes 1–2 sentences situating it in the whole document; **prepend** that context before embedding *and* BM25 indexing | Costly at indexing (use prompt caching on the document); large reduction in retrieval failures reported, more with reranking |
| **Late chunking** | Embed the **whole** document with a long-context embedding model, then pool token vectors per chunk — each chunk vector "knows" the document | Needs a long-context embedding model that exposes token embeddings |
| **Hypothetical questions (doc2query)** | Generate questions each chunk answers; index the questions too | Helps question-vs-statement mismatch |

### 3.3 Better retrievers

**ColBERT (multi-vector, late interaction).** Instead of one vector per chunk, keep **one vector
per token**. Score = for each query token, take its best match among document tokens (**MaxSim**),
then sum. Much finer matching than a single vector; more storage (compressed in practice).

**SPLADE (learned sparse).** A model outputs a **sparse** vector over the vocabulary with learned
term weights *and* expansion terms ("refund" also activates "money back"). It runs on inverted
indexes like BM25, but understands meaning better. A middle ground between BM25 and dense.

**Compressing dense vectors:**

| Method | Size vs float32 | Note |
|---|---|---|
| Matryoshka truncation (Ch 06) | e.g. 4× smaller (1024 → 256 dims) | Small quality loss |
| **int8 scalar quantization** | 4× smaller | Usually tiny loss |
| **Binary quantization** | **32× smaller** (1 bit per dimension), compare with fast Hamming distance | Bigger loss → **rescore** the top candidates with full vectors |

### 3.4 Self-correcting and adaptive RAG

```
                          ┌──────────── grade the retrieved docs ─────────────┐
question → retrieve → ────┤ relevant? → generate → check answer is grounded ─► answer
                          │ ambiguous/irrelevant → rewrite query / other source / web → retrieve again
                          └───────────────────────────────────────────────────┘
```

| Method | Core idea |
|---|---|
| **Self-RAG** | A model trained to emit special *reflection* tokens: decide **whether** to retrieve, judge whether each passage is relevant, whether its own output is supported, and how useful it is |
| **Corrective RAG (CRAG)** | A lightweight **retrieval evaluator** grades results as correct / ambiguous / incorrect; on bad results, fall back to query rewriting or web search; filter retrieved text to keep only relevant strips |
| **Adaptive RAG** | A classifier estimates question complexity and picks: **no retrieval** (simple), **single-step** retrieval, or **multi-step** iterative retrieval |
| **Speculative RAG** | A small specialist model drafts several answers in parallel, each from a different subset of documents; a large model verifies and picks the best |
| **FLARE (active retrieval)** | While generating, if the next sentence contains low-confidence tokens (logprobs, Ch 04), retrieve using that sentence as the query, then regenerate it |

You can get most of the benefit without special models: **a grader step + a retry with a
rewritten query + an "I don't know" exit** (code 4.4).

### 3.5 Multi-hop and iterative retrieval

Some questions need a chain: find the team that owns the payments service → find that team's
manager. **Iterative retrieval** interleaves reasoning and retrieval: retrieve → read → write the
next sub-query → retrieve again, until the answer is complete (bounded by a step limit, Ch 14).
For heavily relational questions, a knowledge graph is often better (Ch 20).

### 3.6 Agentic RAG

Make retrieval a set of **tools** and let an agent decide when and how to use them:

```
tools: search_policies(query, filters) · search_products(query) · sql_orders(query) · web_search(query) · read_document(id, section)
agent: decides which source, how many searches, reformulates, verifies, stops when it has enough
```

Pros: handles multi-source, multi-hop, and "no answer here, try elsewhere" naturally.
Cons: more latency, cost and variance — use the Ch 13 checklist. Many production systems use a
**fixed pipeline for simple questions and agentic RAG for complex ones** (Adaptive RAG idea).

### 3.7 Deep-research agents

The "deep research" products in major AI assistants are agentic RAG at a large scale:

```
question → PLANNER: research plan (sub-questions)
         → SEARCH WORKERS (often parallel sub-agents, Ch 25): search → read → extract claims WITH sources
         → (iterate: gaps found → new searches)
         → WRITER: long report, every claim cited
         → VERIFIER: check citations support claims (Ch 07)
```

Hard parts: keeping sources attached to claims through every step, deduplicating, knowing when
to stop, cost control (hundreds of calls), and long runtimes (async jobs, Ch 38).

---

## 4. Code

These build on `mini_rag.py` from Ch 17 (`Index`, `embed`, `chunk_markdown`).

### 4.1 Conversational query rewriting

```python
# rewrite.py
import ollama

def condense(history, follow_up):
    convo = "\n".join(f"{m['role']}: {m['content']}" for m in history[-6:])
    r = ollama.chat(model="llama3.2", options={"temperature": 0}, messages=[{"role": "user", "content":
        f"Conversation:\n{convo}\n\nRewrite the last question as a standalone search query. "
        f"Keep names, IDs and numbers exactly. Output only the query.\n\nLast question: {follow_up}"}])
    return r["message"]["content"].strip()

if __name__ == "__main__":
    history = [{"role": "user", "content": "How long can I return unworn shoes?"},
               {"role": "assistant", "content": "Unworn items can be returned within 14 days."}]
    print(condense(history, "and damaged ones?"))      # → e.g. "return window for damaged shoes"
```

### 4.2 Multi-query (RAG-Fusion) and HyDE

```python
# fusion_hyde.py
import json
import ollama
from mini_rag import Index, DOCS

def variants(question, n=3):
    r = ollama.chat(model="llama3.2", format={"type": "object", "properties": {"queries": {
        "type": "array", "items": {"type": "string"}}}, "required": ["queries"]},
        messages=[{"role": "user", "content": f"Write {n} different search queries for: {question}"}])
    return [question] + json.loads(r["message"]["content"])["queries"][:n]   # keep the original

def rag_fusion(index, question, k=3, rrf_k=60):
    scores, by_id = {}, {}
    for q in variants(question):
        for rank, chunk in enumerate(index.search(q, k=10)):
            scores[chunk["id"]] = scores.get(chunk["id"], 0) + 1 / (rrf_k + rank + 1)
            by_id[chunk["id"]] = chunk
    return [by_id[i] for i in sorted(scores, key=scores.get, reverse=True)[:k]]

def hyde(index, question, k=3):
    fake = ollama.chat(model="llama3.2", messages=[{"role": "user", "content":
        f"Write a short paragraph that would answer: {question}"}])["message"]["content"]
    return index.search(fake, k=k)          # search with the hypothetical ANSWER

index = Index(DOCS)
q = "can i get my money back if the parcel came smashed"
print([c["id"] for c in rag_fusion(index, q)])
print([c["id"] for c in hyde(index, q)])
```

### 4.3 Parent–child retrieval and contextual chunk enrichment

```python
# parent_child.py
import ollama

def make_parent_child(doc_id, sections, child_words=25):
    """sections: list of section texts. Children are small windows; each points to its parent."""
    parents, children = {}, []
    for p, text in enumerate(sections):
        pid = f"{doc_id}#p{p}"
        parents[pid] = text
        words = text.split()
        for c in range(0, len(words), child_words):
            children.append({"id": f"{pid}.c{c // child_words}", "parent": pid,
                             "text": " ".join(words[c:c + child_words])})
    return parents, children

def contextualize(document, chunk_text):
    """Contextual retrieval: situate the chunk in its document, then prepend before indexing.
    In production, cache the document prefix (Ch 12) — it's identical for every chunk."""
    r = ollama.chat(model="llama3.2", options={"temperature": 0}, messages=[{"role": "user", "content":
        f"<document>\n{document}\n</document>\nHere is a chunk from it:\n<chunk>\n{chunk_text}\n</chunk>\n"
        "Write 1-2 sentences that situate this chunk within the document, to improve search. Output only that."}])
    return r["message"]["content"].strip() + "\n" + chunk_text

# Search over children (precise), then return unique parents (enough context):
def small_to_big(child_hits, parents, k=2):
    seen = []
    for hit in child_hits:
        if hit["parent"] not in seen:
            seen.append(hit["parent"])
    return [parents[pid] for pid in seen[:k]]
```

### 4.4 A corrective loop: grade → retry → abstain

```python
# corrective_rag.py
import json
import ollama
from mini_rag import Index, DOCS
from rewrite import condense

GRADE = {"type": "object", "properties": {"relevant": {"type": "boolean"}}, "required": ["relevant"]}

def relevant(question, chunk):
    r = ollama.chat(model="llama3.2", format=GRADE, options={"temperature": 0}, messages=[{"role": "user",
        "content": f"Question: {question}\nPassage: {chunk['text']}\nDoes the passage help answer the question?"}])
    return json.loads(r["message"]["content"])["relevant"]

def corrective_retrieve(index, question, max_rounds=2):
    query = question
    for round_no in range(max_rounds):
        good = [c for c in index.search(query, k=4) if relevant(question, c)]
        if good:
            return good, round_no + 1
        query = condense([], f"Rephrase with different words for a search engine: {question}")
    return [], max_rounds                     # nothing relevant → caller must answer "I don't know"

index = Index(DOCS)
for q in ["what if my item arrived broken?", "do you sell gift cards?"]:
    chunks, rounds = corrective_retrieve(index, q)
    print(q, "->", [c["id"] for c in chunks] or "NO RELEVANT SOURCES -> abstain", f"({rounds} rounds)")
```

### 4.5 Binary quantization with rescoring (runs offline)

```python
# binary_quant.py — 32x smaller vectors, then rescore the shortlist with full precision
import numpy as np

rng = np.random.default_rng(0)
# synthetic "embeddings" with structure: 20,000 docs around 500 topics (real embeddings cluster too)
topics = rng.normal(size=(500, 768)).astype(np.float32)
docs = topics[rng.integers(0, 500, size=20_000)] + 0.6 * rng.normal(size=(20_000, 768)).astype(np.float32)
docs /= np.linalg.norm(docs, axis=1, keepdims=True)
query = docs[123] + 0.02 * rng.normal(size=768).astype(np.float32)    # a query close to doc 123
query /= np.linalg.norm(query)

exact_top10 = set(np.argsort(-(docs @ query))[:10])

bits_docs = np.packbits(docs > 0, axis=1)            # 768 floats (3072 bytes) -> 96 bytes
bits_query = np.packbits(query > 0)
hamming = np.unpackbits(bits_docs ^ bits_query, axis=1).sum(axis=1)

print("bytes per vector: float32", docs[0].nbytes, "| binary", bits_docs[0].nbytes)
print("recall@10 binary only:", len(set(np.argsort(hamming)[:10]) & exact_top10) / 10)
for shortlist_size in (20, 100):
    shortlist = np.argsort(hamming)[:shortlist_size]                    # cheap first pass
    rescored = shortlist[np.argsort(-(docs[shortlist] @ query))][:10]   # precise second pass
    print(f"recall@10 binary + rescore top {shortlist_size}:", len(set(rescored) & exact_top10) / 10)
```

### 4.6 Agentic RAG: retrieval as tools

```python
# agentic_rag.py — plug these into the Agent from Ch 14
from mini_rag import Index, DOCS

index = Index(DOCS)

def search_policies(query: str) -> str:
    hits = index.search(query, k=3)
    if not hits:
        return "No policy passages found. Try different keywords or answer that the policy doesn't cover it."
    return "\n".join(f"[{c['id']}] {c['text']}" for c in hits)

RAG_TOOLS = [{"type": "function", "function": {
    "name": "search_policies",
    "description": ("Search store policies (returns, shipping, payment errors). Use for any policy question. "
                    "You may call it several times with different queries. Cite the [ids] you use."),
    "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}}]

# from agent import Agent
# agent = Agent(RAG_TOOLS, {"search_policies": search_policies},
#               system="Answer policy questions using search_policies. Cite sources. Call finish when done.")
# print(agent.run("Compare the return window for damaged and unworn items.", run_id="rag-1"))
```

---

## 5. Production view

| Technique | Cost added | Latency added | Measure before keeping it |
|---|---|---|---|
| Query rewriting | 1 small LLM call | +0.3–1s | Recall on follow-up questions |
| Multi-query / HyDE | 1 LLM call + N searches | +0.5–2s | Recall@k on vocabulary-mismatch cases |
| Reranking | Reranker call | +0.1–1s | Precision@k, answer accuracy |
| Contextual retrieval | 1 LLM call **per chunk at indexing** | none at query time | Recall@k; indexing cost with caching |
| Corrective grading | 1 call per candidate | +1–3s | Hallucination rate on absence cases |
| Agentic RAG | Many calls | seconds to minutes | Accuracy on multi-hop cases vs cost/task |

Put the cheap, always-useful ones in the default path (rewriting for chat, hybrid, rerank) and
reserve expensive ones for the questions that need them (Adaptive RAG routing).

---

## 6. Common mistakes

- Adding five techniques at once, then not knowing which helped (isolate the variable!).
- Dropping the original query when using rewrites.
- Contextual retrieval without prompt caching — paying full price for the same document N times.
- Binary quantization without rescoring.
- Agentic RAG for FAQ-style questions a single retrieval answers.
- Graders that never say "irrelevant" (test them on known-irrelevant passages).

---

## 7. Practice

**Level 1**
1. Run `rewrite.py` with five follow-up questions of your own. Are names and IDs preserved?
2. Run `binary_quant.py`. Add shortlist sizes 500 and 1,000, then raise the topic noise from 0.6
   to 0.9 (weaker structure). How do recall and the shortlist you need change? What does that
   tell you about tuning on *your* embeddings rather than trusting defaults?

**Level 2**
3. Using your 20-question set from Ch 17, measure recall@3 for: plain hybrid, + multi-query,
   + HyDE, + rerank. Keep only what improves the number.
4. Implement contextual retrieval for your documents. Compare recall@3 with and without the
   context prefix. Note the indexing cost.

**Level 3**
5. Build **Adaptive RAG**: a router classifies each question as `no_retrieval`, `single`, or
   `multi_hop`; `single` uses the Ch 17 pipeline; `multi_hop` uses the agentic RAG tools with the
   Ch 14 agent. Measure accuracy, average latency and cost vs always-agentic on 20 mixed questions.

---

## 8. Check yourself

1. Why is query rewriting essential in conversational RAG?
2. How does HyDE improve matching?
3. Explain parent–child retrieval in one sentence and why it helps.
4. What does contextual retrieval add to each chunk, and why is it costly without caching?
5. How does ColBERT score a document differently from a single-vector model?
6. What is the core idea of Corrective RAG?
7. When would you choose agentic RAG over a fixed pipeline?

<details>
<summary>Answers</summary>

1. Follow-ups ("and for damaged ones?") contain pronouns and omissions that make poor search
   queries; rewriting turns them into standalone queries.
2. It searches with a hypothetical answer, and answer-like text is more similar to the answer
   passages than a short question is.
3. Match on small chunks for precision, then return the larger parent section so the model has
   enough context.
4. A short LLM-written description of where the chunk sits in the document (and what it's about),
   prepended before embedding/BM25. It requires one LLM call per chunk over the full document —
   expensive unless the document prefix is cached.
5. It keeps a vector per token and sums, for each query token, its maximum similarity to any
   document token (MaxSim), instead of comparing one vector per text.
6. Grade the retrieved documents; if they're poor, correct course (rewrite the query, use
   another source like web search, filter content) before generating; otherwise abstain.
7. When questions need multiple sources or hops, reformulation, or verification that a fixed
   pipeline can't do — and the extra latency/cost is acceptable.

</details>

---

## 9. Key terms

**query rewriting** · **multi-query / RAG-Fusion** · **HyDE** · **query decomposition** ·
**step-back prompting** · **query routing** · **self-query** · **semantic chunking** ·
**parent–child / small-to-big** · **sentence-window** · **proposition chunking** · **contextual
retrieval** · **late chunking** · **doc2query** · **ColBERT / late interaction / MaxSim** ·
**SPLADE** · **scalar / binary quantization** · **Self-RAG** · **Corrective RAG** · **Adaptive
RAG** · **Speculative RAG** · **FLARE** · **multi-hop retrieval** · **agentic RAG** ·
**deep-research agent**

Next: [Chapter 19 — Vectorless and reasoning-based retrieval →](19-vectorless-retrieval.md)
