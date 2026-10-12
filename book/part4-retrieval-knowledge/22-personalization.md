# Chapter 22 — Personalization and personal knowledge

> **Personalization** means adapting what the agent says and does to *this* person — their
> preferences, history, situation and corrections. Done well, it feels like a great
> assistant. Done badly, it's wrong, stale, or creepy. The difference is in how beliefs
> about the user are **earned, used, corrected and forgotten**.

**You will learn:** explicit, implicit and contextual signals; why **corrections** are the most
valuable signal; designing a user model with **confidence that rises slowly and falls fast**,
plus decay; where personalization enters a system (prompt, retrieval, style, tools,
proactivity); **personal knowledge graphs** and memory stores (Mem0, Zep/Graphiti, Letta,
LangMem); personalized retrieval and reranking; recommendation basics; the **eight
personalization failure modes**; privacy, consent and on-device agents; and how to evaluate it.

**Where this fits:** builds on memory (Ch 16 — the storage and policies), knowledge graphs (Ch 20 —
personal graphs), retrieval (Ch 17–18 — personalized ranking). Proactive personal agents use
schedulers (Ch 26); privacy and compliance continue in Ch 36; user feedback UX is Ch 44.

---

## 1. The idea in plain words

| Signal | Example | Trust |
|---|---|---|
| **Explicit** | "I'm vegetarian." Settings: language = Tamil | High — the user said it |
| **Implicit** | Always picks the cheapest shipping; skips long answers; buys size 42 | Medium — inferred from behavior, can be wrong |
| **Contextual** | It's 11pm; user is on mobile; currently writing a contract | Short-lived — true *now* |
| **Corrections** | "No, I meant my *work* address." "Stop suggesting running shoes." | **Highest value** — a labelled example about this person, at the moment you got it wrong |

A **user model** (profile) turns these signals into beliefs the system can use, each with a
confidence, a source and a date.

---

## 2. Analogy

**A good neighbourhood shopkeeper.** After a few visits they remember your usual order — but
they still ask "the usual?" instead of silently packing it. If you say "not today, I'm on a diet",
they adjust immediately. They don't mention your medical prescription in front of other customers.
And if you move away for a year, they don't assume you still want the same things when you return.

That's the whole chapter: **remember, but ask; adjust fast; be discreet; let beliefs fade.**

---

## 3. How it works

### 3.1 A user model with honest confidence

Every belief about the user is a record:

```
{key: "shoe_size", value: "42", confidence: 0.6, source: "inferred:purchases",
 evidence_count: 3, updated_at: "2026-09-30", sensitive: false}
```

**Confidence dynamics** — rise slowly, fall fast, fade with time:

```
explicit statement by user         → set confidence high (e.g. 0.95)
each new supporting observation    → +0.1, capped (e.g. 0.9 for inferred beliefs)
a contradiction or correction      → −0.25 (or replace immediately if the user stated it)
time without new evidence          → decay (e.g. half-life of ~6 months for inferred preferences)
use a belief only if confidence ≥ threshold for that use (higher threshold for actions than for ranking)
```

Why asymmetric? Wrongly personalizing is more costly than not personalizing. One contradiction is
strong evidence your belief is wrong; one more confirming click is weak evidence it's right.

**The `corrections` log** is the most valuable — and most often discarded — personalization data.
Store every correction (what we assumed, what the user said, when). It fixes this user's profile
and, aggregated, shows where your inference logic is systematically wrong.

### 3.2 Where personalization enters the system

| Layer | Example | Risk level |
|---|---|---|
| **Style** | Language, tone, answer length, format, expertise level | Low — start here |
| **Retrieval ranking** | Boost documents for the user's product, region, role | Low–medium (don't *hide* things) |
| **Content** | Recommendations, examples relevant to the user | Medium |
| **Tool defaults** | Pre-fill shipping address, preferred payment | Medium–high → confirm before acting |
| **Proactive actions** | "Your usual order is back in stock — reorder?" (Ch 26) | High → relevance gate, caps, opt-out |

**Rule: personalize style before substance, ranking before filtering, suggestions before actions.**

### 3.3 Injecting the profile into the prompt

Don't dump the whole profile. Select the **few beliefs relevant to this request**, above the
confidence threshold, and label them as beliefs:

```
<user_context>
Known preferences (from past interactions; may be outdated — ask if it matters):
- Prefers short answers (confidence 0.8, inferred)
- Language: English and Tamil (stated by user)
- Usual shoe size: 42 (confidence 0.6, inferred from 3 purchases)
</user_context>
```

