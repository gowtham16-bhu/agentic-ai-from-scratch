# Chapter 32 — LLM gateway and MCP gateway

> A **gateway** is one front door between your agents and everything they call. An **LLM gateway**
> sits in front of model providers (keys, routing, fallbacks, budgets, caching, logging). An **MCP
> gateway** sits in front of tool servers (aggregation, permissions, approvals, audit). Together with
> the registry (Ch 31), they turn a pile of agents into a governed platform.

**You will learn:** why gateways exist; LLM gateway features (unified API, model aliases/roles,
routing, cross-provider fallback, retries, load balancing, **virtual keys**, per-tenant **rate
limits and budgets**, exact and **semantic caching**, guardrail hooks, **PII redaction**, cost
attribution, observability); the product landscape (LiteLLM, Portkey, Kong, Envoy, Cloudflare,
OpenRouter, cloud gateways); **MCP gateway** features (tool aggregation and namespacing, per-agent
allowlists, approval policies, auth/token handling, fingerprints, audit); avoiding the gateway as a
single point of failure; and you'll build a mini version of both.

**Where this fits:** builds on reliability and caching (Ch 12), model roles (Ch 08), tools and tool
search (Ch 11), MCP (Ch 29) and the registry (Ch 31). Guardrails plugged into gateways are Ch 35;
security policy in Ch 36; cost controls in Ch 37; deployment and multi-tenancy in Ch 38; tracing
through the gateway in Ch 34.

---

## 1. The idea in plain words

Without a gateway, every agent team: stores provider API keys, writes its own retry/fallback logic,
has no budget limits, logs prompts (with customer PII) in different places, and calls whatever tools
it likes. With a gateway:

```
                    ┌──────────────── LLM GATEWAY ─────────────────┐
agents / apps ────► │ auth (virtual keys) · policy · rate limit · budget │ ───► provider A (models)
  (no provider      │ alias→model routing · fallback · retries · cache   │ ───► provider B
   keys at all)     │ guardrail hooks · PII redaction · cost attribution │ ───► self-hosted (vLLM, Ch 39)
                    └──────────────────────────────────────────────────────┘
                    ┌──────────────── MCP GATEWAY ─────────────────┐
agents ───────────► │ one MCP endpoint · aggregates many servers        │ ───► MCP server: orders
                    │ namespacing · per-agent allowlists (from registry)│ ───► MCP server: CRM
                    │ approvals for destructive tools · token handling  │ ───► MCP server: KB
                    │ fingerprint checks · audit log · rate limits      │
                    └──────────────────────────────────────────────────────┘
```

It's the same pattern as an API gateway in microservices — specialized for LLM traffic (tokens,
costs, streaming, prompts) and tool traffic (agents acting on systems).

---

## 2. Analogy

**A company's reception and security desk.** Visitors (agents) don't wander the building with master
keys. Reception checks who they are, which rooms they may enter, logs every visit, escorts them to
sensitive areas only with approval, and stops anyone who's used up their allowed visits. Reception
must also never become the reason nobody can enter the building — there are several desks.

---

## 3. How it works

### 3.1 LLM gateway features

