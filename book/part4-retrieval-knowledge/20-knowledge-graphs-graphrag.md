# Chapter 20 — Knowledge graphs and GraphRAG

> A **knowledge graph** stores knowledge as **entities** connected by **relationships**.
> It answers what chunk retrieval structurally can't: multi-hop questions ("who manages the
> team that owns the service that uses the deprecated library?") and global questions
> ("what are the main themes across all these reports?").

**You will learn:** entities, relations, triples and ontologies; property graphs (Neo4j /
Cypher) vs RDF (SPARQL); building a graph with an LLM (schema → extraction → entity
resolution → provenance); querying (traversal tools, text-to-Cypher, graph + vector hybrid);
**Microsoft GraphRAG** (communities, local vs global search), **LazyGraphRAG**, **LightRAG**,
**HippoRAG** (Personalized PageRank), **KAG**, **RAPTOR**; **temporal knowledge graphs**
(Graphiti/Zep); when a graph is worth its cost; and how to keep it correct.

**Where this fits:** builds on RAG (Ch 17–18), vectorless retrieval (Ch 19), structured output
(Ch 10) and bi-temporal memory (Ch 16). Personal knowledge graphs for personalization are in
Ch 22; maintaining graph pipelines in production is in Ch 23.

---

## 1. The idea in plain words

A **triple** is the atom of a knowledge graph:

```
(subject)        —[predicate]→       (object)
(Payments API)   —[OWNED_BY]→        (Team Falcon)
(Team Falcon)    —[MANAGED_BY]→      (Priya Raman)
(Payments API)   —[DEPENDS_ON]→      (libcrypto-1.0)
(libcrypto-1.0)  —[STATUS]→          (deprecated)
```

Question: *"Which managers own services that depend on deprecated libraries?"*

- **Vector RAG**: retrieves chunks *similar* to the question — but the answer is spread over
  four facts in different documents. It can't join them.
- **Knowledge graph**: follow the edges: deprecated library ← DEPENDS_ON ← service → OWNED_BY →
  team → MANAGED_BY → manager. Exact, explainable, complete.

