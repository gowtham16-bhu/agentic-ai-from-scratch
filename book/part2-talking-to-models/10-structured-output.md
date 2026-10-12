# Chapter 10 — Structured output

> When code consumes the model's answer, "please reply in JSON" is not enough. Use
> **schemas**, **constrained decoding** and **validation** — and plan for the day it
> still fails.

**You will learn:** the reliability ladder (prompt-only → JSON mode → schema-constrained
output → forced tool calls), how constrained decoding works, Pydantic for schemas and
validation, schema design rules, the **repair ladder** for broken output, and why
"valid JSON" is not the same as "correct data".

**Where this fits:** builds on prompt engineering (Ch 09) and sampling (Ch 04 —
constrained decoding *is* a sampling filter). Tool calling (Ch 11) uses the same schemas;
routing decisions (Ch 13), judges (Ch 33) and guardrails (Ch 35) all rely on structured
output. Self-hosted constrained decoding appears again with vLLM (Ch 39).

---

## 1. The idea in plain words

Most production LLM calls are not chat. They're **functions**: text in → data out.

```
"Hi, order A-1043 arrived cracked"  →  {"order_id": "A-1043", "issue": "damaged", "urgent": true}
```

Your code needs that data in an exact shape. If one field is missing or misspelled, your
pipeline crashes — or worse, silently does the wrong thing.

---

## 2. Analogy

**A paper form vs a blank page.** Ask someone to "write down your details" and you get every
format imaginable. Give them a form with labelled boxes, checkboxes and a date field, and you
get consistent data. A JSON schema is the form. Constrained decoding is a form where **you
physically can't write outside the boxes**.

Where it breaks: a form guarantees the *shape*, not the *truth*. Someone can still tick the
wrong box. (Valid ≠ correct.)

---

## 3. How it works

### 3.1 The reliability ladder

| Level | Method | Guarantees | Use when |
|---|---|---|---|
| 1 | "Reply in JSON" in the prompt | Nothing | Prototypes only |
| 2 | **JSON mode** | Syntactically valid JSON | Older APIs; still need schema validation |
| 3 | **Schema-constrained output** ("structured outputs": e.g. Anthropic `output_config.format` / `client.messages.parse(...)`, OpenAI `response_format` with a JSON schema, Ollama `format=<schema>`) | Output matches your JSON Schema | Default for extraction/classification |
| 4 | **Strict tools / forced tool call** (`strict: true` on a tool; or `tool_choice` pinned to one tool) | Tool arguments match the tool's schema | Mixing data extraction with tool use (Ch 11). Note: some current models **reject forced `tool_choice`** — use `auto` + `strict` tools + a clear instruction, or level 3 |
| 5 | **Self-hosted constrained decoding** (grammars: Outlines, XGrammar, llguidance, llama.cpp GBNF; built into vLLM/SGLang) | Output matches a schema, regex or grammar | Open models you serve (Ch 39) |

