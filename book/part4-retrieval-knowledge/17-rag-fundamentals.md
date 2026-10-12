# Chapter 17 — RAG fundamentals: classic vector RAG

> **Retrieval-Augmented Generation (RAG)**: before the model answers, *retrieve* the most
> relevant pieces of your documents and put them in the context, so the answer is grounded
> in your data instead of the model's memory.

**You will learn:** when **not** to use RAG, the offline and online pipelines, chunking
basics, embedding-model choice, vector databases, ANN index types (flat, HNSW, IVF, PQ,
DiskANN), metadata filtering, hybrid search (BM25 + vectors with Reciprocal Rank Fusion),
reranking, context assembly, grounded generation with citations, and the one eval rule that
saves weeks.

**Where this fits:** builds on embeddings (Ch 06), hallucination (Ch 07), prompts and
structured output (Ch 09–10) and context engineering's "select" move (Ch 15). Next: better
queries, chunks and self-correcting RAG (Ch 18); retrieval without vectors (Ch 19); graphs
(Ch 20); PDFs and images (Ch 21); personalization (Ch 22); running it all in production
(Ch 23).

---

## 1. The idea in plain words

The model doesn't know your company's documents, and it hallucinates when asked about them
(Ch 07). RAG fixes this in two phases:

```
OFFLINE (indexing, once and on every change)
documents → parse → clean → CHUNK → EMBED → store vectors + text + metadata in an INDEX

ONLINE (every question)
question → embed → SEARCH index (top-k) → (rerank) → put chunks in the prompt → GENERATE answer with citations
```

### First: when NOT to use RAG

| Situation | Better approach |
|---|---|
| All the knowledge fits comfortably in the context (e.g. under ~100–200K tokens) and is reused | Put it in the prompt and **cache** it (CAG, Ch 19) — simpler and often more accurate |
| The data is structured (orders, prices, inventory) | **SQL / API tools** (Ch 11, 19), not embeddings |
| The data changes per second (live order status) | **Tools** that query the system of record |
| One long, well-structured document (contract, annual report) | **Navigation / tree search** like PageIndex (Ch 19) is often better than chunking |
| Questions need relationships across many entities ("which customers use a service built on the deprecated library?") | **Knowledge graph** (Ch 20) |
| Many documents, each question touches a few, data mostly unstructured text | ✅ **RAG** |

"RAG bolted on when the data fits in the context" is one of the most common over-engineering
mistakes. FDEs should ask the size question first.

---

## 2. Analogy

**An open-book exam with a librarian.** The student (model) is smart but can't memorize the
company's 10,000-page manual. Before each question, a librarian (retriever) quickly finds the 5
most relevant pages and hands them over. The answer quality depends on the librarian as much as
on the student: hand over the wrong pages and even a genius answers wrong.

---

## 3. How it works

### 3.1 Chunking basics

You embed **chunks**, not whole documents: one vector for a 50-page document blurs every topic
into one point (Ch 06), and you can't fit whole documents in the prompt anyway.

| Strategy | How | Good for |
|---|---|---|
| **Fixed-size** with overlap | Every N tokens, overlapping M | Quick baseline; uniform text |
| **Recursive** | Split by paragraphs → sentences → words until under the size limit | Most prose; good default |
| **Structure-aware** | Split on headings, sections, list items, table boundaries; keep the heading path | Manuals, policies, Markdown/HTML |

Rules of thumb (tune with evals, Ch 23):
- A few hundred tokens per chunk (e.g. 200–800); **overlap** 10–20% so a sentence cut at a
  boundary appears in both chunks.
