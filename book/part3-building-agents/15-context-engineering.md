# Chapter 15 — Context engineering

> **Context engineering** is deciding, at every step, exactly what goes into the model's
> context window — the smallest set of high-signal tokens that lets the model do the next
> step well. For agents, it matters more than prompt wording.

**You will learn:** what fills an agent's context, the four moves (**write, select,
compress, isolate**), the four ways context goes bad (poisoning, distraction, confusion,
clash), compaction with preserve/drop rules, tool-result clearing, just-in-time retrieval,
structured note-taking, **Skills** and progressive disclosure, project memory files
(AGENTS.md), cache-friendly context, and how to measure all of it.

**Where this fits:** builds on tokens and context rot (Ch 02), cost (Ch 03), prompt
engineering (Ch 09), caching (Ch 12) and the agent loop (Ch 14 — context grows every
iteration). "Write" leads to memory (Ch 16); "select" leads to retrieval (Ch 17–23);
"isolate" leads to multi-agent systems (Ch 25); Skills and AGENTS.md reappear in specs
(Ch 28) and coding agents (Ch 43).

---

## 1. The idea in plain words

Prompt engineering asks "how do I phrase the instructions?" Context engineering asks "what
should the model *see* right now?" In a 30-step agent run, the context is rebuilt 30 times;
each time you decide what to include, what to summarize, what to drop and what to fetch.

```
┌──────────────────────────── one model call ────────────────────────────┐
│ system prompt │ tool definitions │ skills/instructions │ retrieved docs │
│ memory facts  │ conversation history │ tool results │ notes/plan │ input │
└─────────────────────────────────────────────────────────────────────────┘
       every token here costs money, time, and a little attention
```

Too little context → the model guesses (hallucination, Ch 07). Too much → it gets slower,
costlier, and worse (context rot, Ch 02).

---

## 2. Analogy

**A surgeon's instrument tray.** The nurse doesn't dump every instrument in the hospital onto
the tray. They lay out what this step of this operation needs, in order, and swap
instruments as the operation moves on. Context engineering is being that nurse for the model.

---

## 3. How it works

### 3.1 The four moves

| Move | What it means | Techniques |
|---|---|---|
| **WRITE** — save it outside the window | Don't keep everything in context; persist it somewhere the agent can get back to | Scratchpad/notes files, todo lists, memory stores (Ch 16), checkpoints (Ch 14) |
| **SELECT** — pull in only what's relevant | Fetch the right pieces for this step | RAG (Ch 17–23), memory retrieval, tool search (Ch 11), skills loaded on demand, just-in-time file reads |
| **COMPRESS** — keep the meaning, drop the tokens | Shrink what must stay | Compaction/summaries, tool-result clearing, trimming, shorter tool outputs (Ch 11 rule 3) |
| **ISOLATE** — split context across boundaries | Give separate parts of the work separate windows | Sub-agents with their own context (Ch 25), sandboxes holding big data outside the prompt, state objects exposing only some fields |

### 3.2 Four ways context goes bad

| Failure | What happens | Example | Fix |
|---|---|---|---|
| **Poisoning** | A hallucination or error enters the context and gets reused as fact | A wrong order ID guessed at step 2 is used in every later step | Verify before writing to context/memory; provenance tags; clear bad results |
| **Distraction** | So much history that the model follows old patterns instead of thinking | Agent repeats an approach from 40 turns ago | Compaction; fresh context for new sub-tasks |
| **Confusion** | Irrelevant information or tools influence the answer | 60 tools loaded, model picks a wrong similar one | Select fewer tools/docs; tool search |
| **Clash** | Contradictory information in context | Old policy and new policy both retrieved | Freshness metadata, dedupe, bi-temporal facts (Ch 16), retrieve the current version only |

### 3.3 Compaction (compress)

When the context passes a threshold (e.g. 70–80% of your budget or window), replace the older
part of the conversation with a summary and keep the **recent turns verbatim**:

```
before:  [system][turn 1]...[turn 30][turn 31]...[turn 36]
after:   [system][SUMMARY of turns 1–30][turn 31]...[turn 36]
```

Keep the last few turns (e.g. ~6) **verbatim**: the model needs exact recent tool results to
continue; summarizing them destroys the precision it needs right now.

**The compaction prompt is the whole trick.** Tell the summarizer explicitly what to keep and
what to drop:

```
MUST PRESERVE                                   MUST DROP
- decisions made and WHY                        - raw tool outputs already acted on
- IDs, file paths, URLs, numbers used later     - repeated errors and retries
- the user's goal, constraints, preferences     - dead-end explorations
- open questions and next steps                 - chit-chat and pleasantries
- what was tried and failed (one line each)
```

Compaction rewrites the prefix, so it **resets the prompt cache** (Ch 12). Compact rarely and
in big steps, not a little every turn. Some providers now offer **server-side compaction** and
**context editing** (automatically clearing old tool results) — use them when available, but
understand what they do.

### 3.4 Tool-result clearing (the cheapest compression)

Old tool results are often the biggest and least useful tokens. Replace them with a stub:

```
{"role": "tool", "content": "[cleared: get_order A-1043 returned status=shipped. Call again for details.]"}
```

The model knows the call happened and the key fact, and can fetch again if needed.

### 3.5 Just-in-time retrieval (select)

Instead of preloading every document "just in case", keep **lightweight references** in context
(file paths, document IDs, URLs, table names) and give the agent tools to load content **when
it needs it**. This is how coding agents work: they don't load the whole repository; they `ls`,
`grep` and `read` the files they need (Ch 19, 43). Trade-off: more tool calls (latency) for far
less wasted context.

### 3.6 Structured note-taking (write)

For long tasks, have the agent keep a **notes file** or **todo list** outside the context
(`NOTES.md`, a `todo` tool). After compaction or even a full restart, it re-reads its notes and
continues. This is the simplest form of long-term memory (Ch 16).

### 3.7 Skills and progressive disclosure (select)

You may have many specialized procedures ("how to process a return", "how to write a SQL
report", "our brand style"). Putting all of them in the system prompt wastes tokens and
confuses the model. **Progressive disclosure**: show only a one-line description of each; load
the full instructions only when relevant.

The **Agent Skills** format packages this: a folder per skill with a `SKILL.md` file whose
front-matter has a `name` and `description` (always visible to the agent), followed by the full
instructions, plus optional scripts and reference files loaded only on demand.

```
skills/
  process-return/
    SKILL.md        ← --- name: process-return / description: Use when a customer wants to return... ---
                       full step-by-step instructions below the front-matter
    refund_rules.md ← loaded only if the instructions say to
```

### 3.8 Project memory files

Coding and workflow agents commonly read a project instructions file at the start of every
session — `AGENTS.md` (a cross-tool convention), or tool-specific ones such as `CLAUDE.md`. It
holds stable conventions: how to build, test, code style, "never touch X". It's context
engineering for a codebase: write it once, select it every session (Ch 43).

### 3.9 Cache-friendly context

Combine with Ch 12: put stable things first, **append** new things at the end, and avoid
rewriting earlier messages (every rewrite = cache miss from that point). Dynamic values (time,
user state) go late, in the newest message.

### 3.10 Measure the budget

After every turn, print how the context is split:

```
system 1,200 | tools 2,900 | skills 300 | docs 4,100 | history 18,400 | tool results 22,700 | TOTAL 49,600
```

You'll usually discover that tool results and history dominate — and that's where to act.

---

## 4. Code

### 4.1 Context budget report

```python
# context_budget.py
def tokens(text):
    return max(1, len(str(text)) // 4)            # rough estimate; use the provider's counter for billing

def context_report(system, tools, messages):
    parts = {"system": tokens(system), "tools": tokens(tools), "history": 0, "tool_results": 0}
    for m in messages:
        key = "tool_results" if m["role"] == "tool" else "history"
        parts[key] += tokens(m.get("content", ""))
    parts["TOTAL"] = sum(parts.values())
    return " | ".join(f"{k} {v:,}" for k, v in parts.items())
```

### 4.2 Tool-result clearing + compaction

```python
# compaction.py
import ollama
from context_budget import tokens

COMPACTION_PROMPT = """Summarize the conversation below for an AI agent that will continue the task.
MUST PRESERVE: the user's goal and constraints; decisions made and why; every ID, path, URL,
number or name that may be needed later; what was tried and failed (one line each); open
questions and next steps.
MUST DROP: raw tool outputs already acted on, repeated errors, dead ends, small talk.
Write compact bullet points under the headings: Goal, Decisions, Key facts, Failed attempts, Next steps.

<conversation>
{conversation}
</conversation>"""

def clear_old_tool_results(messages, keep_last=3):
    """Replace all but the last few tool results with short stubs."""
    tool_idx = [i for i, m in enumerate(messages) if m["role"] == "tool"]
    for i in tool_idx[:-keep_last]:
        original = str(messages[i]["content"])
        messages[i] = {**messages[i], "content": f"[cleared older tool result: {original[:80]}...]"}
    return messages

def compact_if_needed(messages, budget_tokens=6000, keep_recent=6, model="llama3.2"):
    """messages[0] must be the system message. Returns (messages, compacted?)."""
    if sum(tokens(m.get("content", "")) for m in messages) < budget_tokens * 0.75:
        return messages, False
    system, old, recent = messages[0], messages[1:-keep_recent], messages[-keep_recent:]
    if not old:
        return messages, False
    transcript = "\n".join(f"{m['role']}: {m.get('content', '')}" for m in old)
    r = ollama.chat(model=model, options={"temperature": 0},
                    messages=[{"role": "user", "content": COMPACTION_PROMPT.format(conversation=transcript)}])
    summary = {"role": "user", "content": "[Summary of earlier conversation]\n" + r["message"]["content"]}
    return [system, summary, *recent], True
```

Note `keep_recent` should not split a tool call from its result (an assistant message with
`tool_calls` must be followed by its tool results). Adjust the cut point so pairs stay together.

### 4.3 Skills with progressive disclosure

```python
# skills.py — only descriptions are always in context; full text is loaded via a tool
from pathlib import Path

def parse_skill(text):
    """Split '---' front-matter (name, description) from the body."""
    front, body = "", text
    if text.startswith("---"):
        _, front, body = text.split("---", 2)
    meta = {}
    for line in front.strip().splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    return meta, body.strip()

def load_skill_index(root="skills"):
    index = {}
    for skill_md in Path(root).glob("*/SKILL.md"):
        meta, _ = parse_skill(skill_md.read_text())
        name = meta.get("name", skill_md.parent.name)
        index[name] = {"description": meta.get("description", ""), "path": skill_md}
    return index

def skills_system_section(index):
    lines = [f"- {name}: {s['description']}" for name, s in sorted(index.items())]
    return "Available skills (call load_skill(name) to read one before using it):\n" + "\n".join(lines)

def load_skill(name, index):
    if name not in index:
        return f"No skill named '{name}'. Available: {sorted(index)}"
    return index[name]["path"].read_text()

LOAD_SKILL_TOOL = {"type": "function", "function": {
    "name": "load_skill",
    "description": "Load the full instructions of a skill listed in the system prompt.",
    "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}}}
```

Create `skills/process-return/SKILL.md`:

```markdown
---
name: process-return
description: Use when a customer wants to return or exchange an item.
---
1. Look up the order with get_order.
2. Unworn items: return window is 14 days from delivery. Damaged: 60 days.
3. Always run create_refund with dry_run=true first and show the customer the plan.
```

---

## 5. Production view

| Measure | Why |
|---|---|
| Context tokens per iteration (by section) | Find what's growing (usually tool results) |
| Compaction frequency and token savings | Is it firing too often (cache churn) or never (cost blow-up)? |
| **Quality after compaction** — eval cases that ask about early facts after a compaction | Did the summary keep what mattered? |
| Cache-read ratio before/after compaction | Expect a dip at each compaction, then recovery |
| Skill load rate per skill | Unused skills = noise; always-loaded skills = should be in the system prompt |

---

## 6. Common mistakes

- "The window is 1M tokens, so I'll put everything in." (Context rot, cost, latency.)
- Summarizing the most recent turns, losing the exact data the model needs now.
- A vague compaction prompt ("summarize this") that drops IDs and decisions.
- Compacting every turn (cache misses every turn).
- Keeping full raw tool results forever.
- Writing unverified guesses into notes or memory (poisoning persists across sessions).
- Splitting a tool call from its tool result when trimming (most APIs reject it).

---

## 7. Practice

**Level 1**
1. Add `context_report` to the agent from Ch 14 and print it every iteration on a 5-step task.
   Which section grows fastest?
2. Write two `SKILL.md` files (returns, shipping) and print `skills_system_section`. How many
   tokens do the descriptions cost vs the full skills?

**Level 2**
3. Build a scripted 40-turn conversation (generate it in a loop) where turn 3 mentions an order
   ID and turn 38 asks about it. Run with compaction (budget small enough to trigger). Does the
   final answer still have the right ID? Then weaken the compaction prompt (just "summarize")
   and compare.
4. Add `clear_old_tool_results` to the Ch 14 agent and measure total tokens on a 10-tool-call
   task with and without it.

**Level 3**
5. Implement **structured note-taking**: give the agent `write_note(text)` and `read_notes()`
   tools backed by a file. Run a long task, force a full context reset halfway (new messages list
   containing only system + "continue the task; read your notes first"), and check it finishes
   correctly. Measure success over 5 runs with and without notes.

---

## 8. Check yourself

1. Name the four moves of context engineering with one technique each.
2. What's the difference between context poisoning and context clash?
3. Why keep the most recent turns verbatim during compaction?
4. What must a compaction prompt preserve?
5. Why does compaction hurt the prompt cache, and how do you limit the damage?
6. How do Skills save tokens?

<details>
<summary>Answers</summary>

1. Write (notes file / memory), select (RAG / just-in-time file reads / tool search), compress
   (compaction / tool-result clearing), isolate (sub-agents / sandboxes).
2. Poisoning: a wrong fact enters context and gets reused as truth. Clash: two conflicting facts
   are both in context and the model must choose.
3. The model needs the exact recent details (tool results, values) to continue; summaries lose
   precision.
4. Goal and constraints, decisions and their reasons, IDs/paths/URLs/numbers needed later,
   failed attempts, open questions and next steps.
5. It rewrites the earlier part of the prompt, so the cached prefix no longer matches. Compact
   rarely, in large steps, at thresholds — not every turn.
6. Only short descriptions live in the context permanently; full instructions are loaded only
   when a task needs them.

</details>

---

## 9. Key terms

**context engineering** · **write / select / compress / isolate** · **context poisoning** ·
**context distraction** · **context confusion** · **context clash** · **compaction** ·
**preserve/drop rules** · **tool-result clearing** · **context editing** · **just-in-time
retrieval** · **structured note-taking** · **progressive disclosure** · **Agent Skills /
SKILL.md** · **AGENTS.md** · **context budget**

Next: [Chapter 16 — Agent memory →](16-memory.md)