Graphs shine for: **multi-hop** questions, **aggregation across entities** ("how many vendors in
Germany have expired contracts?"), **global sense-making** ("main themes"), **explainability**
(the path *is* the explanation), and **integrating data** from many sources around shared
entities.

---

## 2. Analogy

**A detective's corkboard.** Photos (entities) pinned up, strings (relationships) between them,
notes on each string (properties: since when, according to whom). A pile of case files
(documents) holds the same information, but only the board lets you *see* that the accountant
knew the driver who rented the van.

Where it breaks: someone has to build and maintain the board. Wrong strings (bad extraction) or
two photos of the same person (duplicate entities) make it actively misleading.

---

## 3. How it works

### 3.1 Two graph models

| | **Property graph** | **RDF** |
|---|---|---|
| Unit | Nodes and relationships, both with properties | Triples (subject, predicate, object) with URIs |
| Schema | Labels + relationship types (+ optional constraints) | Ontologies (RDFS/OWL) — formal semantics, reasoning |
| Query language | **Cypher** (and the GQL standard), Gremlin | **SPARQL** |
| Typical stores | Neo4j, Memgraph, Amazon Neptune, FalkorDB, Postgres + Apache AGE | Triple stores (e.g. GraphDB, Stardog), Amazon Neptune |
| Common in | Application/LLM projects | Enterprise data integration, life sciences, publishing, government |

Most LLM projects use property graphs and Cypher.

### 3.2 The schema (ontology) comes first

Decide the **entity types** and **relationship types** you need *before* extraction:

```
Entities:      Service, Team, Person, Library, Customer, Contract
Relationships: OWNED_BY(Service→Team), MANAGED_BY(Team→Person), DEPENDS_ON(Service→Library),
               USES(Customer→Service), HAS_CONTRACT(Customer→Contract)
Properties:    Library.status, Contract.end_date, …
```

Without a schema, LLM extraction invents hundreds of near-duplicate relation types
("owns", "is owned by", "belongs to", "maintained by") and the graph becomes unqueryable.

### 3.3 Building a graph with an LLM

```
documents → chunks
   → EXTRACT entities + relationships per chunk (structured output constrained to the schema, Ch 10)
   → RESOLVE entities: "IBM" = "International Business Machines" = "I.B.M."
   → STORE with provenance: every node/edge records source chunk id(s)
   → VALIDATE: constraints (a Service has exactly one owner), sample human review
   → UPDATE incrementally as documents change; delete edges whose sources were deleted
```

**Entity resolution** is the hardest part and decides graph quality. Combine: normalization
(case, punctuation, legal suffixes), alias tables, embedding similarity of names + context, and an
LLM or human to confirm uncertain merges. Track a merge precision metric.

### 3.4 Querying

| Method | How | Good for |
|---|---|---|
| **Traversal tools** | Agent tools like `neighbors(entity, relation)`, `path(a, b)` | Agents exploring step by step |
| **Text-to-Cypher** | LLM writes Cypher from the schema; run in a **read-only** transaction with timeouts | Precise questions, aggregations |
| **Graph + vector hybrid** | Vector search finds entry entities/chunks → expand their graph neighbourhood → give that subgraph (as text) plus source chunks to the LLM | Most practical "GraphRAG" setups |
| **Graph algorithms** | PageRank, community detection, shortest paths | Ranking, themes, influence |

### 3.5 Microsoft GraphRAG

A research pipeline (open-sourced in 2024) that popularized the term:

```
INDEXING (expensive, LLM-heavy)
chunks → LLM extracts entities, relationships, claims → graph
       → community detection (hierarchical Leiden algorithm) → nested communities
       → LLM writes a "community report" (summary) for every community at every level

QUERYING
LOCAL search  — entity-centric: find entities relevant to the question, gather their
                neighbours, relationships, source text and related community reports
GLOBAL search — corpus-wide questions ("what are the main themes?"): map-reduce over
                community reports: each report answers partially → reduce into one answer
(also DRIFT search — combines local and global ideas)
```

Its key insight: **global questions** can't be answered by retrieving a few chunks — you need
pre-computed summaries of the whole corpus's structure. Its key cost: **indexing is expensive**
(many LLM calls per chunk plus summaries for every community), and the project itself warns to
start small. As of 2026 its repository states it is **largely in maintenance mode** — the ideas
remain influential; check activity before adopting any specific implementation.

### 3.6 Lighter and newer graph-RAG designs

| Design | Core idea | Why it matters |
|---|---|---|
| **LazyGraphRAG** (Microsoft Research) | Defer expensive LLM summarization to **query time**; build a lightweight concept graph at indexing | Indexing cost near vector RAG; still supports global-style questions |
| **LightRAG** | Graph + vector **dual-level** retrieval: low-level (specific entities/relations) and high-level (broader themes); query modes such as naive, local, global, hybrid, mix; **incremental updates and deletion** | Much cheaper than full GraphRAG; easier to keep current |
| **HippoRAG / HippoRAG 2** | Inspired by the hippocampus: open information extraction builds a graph; the query's entities seed **Personalized PageRank**, which spreads relevance through the graph to rank passages | Strong on multi-hop "associative" questions; efficient offline indexing; framed as long-term memory for LLMs |
| **KAG** (Knowledge Augmented Generation) | Combines KG and text with logical-form-guided reasoning for professional domains | Precision-sensitive domains (finance, medicine, government) |
| **RAPTOR** | Not a KG: recursively **cluster and summarize** chunks into a tree of summaries; retrieve from any level | Good for questions at different levels of abstraction |

### 3.7 Temporal knowledge graphs

Facts change (Ch 16). A **temporal knowledge graph** stores when each edge was valid and when
it was recorded:

```
(Priya)-[WORKS_AT {valid_from: 2023-01, valid_to: 2026-03, recorded_at: 2023-01}]->(Acme)
(Priya)-[WORKS_AT {valid_from: 2026-03, valid_to: null,    recorded_at: 2026-03}]->(Globex)
```

Graphiti (the open-source engine behind Zep's memory) builds bi-temporal knowledge graphs
incrementally from conversation "episodes" — a graph-shaped version of agent memory (Ch 16, 22).

### 3.8 Is a graph worth it?

| Build a graph when | Don't when |
|---|---|
| Questions are about **relationships**, chains, or aggregations across entities | Questions are FAQ-style lookups a chunk answers |
| You need **global** summaries of large corpora | The corpus is small (use CAG, Ch 19) |
| Explainability/lineage is required (compliance, audits) | No one will own schema + entity resolution + updates |
| Several sources describe the **same entities** (CRM + tickets + contracts) | Data is already relational — query the database (Ch 19) |

The honest cost: schema design, extraction quality, entity resolution, update pipelines and graph
QA are ongoing work. FDEs should prototype on a slice and measure before committing.

### 3.9 Keeping a graph correct

- **Schema constraints** (uniqueness, required properties, allowed relation endpoints).
- **Provenance** on every node and edge → delete/recompute when sources change.
- **Quality metrics**: extraction precision/recall on a labelled sample; duplicate-entity rate;
  orphan nodes; contradiction count.
- **Human-in-the-loop** review for low-confidence merges and high-impact edges.
- **Temporal edges** instead of overwrites.

---

## 4. Code

### 4.1 Extract triples with a schema (LLM, structured output)

```python
# kg_extract.py
import json
import ollama

ENTITY_TYPES = ["Service", "Team", "Person", "Library"]
RELATIONS = ["OWNED_BY", "MANAGED_BY", "DEPENDS_ON", "HAS_STATUS"]

SCHEMA = {"type": "object", "properties": {"triples": {"type": "array", "items": {
    "type": "object", "properties": {
        "subject": {"type": "string"}, "subject_type": {"type": "string", "enum": ENTITY_TYPES + ["Status"]},
        "relation": {"type": "string", "enum": RELATIONS},
        "object": {"type": "string"}, "object_type": {"type": "string", "enum": ENTITY_TYPES + ["Status"]}},
    "required": ["subject", "subject_type", "relation", "object", "object_type"]}}}, "required": ["triples"]}

def extract(chunk_id, text):
    r = ollama.chat(model="llama3.2", format=SCHEMA, options={"temperature": 0}, messages=[{
        "role": "user", "content": f"Extract facts as triples using ONLY these relations: {RELATIONS}.\n\n{text}"}])
    triples = json.loads(r["message"]["content"])["triples"]
    return [{**t, "source": chunk_id} for t in triples]      # provenance on every edge

if __name__ == "__main__":
    print(extract("wiki#7", "The Payments API is owned by Team Falcon, which Priya Raman manages. "
                            "It depends on libcrypto-1.0, which is now deprecated."))
```

### 4.2 A tiny graph: resolution, traversal, multi-hop, Personalized PageRank (offline)

```python
# kg_graph.py — pure Python, no graph database needed to learn the ideas
import re
from collections import defaultdict, deque

ALIASES = {"falcon team": "team falcon", "payments service": "payments api"}

def canon(name):
    key = re.sub(r"[^a-z0-9 \-.]", "", name.lower()).strip()
    return ALIASES.get(key, key)                       # entity resolution (rules + alias table)

class Graph:
    def __init__(self):
        self.out = defaultdict(list)                   # node -> [(relation, node, source)]
        self.inc = defaultdict(list)                   # node -> [(relation, node, source)] reversed

    def add(self, s, rel, o, source):
        s, o = canon(s), canon(o)
        if (rel, o, source) not in self.out[s]:
            self.out[s].append((rel, o, source))
            self.inc[o].append((rel, s, source))

    def neighbors(self, node, relation=None, reverse=False):
        edges = (self.inc if reverse else self.out)[canon(node)]
        return [(r, n, src) for r, n, src in edges if relation in (None, r)]

    def path(self, start, goal, max_hops=4):
        """Breadth-first search over edges in both directions; returns the explanation path."""
        start, goal = canon(start), canon(goal)
        queue, seen = deque([(start, [])]), {start}
        while queue:
            node, trail = queue.popleft()
            if node == goal:
                return trail
            if len(trail) >= max_hops:
                continue
            for r, n, src in self.out[node] + [(f"~{r}", n, src) for r, n, src in self.inc[node]]:
                if n not in seen:
                    seen.add(n)
                    queue.append((n, trail + [(node, r, n, src)]))
        return None

    def personalized_pagerank(self, seeds, alpha=0.85, iters=30):
        """HippoRAG-style: start from query entities, spread relevance along edges."""
        nodes = set(self.out) | set(self.inc)
        seeds = {canon(s) for s in seeds} & nodes
        if not seeds:
            return {}
        reset = {n: (1 / len(seeds) if n in seeds else 0.0) for n in nodes}
        rank = dict(reset)
        for _ in range(iters):
            new = {n: (1 - alpha) * reset[n] for n in nodes}
            for n in nodes:
                nbrs = [m for _, m, _ in self.out[n]] + [m for _, m, _ in self.inc[n]]   # undirected walk
                for m in nbrs:
                    new[m] += alpha * rank[n] / len(nbrs)
            rank = new
        return dict(sorted(rank.items(), key=lambda kv: -kv[1]))

if __name__ == "__main__":
    g = Graph()
    for s, r, o, src in [
        ("Payments API", "OWNED_BY", "Team Falcon", "wiki#7"),
        ("Falcon team", "MANAGED_BY", "Priya Raman", "hr#2"),           # alias resolves to team falcon
        ("Payments service", "DEPENDS_ON", "libcrypto-1.0", "deps#1"),  # alias resolves to payments api
        ("libcrypto-1.0", "HAS_STATUS", "deprecated", "sec#4"),
        ("Search API", "OWNED_BY", "Team Owl", "wiki#9"),
        ("Search API", "DEPENDS_ON", "libjson-2", "deps#3"),
    ]:
        g.add(s, r, o, src)

    # Multi-hop: which managers own services depending on deprecated libraries?
    for lib_rel, lib, _ in g.neighbors("deprecated", "HAS_STATUS", reverse=True):
        for _, service, _ in g.neighbors(lib, "DEPENDS_ON", reverse=True):
            for _, team, _ in g.neighbors(service, "OWNED_BY"):
                for _, manager, src in g.neighbors(team, "MANAGED_BY"):
                    print(f"{manager} manages {team}, owner of {service}, which depends on deprecated {lib}")

    print("explanation path:", g.path("Priya Raman", "deprecated"))
    print("PPR from 'libcrypto-1.0':", list(g.personalized_pagerank(["libcrypto-1.0"]).items())[:4])
```

The path doubles as an **explanation** with **sources** — something vector RAG can't give you.

### 4.3 The same in Neo4j with Cypher (for reference)

```bash
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/devpassword neo4j:5
pip install neo4j
```

```python
# kg_neo4j.py
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "devpassword"))

def add_triple(tx, s, s_type, rel, o, o_type, source):
    # MERGE = create if missing (idempotent). Labels/relation types can't be parameters,
    # so they come from our fixed schema enums — never from raw model text.
    assert rel in {"OWNED_BY", "MANAGED_BY", "DEPENDS_ON", "HAS_STATUS"}
    tx.run(f"MERGE (a:{s_type} {{name: $s}}) MERGE (b:{o_type} {{name: $o}}) "
           f"MERGE (a)-[r:{rel}]->(b) SET r.source = $source", s=s, o=o, source=source)

QUERY = """
MATCH (m:Person)<-[:MANAGED_BY]-(t:Team)<-[:OWNED_BY]-(s:Service)-[:DEPENDS_ON]->(l:Library)
      -[:HAS_STATUS]->(:Status {name: 'deprecated'})
RETURN m.name AS manager, t.name AS team, s.name AS service, l.name AS library
"""

with driver.session() as session:
    session.execute_write(add_triple, "Payments API", "Service", "OWNED_BY", "Team Falcon", "Team", "wiki#7")
    # ... add the rest ...
    rows = session.execute_read(lambda tx: tx.run(QUERY).data())    # read-only transaction
    print(rows)
```

For **text-to-Cypher**, give the model the schema, run its query only via `execute_read` with a
database user that has read-only rights, add timeouts and result limits — the same safety rules as
text-to-SQL (Ch 19).

---

## 5. Production view

| Concern | Measure / do |
|---|---|
| Extraction quality | Precision/recall of triples on a labelled sample of 50–100 chunks |
| Entity resolution | Duplicate rate; merge precision; review queue for low-confidence merges |
| Indexing cost | LLM calls and $ per 1,000 chunks; use smaller models for extraction, cache document prefixes |
| Freshness | Incremental updates by source; delete edges whose sources were deleted |
| Query safety | Read-only transactions, timeouts, limits; schema-constrained text-to-Cypher |
| Answer quality | Separate evals for multi-hop and global questions vs your vector baseline (Ch 23) |
| Explainability | Return paths and sources with answers |

---

## 6. Common mistakes

- Extracting without a schema → hundreds of synonym relations.
- Skipping entity resolution → "IBM" and "International Business Machines" never connect.
- No provenance → can't fix or delete wrong facts.
- Building full GraphRAG on day one for a FAQ bot.
- Letting model text become Cypher labels/relationship types (injection; use enums).
- Overwriting edges instead of making them temporal.

---

## 7. Practice

**Level 1**
1. Run `kg_graph.py`. Add a second deprecated library and a service that depends on it. Does the
   multi-hop query find both managers?
2. Run `kg_extract.py` on 5 sentences you write. Count wrong or missing triples.

**Level 2**
3. Build a 30-sentence corpus about a fictional company (services, teams, people, libraries).
   Extract → resolve → load into `Graph` or Neo4j. Write 10 multi-hop questions and compare answers
   from (a) the graph and (b) Ch 17 hybrid RAG over the same sentences.
4. Implement a simple **community summary**: group nodes by connected component (or use a
   community-detection library), have the LLM summarize each group, then answer "what are the
   main areas of this organization?" by map-reducing over the summaries (global search, mini version).

**Level 3**
5. Implement **HippoRAG-style retrieval**: map each passage to the entities it mentions; for a
   question, extract its entities, run Personalized PageRank from them, score passages by the sum
   of their entities' ranks, and return the top 3. Compare recall@3 with dense retrieval on your
   multi-hop questions.

---

## 8. Check yourself

1. What is a triple? Give an example.
2. Why can't vector RAG reliably answer multi-hop questions?
3. Why must you define a schema before LLM extraction?
4. What is entity resolution and why does graph quality depend on it?
5. Microsoft GraphRAG: what's the difference between local and global search?
6. How does HippoRAG use Personalized PageRank?
7. Give two reasons *not* to build a knowledge graph.

<details>
<summary>Answers</summary>

1. A (subject, predicate, object) fact, e.g. (Payments API, OWNED_BY, Team Falcon).
2. The facts needed are spread across several documents; similarity search retrieves chunks
   similar to the question, not the chain of connected facts, and can't join them.
3. Without allowed entity/relation types, extraction produces many inconsistent synonyms, making
   the graph fragmented and unqueryable.
4. Deciding which mentions refer to the same real entity and merging them. Without it, the same
   thing appears as several disconnected nodes and multi-hop paths break.
5. Local: start from entities relevant to the question and use their neighbourhood and related
   text. Global: answer corpus-wide questions by map-reducing over pre-computed community summaries.
6. It seeds PageRank with the question's entities and lets relevance spread through the graph's
   connections, then ranks passages by the scores of entities they contain — finding associated
   facts several hops away.
7. Any two: questions are simple lookups; the corpus is small; data is already relational; no one
   can own schema/entity resolution/updates; indexing cost isn't justified by measured gains.

</details>

---

## 9. Key terms

**knowledge graph** · **entity** · **relationship** · **triple** · **ontology / schema** ·
**property graph** · **RDF** · **Cypher** · **SPARQL** · **entity resolution** · **provenance** ·
**text-to-Cypher** · **graph + vector hybrid** · **GraphRAG** · **community detection (Leiden)** ·
**community report** · **local vs global search** · **LazyGraphRAG** · **LightRAG** · **HippoRAG** ·
**Personalized PageRank** · **KAG** · **RAPTOR** · **temporal knowledge graph** · **Graphiti**

Next: [Chapter 21 — Document and multimodal RAG →](21-document-multimodal-rag.md)
