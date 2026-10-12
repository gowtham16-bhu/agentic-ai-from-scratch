# Chapter 23 — Retrieval in production

> A RAG demo over 50 files works in an afternoon. Production retrieval means millions of
> documents that change every day, many tenants, per-user permissions, deletions you're
> legally required to honor, embedding-model upgrades, latency SLOs — and **numbers** that
> prove quality.

**You will learn:** ingestion pipelines at scale (connectors, change detection, CDC, queues,
idempotency with content hashing, dead-letter queues), freshness and deletion, embedding-model
migration without downtime, permission-aware retrieval, multi-tenant index designs, vector DB
operations (capacity, sharding, replication, quantization, backups), retrieval caching,
retrieval and RAG metrics (**recall@k, precision@k, MRR, nDCG**, faithfulness, Ragas-style
metrics), building a golden set, and debugging retrieval vs generation.

**Where this fits:** builds on all of Part 4 (Ch 17–22) and memory deletion (Ch 16). Evals in
general are Ch 33; tracing in Ch 34; multi-tenancy and queues at the platform level in Ch 38;
cost of embeddings and caching in Ch 37; data-access security in Ch 36.

---

## 1. The idea in plain words

Production retrieval is a **data pipeline** plus a **search service** plus a **quality system**:

```
SOURCES (Drive, SharePoint, Confluence, S3, databases, websites, tickets)
   │ connectors + change detection (webhooks, CDC, polling)
   ▼
QUEUE (Kafka / SQS / Redis streams) ──► WORKERS: fetch → parse → chunk → enrich → embed → upsert
   │                                        │ idempotent (content hash), retries, dead-letter queue
   ▼                                        ▼
INDEX (vectors + BM25 + metadata + ACLs, per-tenant isolation)  ◄── deletes / tombstones
   │
   ▼
SEARCH SERVICE (filters, hybrid, rerank, caching, SLOs) ──► RAG / agents
   │
   ▼
QUALITY: golden sets, retrieval + generation metrics, online signals, traces
```

---

## 2. Analogy

**A library at city scale.** New books arrive daily, old editions are withdrawn, some rooms are
restricted to certain members, branches serve different neighbourhoods, and the catalog must be
re-printed when the classification system changes — without closing the library. And the head
librarian measures how often people find what they came for.

---

## 3. How it works

### 3.1 Ingestion at scale

| Concern | Practice |
|---|---|
| **Connectors** | One per source system; respect API rate limits; capture source IDs, URLs, owners, ACLs, modified times |
| **Change detection** | Webhooks/notifications where available; **CDC** (change data capture from database logs, e.g. Debezium → Kafka) for databases; otherwise polling with modified-time/ETag checks |
| **Queues** | Decouple discovery from processing; scale workers horizontally; backpressure when embedding APIs rate-limit |
| **Idempotency** | Hash each chunk: `sha256(normalized_text + parser_version + chunker_version + embedding_model)`. Same hash → skip. Re-running the pipeline must not duplicate anything |
| **Failures** | Bounded retries with backoff (Ch 12); then a **dead-letter queue** with the error for review; alert on DLQ growth |
| **Backfills** | Full re-processing jobs (new parser, new embedding model) run at low priority with progress tracking |
| **Pipeline metrics** | Lag (source change → searchable), throughput, error rate, cost per 1K documents |

If you know Kafka and Kubernetes from backend work, this is your home turf: ingestion is an event
pipeline with consumers, retries and idempotency — just with LLM-shaped steps in the middle.

### 3.2 Freshness and deletion

- **Freshness SLA:** e.g. "a policy update is searchable within 15 minutes". Measure the lag.
- **Updates:** when a document changes, re-chunk it and **delete chunks that no longer exist**
  (otherwise old and new versions clash, Ch 15).
- **Deletes:** when a source document is deleted, delete its chunks, vectors, graph edges (Ch 20),
  cache entries and derived summaries. Use **tombstones** so late-arriving events don't resurrect it.