### 3.4 Personal knowledge graphs and memory stores

A **personal knowledge graph** models the user's world: people (manager: Priya), projects, places,
devices, preferences, and how they relate — with temporal edges (Ch 20) because life changes.
Tools you'll meet:

| Tool | Idea |
|---|---|
| **Mem0** | A memory layer: extracts memories from conversations, updates/merges them, searches them by relevance |
| **Zep / Graphiti** | Temporal knowledge-graph memory: bi-temporal facts built incrementally from conversation "episodes" |
| **Letta** (from the MemGPT research) | Agents with editable memory blocks they manage themselves (virtual context, Ch 16) |
| **LangMem** | Memory tools and background memory management for LangGraph agents |
| Built-in assistant memory | Major consumer assistants now offer user-visible memory that users can view and delete |

All of them implement the Ch 16 ideas — write policy, read policy, updates, deletion. Evaluate them
on *your* cases before adopting.

### 3.5 Personalized retrieval and reranking

```
final_score(doc) = relevance(query, doc) + β · affinity(user, doc)
affinity examples: doc is about the user's product (+), user's region (+), user already read it (−),
                   user's expertise level matches the doc's level (+)
```

Keep β small enough that **relevance still wins** — a highly relevant document must not be buried
because it doesn't match the profile (that's how filter bubbles start). Log both scores so you can
explain rankings.

### 3.6 Recommendation basics (enough to talk to a data science team)

| Method | Idea | Weakness |
|---|---|---|
| **Content-based** | Recommend items similar to what the user liked (embeddings, Ch 06) | Narrow; "more of the same" |
| **Collaborative filtering** | Users similar to you liked X | Cold start for new users and new items |
| **Hybrid / two-tower models** | Learn user and item embeddings together | Needs data and ML infrastructure |
| **LLM layer** | Explain recommendations, handle natural-language requests, rerank candidates | Cost; must stay grounded in real inventory |

**Exploration vs exploitation:** always show some items *outside* the user's known taste, or you'll
never learn they changed.

### 3.7 The eight personalization failure modes

| # | Failure | Example | Guard |
|---|---|---|---|
| 1 | **Overfitting** | One gift purchase of baby clothes → months of baby recommendations | Require repeated evidence; low weight for single events; "this was a gift" correction |
| 2 | **Stale beliefs** | Still recommends the city they left a year ago | Decay; bi-temporal facts; reconfirm old beliefs |
| 3 | **Creepy recall** | Unprompted: "Since you were looking at divorce lawyers…" | Never surface sensitive memories unprompted; sensitive categories opt-in |
| 4 | **Filter bubble** | Only ever sees one brand/viewpoint | Exploration; cap affinity boost; diversity in results |
| 5 | **Silent wrongness** | Wrong assumption shapes answers and is never visible | Show "based on your preference for X" so users can correct it |
| 6 | **No escape hatch** | User can't turn it off or fix a belief | View/edit/delete memory; "don't personalize" switch |
| 7 | **Cross-contamination** | Shared family account; another user's data leaks into answers | Per-person profiles, scoped memory (Ch 16), context separation (work vs personal) |
| 8 | **Cold-start harm** | New user gets bad defaults or stereotyped guesses | Neutral defaults; ask 1–2 onboarding questions; never infer sensitive traits |

### 3.8 Privacy, consent and on-device agents

- **Consent and transparency:** tell users what is remembered and why; let them see it.
- **Purpose limitation and minimization:** store only what serves the user; don't infer sensitive
  attributes (health, religion, politics, sexuality, finances) unless the user explicitly opts in
  for a clear benefit.
- **User rights:** access, correction, deletion, objection to profiling (GDPR-style rights — check
  the regulations that apply to your customer, Ch 36).
- **Retention:** expire inferred beliefs; delete on request across all stores (Ch 16).
- **On-device / local personal agents:** keep personal data on the user's device and run a small
  model locally (Ch 08, 39). Strongest privacy, weaker model; a common hybrid sends only
  non-sensitive, minimized context to a cloud model.

### 3.9 Evaluating personalization

