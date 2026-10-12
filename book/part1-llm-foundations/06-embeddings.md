# Chapter 06 — Embeddings

> An **embedding** turns text into a list of numbers so that texts with similar *meaning*
> end up close together. It's the foundation of semantic search, RAG, clustering,
> deduplication, semantic caching and routing.

**You will learn:** what embeddings are, how embedding models are trained, cosine vs dot
vs Euclidean similarity, normalization, dimensions and Matryoshka embeddings, query and
document prefixes, bi-encoders vs cross-encoders, what embeddings are good and bad at, and
how to use them for search, classification, clustering and dedupe.

**Where this fits:** builds on [Ch 05](05-inside-the-transformer.md) (tokens become
vectors inside the model). Embeddings power vector RAG (Ch 17), advanced retrieval like
ColBERT and binary quantization (Ch 18), memory search (Ch 16), personalization (Ch 22),
semantic caching (Ch 37) and semantic routing in gateways (Ch 32). Ch 19 shows when you
don't need them at all.

---

## 1. The idea in plain words

An **embedding model** reads a text and outputs a fixed-length vector, e.g. 768 numbers.

```
"How do I return a damaged shirt?"   → [ 0.12, -0.48, 0.05, ..., 0.33 ]   (768 numbers)
"Refund for a broken item"            → [ 0.10, -0.45, 0.09, ..., 0.29 ]   ← close
"What time does the store open?"      → [-0.31,  0.22, 0.40, ..., -0.07 ]  ← far
```

The vectors are built so that **similar meaning → nearby vectors**, even with no words in
common ("return damaged shirt" ≈ "refund broken item"). That's called **semantic
similarity**, and it's what keyword search can't do.

Embedding models are **different** from chat models: smaller, faster, cheaper, and they
output a vector, not text.

---

## 2. Analogy

**GPS coordinates for meaning.** Every text gets a location on a giant map. Texts about
refunds are in one neighbourhood, texts about opening hours in another. Search = "find the
places nearest to my location".

Where it breaks: a real map has 2 dimensions; embeddings have hundreds or thousands. And
"near" means *related topic*, not *same truth* — "the store opens at 9" and "the store opens
at 10" are neighbours, though only one is true.

---

## 3. How it works

### 3.1 How embedding models learn

They're trained with **contrastive learning**: show the model pairs that *should* be close
(a question and its answer, a title and its article, two paraphrases) and push them together;
push random unrelated pairs apart. After millions of examples, the space organizes itself by
meaning.

### 3.2 Measuring closeness

| Measure | Formula idea | Notes |
|---|---|---|
| **Cosine similarity** | Angle between vectors; 1 = same direction, 0 = unrelated | Ignores length. The default for text. |
| **Dot product** | Sum of element-wise products | Equals cosine **if vectors are normalized** (length 1). Fastest. |
| **Euclidean (L2) distance** | Straight-line distance | Smaller = closer. Same ranking as cosine for normalized vectors. |

**Normalize your vectors** (divide by their length) once at storage time, then use dot
product — same ranking as cosine, cheaper to compute. Many vector DBs do this for you.

### 3.3 Dimensions and Matryoshka embeddings

More dimensions can hold more nuance but cost more storage and search time.

```
1,000,000 chunks × 1,024 dims × 4 bytes (float32) ≈ 4 GB of vectors
```

**Matryoshka embeddings** are trained so the **first k dimensions are already a good
embedding on their own** (like nested dolls). You can store 256 of 1,024 dims and lose only a
little quality. Some APIs let you request fewer dimensions directly. (Further compression —
int8 and binary quantization — in Ch 18.)

### 3.4 Query vs document prefixes (an easy-to-miss gotcha)

Some embedding models were trained with **task prefixes** and work noticeably worse without
them. For example, `nomic-embed-text` expects `search_query: ...` for queries and
`search_document: ...` for documents; E5-family models use `query: ` and `passage: `. Always
read the model card.

### 3.5 Bi-encoder vs cross-encoder

```
BI-ENCODER (embedding model)                CROSS-ENCODER (reranker)
query ──► encoder ──► vector ┐              [query + document] ──► model ──► relevance score
doc   ──► encoder ──► vector ┴► cosine
- docs embedded ONCE, ahead of time          - must run for EVERY (query, doc) pair at query time
- search millions in milliseconds            - much more accurate (reads both together)
- good for "find candidates"                 - good for "re-order the top 20–100" (Ch 17)
```