| Feature | What it does | Why |
|---|---|---|
| **Unified API** | One request format for all providers (often OpenAI-compatible) | Swap providers without code changes |
| **Aliases / roles** | Apps ask for `fast`, `smart`, `judge`; the gateway resolves to real models (Ch 08) | Central upgrades and per-tenant overrides |
| **Routing & load balancing** | Spread traffic across deployments/regions/keys | Throughput, latency, rate-limit headroom |
| **Fallback & retries** | Cross-provider chains, backoff, circuit breakers (Ch 12) — in **one** layer | Survive outages without retry amplification |
| **Virtual keys** | Each team/app/tenant gets a revocable gateway key; provider keys live only in the gateway | Secret hygiene, instant revocation, attribution |
| **Rate limits & budgets** | RPM/TPM and $ budgets per key/team/tenant | Stop runaway agents and noisy neighbours |
| **Exact cache** | Return a stored response for an identical deterministic request | Cheap wins for repeated calls |
| **Semantic cache** | Reuse a response when a new prompt is *similar* (embeddings) | Big savings on FAQ-style traffic — risky (below) |
| **Guardrail hooks** | Input/output checks (PII, injection classifiers, moderation) before/after the model (Ch 35) | Central safety policy |
| **PII redaction in logs** | Mask emails, phones, card numbers before storing | Privacy and compliance |
| **Cost attribution & observability** | Tokens, cost, latency, model resolved, per team/tenant; trace export (Ch 34) | FinOps, debugging, chargeback |
| **Prompt-cache friendliness** | Don't mutate prompts in ways that break provider prefix caching (Ch 12) | A badly built gateway can double your bill |

**Semantic caching cautions:** "What's the return window for shoes?" and "…for *damaged* shoes?" are
similar but have different answers. Use semantic caching only for generic, non-personalized,
non-permissioned content, with a high similarity threshold, a short TTL, tenant namespacing, and
clearly labelled cached answers. Never for anything user-specific.

### 3.2 Product landscape (check current features)

| Option | Notes |
|---|---|
| **LiteLLM** | Open-source SDK + proxy: 100+ providers behind an OpenAI-compatible API; virtual keys, budgets, rate limits, fallbacks, load balancing, logging callbacks |
| **Portkey** | AI gateway with routing, fallbacks, caching, guardrails, observability (open-source gateway + hosted platform) |
| **Kong AI Gateway**, **Envoy AI Gateway** | AI plugins/extensions on established API gateways — good when you already run them |
| **Cloudflare AI Gateway** | Hosted gateway at the edge: caching, rate limiting, analytics |
| **OpenRouter** | Hosted router/marketplace: one API and billing for many models |
| **Cloud platforms** | Cloud API-management products and AI platforms add gateway features (quotas, keys, logging) for their model catalogs |
| **MCP gateways** | Several API-gateway vendors and open-source projects now offer MCP-aware gateways (single MCP endpoint, auth, policy, audit) |

Build vs buy: buy/adopt for the commodity parts (provider adapters, keys, budgets); build the
**policy** that's specific to your company (registry integration, approvals, data rules).

### 3.3 MCP gateway features

| Feature | Why |
|---|---|
| **Aggregation** | Agents connect to one MCP endpoint instead of N servers |
| **Namespacing** (`orders__get_order`) | Prevent tool-name collisions and tool shadowing (Ch 29) |
| **Per-agent allowlists** (from the registry) | Least privilege; agents only *see* allowed tools (smaller context, Ch 11) |
| **Approval policy** for destructive tools | Decided by *your* policy, not by the server's own annotations |
| **Auth & token handling** | Validate agent identity; obtain per-server, audience-bound tokens; never pass user tokens through (Ch 28–29) |
| **Fingerprint checks** | Block servers whose tool definitions changed since approval (rug pulls) |
| **Audit log** | Who (agent + user) called what, with which arguments, allowed or denied |
| **Rate limits & quotas** | Protect fragile backends from agent traffic spikes |
| **Response filtering** | Strip secrets, cap result sizes (Ch 11 rule 3), label untrusted content |

### 3.4 Don't make the gateway your single point of failure

- **Multiple stateless replicas** behind a load balancer, in each region; shared state (rate limits,
  budgets, cache) in Redis or similar.
- **Latency budget:** the gateway should add milliseconds, not seconds — run heavy guardrails
  asynchronously or only on risky routes.
- **Fail closed** for authentication and authorization; decide explicitly for budgets and guardrails.
- **Cache policy decisions** from the registry so a registry outage doesn't stop all traffic.
- **Emergency bypass** procedure (documented, audited) and a **kill switch** (Ch 35).
- Health checks and SLOs on the gateway itself (Ch 34, 38).

---

## 4. Code