- **Prepend context** to each chunk: document title + section heading ("Return Policy > Damaged
  items: ..."). Cheap and very effective (Ch 18 takes this further: contextual retrieval).
- Never exceed the embedding model's input limit (silent truncation, Ch 06).
- Keep **metadata** on every chunk: `doc_id`, `chunk_id`, title, section, page, URL, updated_at,
  `tenant_id`, access-control info.

Too big → topics blur, retrieval gets vague. Too small → chunks lose the context needed to
answer. Advanced chunking (semantic, parent-child, late chunking…) is in Ch 18.

### 3.2 Vector databases

| Option | What it is | Choose when |
|---|---|---|
| **pgvector** (Postgres extension) | Vectors as a column in Postgres; SQL filters and joins | You already run Postgres; up to many millions of vectors; want one database. **Best default.** |
| **Qdrant** | Purpose-built vector DB (Rust); strong filtering, quantization | Need advanced filtering/performance at large scale |
| **Weaviate** | Vector DB with built-in hybrid search and modules | Want hybrid + features out of the box |
| **Milvus** | Distributed vector DB for very large scale | Billions of vectors, dedicated team |
| **Pinecone** | Fully managed, serverless | No ops, pay per usage |
| **Chroma** | Simple, embedded | Prototypes, local dev |
| **LanceDB** | Embedded, columnar, good for multimodal | Local/embedded apps, large multimodal data |
| **Elasticsearch / OpenSearch** | Search engines with BM25 + vectors | You already run them; want keyword + vector in one place |

Rule: **start with the database you already operate.** Move to a specialized one when
measurements (latency, recall, cost) say so.

### 3.3 Index types: how search stays fast

Comparing the query with every vector (**flat** / brute-force search) is exact but slow at scale.
**Approximate nearest neighbour (ANN)** indexes trade a little recall for big speedups:

| Index | Idea | Trade-offs |
|---|---|---|
| **Flat (exact)** | Compare with everything | Perfect recall; fine up to ~100K vectors |
| **HNSW** | A layered graph; walk from neighbour to neighbour toward the query | Fast, high recall, the common default; uses lots of memory; tune `M`, `ef_search` |
| **IVF** | Cluster vectors; search only the nearest clusters (`nprobe`) | Less memory than HNSW; recall depends on `nprobe` |
| **PQ** (product quantization) | Compress vectors into short codes | Much less memory; some recall loss; often combined (IVF-PQ) |
| **DiskANN** | Graph index designed for SSDs | Billions of vectors without keeping all in RAM |

"Approximate" means the index can **miss** true nearest neighbours. Measure **ANN recall@k
against exact search** on a sample when you tune parameters.

### 3.4 Metadata filtering

Real queries need constraints: this **tenant**, documents this **user may see**, only
**current** policies, only **product manuals**.

- **Pre-filtering** (filter, then search within allowed items) — correct; supported by good
  vector DBs and SQL.
- **Post-filtering** (search top-k, then drop disallowed) — can return **zero** results (all
  top-k were filtered out) and, for permissions, it's a security risk (Ch 23, 36).

**Always filter tenant and permissions at retrieval time.**

### 3.5 Hybrid search: BM25 + vectors

Embeddings miss exact terms (error codes, SKUs, names — Ch 06). **BM25** is the classic keyword
ranking (term frequency with saturation, inverse document frequency, length normalization). Run
both and **fuse** the rankings with **Reciprocal Rank Fusion (RRF)**:

```
RRF_score(doc) = Σ over each ranked list   1 / (k + rank_in_that_list)        k ≈ 60
```

RRF only uses **ranks**, so you don't need to make BM25 scores and cosine scores comparable.
Documents that rank well in either list rise to the top. Hybrid is the common production
default for text search.

### 3.6 Reranking

The retriever's top results are a *rough* shortlist. A **reranker** (a cross-encoder, Ch 06)
reads the question and each candidate **together** and scores relevance precisely:

```
retrieve top 30–100 (fast, cheap)  →  rerank to top 3–8 (slower, accurate)  →  generate
```

Options: open cross-encoder models (e.g. MiniLM-based MS MARCO models, BGE rerankers), hosted
rerank APIs, or an LLM as reranker (accurate, but slow and expensive per candidate — prototype
only). Reranking is often the **single biggest quality improvement** in a RAG pipeline.

### 3.7 Context assembly and grounded generation

- Put the final chunks in the prompt with **IDs and source labels**:
  `[policy.md#3 | Return Policy > Damaged items] Items damaged in shipping...`
- Dedupe near-identical chunks; respect a token budget; most relevant first.
- System prompt: answer **only** from the provided sources, **cite** chunk IDs, and say "I don't
  know" if the sources don't contain the answer (Ch 07).
- Map chunk IDs to **human-readable citations** (title, section, URL) before showing users —
  `policy.md#3` means nothing to a customer.
- Optionally verify the answer's claims against the chunks (Ch 07 groundedness check).

### 3.8 The eval rule that saves weeks

**Measure retrieval and generation separately.**

```
recall@5 is LOW                → fix retrieval: chunking, embeddings, hybrid, reranking, filters
recall@5 is HIGH, answers BAD  → fix generation: prompt, model, context assembly — NOT retrieval
```

Fixing the wrong half is the most common wasted week in RAG. Full RAG evaluation is in Ch 23.

---

## 4. Code

### 4.1 A complete mini-RAG (chunk → embed → hybrid → RRF → generate with citations)

```python
# mini_rag.py — needs: pip install ollama numpy rank_bm25 ; ollama pull nomic-embed-text llama3.2
import re
import numpy as np
import ollama
from rank_bm25 import BM25Okapi

DOCS = {
    "returns.md": "# Return Policy\n\n## Unworn items\nUnworn items can be returned within 14 days of delivery.\n\n"
                  "## Damaged items\nItems damaged in shipping can be returned within 60 days for a full refund.",
    "shipping.md": "# Shipping\n\n## Delivery times\nStandard delivery takes 3-5 business days.\n\n"
                   "## International\nWe ship to India, Sri Lanka and Singapore.",
    "errors.md": "# Payment errors\n\n## PX-125\nPX-125 means the bank declined the payment.\n\n"
                 "## PX-152\nPX-152 means the card has expired.",
}

def chunk_markdown(doc_id, text, max_words=120):
    """Structure-aware chunking: one chunk per '##' section, prefixed with its heading path."""
    title = re.search(r"^# (.+)$", text, re.M).group(1)
    chunks = []
    for i, section in enumerate(re.split(r"\n(?=## )", text)):
        heading = re.search(r"^## (.+)$", section, re.M)
        body = re.sub(r"^#+ .+$", "", section, flags=re.M).strip()
        if not body:
            continue
        words = body.split()
        for j in range(0, len(words), max_words):
            label = f"{title} > {heading.group(1)}" if heading else title
            chunks.append({"id": f"{doc_id}#{i}.{j // max_words}", "label": label,
                           "text": f"{label}: {' '.join(words[j:j + max_words])}"})
    return chunks

def tokenize(text):                       # lowercase + keep codes like px-125 together
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())

def embed(texts, kind):
    prefix = "search_query: " if kind == "query" else "search_document: "
    vecs = np.array(ollama.embed(model="nomic-embed-text", input=[prefix + t for t in texts])["embeddings"])
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)

class Index:
    def __init__(self, docs):
        self.chunks = [c for doc_id, text in docs.items() for c in chunk_markdown(doc_id, text)]
        self.vectors = embed([c["text"] for c in self.chunks], "document")     # once, offline
        self.bm25 = BM25Okapi([tokenize(c["text"]) for c in self.chunks])

    def search(self, query, k=3, rrf_k=60, candidates=10):
        dense = np.argsort(-(self.vectors @ embed([query], "query")[0]))[:candidates]
        sparse = np.argsort(-self.bm25.get_scores(tokenize(query)))[:candidates]
        fused = {}
        for ranking in (dense, sparse):
            for rank, idx in enumerate(ranking):
                fused[int(idx)] = fused.get(int(idx), 0) + 1 / (rrf_k + rank + 1)
        best = sorted(fused, key=fused.get, reverse=True)[:k]
        return [self.chunks[i] for i in best]

SYSTEM = """Answer using ONLY the sources below. Cite the source id in square brackets after each claim,
e.g. [returns.md#2.0]. If the sources do not contain the answer, say "I don't know based on our documents."
<sources>
{sources}
</sources>"""

def answer(index, question):
    hits = index.search(question)
    sources = "\n".join(f"[{c['id']}] {c['text']}" for c in hits)
    r = ollama.chat(model="llama3.2", options={"temperature": 0}, messages=[
        {"role": "system", "content": SYSTEM.format(sources=sources)},
        {"role": "user", "content": question}])
    labels = {c["id"]: c["label"] for c in hits}            # chunk id → human-readable citation
    return r["message"]["content"], labels

if __name__ == "__main__":
    index = Index(DOCS)
    for q in ["My shoes arrived broken, how long do I have to return them?",
              "What does PX-152 mean?",
              "Do you offer gift wrapping?"]:
        text, labels = answer(index, q)
        print(f"Q: {q}\nA: {text}\nSources: {labels}\n")
```

Try removing the BM25 half (use only `dense`) and ask about "PX-152": you'll often see the
PX-125 chunk ranked first — exactly the exact-identifier weakness from Ch 06 that hybrid search fixes.

### 4.2 The same index in Postgres with pgvector

```bash
docker run -d --name pg -e POSTGRES_PASSWORD=dev -p 5432:5432 pgvector/pgvector:pg17
pip install "psycopg[binary]" pgvector
```

```python
# pgvector_rag.py
import numpy as np
import psycopg
from pgvector.psycopg import register_vector

conn = psycopg.connect("postgresql://postgres:dev@localhost:5432/postgres", autocommit=True)
conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
register_vector(conn)
conn.execute("""
CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, label TEXT, text TEXT NOT NULL,
    embedding vector(768) NOT NULL)""")
# HNSW index for cosine distance (the <=> operator)
conn.execute("CREATE INDEX IF NOT EXISTS chunks_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)")

def upsert(chunk, tenant_id, vector):
    conn.execute("""INSERT INTO chunks (id, tenant_id, label, text, embedding) VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT (id) DO UPDATE SET text=EXCLUDED.text, embedding=EXCLUDED.embedding""",
                 (chunk["id"], tenant_id, chunk["label"], chunk["text"], np.asarray(vector)))

def search(query_vector, tenant_id, k=5):
    # the tenant filter is part of the query → pre-filtering, never post-filtering
    return conn.execute("""SELECT id, label, text, 1 - (embedding <=> %s) AS similarity
                           FROM chunks WHERE tenant_id = %s
                           ORDER BY embedding <=> %s LIMIT %s""",
                        (np.asarray(query_vector), tenant_id, np.asarray(query_vector), k)).fetchall()
```

pgvector operators: `<=>` cosine distance, `<->` Euclidean (L2) distance, `<#>` negative inner
product. Postgres also gives you full-text search (`tsvector`) for the BM25-style half of hybrid.

---

## 5. Production view

| Symptom | Likely cause | Fix |
|---|---|---|
| Right document exists, never retrieved | Bad chunking, missing exact-term match, wrong prefixes | Structure-aware chunks with headings, hybrid search, check embedding prefixes |
| Retrieved but answer still wrong | Generation problem | Prompt, reranking order, fewer but better chunks |
| Answers mix old and new policy | Stale chunks still indexed | Freshness metadata, deletion on update (Ch 23) |
| Slow queries at scale | Flat search or untuned ANN | HNSW/IVF, tune parameters, measure ANN recall |
| Zero results with filters | Post-filtering | Pre-filter in the query |
| Users can't verify answers | Internal chunk IDs as citations | Map IDs to titles/URLs |
| Re-embedding everything on every request | Embeddings not stored | Embed documents once, at ingestion |

---

## 6. Common mistakes

- Using RAG when the data fits in context, is structured, or is live.
- One embedding per whole document.
- No overlap and no heading context in chunks.
- Vector-only search for content full of codes and names.
- Post-filtering permissions.
- Retrieving 20 chunks "to be safe" (distraction, cost, lost-in-the-middle).
- Evaluating only the final answers, never retrieval.

---

## 7. Practice

**Level 1**
1. Run `mini_rag.py`. For each question, print the retrieved chunk IDs before the answer. Are
   they the right ones?
2. Turn off BM25 (dense only) and ask "What does PX-152 mean?" five times. Then dense + BM25.
   Record the top-1 chunk each time.

**Level 2**
3. Add 10 more documents (write realistic policy pages). Build 20 questions with the expected
   chunk ID for each. Compute **recall@3** for dense-only, BM25-only and hybrid.
4. Move the index to pgvector (4.2). Add a second tenant with a conflicting return policy and
   prove a tenant-A query never returns tenant-B chunks.

**Level 3**
5. Add a **reranker**: retrieve top 10 with hybrid, rerank with a cross-encoder (e.g.
   `sentence-transformers` `CrossEncoder` with an MS MARCO MiniLM model) or an LLM scorer,
   keep top 3. Measure recall@3 and answer accuracy before/after, plus added latency. Write
   the trade-off down.

---

## 8. Check yourself

1. Give three situations where RAG is the wrong tool and what you'd use instead.
2. Why chunk documents instead of embedding them whole?
3. What does RRF use from each ranked list, and why is that convenient?
4. Why is post-filtering dangerous for permissions?
5. What is the difference between the retriever and the reranker?
6. Recall@5 is 95% but answers are often wrong. Where do you look?

<details>
<summary>Answers</summary>

1. Data fits in context → long context + caching (CAG); structured data → SQL/API tools; live
   data → tools; one long structured document → tree navigation (PageIndex); relationship-heavy
   questions → knowledge graph.
2. A single vector for a long document blurs many topics; chunks give focused vectors and pieces
   small enough to put in the prompt.
3. Only the **rank** positions. So you can fuse lists whose scores are on different scales (BM25
   vs cosine) without normalizing them.
4. The top-k may be all disallowed (zero results), and disallowed data was already fetched and
   possibly logged/cached — a leak risk. Filter inside the query.
5. The retriever (bi-encoder/BM25) quickly finds candidates from millions; the reranker
   (cross-encoder) carefully re-scores a few dozen candidates by reading query and text together.
6. Generation: the prompt, the model, the order and number of chunks in the context — not
   retrieval.

</details>

---

## 9. Key terms

**RAG** · **indexing pipeline** · **chunk** · **overlap** · **structure-aware chunking** ·
**metadata** · **vector database** · **pgvector** · **ANN** · **flat / HNSW / IVF / PQ /
DiskANN** · **pre- vs post-filtering** · **BM25** · **hybrid search** · **Reciprocal Rank
Fusion (RRF)** · **reranker / cross-encoder** · **context assembly** · **citations** ·
**recall@k**

Next: [Chapter 18 — Advanced RAG →](18-advanced-rag.md)
