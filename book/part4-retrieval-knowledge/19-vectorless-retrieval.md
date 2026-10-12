# Chapter 19 — Vectorless and reasoning-based retrieval

> Retrieval doesn't have to mean embeddings. An agent can **search with keywords and grep**,
> **navigate a document's structure** like a human expert (PageIndex), **read everything
> from a cached context** (CAG), or **query structured data directly** (text-to-SQL). Knowing
> when *not* to build a vector index is a senior skill.

**You will learn:** why "similarity ≠ relevance", agentic search with grep/glob/read (how
coding agents retrieve), keyword-first agents, **PageIndex** and tree-index reasoning,
building your own document-navigation tools, long-context stuffing and **Cache-Augmented
Generation (CAG)**, text-to-SQL and API retrieval for structured data, and a decision guide
for when vectors still win.

**Where this fits:** builds on classic and advanced RAG (Ch 17–18), tools (Ch 11), the agent
loop (Ch 14), context engineering's just-in-time retrieval (Ch 15) and prompt caching
(Ch 12). Graph-based retrieval is next (Ch 20); coding agents in depth are Ch 43; SQL safety
connects to agent security (Ch 36).

---

## 1. The idea in plain words

Vector search answers "which text **looks similar** to the question?" But what you need is
"which text **answers** the question?" Those differ:

- A financial report's answer may sit in "Note 14: Contingent Liabilities" — a section that
  shares few words or embedding features with "are there any pending lawsuits?".
- Two policy versions are both *similar*; only one is *current*.
- "See Appendix G" — the answer is where the reference points, not where the words match.

As models got better at reasoning and tool use, and as context windows and prompt caching made
long inputs cheaper, **vectorless** approaches became practical:

| Approach | One-line idea |
|---|---|
| **Agentic search** | Give the agent `grep`/`glob`/`read`/keyword-search tools; it searches, reads, refines, repeats |
| **Tree-index reasoning (PageIndex)** | Build a table-of-contents tree with summaries; the LLM *reasons* down the tree to the right sections |
| **Document navigation tools** | `get_outline`, `read_section`, `search_in_doc` — the DIY version of the above |
| **Long context / CAG** | If it fits, put all of it in the (cached) context — no retrieval step |
| **Structured retrieval** | Text-to-SQL, APIs, spreadsheets via code — for data that lives in tables |

---

## 2. Analogy

**How an expert reads a 300-page annual report.** They don't cut it into 2,000 snippets and
compare each one with the question. They open the **table of contents**, jump to the right
chapter, skim the section headings, read the relevant pages, follow "see Note 14", and come
back. Vector RAG is a shredder plus a similarity sorter; tree navigation is the expert.

Where it breaks: the expert is slow and expensive per question. For a million short support
tickets, a fast similarity index is still the right tool.

---

## 3. How it works

### 3.1 Agentic search (how coding agents retrieve)

Coding agents typically don't embed your whole repository. They use tools like `glob` (find
files by pattern), `grep` (search contents with regex), and `read` (read a file range), and
iterate:

```
"where is the refund limit enforced?"
 → grep "refund" --files       → 14 files
 → grep "limit|max_refund" src/ → 3 hits in billing/refunds.py
 → read billing/refunds.py lines 40–90
 → follow the import → read config/limits.py
 → answer with file:line references
```

| Strengths | Weaknesses |
|---|---|
| No index to build or keep fresh — always current | More tool calls → more latency and tokens per question |
| **Exact** matches (IDs, function names, error codes) | Synonyms/paraphrases need the model to try several keywords |
| Iterative: refines queries from what it reads | Gets slow on very large corpora without an index (fast tools like ripgrep help a lot) |
| Traceable results (file:line) | Depends on a capable tool-using model |