```bash
pip install fastapi httpx "mcp[cli]"
```

### 4.1 A mini LLM gateway

```python
# llm_gateway.py — virtual keys, budgets, rate limits, model aliases, fallback, cache, redacted logs
import hashlib
import json
import re
import time
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

# --- config (in production: from the registry/DB, Ch 31) -----------------------------------
VIRTUAL_KEYS = {  # apps never see provider keys; each team gets a revocable virtual key
    "vk-support-123": {"team": "cx", "tenant": "acme", "monthly_budget_usd": 50.0, "rpm": 60,
                       "allowed_aliases": {"fast", "smart"}},
}
ALIASES = {"fast": ["local/llama3.2", "providerB/small"], "smart": ["providerA/large", "providerB/large"]}
PRICES = {"local/llama3.2": (0.0, 0.0), "providerB/small": (0.8, 4.0),   # USD per 1M tokens (example)
          "providerA/large": (3.0, 15.0), "providerB/large": (2.5, 12.0)}

def call_provider(model, messages):
    """Stand-in for real provider SDK calls (Ch 12). Raise to simulate an outage."""
    if model in DOWN:
        raise ConnectionError(f"{model} unavailable")
    text = f"[{model}] reply to: {messages[-1]['content'][:40]}"
    return text, sum(len(m["content"]) for m in messages) // 4, len(text) // 4

DOWN: set[str] = set()

# --- state (in production: Redis, shared by all gateway replicas) ---------------------------
SPEND: dict[str, float] = {}
WINDOW: dict[str, list[float]] = {}
CACHE: dict[str, dict] = {}
LOGS: list[dict] = []

PII = [(re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "<email>"),
       (re.compile(r"\b(?:\d[ -]?){13,16}\b"), "<card>"),
       (re.compile(r"\+?\d[\d -]{8,}\d"), "<phone>")]

def redact(text):
    for pattern, repl in PII:
        text = pattern.sub(repl, text)
    return text

class ChatRequest(BaseModel):
    model: str                     # an ALIAS such as "fast" — never a raw provider model id
    messages: list[dict]
    temperature: float = 0.0

app = FastAPI(title="llm-gateway")

@app.post("/v1/chat")
def chat(req: ChatRequest, authorization: str = Header(...)):
    key = authorization.removeprefix("Bearer ").strip()
    cfg = VIRTUAL_KEYS.get(key)
    if cfg is None:
        raise HTTPException(401, "unknown virtual key")
    if req.model not in cfg["allowed_aliases"]:
        raise HTTPException(403, f"alias '{req.model}' not allowed for team {cfg['team']}")
    now = time.time()                                                    # sliding-window rate limit
    WINDOW[key] = [t for t in WINDOW.get(key, []) if now - t < 60] + [now]
    if len(WINDOW[key]) > cfg["rpm"]:
        raise HTTPException(429, "rate limit exceeded", headers={"Retry-After": "10"})
    if SPEND.get(key, 0.0) >= cfg["monthly_budget_usd"]:
        raise HTTPException(402, "monthly budget exhausted for this key")

    cache_key = None
    if req.temperature == 0:                     # exact cache only for deterministic requests,
        cache_key = hashlib.sha256(json.dumps(  # namespaced by TENANT (no cross-tenant leaks)
            [cfg["tenant"], req.model, req.messages], sort_keys=True).encode()).hexdigest()
        if cache_key in CACHE:
            return {**CACHE[cache_key], "cached": True}

    errors = []
    for model in ALIASES[req.model]:                                     # fallback chain
        try:
            text, tin, tout = call_provider(model, req.messages)
        except ConnectionError as e:
            errors.append(str(e))
            continue
        p_in, p_out = PRICES[model]
        cost = (tin * p_in + tout * p_out) / 1e6
        SPEND[key] = SPEND.get(key, 0.0) + cost
        LOGS.append({"team": cfg["team"], "tenant": cfg["tenant"], "alias": req.model,  # cost attribution
                     "model_resolved": model, "tokens_in": tin, "tokens_out": tout, "cost_usd": cost,
                     "prompt_redacted": redact(req.messages[-1]["content"]), "fallbacks": len(errors)})
        result = {"model": model, "text": text, "usage": {"input_tokens": tin, "output_tokens": tout}}
        if cache_key:
            CACHE[cache_key] = result
        return {**result, "cached": False}
    raise HTTPException(503, f"all models failed for alias '{req.model}': {errors}")
```