The standard production pattern: **bi-encoder to retrieve many candidates fast → cross-encoder
to rerank the top few accurately.**

### 3.6 What embeddings are good and bad at

| Good at | Bad at |
|---|---|
| Paraphrases, synonyms, topic similarity | **Exact** identifiers: SKUs, error codes, names ("PX-125" vs "PX-152") |
| Cross-lingual matching (multilingual models) | **Negation** ("contains nuts" ≈ "does not contain nuts") |
| Fuzzy, natural-language queries | Numbers, dates, comparisons ("orders over $500") |
| Grouping similar items | Truth — they encode topic, not correctness |
| | Long texts — inputs over the model's limit are **truncated**, often silently |

This table is why production retrieval is usually **hybrid** (embeddings + keyword search,
Ch 17), and why structured questions go to SQL instead (Ch 19).

### 3.7 Uses beyond search

| Use | How |
|---|---|
| **Semantic search / RAG** | Nearest vectors to the query (Ch 17) |
| **Classification** | Compare to labelled examples (k-nearest-neighbours) or class "centroids" |
| **Clustering** | Group vectors (k-means) to discover topics in tickets/feedback |
| **Deduplication** | Pairs with similarity above a threshold are near-duplicates |
| **Semantic routing** | Route a request to the handler whose examples it's closest to (Ch 13, 32) |
| **Semantic caching** | Reuse an answer if a new question is very close to a past one (Ch 37 — with care) |
| **Anomaly detection** | Inputs far from everything seen before |

---

## 4. Code

### 4.1 Embed, compare, search

```python
# ch06_embeddings.py
import numpy as np
import ollama

MODEL = "nomic-embed-text"

def embed(texts, kind="document"):
    prefix = "search_query: " if kind == "query" else "search_document: "
    # input can be a LIST OF STRINGS (one vector per string) — never a list of single words
    r = ollama.embed(model=MODEL, input=[prefix + t for t in texts])
    vecs = np.array(r["embeddings"], dtype=np.float32)
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)    # normalize → dot == cosine

def search(query, docs, doc_vecs, k=2):
    q = embed([query], kind="query")[0]
    scores = doc_vecs @ q                        # one dot product per document
    best = np.argsort(-scores)[:k]
    return [(round(float(scores[i]), 3), docs[i]) for i in best]

if __name__ == "__main__":                       # demo runs only when executed directly
    docs = [
        "Items damaged in shipping can be returned within 60 days for a full refund.",
        "Standard returns are accepted within 14 days of delivery.",
        "Our store opens at 9am and closes at 9pm, Monday to Saturday.",
        "We ship to India, Sri Lanka and Singapore.",
        "Error code PX-125 means the payment was declined by the bank.",
    ]
    doc_vecs = embed(docs)                       # embed documents ONCE
    print("vector size:", doc_vecs.shape[1])
    for q in ["my shirt arrived broken, can I get my money back?",
              "when are you open?",
              "what does PX-152 mean?"]:        # note: 152, not 125
        print(q, "->", search(q, docs, doc_vecs))
```

Watch the last query: embeddings will happily return the PX-125 document for "PX-152",
because the strings *look* similar. That's the exact-identifier weakness — and why you'll
add keyword search in Ch 17.

### 4.2 Classification with nearest neighbours

```python
# ch06_classify.py — a tiny intent classifier with zero training
import numpy as np
from ch06_embeddings import embed

examples = {
    "refund":   ["I want my money back", "refund my order", "the item is broken, return it"],
    "shipping": ["where is my package", "how long does delivery take", "do you ship abroad"],
    "account":  ["reset my password", "change my email", "I can't log in"],
}
labels, texts = zip(*[(lbl, t) for lbl, ts in examples.items() for t in ts])
vecs = embed(list(texts))

def classify(text):
    q = embed([text], kind="query")[0]
    scores = vecs @ q
    best = int(np.argmax(scores))
    return labels[best], round(float(scores[best]), 3)

for t in ["my parcel never arrived", "login keeps failing", "can I return a cracked mug?"]:
    print(t, "->", classify(t))
```

### 4.3 Negation test — see a weakness yourself

```python
# ch06_negation.py
from ch06_embeddings import embed

a, b, c = embed(["This cake contains nuts.",
                 "This cake does not contain nuts.",
                 "The train leaves at noon."])
print("contains vs does-not-contain:", round(float(a @ b), 3))   # usually very high
print("cake vs train:               ", round(float(a @ c), 3))   # low
```

