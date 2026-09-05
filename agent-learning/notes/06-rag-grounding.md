# Module 6/7 — RAG (grounding support_chat in real documents)
*2026-09-05*

## What I built
Real embedding-based retrieval in `step8_context_budget.py` — `cosine_similarity()` and
`retrieve()`, using `ollama.embed(model="nomic-embed-text")` over a 3-doc corpus
(`store_policy.txt`, `shipping_policy.txt`, `warranty_policy.txt`).

## The problem this solves
`support_chat()` was asked "What's your return policy?" with no real policy document
anywhere in its context. The model answered anyway — fluently, confidently, and
completely made up (a fake 30-day window, a fake link). RAG means retrieving the actual
document and putting it in context so the model answers from something real instead of
guessing from training data.

## What surprised me
Two things:
1. I assumed you always need embeddings for RAG. For a single small file, you don't —
   just put the whole file in the system prompt. Embeddings only pay for themselves once
   the corpus is too big to fit in context and you need to rank which piece is relevant.
2. Even with the RIGHT document retrieved and injected, the model still invented a
   detail that wasn't in the source text ("send a clear photo of the damage" — not
   anywhere in `warranty_policy.txt`). Grounding reduces hallucination, it doesn't erase
   it.

## The failure I caused on purpose
Asked a question that straddles two documents: "Can I get a warranty repair on a shirt
that arrived damaged?" Top-1 retrieval picked only `warranty_policy.txt` (score 0.716)
and never surfaced `store_policy.txt`'s also-relevant 60-day damaged-item return option.
Real information loss, caused by hardcoding k=1 — not a bug, a design limit I hadn't
accounted for.

## Numbers
- "What's your return policy?" → retrieved `store_policy.txt`, score 0.695, context 237
  tokens, answer matched the file exactly (14-day window, 60-day damaged-item window,
  instant store credit, 3-7 day refund).
- Damaged-shirt/warranty question → retrieved `warranty_policy.txt` only, score 0.716,
  context 176 tokens, answer included one invented detail not present in the source doc.

## What I would do differently
Not hardcode top-1. Either use a similarity threshold (include every doc above a cutoff)
or retrieve top-k with k>1 for the first version, instead of assuming one document is
always enough.

## Open question
How do you actually decide the right k or threshold for a real corpus, before you have
enough real user questions to tune it against? Left open — revisit if the corpus grows
past 3 docs.

## Known gaps (not fixed yet, logged in PROGRESS.md)
- `retrieve()` re-embeds all N documents from scratch on every call — should cache doc
  embeddings once and only embed the incoming question each time.
- No "answer only from the provided document" constraint in the system prompt — the
  natural next eval case once Module 8 (evals, deliberately last) is reached.