- **Versions:** keep a `version`/`is_current` field; serve only current by default; keep history
  (bi-temporal, Ch 16) if users need "what did the policy say in March?".

### 3.3 Embedding-model migration

Vectors from different models aren't comparable (Ch 06). Changing the model = re-embedding
everything. Do it like a database migration:

```
1. create the NEW index (vectors tagged with model + version)
2. dual-write: ingestion writes to old AND new
3. backfill: re-embed the existing corpus into new (throttled; estimate cost first: tokens × price)
4. evaluate: run the golden set against both; compare recall@k, nDCG, latency
5. shift reads gradually (canary → 100%), keep old index for rollback
6. stop dual-write; delete old index after a safe period
```

### 3.4 Permission-aware retrieval (security trimming)

A support agent must never quote a document the user isn't allowed to see.

- Sync **ACLs** from the source (users, groups, roles) onto each chunk (`allowed_groups`).
- At query time, resolve the user's groups and **pre-filter** in the search query (Ch 17).
- **Early binding** (store ACLs on chunks, sync periodically) is fast but can lag behind permission
  changes; **late binding** (check the source system at query time) is accurate but slower. Many
  systems combine both: filter by stored ACLs, then verify the final few results live.
- **Never** rely on the LLM to "not mention" restricted content — if it's in the context, it can leak.
- Include the ACL scope in every cache key (3.7).

### 3.5 Multi-tenant index designs

| Design | How | Pros | Cons |
|---|---|---|---|
| **Index/collection per tenant** (silo) | Separate index per customer | Strongest isolation; per-tenant tuning, deletion = drop index | Overhead with many small tenants |
| **Shared index + tenant filter** (pool) | `tenant_id` on every chunk; mandatory filter | Efficient | One missing filter = cross-tenant leak; noisy neighbours |
| **Namespaces / partitions** | DB-native partitioning (namespaces, partitions, Postgres row-level security) | Middle ground; DB enforces separation | Feature depends on the database |

Enforce the tenant filter **in the data layer** (row-level security, a search-service wrapper that
always injects it), not in each caller. Write tests that try to read across tenants (Ch 33).

### 3.6 Vector database operations

| Topic | What to know |
|---|---|
| **Capacity** | Raw vectors = count × dims × bytes (1M × 1024 × 4 B ≈ 4 GB); HNSW adds graph overhead; plus metadata and BM25 indexes |
| **Memory vs disk** | HNSW wants RAM; quantization (int8/binary, Ch 18) and disk-based indexes (DiskANN-style) cut memory |
| **Sharding & replication** | Shard by tenant or hash for size; replicate for read throughput and availability |
| **Index builds** | Building HNSW over millions of vectors takes time — plan rebuilds and bulk loads |
| **Backups** | Snapshot indexes, or be able to rebuild from the source of truth + stored embeddings |
| **SLOs** | p95 search latency, availability, freshness lag, ANN recall vs exact on a sample |
| **Cost** | Managed services charge by storage/reads; self-hosted costs RAM/CPU/ops time — compare at your scale |

### 3.7 Caching

| Cache | Key | Watch out |
|---|---|---|
| Query-embedding cache | normalized query text + embedding model | Cheap win for repeated queries |
| Retrieval-result cache | normalized query + **tenant** + **ACL scope** + **index version** | Invalidate on index changes; never share across ACL scopes |
| Answer cache / semantic cache | (Ch 37) | Risky with personalization and permissions; label cached answers |

### 3.8 Measuring retrieval

Given a **golden set** (questions with labelled relevant chunks):

| Metric | Meaning | Use |
|---|---|---|
| **Hit rate@k / recall@k** | Did the relevant chunk(s) appear in the top k? (recall: fraction of relevant chunks found) | The headline retrieval metric |
| **Precision@k** | Fraction of top-k that are relevant | Context noise / cost |
| **MRR** (mean reciprocal rank) | Average of 1/rank of the first relevant result | Is the right answer near the top? |
| **nDCG@k** | Graded relevance with a discount for lower positions | When relevance has degrees (perfect / partial / none) |