### 4.2 Exercise it

```python
# test_llm_gateway.py
from fastapi.testclient import TestClient
import llm_gateway as gw
c = TestClient(gw.app)
H = {"Authorization": "Bearer vk-support-123"}
msg = [{"role": "user", "content": "My email is priya@example.com, card 4111 1111 1111 1111. Where is A-1043?"}]
print(c.post("/v1/chat", headers=H, json={"model": "fast", "messages": msg}).json())
print(c.post("/v1/chat", headers=H, json={"model": "fast", "messages": msg}).json()["cached"])
gw.DOWN.add("local/llama3.2")
print(c.post("/v1/chat", headers=H, json={"model": "fast", "messages": msg, "temperature": 0.7}).json()["model"])
print(c.post("/v1/chat", headers={"Authorization": "Bearer nope"}, json={"model": "fast", "messages": msg}).status_code)
print(gw.LOGS[-1])
gw.VIRTUAL_KEYS["vk-support-123"]["monthly_budget_usd"] = 0.0
print(c.post("/v1/chat", headers=H, json={"model": "smart", "messages": msg, "temperature": 0.5}).json())
```

Verified behaviour: the first call answers from `local/llama3.2`; the identical call returns
`cached: True`; with `local/llama3.2` down, a non-cached call falls back to `providerB/small`; an
unknown key gets 401; the log line contains the team, tenant, resolved model, tokens, cost and a
**redacted** prompt (`My email is <email>, card <card>. Where is A-1043?`); with the budget at zero,
the gateway returns 402 "monthly budget exhausted".

### 4.3 A mini MCP gateway

```python
# mcp_gateway.py — one front door to many MCP servers: namespacing, allowlists, approvals, audit
import json
import time
from contextlib import AsyncExitStack
from mcp import Client

class MCPGateway:
    def __init__(self, servers, policy, approve_fn, audit_log):
        self.servers = servers            # {"orders": <server or URL>, "kb": ...}
        self.policy = policy              # {"agent:support": {"orders__get_order", "kb__search", ...}}
        self.approve_fn = approve_fn      # human/rule approval for destructive tools
        self.audit = audit_log
        self.clients, self.tools = {}, {}

    async def __aenter__(self):
        self._stack = AsyncExitStack()
        for prefix, server in self.servers.items():
            client = await self._stack.enter_async_context(Client(server))
            self.clients[prefix] = client
            for t in (await client.list_tools()).tools:
                self.tools[f"{prefix}__{t.name}"] = (prefix, t)       # namespacing prevents collisions
        return self

    async def __aexit__(self, *exc):
        await self._stack.aclose()

    def list_tools_for(self, agent_id):
        """Discovery is filtered: an agent only SEES tools it may call (least privilege, smaller context)."""
        allowed = self.policy.get(agent_id, set())
        return [{"name": name, "description": t.description, "input_schema": t.input_schema,
                 "destructive": bool(t.annotations and t.annotations.destructive_hint)}
                for name, (_, t) in self.tools.items() if name in allowed]

    async def call(self, agent_id, name, arguments, on_behalf_of):
        entry = {"ts": time.time(), "agent": agent_id, "user": on_behalf_of, "tool": name,
                 "args": json.dumps(arguments, sort_keys=True)}
        if name not in self.policy.get(agent_id, set()):
            self.audit.append({**entry, "decision": "denied:not_allowed"})
            return {"is_error": True, "text": f"Tool '{name}' is not available to this agent."}
        prefix, tool = self.tools[name]
        # the registry/host decides what needs approval — never trust the server's own hint alone
        if tool.annotations and tool.annotations.destructive_hint and not arguments.get("dry_run", False):
            if not self.approve_fn(agent_id, name, arguments, on_behalf_of):
                self.audit.append({**entry, "decision": "denied:approval"})
                return {"is_error": True, "text": "A human declined this action. Tell the user it was not done."}
        result = await self.clients[prefix].call_tool(tool.name, arguments)
        text = json.dumps(result.structured_content) if result.structured_content is not None else \
            "\n".join(getattr(c, "text", "") for c in result.content)
        self.audit.append({**entry, "decision": "allowed", "is_error": result.is_error})
        return {"is_error": result.is_error, "text": text}
```