For an allergy question, those two sentences mean opposite things — yet they're near
neighbours. Never let embedding similarity alone decide safety-critical answers.

---

## 5. Production view

| Problem | Detect | Fix |
|---|---|---|
| Re-embedding the whole corpus on every query | Embedding calls per query ≫ 1 | Embed documents **once**, store vectors; embed only the query per request |
| Switched embedding model, search got worse | Retrieval eval dropped (Ch 23) | Vectors from different models are **not comparable** — re-embed everything; dual-write during migration |
| Silent truncation of long chunks | Chunk tokens > model max input | Chunk below the model's input limit (Ch 17) |
| Missed prefix (query/document) | Lower retrieval quality than the model card claims | Apply the model's required prefixes consistently |
| Exact IDs not found | Failures cluster on codes, SKUs, names | Hybrid search with BM25 (Ch 17) |
| Storage cost explodes | Vector index size | Fewer dimensions (Matryoshka), int8/binary quantization (Ch 18) |
| Picked the "top of the leaderboard" model, still poor | Benchmarks ≠ your data | Build 30–50 query→correct-doc pairs from **your** data and compare models (Ch 23) |

---

## 6. Common mistakes

- **Passing a list of words** to an embed call that expects a list of texts — you get one
  vector per word, not per sentence, and similarity scores collapse. (A real bug from this
  repo's history.)
- **Mixing vectors from two different models** in one index.
- **Using a chat model's hidden states as embeddings** instead of a proper embedding model.
- **Trusting a similarity threshold you never measured.** Pick thresholds from labelled data.
- **Assuming similarity = relevance.** Similar topic ≠ answers the question. That's what
  rerankers fix (Ch 17) and what reasoning-based retrieval argues about (Ch 19).

---

## 7. Practice

**Level 1**
1. Run `ch06_embeddings.py`. Add three documents of your own and three queries. Which query
   returned the wrong top result? Why?
2. Run the negation test. Try two more pairs ("is safe" / "is not safe", "approved" /
   "rejected"). Record the scores.

**Level 2**
3. Remove the `search_query:` / `search_document:` prefixes. Compare the top scores and
   rankings on your queries.
4. Request fewer dimensions (`ollama.embed(..., dimensions=256)` if your model supports it,
   or slice `vec[:256]` and re-normalize). Does ranking change on your 5 queries?
5. Find near-duplicates: embed 30 FAQ questions (write some paraphrases on purpose) and print
   all pairs with similarity > 0.9. Tune the threshold by hand-checking pairs.

**Level 3**
6. Cluster 100 short texts (write or generate them across 4 topics) with k-means (implement
   it in numpy: assign → recompute centroids → repeat). For each cluster, print the 3 texts
   closest to its centroid and name the topic. This is how FDEs discover "what are customers
   actually asking about" in a pile of tickets.

---

## 8. Check yourself

1. What does it mean that two embeddings are "close"?
2. When is dot product the same as cosine similarity?
3. Why can't embeddings reliably distinguish "PX-125" from "PX-152"?
4. Bi-encoder vs cross-encoder — which one do you use to search 5 million documents, and
   which to re-order the top 50? Why?
5. You changed embedding models but kept the old vectors. What happens?

<details>
<summary>Answers</summary>

1. Their texts have similar meaning or topic, as learned by the embedding model.
2. When both vectors are normalized to length 1.
3. Embeddings capture overall meaning/shape of text; the two codes look almost identical as
   text, so their vectors are almost identical. Exact matching needs keyword search.
4. Bi-encoder for the 5 million (documents pre-embedded, search is fast). Cross-encoder for
   the top 50 (reads query and document together → more accurate, but too slow for millions).
5. The query (new model) and documents (old model) live in different vector spaces;
   similarity scores become meaningless. You must re-embed all documents.

</details>

---

## 9. Key terms

**embedding** · **embedding model** · **vector** · **semantic similarity** ·
**contrastive learning** · **cosine similarity** · **dot product** · **Euclidean distance** ·
**normalization** · **dimensions** · **Matryoshka embeddings** · **task prefixes** ·
**bi-encoder** · **cross-encoder** · **k-nearest neighbours** · **clustering** ·
**deduplication** · **semantic routing**

Next: [Chapter 07 — Hallucination →](07-hallucination.md)