**Generation metrics** (on the same questions):

| Metric | Meaning |
|---|---|
| **Faithfulness / groundedness** | Are the answer's claims supported by the retrieved context? (Ch 07) |
| **Answer relevance** | Does the answer address the question? |
| **Answer correctness** | Does it match the reference answer? |
| **Citation accuracy** | Do cited chunks actually support the claims? |
| **Abstention accuracy** | "I don't know" exactly when the answer isn't available (Ch 07 matrix) |

Libraries such as **Ragas** implement metrics with these names (context precision, context
recall, faithfulness, answer relevancy) using LLM judges — useful, but calibrate the judges against
your own labels (Ch 33).

### 3.9 Building the golden set

- Start from **real user questions** (search logs, tickets) — 50–200 to start.
- Label relevant chunks/documents (by **doc id + section**, not chunk position — chunk ids change
  when you re-chunk).
- Include: easy lookups, paraphrases, exact-ID queries, multi-hop, **absence** cases, **contradiction**
  cases, permission-restricted cases, other-language queries.
- Synthetic questions (LLM generates questions from chunks) help coverage but are biased toward easy
  word overlap — mix, don't replace.
- Version the set; update labels when documents change.

### 3.10 Debugging: retrieval or generation?

```
for a failing question, look at the trace:
  was a relevant chunk in the top-k candidates?        no → retrieval problem
      → check: parsing (Ch 21)? chunking? filters/ACL too strict? exact term missing (need BM25)?
               embedding prefixes? query rewriting? reranker demoting it?
  yes, but the answer is wrong/unsupported?             → generation problem
      → check: was it in the FINAL context (after rerank/trim)? position (lost in middle)?
               conflicting chunks? prompt (grounding, abstention)? model capability?
```

Log per query: query (and rewrites), filters, candidate ids + scores, reranker scores, final context
ids, answer, citations, latency per stage (Ch 34).

---

## 4. Code

### 4.1 Idempotent ingestion with content hashing and deletes

```python
# ingest_state.py — skip unchanged chunks, delete removed ones (state in SQLite)
import hashlib
import sqlite3

PIPELINE_VERSION = "parser=2|chunker=3|embed=nomic-embed-text-v1.5"

class IngestState:
    def __init__(self, path="ingest_state.db"):
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS chunks (
            tenant_id TEXT, doc_id TEXT, chunk_key TEXT, content_hash TEXT,
            PRIMARY KEY (tenant_id, doc_id, chunk_key))""")

    @staticmethod
    def content_hash(text):
        normalized = " ".join(text.split()).lower()
        return hashlib.sha256(f"{PIPELINE_VERSION}|{normalized}".encode()).hexdigest()

    def sync_document(self, tenant_id, doc_id, chunks, embed_and_upsert, delete_from_index):
        """chunks: {chunk_key: text}. Calls embed_and_upsert only for new/changed chunks."""
        existing = dict(self.db.execute(
            "SELECT chunk_key, content_hash FROM chunks WHERE tenant_id=? AND doc_id=?", (tenant_id, doc_id)))
        stats = {"embedded": 0, "skipped": 0, "deleted": 0}
        for key, text in chunks.items():
            h = self.content_hash(text)
            if existing.get(key) == h:
                stats["skipped"] += 1
                continue
            embed_and_upsert(tenant_id, doc_id, key, text)
            self.db.execute("INSERT OR REPLACE INTO chunks VALUES (?,?,?,?)", (tenant_id, doc_id, key, h))
            stats["embedded"] += 1
        for key in set(existing) - set(chunks):                   # chunks that disappeared
            delete_from_index(tenant_id, doc_id, key)
            self.db.execute("DELETE FROM chunks WHERE tenant_id=? AND doc_id=? AND chunk_key=?",
                            (tenant_id, doc_id, key))
            stats["deleted"] += 1
        self.db.commit()
        return stats

    def delete_document(self, tenant_id, doc_id, delete_from_index):
        for (key,) in self.db.execute("SELECT chunk_key FROM chunks WHERE tenant_id=? AND doc_id=?",
                                      (tenant_id, doc_id)).fetchall():
            delete_from_index(tenant_id, doc_id, key)
        self.db.execute("DELETE FROM chunks WHERE tenant_id=? AND doc_id=?", (tenant_id, doc_id))
        self.db.commit()

if __name__ == "__main__":
    state = IngestState(":memory:")
    upsert = lambda t, d, k, text: None            # replace with: embed + write to your vector DB
    delete = lambda t, d, k: None
    v1 = {"returns": "Unworn items: 14 days.", "damaged": "Damaged items: 60 days."}
    v2 = {"returns": "Unworn items: 14 days.", "damaged": "Damaged items: 90 days.", "gift": "Gift cards: no refunds."}
    v3 = {"returns": "Unworn items: 14 days."}
    for version in (v1, v1, v2, v3):
        print(state.sync_document("acme", "policy.md", version, upsert, delete))
```