A second server to aggregate:

```python
# kb_server.py — a second MCP server (knowledge base search)
from mcp.server import MCPServer
from mcp.types import ToolAnnotations

mcp = MCPServer("acme-kb")

@mcp.tool(annotations=ToolAnnotations(read_only_hint=True))
def search(query: str) -> str:
    """Search help-center articles. Returns up to 3 titles."""
    return "Returns policy | Shipping times | Payment errors"
```

### 4.4 Exercise it: visibility, denial, approvals, audit

```python
# test_mcp_gateway.py — needs orders_server.py from Ch 29 and kb_server.py
import asyncio
from mcp_gateway import MCPGateway
from orders_server import mcp as orders
from kb_server import mcp as kb

audit = []
policy = {"agent:support": {"orders__get_order", "orders__create_refund", "kb__search"},
          "agent:faq-bot": {"kb__search"}}
approve = lambda agent, tool, args, user: args.get("amount", 0) <= 20      # e.g. auto-approve small refunds only

async def main():
    async with MCPGateway({"orders": orders, "kb": kb}, policy, approve, audit) as gw:
        print("faq-bot sees:", [t["name"] for t in gw.list_tools_for("agent:faq-bot")])
        print("support sees:", [t["name"] for t in gw.list_tools_for("agent:support")])
        print(await gw.call("agent:faq-bot", "orders__get_order", {"order_id": "A-1043"}, "user-1"))
        print(await gw.call("agent:support", "orders__get_order", {"order_id": "A-1043"}, "user-1"))
        print(await gw.call("agent:support", "orders__create_refund",
                            {"order_id": "A-1043", "amount": 49.99, "idempotency_key": "k1", "dry_run": False}, "user-1"))
        print(await gw.call("agent:support", "orders__create_refund",
                            {"order_id": "A-1043", "amount": 10.0, "idempotency_key": "k2", "dry_run": False}, "user-1"))
    for a in audit:
        print(a["agent"], a["tool"], a["decision"])
asyncio.run(main())
```

Verified output:

```
faq-bot sees: ['kb__search']
support sees: ['orders__get_order', 'orders__create_refund', 'kb__search']
{'is_error': True, 'text': "Tool 'orders__get_order' is not available to this agent."}
{'is_error': False, 'text': '{"order_id": "A-1043", "status": "shipped", "carrier": "DHL", "eta": "2026-10-15"}'}
{'is_error': True, 'text': 'A human declined this action. Tell the user it was not done.'}
{'is_error': False, 'text': '{"result": "Refund RF-0001 created for 10.0."}'}
agent:faq-bot orders__get_order denied:not_allowed
agent:support orders__get_order allowed
agent:support orders__create_refund denied:approval
agent:support orders__create_refund allowed
```

In production, this gateway would itself be exposed as **one MCP server** (so any MCP host can use it),
load its policy from the registry (Ch 31), and authenticate agents with workload identity (Ch 36).

---

## 5. Production view