| Evaluation | Question it answers |
|---|---|
| **Counterfactual tests** | Same request, different profiles → are the differences appropriate (and absent when they shouldn't exist)? |
| **Held-out history** | Does using the profile predict what the user later chose/accepted? |
| **Online metrics** | Acceptance rate, **edit/override rate**, "not relevant" feedback, opt-out rate, complaints |
| **Safety tests** | Creepy-recall prompts, sensitive-inference attempts, shared-account scenarios |
| **Cold-start tests** | Quality for users with zero history |

Watch the **override rate** (users editing or rejecting personalized output): rising overrides mean
your beliefs are wrong (Ch 33).

---

## 4. Code

### 4.1 A user model with asymmetric confidence, decay and corrections (offline)

```python
# user_model.py
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
SENSITIVE_KEYS = {"health", "religion", "politics", "finances"}
HALF_LIFE_DAYS = 180

@dataclass
class Belief:
    value: str
    confidence: float
    source: str                     # "stated" or "inferred:<signal>"
    updated_at: datetime
    evidence: int = 1

@dataclass
class UserModel:
    user_id: str
    beliefs: dict = field(default_factory=dict)
    corrections: list = field(default_factory=list)
    consented_sensitive: set = field(default_factory=set)

    def stated(self, key, value, now=None):
        self.beliefs[key] = Belief(value, 0.95, "stated", now or datetime.now(UTC))

    def observe(self, key, value, signal, now=None):
        now = now or datetime.now(UTC)
        b = self.beliefs.get(key)
        if b is None:
            self.beliefs[key] = Belief(value, 0.3, f"inferred:{signal}", now)
        elif b.value == value:
            cap = 0.95 if b.source == "stated" else 0.9
            b.confidence, b.evidence, b.updated_at = min(cap, b.confidence + 0.1), b.evidence + 1, now
        else:                                            # contradiction: fall fast
            b.confidence -= 0.25
            if b.confidence < 0.3:
                self.beliefs[key] = Belief(value, 0.3, f"inferred:{signal}", now)

    def correct(self, key, wrong, right, now=None):
        now = now or datetime.now(UTC)
        self.corrections.append({"key": key, "assumed": wrong, "user_said": right, "at": now.isoformat()})
        self.stated(key, right, now)                     # the user told us — trust it

    def effective_confidence(self, key, now=None):
        b = self.beliefs[key]
        if b.source == "stated":
            return b.confidence
        age_days = ((now or datetime.now(UTC)) - b.updated_at).days
        return b.confidence * 0.5 ** (age_days / HALF_LIFE_DAYS)     # decay inferred beliefs

    def for_prompt(self, relevant_keys, threshold=0.5, now=None):
        lines = []
        for key in relevant_keys:
            if key not in self.beliefs:
                continue
            if key in SENSITIVE_KEYS and key not in self.consented_sensitive:
                continue                                 # never use sensitive data without opt-in
            conf = self.effective_confidence(key, now)
            if conf >= threshold:
                b = self.beliefs[key]
                lines.append(f"- {key}: {b.value} (confidence {conf:.2f}, {b.source})")
        if not lines:
            return ""
        return ("<user_context>\nKnown preferences (may be outdated — ask if it matters):\n"
                + "\n".join(lines) + "\n</user_context>")

if __name__ == "__main__":
    t0 = datetime(2026, 1, 1, tzinfo=UTC)
    u = UserModel("user-42")
    for i in range(4):
        u.observe("shoe_size", "42", "purchase", now=t0 + timedelta(days=i * 10))
    print("after 4 purchases:", round(u.beliefs["shoe_size"].confidence, 2))
    u.observe("shoe_size", "40", "purchase", now=t0 + timedelta(days=50))    # a gift for someone?
    print("after 1 contradiction:", round(u.beliefs["shoe_size"].confidence, 2))
    print("decayed 1 year later:", round(u.effective_confidence("shoe_size", now=t0 + timedelta(days=400)), 2))
    u.stated("language", "Tamil")
    u.correct("delivery_address", wrong="home", right="work")
    u.observe("health", "diabetic", "purchase")       # inferred sensitive trait — must not be used
    print(u.for_prompt(["shoe_size", "language", "delivery_address", "health"], now=t0 + timedelta(days=60)))
    print("corrections log:", u.corrections)
```

### 4.2 Personalized reranking with an explanation

```python
# personal_rerank.py
def rerank(results, user_tags, beta=0.08):
    """results: [{'id', 'relevance', 'tags'}]. Relevance dominates; affinity nudges."""
    ranked = []
    for r in results:
        overlap = sorted(set(r["tags"]) & set(user_tags))
        affinity = min(len(overlap), 2) / 2                 # capped: avoid filter bubbles
        ranked.append({**r, "score": r["relevance"] + beta * affinity,
                       "because": f"matches your interest in {', '.join(overlap)}" if overlap else ""})
    return sorted(ranked, key=lambda x: -x["score"])

results = [{"id": "trail-guide", "relevance": 0.81, "tags": ["trail", "running"]},
           {"id": "returns-policy", "relevance": 0.90, "tags": ["policy"]},
           {"id": "city-shoes", "relevance": 0.80, "tags": ["city", "walking"]}]
for r in rerank(results, user_tags=["trail", "running"]):
    print(f"{r['id']:15s} {r['score']:.2f}  {r['because']}")
```

The most relevant result (the policy page) still ranks first. Personalization only reordered the two
nearly-tied guides — it nudged, it didn't override.

---

## 5. Production view

| Signal | Meaning | Action |
|---|---|---|
| Override / edit rate on personalized outputs | Beliefs are wrong | Inspect corrections log; tighten inference rules |
| Opt-out rate | Personalization feels intrusive or unhelpful | Reduce scope; better explanations; sensitive-data audit |
| Complaints tagged "creepy" | Sensitive or surprising recall | Hard rules: no unprompted sensitive recall |
| Diversity of recommendations | Filter-bubble risk | Exploration slots; cap affinity |
| Cold-start quality | New-user experience | Neutral defaults; onboarding questions |
| Deletion SLA | Compliance | Fan-out deletion across stores (Ch 16) |

---

## 6. Common mistakes

- Treating one event as a preference.
- Never decaying inferred beliefs.
- Using inferred sensitive traits.
- Hiding results that don't match the profile instead of ranking them lower.
- Acting (orders, emails) on low-confidence beliefs without confirmation.
- Throwing away corrections after applying them once.
- One profile per *account* when several people share it.

---

## 7. Practice

**Level 1**
1. Run `user_model.py`. Change the half-life to 30 days. How does the year-later confidence change?
2. Run `personal_rerank.py` with `beta=0.5`. What goes wrong? Why should β stay small?

**Level 2**
3. Add a `profile` tool to the Ch 14 agent that returns `for_prompt(...)` for the keys relevant to the
   current request, and a `correct_preference` tool. Write 5 conversations where the user corrects the
   agent and check the profile updates.
4. Write 10 counterfactual tests: the same request with two different profiles. Decide for each what
   *should* differ and what must *not* differ (e.g. return policy facts). Run and grade.

**Level 3**
5. Build a small **personal knowledge graph** for one user from 20 synthetic chat messages (people,
   projects, places, preferences), with temporal edges (Ch 20). Answer "who should I invite to the
   project X review?" using the graph, and show the path used as the explanation. Add a "forget this
   person" operation and test it removes all related edges.

---

## 8. Check yourself

1. Why are corrections the most valuable personalization signal?
2. Explain "rise slowly, fall fast" and why it's asymmetric.
3. In what order should you introduce personalization across layers, and why?
4. Name the eight personalization failure modes.
5. How do you keep personalized ranking from creating a filter bubble?
6. What is a counterfactual personalization test?

<details>
<summary>Answers</summary>

1. They're explicit, labelled evidence about this specific user, captured exactly where the system
   was wrong — they fix the profile and reveal systematic inference errors.
2. Confidence increases a little with each supporting observation but drops a lot on a contradiction,
   because acting on a wrong belief costs more than not personalizing, and a contradiction is stronger
   evidence than one more confirmation.
3. Style → retrieval ranking → content suggestions → tool defaults → proactive actions; risk and
   impact of mistakes increase along that order.
4. Overfitting, stale beliefs, creepy recall, filter bubble, silent wrongness, no escape hatch,
   cross-contamination, cold-start harm.
5. Keep relevance dominant (small β, capped affinity), add exploration/diversity, and never filter
   out results only because they don't match the profile.
6. Running the same request with different user profiles and checking that outputs differ only in
   the ways they should (and stay identical where facts must not change).

</details>

---

## 9. Key terms

**personalization** · **explicit / implicit / contextual signals** · **corrections log** · **user
model / profile** · **belief confidence** · **decay / half-life** · **personal knowledge graph** ·
**Mem0 / Zep / Graphiti / Letta / LangMem** · **personalized reranking** · **affinity** ·
**content-based vs collaborative filtering** · **cold start** · **exploration vs exploitation** ·
**filter bubble** · **creepy recall** · **escape hatch** · **on-device agent** ·
**counterfactual test** · **override rate**

Next: [Chapter 23 — Retrieval in production →](23-retrieval-in-production.md)