### 4.2 Retrieval metrics (offline)

```python
# retrieval_metrics.py
import math

def recall_at_k(retrieved, relevant, k):
    return len(set(retrieved[:k]) & set(relevant)) / len(relevant) if relevant else 0.0

def hit_at_k(retrieved, relevant, k):
    return 1.0 if set(retrieved[:k]) & set(relevant) else 0.0

def precision_at_k(retrieved, relevant, k):
    return len(set(retrieved[:k]) & set(relevant)) / k

def mrr(retrieved, relevant):
    for rank, doc in enumerate(retrieved, start=1):
        if doc in relevant:
            return 1 / rank
    return 0.0

def ndcg_at_k(retrieved, grades, k):
    """grades: {doc_id: relevance grade, e.g. 2=perfect, 1=partial}."""
    dcg = sum(grades.get(doc, 0) / math.log2(i + 2) for i, doc in enumerate(retrieved[:k]))
    ideal = sorted(grades.values(), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0

def evaluate(golden, search, k=5):
    """golden: [{'q':..., 'relevant': {...ids}, 'grades': {...}}]; search(q) -> ranked ids."""
    rows = []
    for case in golden:
        ranked = search(case["q"])
        rows.append({"hit": hit_at_k(ranked, case["relevant"], k),
                     "recall": recall_at_k(ranked, case["relevant"], k),
                     "precision": precision_at_k(ranked, case["relevant"], k),
                     "mrr": mrr(ranked, case["relevant"]),
                     "ndcg": ndcg_at_k(ranked, case.get("grades") or {d: 1 for d in case["relevant"]}, k)})
    return {m: round(sum(r[m] for r in rows) / len(rows), 3) for m in rows[0]}

if __name__ == "__main__":
    golden = [
        {"q": "damaged item return window", "relevant": {"returns#damaged"}},
        {"q": "what is PX-152", "relevant": {"errors#px152"}},
        {"q": "compare unworn and damaged windows", "relevant": {"returns#damaged", "returns#unworn"},
         "grades": {"returns#damaged": 2, "returns#unworn": 2, "faq#returns": 1}},
    ]
    fake_results = {
        "damaged item return window": ["returns#damaged", "shipping#intl"],
        "what is PX-152": ["errors#px125", "errors#px152"],
        "compare unworn and damaged windows": ["faq#returns", "returns#unworn", "returns#damaged"],
    }
    print(evaluate(golden, lambda q: fake_results[q], k=3))
```

### 4.3 Permission-filtered search wrapper

```python
# secure_search.py — the only search function callers are allowed to use
def secure_search(index_search, query, user):
    """index_search(query, filters) must apply filters INSIDE the query (pre-filtering)."""
    if not user.get("tenant_id") or user.get("groups") is None:
        raise PermissionError("search requires an authenticated user with tenant and groups")
    filters = {"tenant_id": user["tenant_id"],                 # always injected, never optional
               "allowed_groups_any": sorted(user["groups"]),
               "is_current": True}
    return index_search(query, filters)
```

---

## 5. Production view

