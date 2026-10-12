# Chapter 45 — The FDE role

> A **Forward Deployed Engineer (FDE)** builds production systems *inside the customer's world*: their data,
> their systems, their security rules, their people. The technology is the other 44 chapters. This chapter is
> the craft around it: **finding the real problem, scoping a pilot that can succeed, proving it with numbers,
> getting through security, writing clearly, and getting people to actually use what you built.**

**You will learn:** what FDEs do and how the role differs from neighbouring roles; the engagement lifecycle
(discovery → scope → demo → pilot → production); **discovery** techniques and a question bank; dealing with
**messy enterprise data**; **scoping pilots** and agreeing **success metrics** up front; a **2-week MVP** shape;
what changes from **demo → pilot → production**; deploying into **customer clouds, VPCs and on-prem**;
**security reviews**; the writing an FDE does (design docs, status updates, pilot reports); **adoption** and
change management; **ROI**; and feeding field learnings back to the product.

**Where this fits:** this is where everything is used. Model choice memos (Ch 08), evals with numbers (Ch 33),
tracing (Ch 34), guardrails and security (Ch 35–36), cost (Ch 37), deployment stages S0–S3 (Ch 38), self-hosting
for VPC/on-prem (Ch 39), specs as contracts (Ch 43) and the autonomy ladder (Ch 44). Interviews are Ch 46; the
capstone (Ch 47) ends with a pilot report.

> **About this chapter:** it describes common practice, not one company's process. Titles and team shapes
> vary: some companies call this role solutions engineer, AI engineer (customer-facing) or deployment
> strategist. The code in section 4 was run.

---

## 1. The idea in plain words

| Role | Main job | Writes production code? | Measured on |
|---|---|---|---|
| **Forward Deployed Engineer** | Make the product succeed in a specific customer's environment, building whatever is missing | **Yes**, a lot | Customer outcomes in production, expansion |
| Solutions / sales engineer | Win the deal: demos, technical questions, proofs of concept | Prototypes | Deals won |
| Solutions architect | Design how the customer should use the platform | Some | Sound architectures, adoption |
| Consultant | Deliver a defined project | Varies | Delivery on scope |
| Product engineer | Build the core product for all customers | Yes | Product quality and velocity |

An FDE is part engineer, part product manager, part consultant. The engineer builds. The PM decides what
*not* to build and what "done" means. The consultant earns trust and handles people. The defining trait is
**ownership of the outcome**, not of a ticket.

---

## 2. Analogy

**A field engineer sent to install a factory machine.** The brochure says "plug and play". On site, the power is
different, the floor isn't level, the operators were never asked, and the safety officer has a 40-question
checklist. A good field engineer doesn't blame the factory. They measure the floor, adapt the mounting, train
the operators, get the safety sign-off, prove the machine's output with numbers, and report back to the
designers: "Every site has this voltage issue. Fix it in the next model."

---

## 3. How it works

### 3.1 The engagement lifecycle

| Stage | Goal | Typical length | Output |
|---|---|---|---|
| **Discovery** | Find the real problem, its value and its owner | 1–2 weeks (overlaps) | Problem statement, data access, success metrics draft |
| **Scope** | Agree what the pilot will prove and how | Days | Pilot one-pager signed by the decision-maker |
| **Demo / MVP** | Show it works on *their* data, end to end | ~2 weeks | Working slice + first eval numbers |
| **Pilot** | Prove value with real users, safely | 4–8 weeks | Scorecard vs agreed metrics; go/no-go |
| **Production** | Run it reliably at scale | Ongoing | SLOs, on-call, runbooks, handover |
| **Expand** | Next workflow, team or region | — | Reuse, case study, product feedback |

Map these to the technical stages of Ch 38: the MVP is S0–S1, the pilot is S2, production is S3.

### 3.2 Discovery: find the real problem