Even at level 3–5, you **still validate** in code: business rules (e.g. "refund ≤ order
total") are not in the schema, and providers support different subsets of JSON Schema.

### 3.2 How constrained decoding works

Remember sampling (Ch 04): the model gives probabilities for every token. **Constrained
decoding** adds one step — before picking, it **masks out every token that would make the
output invalid** under the grammar/schema:

```
output so far:  {"issue": "
schema says:    issue ∈ {"damaged", "late", "wrong_item", "other"}
allowed next:   "d" "l" "w" "o"   (everything else gets probability 0)
```

So the model literally cannot produce invalid structure. Cost: a little latency to compute
masks; benefit: zero parse failures.

**A subtle quality trap:** forcing structure from the first token can hurt reasoning. If the
answer needs thought, add a `reasoning` field **before** the answer fields (fields are generated
in order), or do reasoning in one call and extraction in a second.

### 3.3 Pydantic: one definition → schema + validation

[Pydantic](https://docs.pydantic.dev) lets you define the data shape once in Python and get:
- a **JSON Schema** to send to the model (`Model.model_json_schema()`),
- **parsing + validation** of the result (`Model.model_validate_json(text)`),
- custom **business-rule validators**.

### 3.4 Schema design rules

| Rule | Example |
|---|---|
| **Enums over free text** | `issue: Literal["damaged", "late", "wrong_item", "other"]` |
| **Make "unknown" representable** (prevents invented values, Ch 07) | `order_id: str \| None` with description "null if not mentioned" |
| **Describe every field** — descriptions are prompts | `Field(description="ISO 8601 date the customer says the item arrived")` |
| **Reasoning fields first, answer fields last** | `reasoning`, then `label` |
| **Flat beats deeply nested** | Fewer levels → fewer mistakes |
| **Use standard formats** | ISO dates, currency as integer minor units or string decimals |
| **Bound lists** | `max_length=10` — prevents runaway output |
| **Keep the schema small** | Schemas are tokens on every call |

### 3.5 The repair ladder (when you can't use constrained output, or it still fails)

Each rung is cheaper than the next:

```
1. Strip markdown fences        ```json ... ```  → ...
2. Light repair                 trailing commas, single quotes, smart quotes
3. Extract the JSON substring   first "{" to its matching "}"
4. Re-prompt with the error     "Your output failed validation: <error>. Return corrected JSON only."
5. Re-prompt with a forced schema / tool call
6. Degrade gracefully           return a safe default, mark as "needs review" — never crash the user flow
```

Count how often each rung is used. If rung 4+ fires often, fix the prompt/schema/model instead.

---

## 4. Code

### 4.1 Pydantic schema → constrained output → validation → retry with error

```python
# ch10_extract.py
import json
from typing import Literal
import ollama
from pydantic import BaseModel, Field, ValidationError, field_validator

class Ticket(BaseModel):
    reasoning: str = Field(description="One short sentence explaining the classification")
    order_id: str | None = Field(description="Order ID like A-1043, or null if not mentioned")
    issue: Literal["damaged", "late", "wrong_item", "other"]
    urgent: bool = Field(description="True only if the customer is upset or it blocks them")

    @field_validator("order_id")
    @classmethod
    def order_format(cls, v):
        if v is not None and not (v.startswith("A-") and v[2:].isdigit()):
            raise ValueError("order_id must look like A-1234 or be null")
        return v

SCHEMA = Ticket.model_json_schema()

def extract(message, max_attempts=3):
    messages = [
        {"role": "system", "content": "Extract a support ticket from the customer message."},
        {"role": "user", "content": message},
    ]
    for attempt in range(1, max_attempts + 1):
        r = ollama.chat(model="llama3.2", messages=messages, format=SCHEMA,
                        options={"temperature": 0})
        raw = r["message"]["content"]
        try:
            return Ticket.model_validate_json(raw), attempt
        except ValidationError as e:
            # feed the exact error back — errors are prompts
            messages += [{"role": "assistant", "content": raw},
                         {"role": "user", "content": f"That failed validation:\n{e}\nReturn corrected JSON only."}]
    return None, max_attempts            # degrade: caller routes to "needs review"

for msg in ["Order A-1043 arrived with a cracked screen!!",
            "Do you have this jacket in blue?",
            "my order a1043 is late"]:              # sloppy ID → validator + retry
    ticket, attempts = extract(msg)
    print(attempts, "attempt(s):", ticket.model_dump() if ticket else "NEEDS REVIEW")
```

### 4.2 The repair ladder as code

```python
# repair.py — cheap fixes before an expensive re-prompt
import json
import re

FENCE = "`" * 3                     # a markdown code fence: three backticks

def repair_json(text):
    """Return (data, rung_used) or (None, 'failed')."""
    candidates = [("raw", text)]
    stripped = re.sub(r"^`{3}(?:json)?\s*|\s*`{3}$", "", text.strip())
    candidates.append(("strip_fences", stripped))
    fixed = (stripped.replace("“", '"').replace("”", '"')
             .replace("'", '"'))                          # naive: fine for simple cases
    fixed = re.sub(r",\s*([}\]])", r"\1", fixed)          # trailing commas
    candidates.append(("light_repair", fixed))
    start, end = fixed.find("{"), fixed.rfind("}")
    if start != -1 and end > start:
        candidates.append(("extract_substring", fixed[start:end + 1]))
    for rung, candidate in candidates:
        try:
            return json.loads(candidate), rung
        except json.JSONDecodeError:
            continue
    return None, "failed"        # next rungs: re-prompt with error, forced schema, degrade

tests = ['{"a": 1}',
         FENCE + 'json\n{"a": 1,}\n' + FENCE,
         "Sure! Here is the data: {'a': 1} Hope that helps!",
         "no json here"]
for t in tests:
    print(repair_json(t))
```

---

## 5. Production view

| Problem | Detect | Fix |
|---|---|---|
| Pipeline crashes on bad JSON | **Parse-failure rate** metric; repair-rung histogram | Schema-constrained output; repair ladder; graceful degradation |
| Valid JSON, wrong values | Field-level accuracy in evals (Ch 33) | Better descriptions, enums, reasoning field first, examples |
| Invented values in required fields | Values that don't appear in the input | Nullable fields; check extracted values appear in the source text |
| Provider rejects your schema | 400 errors on deploy | Use the provider's supported JSON Schema subset; test schemas in CI |
| Schema change breaks consumers | Downstream errors after deploy | **Version schemas**; additive changes only; migrate consumers first |
| Slow UI waiting for full JSON | Long time-to-display | Stream and parse partial JSON for progressive UI |

---

## 6. Common mistakes

- **Trusting "reply in JSON"** in production.
- **No validation after constrained output** — business rules aren't in the schema.
- **Answer field before reasoning field** for tasks that need thought.
- **Required fields with no "unknown" option** → hallucinated values.
- **Huge schemas** with dozens of optional fields "just in case" — tokens, confusion, slower.
- **Retrying forever.** Cap attempts; degrade gracefully.

---

## 7. Practice

**Level 1**
1. Run `ch10_extract.py`. Which message needed more than one attempt? Print the validation
   error that was fed back.
2. Run `repair.py`. Add two broken JSON strings of your own and see which rung fixes them.

**Level 2**
3. Make an `Invoice` model (vendor, invoice_number, date ISO, currency enum, total, line_items
   max 20 with description/qty/unit_price). Add a validator that line items sum to the total
   (±0.01). Test on 5 invoice texts you write; include one where the numbers don't add up.
4. Move `reasoning` to be the *last* field. Does classification accuracy change on 20 cases?

**Level 3**
5. Build `structured_call(model, messages, PydanticModel)` used by the rest of the book:
   schema-constrained output → validate → repair ladder → retry with error → degrade.
   It returns `(obj | None, metadata)` where metadata includes attempts, rung used, tokens and
   latency. Log metadata to a JSONL file and compute parse-failure and repair rates over 50
   calls.

---

## 8. Check yourself

1. What's the difference between JSON mode and schema-constrained output?
2. How does constrained decoding prevent invalid output?
3. Why put a `reasoning` field before the `label` field?
4. Your output is valid JSON and matches the schema, but the total is wrong. What layer
   should catch this?
5. Name the six rungs of the repair ladder.

<details>
<summary>Answers</summary>

1. JSON mode guarantees valid JSON syntax only. Schema-constrained output guarantees the
   output matches your specific schema (fields, types, enums).
2. At each step it masks out tokens that would violate the grammar/schema, so only valid
   continuations can be sampled.
3. Fields are generated in order; reasoning first lets the model "think" before committing
   to the label, which improves accuracy.
4. Application-level validation (e.g. a Pydantic validator / business rule) and evals.
5. Strip fences → light repair → extract substring → re-prompt with the error → re-prompt
   with a forced schema/tool → degrade gracefully.

</details>

---

## 9. Key terms

**structured output** · **JSON mode** · **JSON Schema** · **constrained decoding** ·
**grammar** · **Pydantic** · **validator** · **enum** · **nullable field** · **repair ladder** ·
**parse-failure rate** · **schema versioning** · **graceful degradation**

Next: [Chapter 11 — Tool calling →](11-tool-calling.md)