| Dashboard | Alert when |
|---|---|
| Ingestion lag (p95) | Above the freshness SLA |
| DLQ size / parse error rate by source | Growing — a connector or parser broke |
| Retrieval p95 latency by stage (embed, search, rerank) | SLO breach |
| No-result and low-score rate | Rising — content gaps or broken filters |
| Golden-set recall@k and nDCG (nightly + on every pipeline change) | Drop beyond tolerance → block the change |
| Cross-tenant/ACL test suite | Any failure is a P0 |
| Embedding cost per day | Unexpected re-embedding (hashing broken?) |

---

## 6. Common mistakes

- Re-embedding everything on every sync (no content hashing).
- Updating documents without deleting their removed chunks.
- Golden labels tied to chunk positions that change when you re-chunk.
- Tenant filters implemented in each caller instead of one enforced layer.
- Retrieval caches keyed without tenant/ACL scope.
- Migrating embedding models in place (mixed vector spaces during the switch).
- Measuring only end-to-end answer quality, never retrieval.

---

## 7. Practice

**Level 1**
1. Run `ingest_state.py` and explain each of the four printed lines.
2. Run `retrieval_metrics.py`. Compute MRR for the second query by hand and check it matches.

**Level 2**
3. Build a 40-question golden set for your Part 4 corpus with doc-level labels and a few graded
   cases. Evaluate dense-only, BM25-only, hybrid and hybrid+rerank. Put the table in your notes.
4. Wire `IngestState` to the pgvector store from Ch 17: real upserts and deletes. Edit a document,
   delete another, re-run, and verify the index matches the source.

**Level 3**
5. Simulate an **embedding-model migration**: build index A with one embedding model and index B
   with another; dual-write new documents; backfill B; evaluate both on the golden set; switch reads
   with a feature flag; roll back. Write a one-page runbook from what you learned.

---

## 8. Check yourself

1. What goes into a chunk's content hash, and why include versions?
2. Why use tombstones for deletions?
3. List the steps of a safe embedding-model migration.
4. Early vs late binding of ACLs — trade-offs?
5. When is "index per tenant" better than a shared index with a tenant filter?
6. Define MRR and nDCG in one sentence each.
7. A query fails. How do you decide between a retrieval problem and a generation problem?

<details>
<summary>Answers</summary>

1. Normalized chunk text plus parser, chunker and embedding-model versions — so a pipeline change
   correctly triggers re-processing, while unchanged content is skipped.
2. So late or out-of-order events (an old "updated" message) can't re-create a deleted document.
3. Create new index → dual-write → backfill re-embed → evaluate on golden set → shift reads
   gradually with rollback → stop dual-write → retire old index.
4. Early binding (ACLs stored on chunks) is fast but can be stale after permission changes; late
   binding (check the source at query time) is accurate but slower. Combine: pre-filter by stored
   ACLs, verify final results live.
5. When isolation requirements are strict (regulated customers, per-tenant keys), tenants are large,
   or deletion/export per tenant must be simple — and the number of tenants is manageable.
6. MRR: the average of 1/(rank of the first relevant result). nDCG: a position-discounted score of
   graded relevance, normalized by the best possible ordering.
7. Check the trace: if no relevant chunk is among the retrieved candidates it's retrieval; if
   relevant chunks were in the final context but the answer is still wrong, it's generation.

</details>

---

## 9. Key terms

**connector** · **change detection** · **CDC** · **ingestion queue** · **content hashing** ·
**idempotent ingestion** · **dead-letter queue** · **backfill** · **freshness SLA** · **tombstone** ·
**embedding migration / dual-write** · **ACL / security trimming** · **early vs late binding** ·
**silo vs pool index** · **row-level security** · **sharding / replication** · **hit rate@k /
recall@k / precision@k / MRR / nDCG** · **faithfulness** · **answer relevance** · **golden set** ·
**Ragas**

Next: [Part 5 — Chapter 24: Planning and reasoning →](../part5-advanced-agents/24-planning-and-reasoning.md)