Customers ask for solutions ("we want a chatbot"). Your job is to find the problem ("40% of tickets are 'where
is my order?', each costs 8 minutes, and the backlog makes customers angry"). Techniques:

- **"Walk me through the last 10 cases."** Real cases beat process diagrams. Ask for the weird ones too.
- **Shadow users** for an hour. You'll learn what the documentation doesn't say: the side spreadsheet, the
  colleague everyone asks, the system that's down every Monday.
- **Five whys** on the stated request, until you reach a metric someone is accountable for.
- **Separate stated from actual requirements.** "It must be 100% accurate" usually means "errors must be caught
  before they reach a customer". That's a human-review design, not an impossible model.
- **Find the owner and the decider.** Who owns the metric? Who signs off? Who can block (security, legal,
  works council, IT)? Meet the blockers early.

Question bank:

| Area | Questions |
|---|---|
| **Value** | What does this cost today (time, money, errors, churn)? What happens if nothing changes? What was tried before, and why did it stop? |
| **Users and process** | Who does this work? How many people, how many cases a day? What are the exceptions? Where do mistakes happen? |
| **Data** | Where does it live? Who owns it? How do we get access, and how long does that take? How much is there? What's in it (PII, other languages, scans)? Is there a history of correct answers? |
| **Systems** | Which systems must the agent read or write? Are there APIs? What auth? What rate limits? Which are legacy? |
| **Constraints** | Security policies, data residency, regulations, approved vendors and models, budget, deadlines |
| **Decision** | What result in 6 weeks would make you expand this? Who decides, and by when? |

**Good-fit use cases** are high volume, repetitive and text- or document-heavy, with checkable outcomes,
tolerance for some error with a human backstop, accessible data and a motivated owner. **Bad fits**: rare,
high-stakes decisions with no way to verify, no data access, no owner, or "we need an AI strategy" with no
process attached. Saying "this isn't a good first use case; this one is" builds more trust than a demo.

### 3.3 Messy enterprise data

Expect exports in Excel, PDFs and scans; outdated wikis; policies that contradict each other; labels spelled
five ways; ambiguous dates (is 03/02 the 3rd of February or the 2nd of March?); PII everywhere; and access
rules (ACLs) that your retrieval must respect (Ch 23).

What to do:

1. **Request data access on day 1.** It's usually the critical path, often longer than building.
2. **Profile before you build** (section 4.1): missing fields, duplicates, formats, PII, label chaos, long
   texts. Share the profile with the customer; it often surprises them too.
3. **Work on a representative sample** under a data-processing agreement; use synthetic data for public demos.
4. **Build the golden set with their experts** (Ch 33). Disagreements between experts are findings: the
   process itself is ambiguous, and the agent can't be more consistent than its spec.
5. **Find the source of truth** for each fact (Ch 20's entity resolution, Ch 23's freshness). When two
   documents disagree, the customer must decide which wins. Write that decision down.

### 3.4 Scoping a pilot that can succeed

One workflow, one user group, one measurable outcome. Put it on one page and get it signed:

```markdown
# Pilot: Order-status and returns assistant — Acme Support (EU)

Problem: 38% of 20K monthly tickets are order-status/returns; 8 min average handle time; backlog 3 days.
Users: 25 tier-1 agents (assist mode, weeks 1–3) → customers on web chat (weeks 4–6, 20% of traffic).
In scope: order status, return eligibility, return labels, refunds ≤ €50 with approval.
Out of scope: complaints, fraud, B2B accounts, refunds > €50, voice.
Data & systems: OMS API (read), returns API (write, sandbox first), policy docs (14 PDFs), 2K labelled tickets.
Success (agreed baseline → target):
  - Task success on the 300-case eval set: ≥ 85%   - Severe errors: ≤ 0.5%   - p95 latency ≤ 8 s
  - Handle time for assisted tickets: 8.0 → ≤ 5.5 min   - CSAT not below human baseline (4.3)
Guardrails: approvals for every refund, kill switch, PII redaction in logs, EU-region processing only.
Timeline: 6 weeks; weekly status every Friday; go/no-go meeting 2026-12-04 with VP Support (decider).
Risks: OMS API rate limits (owner: Acme IT); policy docs conflict on gift returns (owner: Support Ops).
```

Rules that keep pilots alive:

- **Measure the baseline first.** "Handle time went down" means nothing without "from what".
- **Agree the eval set and grading method before you see results** (Ch 33). Otherwise every result is
  arguable.
- **Must-haves vs nice-to-haves.** A pilot that misses a nice-to-have can still be a GO (section 4.3).
- **Start in assist mode** (autonomy level 1, Ch 44), then move up with data. "Shadow mode" (the agent
  runs silently alongside humans and you compare outputs) is the safest first step.
- **Fix the decision date and decider now.** Pilots without them drift forever ("pilot purgatory").

### 3.5 Success metrics

| Type | Examples | Note |
|---|---|---|
| **Business** | Handle time, resolution rate, cost per case, backlog, revenue, churn | What the sponsor cares about |
| **Quality** | Task success, groundedness, severe error rate (Ch 33) | What makes it safe to scale |
| **Operational** | p95 latency, availability, cost per task (Ch 37–38) | What makes it run |
| **Adoption** | Weekly active users, % of eligible cases using it, override rate, feedback | What makes it real |

Avoid vanity metrics ("10,000 chats!"). Pair every number with a baseline and an honest confidence interval
(Ch 33's bootstrap). Report **severe errors by name**, not just as a rate. Executives remember the one
embarrassing failure, so show you found it first.

### 3.6 The 2-week MVP shape

| Days | Work |
|---|---|
| 1–2 | Discovery sessions, shadowing, access requests, data profile, 30-case seed eval set with an expert |
| 3–5 | **Thin end-to-end slice** on real data: one workflow, real retrieval and tools (read-only), simple UI (S0 → S1) |
| 6–7 | Eval harness running; first numbers; trace every run (Ch 33–34) |
| 8–9 | Fix the top failure modes from the traces; add guardrails and approvals for any write |
| 10 | Demo on *their* data with *real* numbers, including failures, plus the pilot one-pager for sign-off |

Breadth kills MVPs. One workflow done end to end beats five half-done.

### 3.7 Demo → pilot → production: what changes

| | Demo | Pilot | Production |
|---|---|---|---|
| Data | Curated sample | Real, representative | All of it, live |
| Users | You | A small real group | Everyone eligible |
| Failure handling | Skip the bad cases | Human review, kill switch | SLOs, on-call, runbooks, incident process |
| Evals | Eyeballing | Agreed eval set + scorecard | Eval gates in CI, online monitoring, drift alerts |
| Security | NDA | Security review for pilot scope | Full review, pen test, audit logs |
| Ops | Laptop | One environment | Multi-env, canaries, capacity plans (Ch 38) |
| People | Excitement | Training, champions | Change management, support model, handover |

The classic trap: a dazzling demo sets expectations a pilot can't meet. **Demo honestly**: show a failure and
how it's caught.

### 3.8 Where it runs: customer cloud, VPC, on-prem

| Option | What it means | FDE implications |
|---|---|---|
| **Vendor API (SaaS)** | Calls go to the model provider | Fastest; data-processing terms, retention and residency must pass review |
| **Through the customer's cloud provider** | Models consumed via their cloud account (e.g. Bedrock, Vertex AI, Azure) | Billing, region and IAM in their account; check model and feature availability per region |
| **Customer VPC, self-hosted models** | Open-weight models served by vLLM etc. inside their network (Ch 39) | You need GPU capacity, ops skills and their deployment tooling (Terraform, Helm, their CI) |
| **On-prem / air-gapped** | No internet | Offline model weights and container images, internal registries, no external telemetry, offline evals; every update is a delivery |

You often **can't see production**. Build for that: structured logs with redaction the customer can share, a
"support bundle" script that collects config, versions and recent sanitized traces, a replay harness for
sanitized traces, and health endpoints that explain themselves (Ch 38).

### 3.9 Security reviews

For enterprise customers, the security review often takes longer than the build. Start it in week 1 with a
**security pack**:

- **Data-flow diagram**: every place data goes (model provider, vector store, logs, traces, backups), with
  regions.
- **Data handling**: what is sent, retention periods, whether data trains any model (normally no, in writing),
  deletion process, sub-processors.
- **Access**: SSO/SAML, RBAC, least-privilege service accounts, secrets management, audit logs.
- **Security posture**: certifications (SOC 2, ISO/IEC 27001, increasingly **ISO/IEC 42001** for AI
  management), pen-test summary, incident response, vulnerability management.
- **AI-specific**: prompt-injection defences, tool permissions and approvals, guardrails, red-team and eval
  results, human oversight, model provider terms, and regulatory classification (e.g. EU AI Act risk
  category, Ch 36).
- **Questionnaire answers**: customers send standard questionnaires (often hundreds of questions). Keep a
  maintained answer library.

Sector rules add more (health, finance, public sector). Banks often run **model risk management** reviews
covering documentation, validation and monitoring. Your eval reports and traces are the evidence.

### 3.10 Writing: half the job

| Document | When | Core content |
|---|---|---|
| **Pilot one-pager** | Before the pilot | Problem, users, scope in/out, metrics with baselines, timeline, decider, risks |
| **Design doc** | Before building anything non-trivial | Context, goals/non-goals, architecture, data flow, alternatives considered, risks, rollout |
| **Weekly status** | Every week | Status (green/amber/red), progress vs plan, metrics, risks with owners, **asks** |
| **Decision memo** | Model choice, build vs buy, go/no-go | Options, evidence, recommendation, what would change the decision (Ch 08) |
| **Pilot report** | End of pilot | Scorecard vs agreed metrics, failures and fixes, cost, ROI, recommendation, production plan |
| **Runbook** | Before production | How to deploy, monitor, roll back, use the kill switch, handle top incidents |

Principles: **lead with the answer**; numbers with baselines and confidence; risks with owners and dates; plain
language an executive can repeat; a clear ask. Weekly status template:

```markdown
**Status: AMBER** — on track for the 4 Dec decision; one risk needs Acme IT this week.
Progress: refunds tool live in sandbox; eval 81% → 86% (300 cases); p95 6.4 s.
Top failures: gift returns (policy conflict, 9 cases) — waiting on Support Ops decision.
Risks: OMS rate limit (60 rpm) blocks the 20% traffic step — owner: Acme IT, needed by 20 Nov.
Asks: (1) rate-limit increase to 300 rpm; (2) decision on gift-return policy.
Next week: customer-facing beta for 5% of web chat; handoff summaries to tier-2.
```

### 3.11 Adoption and change management

A system nobody uses has zero ROI. Adoption is designed, not hoped for:

- **Involve frontline users early**; they know the exceptions, and people support what they help build.
- **Champions**: a few respected users who test first and teach peers.
- **Fit into existing tools** (help-desk sidebar, CRM, Slack) instead of "yet another app".
- **Training** on what it does well, what it doesn't, and how to give feedback (Ch 44).
- **Be honest about job impact.** Fear kills adoption quietly. Frame it around removing drudgery, and mean it.
- **Measure usage** weekly; low usage is a finding, not a failure to hide.

### 3.12 ROI

Build the business case with **the customer's numbers** (section 4.2) and show the sensitivity: savings depend
heavily on the share of cases the agent fully resolves. Include the costs people forget: AI cost on *every*
case (including escalated ones), human review time, the cost of agent errors, platform and on-call costs, and
one-time build and integration costs (payback period). Also count non-financial value: 24/7 coverage,
consistency, faster response, audit trails.

### 3.13 Feedback to product, and saying no

FDEs see what customers actually need before anyone else. Turn that into product input with evidence: "4 of 6
customers built the same handoff summary; here are the specs and usage numbers." Build reusable pieces, not
one-off forks of the product.

Scope creep is the silent pilot killer: "Can it also do complaints?" The answer is "Yes, as phase 2, after we
hit the agreed metrics. Here's what adding it now would risk." Protect the success metric.

### 3.14 Habits of strong FDEs

Ownership (the outcome is yours, even when the cause is the customer's IT). Debugging unfamiliar systems
calmly. Speed *with* judgement. Talking to a VP and a database admin in the same hour. Writing every week.
Never overpromising: say what the system can't do before the customer finds out. Leave every customer with
something they can run without you.

---

## 4. Code

### 4.1 Profile a customer's data export (runs anywhere)

```python
# data_profile.py — the first thing an FDE runs on a customer export: what does the data REALLY look like?
import re
from collections import Counter
from datetime import datetime

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")
DATE_FORMATS = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%b-%Y"]

def date_format(value):
    matches = []
    for fmt in DATE_FORMATS:
        try:
            matches.append((fmt, datetime.strptime(value, fmt)))
        except (ValueError, TypeError):
            pass
    if not matches:
        return "unparseable"
    if len({d for _, d in matches}) > 1:
        return "AMBIGUOUS (day/month?)"                    # 03/02/2026: 3 Feb or 2 Mar? Ask the customer
    return matches[0][0]

def profile(rows, text_field="body", label_field="category", date_field="created"):
    n = len(rows)
    report = {"rows": n}
    report["missing"] = {k: sum(1 for r in rows if not r.get(k)) for k in rows[0]}
    report["exact_duplicates"] = n - len({r.get(text_field) for r in rows})
    report["date_formats"] = dict(Counter(date_format(r.get(date_field)) for r in rows))
    report["rows_with_email"] = sum(1 for r in rows if EMAIL.search(r.get(text_field) or ""))
    report["rows_with_phone"] = sum(1 for r in rows if PHONE.search(r.get(text_field) or ""))
    raw = Counter(r.get(label_field) or "<none>" for r in rows)
    labels = Counter((r.get(label_field) or "<none>").strip().lower() for r in rows)
    report["labels"] = dict(labels.most_common())
    report["label_spellings"] = f"{len(raw)} raw values -> {len(labels)} after trim/lowercase"
    lengths = sorted(len(r.get(text_field) or "") for r in rows)
    pct = lambda q: lengths[min(n - 1, round(q * (n - 1)))]
    report["text_len_p50_p95"] = (pct(0.5), pct(0.95))
    return report

if __name__ == "__main__":
    rows = [
        {"id": 1, "created": "2026-03-02", "category": "Billing", "body": "Charged twice, call me on +44 7700 900123"},
        {"id": 2, "created": "03/02/2026", "category": "billing ", "body": "Refund please. jo@example.com"},
        {"id": 3, "created": "2-Mar-2026", "category": "", "body": "Where is my order A-1043?"},
        {"id": 4, "created": "2026-03-03", "category": "Shipping", "body": "Where is my order A-1043?"},
        {"id": 5, "created": None, "category": "Returns", "body": "Lamp arrived broken " + "and more details " * 40},
        {"id": 6, "created": "2026-03-04", "category": "Shipping", "body": ""},
    ]
    for k, v in profile(rows).items():
        print(f"{k:<18} {v}")
```

Output:

```text
rows               6
missing            {'id': 0, 'created': 1, 'category': 1, 'body': 1}
exact_duplicates   1
date_formats       {'%Y-%m-%d': 3, 'AMBIGUOUS (day/month?)': 1, '%d-%b-%Y': 1, 'unparseable': 1}
rows_with_email    1
rows_with_phone    1
labels             {'billing': 2, 'shipping': 2, '<none>': 1, 'returns': 1}
label_spellings    5 raw values -> 4 after trim/lowercase
text_len_p50_p95   (25, 700)
```

Six rows, and already: an ambiguous date, PII in free text, a duplicate, an unlabelled ticket and label
spelling chaos. On real exports, this table drives your first meeting with the data owner.

### 4.2 An ROI model with sensitivity (runs anywhere)

```python
# roi_model.py — a business case the customer's finance team can check. Every input is THEIR number, not yours.
def monthly(volume, handle_min, cost_per_hour, resolved_rate, ai_cost_per_case, review_min_per_case,
            error_rate, cost_per_error, platform_fixed):
    human_cost_per_case = handle_min / 60 * cost_per_hour
    baseline = volume * human_cost_per_case
    resolved = volume * resolved_rate                      # fully handled by the agent
    escalated = volume - resolved                          # still handled by people (often faster: context provided)
    with_agent = (volume * ai_cost_per_case                # model + infra on every case, including escalations
                  + escalated * human_cost_per_case
                  + volume * review_min_per_case / 60 * cost_per_hour     # spot checks, approvals
                  + resolved * error_rate * cost_per_error               # what agent mistakes cost
                  + platform_fixed)                                       # licences, hosting, on-call
    return baseline, with_agent

def payback_months(one_time_cost, monthly_saving):
    return float("inf") if monthly_saving <= 0 else one_time_cost / monthly_saving

if __name__ == "__main__":
    base = dict(volume=20_000, handle_min=8, cost_per_hour=30, ai_cost_per_case=0.15, review_min_per_case=0.3,
                error_rate=0.02, cost_per_error=40, platform_fixed=6_000)
    print(f"{'resolved by agent':>18}{'baseline $/mo':>15}{'with agent':>12}{'saving':>10}{'payback':>10}")
    for rate in (0.2, 0.35, 0.5, 0.65):
        b, w = monthly(resolved_rate=rate, **base)
        print(f"{rate:>18.0%}{b:>15,.0f}{w:>12,.0f}{b - w:>10,.0f}{payback_months(150_000, b - w):>9.1f}m")
```

Output:

```text
 resolved by agent  baseline $/mo  with agent    saving   payback
               20%         80,000      79,200       800    187.5m
               35%         80,000      69,600    10,400     14.4m
               50%         80,000      60,000    20,000      7.5m
               65%         80,000      50,400    29,600      5.1m
```

At 20% the business case is nearly zero: per-case AI cost, review time, errors and fixed costs eat the
savings. That's why the pilot's metric is the share of cases fully resolved, and why discovery hunts for the
high-volume, simple cases first.

### 4.3 The pilot scorecard (runs anywhere)

```python
# pilot_scorecard.py — success criteria AGREED BEFORE the pilot, evaluated the same way after it
CRITERIA = [  # (metric, comparison, target, must_have)
    ("task_success_rate",        ">=", 0.85, True),     # on the agreed eval set, graded as agreed (Ch 33)
    ("severe_error_rate",        "<=", 0.005, True),    # e.g. wrong refund amount, data shown to the wrong user
    ("p95_latency_s",            "<=", 8.0, True),
    ("cost_per_resolved_case",   "<=", 0.50, False),
    ("agent_csat",               ">=", 4.2, False),     # same survey as human-handled cases
    ("handoff_quality_score",    ">=", 0.8, False),     # do human agents rate the handoff summary useful?
]

def evaluate(measured):
    ok = lambda v, op, t: v >= t if op == ">=" else v <= t
    rows, go = [], True
    for metric, op, target, must in CRITERIA:
        value = measured.get(metric)
        passed = value is not None and ok(value, op, target)
        go &= passed or not must
        rows.append(f"{metric:<24}{op} {target:<8}{value!s:<8}{'PASS' if passed else 'FAIL'}{'  (must-have)' if must else ''}")
    return rows, ("GO: expand to production plan" if go else "NO-GO: fix must-haves or stop")

if __name__ == "__main__":
    results = {"task_success_rate": 0.88, "severe_error_rate": 0.003, "p95_latency_s": 6.1,
               "cost_per_resolved_case": 0.62, "agent_csat": 4.4, "handoff_quality_score": 0.75}
    rows, verdict = evaluate(results)
    print("\n".join(rows))
    print(verdict)
```

Output:

```text
task_success_rate       >= 0.85    0.88    PASS  (must-have)
severe_error_rate       <= 0.005   0.003   PASS  (must-have)
p95_latency_s           <= 8.0     6.1     PASS  (must-have)
cost_per_resolved_case  <= 0.5     0.62    FAIL
agent_csat              >= 4.2     4.4     PASS
handoff_quality_score   >= 0.8     0.75    FAIL
GO: expand to production plan
```

The criteria were written before the pilot; the scorecard just applies them. The two misses become the
production plan's first work items (cost: Ch 37; handoff quality: Ch 44).

### 4.4 Pilot report outline

```markdown
# Pilot report — <workflow>, <customer>, <dates>
1. Recommendation (one paragraph): GO / NO-GO / EXTEND, and why.
2. Scorecard vs agreed criteria (table from pilot_scorecard.py), with baselines and confidence intervals.
3. What users said (adoption numbers, 3 quotes, top feedback themes).
4. Failures: the top 5 failure modes, examples, fixes made, what remains (with severe errors listed).
5. Cost: per task and per month at target volume; ROI and payback with the customer's inputs.
6. Security & compliance: review status, open items, owners.
7. Production plan: scope, autonomy level per action, SLOs, rollout stages, team and support model.
8. Asks and decisions needed, with dates.
Appendix: eval set description, grading method, architecture and data-flow diagrams.
```

---

## 5. Production view

| Concern | What to do |
|---|---|
| **Problem choice** | High-volume, checkable, owned problems first; say no to bad first use cases |
| **Data** | Access requests on day 1; profile; golden set with experts; source-of-truth decisions in writing |
| **Scope** | One-page pilot plan signed by the decider; in/out of scope; decision date |
| **Metrics** | Baselines first; eval set and grading agreed in advance; must-haves vs nice-to-haves |
| **Delivery** | Thin end-to-end slice in 2 weeks; assist/shadow mode before autonomy |
| **Environment** | Choose SaaS / customer-cloud / VPC / on-prem early; build support bundles for systems you can't see |
| **Security** | Security pack in week 1; data-flow diagram; maintained questionnaire answers |
| **Communication** | Weekly status with asks; decision memos; honest demos including failures |
| **Adoption** | Frontline involvement, champions, in-tool integration, usage tracked weekly |
| **Value** | ROI with the customer's numbers and sensitivity; hidden costs included |
| **Product loop** | Field notes → evidence-backed product requests → reusable components |

---

## 6. Common mistakes

- Building what was asked for instead of what's needed.
- Starting to build before data access is confirmed.
- Agreeing success metrics *after* seeing results, or never measuring the baseline.
- Five workflows at 60% instead of one at 90%.
- A demo of the happy path that sets impossible expectations.
- Leaving the security review until the week before launch.
- Status updates with no asks, no risks and no numbers.
- No decision date, so the pilot never ends.
- Ignoring the frontline users who will decide whether it's used.
- Forking the product for one customer and maintaining it forever.

---

## 7. Practice

**Level 1**
1. Run `data_profile.py` on a public dataset of support tickets or emails (or one you create with 50 messy
   rows). Write five findings you would raise with the data owner.
2. Rewrite the pilot one-pager in 3.4 for a different workflow: invoice data extraction for an accounts-payable
   team.

**Level 2**
3. Role-play discovery with a friend or an LLM playing a skeptical support director who asks for "a chatbot".
   Use the question bank. Write the problem statement you end with, and compare it to the original ask.
4. Fill `roi_model.py` with realistic numbers for that invoice workflow and find the break-even automation
   rate.

**Level 3**
5. Produce the full pilot document set for your capstone (Ch 47): one-pager, design doc, security pack with a
   data-flow diagram, two weekly status updates and the pilot report with a real scorecard from your eval
   harness.

---

## 8. Check yourself

1. How does an FDE differ from a solutions engineer?
2. Give three discovery techniques and explain why "walk me through the last 10 cases" works.
3. What makes a good first use case? A bad one?
4. Why must success metrics and the grading method be agreed before the pilot?
5. What are the four kinds of success metrics?
6. What changes between a pilot and production?
7. What goes into a security pack?
8. Why does the ROI case collapse at low automation rates?

<details>
<summary>Answers</summary>

1. The FDE builds and owns production outcomes in the customer's environment after (or alongside) the sale; a
   solutions engineer mainly supports winning the deal with demos and proofs of concept.
2. Last-N-cases walkthroughs, shadowing users, five whys, separating stated from actual requirements, finding
   owner/decider/blockers. Real recent cases reveal exceptions, workarounds and data issues that process
   descriptions hide.
3. Good: high volume, repetitive, text-heavy, checkable outcomes, tolerance for error with a human backstop,
   accessible data, a motivated owner. Bad: rare high-stakes decisions without verification, no data access,
   no owner, vague "AI strategy".
4. Otherwise results can be argued away (or cherry-picked), and the go/no-go becomes politics instead of
   evidence.
5. Business, quality, operational and adoption metrics.
6. All real data and users, SLOs and on-call, eval gates in CI and online monitoring, a full security review and
   audit logs, multi-environment ops and capacity planning, plus change management, support and handover.
7. A data-flow diagram, data handling (what's sent, retention, no training, deletion, sub-processors, regions),
   access controls, certifications and security posture, AI-specific controls (injection defences,
   approvals, guardrails, red-team/eval results, oversight), regulatory classification, questionnaire answers.
8. AI and infrastructure cost applies to every case, escalated cases still cost a human, and review time, error
   costs and fixed platform costs remain, so savings only appear when enough cases are fully resolved.

</details>

---

## 9. Key terms

**Forward Deployed Engineer (FDE)** · **discovery** · **last-N-cases walkthrough** · **shadowing** · **five
whys** · **stated vs actual requirements** · **decider / blocker** · **data profile** · **golden set with
SMEs** · **pilot one-pager** · **baseline** · **must-have vs nice-to-have** · **shadow mode / assist mode** ·
**pilot purgatory** · **thin end-to-end slice** · **customer VPC / on-prem / air-gapped** · **support bundle** ·
**security pack / data-flow diagram** · **model risk management** · **weekly status (RAG)** · **pilot
report** · **champions** · **ROI / payback** · **scope creep**

Next: [Chapter 46 — AI system design and interviews →](46-ai-system-design-interviews.md)