| Dashboard | Why |
|---|---|
| Requests, errors, p95 latency **added by the gateway** | The gateway must stay cheap |
| **Fallback rate** per alias/provider | Rising = a provider degrading (one of the four core agent dashboards) |
| Spend per team/tenant vs budget; top-cost requests | FinOps, runaway agents |
| 429s and budget denials per key | Limits too tight or a misbehaving agent |
| Cache hit rate (exact, semantic) and semantic-cache complaints | Savings vs wrong answers |
| MCP: denials, approvals pending/declined, fingerprint mismatches | Security posture |
| Audit-log completeness | Compliance |

---

## 6. Common mistakes

- Giving every app the raw provider keys "temporarily".
- Retrying in the SDK, the app *and* the gateway (amplification).
- Semantic caching personalized or permission-scoped answers.
- Logging full prompts with PII, or redacting so aggressively that debugging is impossible (keep a
  secure, access-controlled raw store if policy allows).
- A gateway that rewrites prompts and silently breaks provider prompt caching.
- One gateway instance, no health checks — now every agent depends on it.
- Trusting MCP servers' `destructive_hint` instead of your own approval policy.

---

## 7. Practice

**Level 1**
1. Run `test_llm_gateway.py`. Add a second virtual key for another tenant and prove the cache doesn't
   return tenant A's answer to tenant B.
2. Run `test_mcp_gateway.py`. Add an `agent:readonly-auditor` that can see only read-only tools — derive its
   allowlist automatically from annotations *and* a registry flag.

**Level 2**
3. Replace `call_provider` with the real `llm.py` client from Ch 12 (local Ollama as `fast`). Add a
   **token-based** limit (tokens per minute) in addition to RPM.
4. Add a semantic cache to the LLM gateway (embeddings from Ch 06) with a threshold, TTL, tenant namespace and
   an allowlist of "cacheable" routes. Write three tests where it must *not* return a cached answer.

**Level 3**
5. Run the gateway with **LiteLLM's proxy** (or another gateway product) in Docker instead of your mini version:
   configure two providers, an alias with fallback, virtual keys and budgets. Point the Ch 14 agent at it.
   Write a one-page comparison: what you got for free, what you still had to build (registry policy, approvals).

---

## 8. Check yourself

1. Name six features of an LLM gateway.
2. Why do apps get virtual keys instead of provider keys?
3. When is semantic caching dangerous?
4. What does an MCP gateway add on top of connecting to servers directly?
5. How do you keep the gateway from being a single point of failure?
6. Why should approval policy for destructive tools live in the gateway/registry rather than in MCP
   server annotations?

<details>
<summary>Answers</summary>

1. Any six: unified API, aliases/roles, routing/load balancing, fallback/retries, virtual keys, rate limits and
   budgets, exact/semantic caching, guardrail hooks, PII redaction, cost attribution/observability.
2. Provider keys stay in one secured place; each team's access can be limited, attributed and revoked without
   rotating the real keys.
3. When similar-looking prompts need different answers (details matter), when answers are personalized or
   permission-scoped, or when content changes (staleness) — and especially without tenant namespacing.
4. A single endpoint, namespacing, per-agent allowlists and filtered discovery, approval policies, token
   handling, fingerprint checks, audit logging and rate limits.
5. Multiple stateless replicas per region with shared state in a fast store, health checks/SLOs, cached policy,
   a small latency budget, explicit fail-closed/fail-open decisions, and an audited emergency bypass.
6. Annotations are claims by the server and can be wrong or malicious; the platform's own policy must decide.

</details>

---

## 9. Key terms

**LLM gateway** · **AI gateway** · **unified API** · **model alias** · **routing / load balancing** ·
**fallback chain** · **virtual key** · **rate limit (RPM/TPM)** · **budget** · **exact cache** ·
**semantic cache** · **guardrail hook** · **PII redaction** · **cost attribution / chargeback** ·
**MCP gateway** · **tool aggregation** · **namespacing** · **allowlist** · **approval policy** ·
**audit log** · **single point of failure** · **fail closed**

Next: [Part 7 — Chapter 33: Evals →](../part7-quality/33-evals.md)