Research on **keyword-first agentic retrieval** (an agent iterating with BM25/keyword tools,
no vector store) has reported answer quality close to vector RAG on several benchmarks. A
practical takeaway many teams now follow: **hybrid or keyword search as the default, vectors as
an addition where measured to help** — not the other way round.

### 3.2 Tree-index reasoning: PageIndex

**PageIndex** (open source, from VectifyAI) is a *vectorless, reasoning-based* RAG engine:

```
INDEX (once per document)                         RETRIEVE (per question)
document ─► hierarchical tree, like a             LLM looks at the top-level nodes (titles + summaries)
            table of contents:                     → picks the promising branch(es)
   root                                            → opens children, picks again
   ├─ 1 Business overview   (summary)              → reaches leaf sections/pages
   ├─ 2 Risk factors        (summary)              → reads them; may jump to referenced sections
   │   ├─ 2.1 Market risk   (summary, pages 31–35) → answers with section/page references
   │   └─ 2.2 Legal         (summary, pages 36–40)
   └─ 3 Financial statements ...
```

As the project describes it: the **tree structure** is extracted from the document's own
layout, an index model summarizes and refines the nodes, and at query time a (preferably
strong) chat model **searches the tree with reasoning** — no vector database, no chunking.
Retrieval is **traceable** to explicit sections and pages. The project reports strong results
on financial-document QA (e.g. a vendor-reported 98.7% on FinanceBench) — treat
vendor-reported numbers as claims to verify on your own documents. It also describes a
file-level tree layer for searching across many documents, not just one.

| Good fit | Weaker fit |
|---|---|
| Long, structured professional documents: annual reports, filings, contracts, regulations, technical manuals, medical/academic texts | Millions of short, unstructured texts (tickets, chats, reviews) |
| Questions needing context, cross-references, multi-step reading | Very low-latency, high-QPS lookups (each query = several LLM calls) |
| When users must see *where* an answer came from | Documents with no meaningful structure (though structure can be generated) |

### 3.3 DIY document navigation tools

You can apply the same idea with three tools and the agent loop from Ch 14:

```
get_outline(doc_id)                 → numbered headings with 1-line summaries and page ranges
read_section(doc_id, section_id)    → text of one section (paginated if long)
search_in_doc(doc_id, keywords)     → section ids where the keywords appear (exact search)
```

The agent reads the outline, chooses sections, reads them, follows references, and answers with
section citations. It uses document structure — which chunking destroys — and handles multi-hop
reading naturally.

### 3.4 Long context and Cache-Augmented Generation (CAG)

If the whole knowledge base fits comfortably in the context window, the simplest retrieval is
**none**: put everything in the prompt, **cache** it (Ch 12), and ask questions against it.
**CAG** is the name for preloading the knowledge (and its KV cache) so each question reuses it.

```
first request:  [system][ALL policy docs ~80K tokens][question 1]   → cache written
next requests:  [system][ALL policy docs ~80K tokens][question N]   → prefix read from cache (cheap, fast)
```

| Pros | Cons |
|---|---|
| No retrieval errors (nothing to miss) | Limited by the window; quality can drop with length (context rot, Ch 02) |
| Model sees everything — good for "summarize all" or cross-document questions | Every question pays for reading all of it (cheaper with caching, not free) |
| Very simple to build | Updating knowledge = rebuilding the cached prefix |
| | Not suitable for per-user permissions inside the corpus (everyone sees the whole context) |

**Rule of thumb:** small, stable, shared corpus (a few hundred pages) → try CAG first. It's the
baseline every RAG system should be compared against.

### 3.5 Structured data: query it, don't embed it

Orders, prices, inventory, metrics live in **tables**. Embedding rows into a vector index is
almost always wrong (stale, imprecise, can't aggregate). Instead:

- **Text-to-SQL:** give the model the schema (tables, columns, descriptions, example values); it
  writes SQL; you run it **safely**; it answers from the result.
- **API tools:** `get_order(id)`, `search_orders(email, status)` (Ch 11).
- **Semantic layer:** predefined metrics ("revenue = sum(amount) where status='paid'") the model
  selects instead of writing raw SQL — more reliable for business metrics.
- **Code execution:** load a CSV/spreadsheet with pandas in a sandbox (Ch 43).

**Text-to-SQL safety checklist** (non-negotiable):

```
✔ read-only database user (or read replica)       ✔ only allowlisted tables/views
✔ parse and validate: a single SELECT statement   ✔ row LIMIT and query timeout
✔ tenant/row-level security enforced BY THE DATABASE, not by the prompt
✔ log every query; show the SQL to power users     ✔ never let the model build DDL/DML
```

### 3.6 When vectors still win

| Situation | Why vectors |
|---|---|
| Huge corpus of short, independent texts (tickets, reviews, chats, product descriptions) | Cheap, fast semantic matching; no structure to navigate |
| Fuzzy, natural-language queries with heavy vocabulary mismatch | Embeddings capture paraphrase |
| Multilingual search | Cross-lingual embedding models |
| High QPS, low latency, low cost per query | One embedding + one index lookup vs many LLM calls |
| Similarity tasks: recommendations, dedupe, clustering | That's literally what embeddings are |

### 3.7 Decision guide

```
Is the data structured (tables)?                      → SQL / API tools / semantic layer
Does it all fit in context and is it reused?           → long context + caching (CAG)
Few long, structured documents; precision matters?     → tree navigation (PageIndex / DIY outline tools)
Code or text where exact terms matter; freshness key?  → agentic search (grep/glob/read, keyword tools)
Many short unstructured texts; fuzzy queries; scale?   → hybrid vector RAG (Ch 17–18)
Relationship / global questions across entities?       → knowledge graph (Ch 20)
Mixed?                                                 → route between them (Adaptive RAG, Ch 18)
```

---

## 4. Code

### 4.1 Agentic search tools (grep / glob / read)

```python
# search_tools.py — plug into the Agent from Ch 14
import re
from pathlib import Path

ROOT = Path("knowledge").resolve()           # the only folder the agent may read
MAX_CHARS = 3000

def _safe(path):
    p = (ROOT / path).resolve()
    if not p.is_relative_to(ROOT):            # block ../../etc/passwd
        raise ValueError("path outside the knowledge folder")
    return p

def glob_files(pattern: str = "**/*.md") -> str:
    files = sorted(str(p.relative_to(ROOT)) for p in ROOT.glob(pattern) if p.is_file())
    return "\n".join(files[:100]) or "No files match. Try a broader pattern like '**/*'."

def grep(regex: str, file_pattern: str = "**/*.md") -> str:
    try:
        rx = re.compile(regex, re.IGNORECASE)
    except re.error as e:
        return f"Invalid regex: {e}. Use a simpler pattern."
    hits = []
    for p in ROOT.glob(file_pattern):
        if p.is_file():
            for n, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{p.relative_to(ROOT)}:{n}: {line.strip()[:160]}")
    if not hits:
        return "No matches. Try synonyms or a shorter pattern."
    more = f"\n... {len(hits) - 30} more matches; narrow the regex." if len(hits) > 30 else ""
    return "\n".join(hits[:30]) + more

def read_file(path: str, start_line: int = 1, end_line: int = 80) -> str:
    try:
        lines = _safe(path).read_text(errors="ignore").splitlines()
    except (ValueError, FileNotFoundError) as e:
        return f"Cannot read '{path}': {e}. Use glob_files to see available files."
    chunk = "\n".join(f"{i}: {l}" for i, l in enumerate(lines[start_line - 1:end_line], start_line))
    note = f"\n[showing lines {start_line}-{min(end_line, len(lines))} of {len(lines)}]"
    return chunk[:MAX_CHARS] + note
```

Register them as tools with clear descriptions ("Use grep first to find where a term appears,
then read_file around the line numbers"), and you have the core of a coding-agent retriever.

### 4.2 A tree index and LLM tree search (the PageIndex idea, simplified)

```python
# tree_search.py
import json
import re
import ollama

def build_tree(markdown, doc_id="doc"):
    """Tree from markdown headings. Node summary = first sentence (an LLM summary is better)."""
    root = {"id": doc_id, "title": "ROOT", "level": 0, "text": "", "children": []}
    stack = [root]
    for block in re.split(r"\n(?=#{1,6} )", markdown):
        m = re.match(r"(#{1,6}) (.+)", block)
        if not m:
            continue
        level, title = len(m.group(1)), m.group(2).strip()
        body = block[m.end():].strip()
        while stack[-1]["level"] >= level:
            stack.pop()
        node = {"id": f"{stack[-1]['id']}.{len(stack[-1]['children']) + 1}", "title": title,
                "level": level, "text": body, "summary": body.split(". ")[0][:150], "children": []}
        stack[-1]["children"].append(node)
        stack.append(node)
    return root

CHOOSE = {"type": "object", "properties": {"node_ids": {"type": "array", "items": {"type": "string"}},
          "reason": {"type": "string"}}, "required": ["node_ids", "reason"]}

def tree_search(node, question, max_children=2, path=()):
    """Descend from the root, letting the LLM choose which children to open at each level."""
    if not node["children"]:
        return [{"id": node["id"], "path": " > ".join(path + (node["title"],)), "text": node["text"]}]
    menu = "\n".join(f"{c['id']}: {c['title']} — {c['summary']}" for c in node["children"])
    r = ollama.chat(model="llama3.2", format=CHOOSE, options={"temperature": 0}, messages=[{
        "role": "user", "content": f"Question: {question}\n\nSections:\n{menu}\n\n"
        f"Which at most {max_children} section ids most likely contain the answer?"}])
    chosen = json.loads(r["message"]["content"])["node_ids"][:max_children]
    results = []
    for child in node["children"]:
        if child["id"] in chosen:
            here = path + ((node["title"],) if node["title"] != "ROOT" else ())
            results += tree_search(child, question, max_children, here)
    return results

REPORT = """# Annual Report 2025
## 1 Business overview
We sell footwear online in three countries. Revenue grew 18 percent.
## 2 Risk factors
### 2.1 Market risk
Currency moves affect our import costs.
### 2.2 Legal proceedings
A supplier filed a contract claim of 2.1 million in May 2025; we dispute it.
## 3 Financial statements
### 3.1 Income statement
Operating margin was 7.4 percent.
"""

if __name__ == "__main__":
    tree = build_tree(REPORT, doc_id="ar2025")
    for hit in tree_search(tree, "Are there any pending lawsuits against the company?"):
        print(f"[{hit['id']}] {hit['path']}\n  {hit['text']}")
```

Notice that "pending lawsuits" shares almost no words with "Legal proceedings … contract claim",
yet a reasoning model navigating headings finds it — and the answer cites `ar2025.1.2.2` with its
path.

### 4.3 Cache-Augmented Generation (all knowledge in a cached prefix)

```python
# cag.py — every question reuses the same cached prefix (needs an Anthropic key)
from pathlib import Path
import anthropic

client = anthropic.Anthropic()
KNOWLEDGE = "\n\n".join(f"<doc name='{p.name}'>\n{p.read_text()}\n</doc>"
                        for p in sorted(Path("knowledge").glob("*.md")))     # sorted = stable prefix

def ask(question):
    r = client.messages.create(
        model="claude-haiku-5-5", max_tokens=500,
        system=[{"type": "text", "text": "Answer only from the documents. Cite the doc name. "
                                         "If not covered, say so.\n\n" + KNOWLEDGE,
                 "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": question}])
    u = r.usage
    print(f"[cache read {u.cache_read_input_tokens}, uncached {u.input_tokens}]")
    return "".join(b.text for b in r.content if b.type == "text")   # skip thinking blocks
```

With a local model, the equivalent is keeping the model loaded (`keep_alive`) and sending the
same prefix; servers like vLLM reuse prefixes automatically (prefix caching, Ch 39).

### 4.4 Safe text-to-SQL

```python
# text_to_sql.py — read-only, single SELECT, allowlisted tables, LIMIT
import json
import re
import sqlite3
import time
import ollama

def setup(path="shop.db"):
    db = sqlite3.connect(path)
    db.executescript("""
    DROP TABLE IF EXISTS orders;
    CREATE TABLE orders (id TEXT, customer_email TEXT, status TEXT, total REAL, created_at TEXT);
    INSERT INTO orders VALUES ('A-1043','priya@example.com','shipped',49.99,'2026-10-01'),
                              ('A-1044','ravi@example.com','delivered',120.00,'2026-09-20'),
                              ('A-1045','priya@example.com','cancelled',15.50,'2026-09-28');""")
    db.commit()

SCHEMA = """Table orders(id TEXT 'like A-1043', customer_email TEXT, status TEXT one of
'shipped','delivered','cancelled', total REAL in USD, created_at TEXT ISO date)"""
ALLOWED_TABLES = {"orders"}

def validate(sql):
    s = sql.strip().rstrip(";")
    if ";" in s or not re.match(r"(?is)^\s*select\b", s):
        raise ValueError("only a single SELECT statement is allowed")
    if re.search(r"(?i)\b(insert|update|delete|drop|alter|create|attach|pragma)\b", s):
        raise ValueError("write/DDL keywords are not allowed")
    tables = set(re.findall(r"(?i)\b(?:from|join)\s+([a-z_][a-z0-9_]*)", s))
    if not tables <= ALLOWED_TABLES:
        raise ValueError(f"tables not allowed: {tables - ALLOWED_TABLES}")
    return s if re.search(r"(?i)\blimit\s+\d+", s) else s + " LIMIT 50"

def ask_sql(question, path="shop.db"):
    r = ollama.chat(model="llama3.2", format={"type": "object", "properties": {"sql": {"type": "string"}},
                    "required": ["sql"]}, options={"temperature": 0}, messages=[{"role": "user", "content":
                    f"Schema:\n{SCHEMA}\n\nWrite one SQLite SELECT query answering: {question}"}])
    sql = validate(json.loads(r["message"]["content"])["sql"])
    ro = sqlite3.connect(f"file:{path}?mode=ro", uri=True)        # read-only connection
    deadline = time.monotonic() + 2.0                             # query timeout: 2 seconds
    ro.set_progress_handler(lambda: time.monotonic() > deadline, 10_000)   # True = abort the query
    rows = ro.execute(sql).fetchall()
    return sql, rows

if __name__ == "__main__":
    setup()
    print(ask_sql("How much has priya@example.com spent on orders that were not cancelled?"))
```

A regex validator is a teaching stand-in. In production use a real SQL parser (e.g. `sqlglot`),
database permissions, row-level security for tenants, and query timeouts.

---

## 5. Production view

| Approach | Cost per query | Index/build cost | Freshness | Traceability | Watch out for |
|---|---|---|---|---|---|
| Vector/hybrid RAG | Low | Medium (embed everything) | Needs re-indexing | Chunk ids | Similar-but-wrong chunks |
| Agentic grep/keyword | Medium–high (many tool calls) | None | Always fresh | file:line | Latency; synonym misses |
| Tree reasoning (PageIndex) | Medium–high (several LLM steps) | Low–medium per document | Re-index changed docs | Section/page | Latency; needs good structure |
| CAG / long context | Medium (cached) | Load once | Rebuild prefix on change | Doc names | Window limits; context rot; no per-user filtering |
| Text-to-SQL | Low | None | Live | The SQL itself | Safety; wrong joins → validate & eval |

**FDE move:** in week one of a pilot, build the **simplest baseline** (often CAG or keyword
search) and an eval set; only then decide whether vectors, trees or graphs earn their
complexity on *this* customer's data.

---

## 6. Common mistakes

- Embedding database rows instead of querying the database.
- Building a vector pipeline for 50 pages that fit in a cached prompt.
- Believing "vectorless beats vectors" (or the reverse) as a universal rule — it depends on the
  data and questions; measure.
- Giving an agent a grep tool with no path restriction or output limit.
- Text-to-SQL with a writable connection or tenant filtering done in the prompt.
- Comparing approaches on vendor benchmarks instead of the customer's documents.

---

## 7. Practice

**Level 1**
1. Create a `knowledge/` folder with 5 Markdown policy files. Plug the three search tools into
   the Ch 14 agent and ask 5 questions. Count tool calls per question.
2. Run `tree_search.py`. Ask three more questions (one about margins, one about currency, one
   not covered). Does it abstain correctly on the last?

**Level 2**
3. Run `text_to_sql.py`, then try to break it: ask questions that tempt `DELETE`, multiple
   statements, or another table. Does `validate` stop all of them? Replace the regex with
   `sqlglot` parsing.
4. For your 5 policy files, build three systems — CAG (all docs in context), agentic grep, and the
   Ch 17 hybrid RAG — and run the same 15 questions. Compare accuracy, tokens and latency.

**Level 3**
5. Take a long real document with structure (a public annual report or a technical manual, as
   text). Build an outline tool with LLM-written node summaries, plus `read_section` and
   `search_in_doc`. Compare with chunked hybrid RAG on 15 questions, including 3 that need a
   cross-reference. Write up where each approach wins.

---

## 8. Check yourself

1. Explain "similarity ≠ relevance" with an example.
2. How do coding agents usually find relevant code without a vector index?
3. Describe the two steps of PageIndex.
4. When is CAG a better choice than RAG, and when is it a bad choice?
5. Why shouldn't you embed order rows into a vector index?
6. Name four safety measures for text-to-SQL.
7. Give two situations where vector search is still the best choice.

<details>
<summary>Answers</summary>

1. "Are there pending lawsuits?" is relevant to a "Legal proceedings: supplier contract claim"
   section that shares few words/features with it; meanwhile a similar-looking but outdated
   policy is similar yet not relevant.
2. They iterate with tools: glob to find files, grep to find terms, read to inspect ranges,
   following imports/references until they have enough context.
3. Index: build a hierarchical tree (table-of-contents-like, with summaries) from the document's
   structure. Retrieve: an LLM reasons over the tree, choosing branches until it reaches and reads
   the relevant sections, returning answers with section/page references.
4. Better: a small, stable, shared corpus that fits comfortably in the window and is queried
   repeatedly (cached). Bad: large or frequently changing corpora, per-user permissions inside the
   corpus, or when quality drops at long context lengths.
5. Order data is structured and changes often; embeddings are imprecise for exact values, go stale
   immediately, and can't do filters/aggregations like SQL can.
6. Read-only user/replica; single validated SELECT; allowlisted tables; LIMIT + timeout; tenant/row
   security enforced by the database; logging.
7. Large collections of short unstructured texts with fuzzy queries; high-QPS low-latency search;
   multilingual matching; recommendation/similarity tasks.

</details>

---

## 9. Key terms

**vectorless retrieval** · **similarity vs relevance** · **agentic search** · **grep / glob /
read tools** · **keyword-first agent** · **PageIndex** · **tree index** · **tree search** ·
**document navigation tools** · **long-context stuffing** · **Cache-Augmented Generation
(CAG)** · **text-to-SQL** · **semantic layer** · **read-only connection** · **row-level
security**

Next: [Chapter 20 — Knowledge graphs and GraphRAG →](20-knowledge-graphs-graphrag.md)
