# Chapter 28 — Specs and standards map

> Agent systems are built on a stack of **open specifications**: how messages are framed, how
> tools and agents are described, how identities are proven, how UIs and payments connect, and
> how traces are recorded. You don't need to memorize them — you need to know **which spec
> solves which problem** and where to read the current version.

**You will learn:** the foundational specs (JSON-RPC 2.0, JSON Schema 2020-12, OpenAPI),
identity and authorization (OAuth 2.1, PKCE, OIDC, RFC 8693 token exchange, RFC 9728, RFC 8707,
client registration, SPIFFE/mTLS, JWS/JCS), the agent protocols (MCP, A2A), agent↔UI protocols
(AG-UI, A2UI, MCP Apps), agentic commerce (ACP, AP2), discovery and description (MCP Registry,
Agent Cards, AGNTCY/OASF), agent instructions (AGENTS.md, Agent Skills, llms.txt), and
observability (OpenTelemetry GenAI conventions).

**Where this fits:** the map for Part 6. MCP in depth is Ch 29, A2A Ch 30, registries Ch 31,
gateways Ch 32. Identity specs return in agent security (Ch 36); OTel in observability (Ch 34);
AGENTS.md and Skills were introduced in Ch 15 and return in Ch 43.

> **Status line:** checked against the specs' own repositories on 2026-10-12. Versions move —
> always confirm the current version in the official repo before you build.

---

## 1. The idea in plain words

```
                   ┌───────────────────────── USERS & UIs ─────────────────────────┐
                   │  AG-UI (agent ↔ frontend events) · A2UI (agent-generated UI)  │
                   │  MCP Apps (interactive UI inside chat clients)                │
                   └───────────────────────────────┬────────────────────────────────┘
                                                   │
 ┌──────────── AGENT ↔ AGENT ────────────┐   ┌──────┴───────┐   ┌──────── COMMERCE ─────────┐
 │ A2A (Agent Cards, tasks, streaming)    │◄─►│    AGENT     │◄─►│ ACP (checkout), AP2       │
 │ discovery: Agent Cards, registries,    │   │  (your code) │   │ (payment mandates)        │
 │ AGNTCY Directory / OASF records        │   └──────┬───────┘   └───────────────────────────┘
 └────────────────────────────────────────┘          │
                                         ┌───────────┴────────── AGENT ↔ TOOLS/DATA ─────────┐
                                         │ MCP (tools, resources, prompts) · MCP Registry     │
                                         │ OpenAPI (REST tools) · JSON Schema (all arguments) │
                                         └────────────────────────────────────────────────────┘
 underneath everything:  JSON-RPC 2.0 · HTTP/SSE/gRPC · OAuth 2.1/OIDC · token exchange · mTLS/SPIFFE · JWS
 instructions & know-how: AGENTS.md · Agent Skills (SKILL.md) · llms.txt
 observability:           OpenTelemetry GenAI semantic conventions (+ W3C trace context)
```

---

## 2. Analogy

**The standards that make the internet work.** You don't think about TCP, DNS, TLS and HTTP when
you open a website — but every engineer who builds websites knows what each one is for. Agent
specs are becoming that layer for AI systems: MCP is a bit like "USB for tools", A2A like "email
between agents", OAuth like "the visitor badge system".

---

## 3. How it works

### 3.1 Foundations

| Spec | What it standardizes | Where you meet it |
|---|---|---|
| **JSON-RPC 2.0** | Request/response messages: `{"jsonrpc":"2.0","id":1,"method":"...","params":{...}}`, plus notifications (no `id`) and standard error codes (`-32602` invalid params, etc.) | MCP and A2A (JSON-RPC binding) message framing |
| **JSON Schema (2020-12)** | Describing the shape of JSON data | Tool arguments and outputs (Ch 10–11), MCP `inputSchema`/`outputSchema` (MCP's default dialect is 2020-12) |
| **OpenAPI** | Describing REST APIs | Generating tools from existing APIs; gateways; documentation |
| **HTTP + SSE, gRPC** | Transports; server-sent events for streaming | Streamable HTTP in MCP; A2A bindings (JSON-RPC, gRPC, HTTP+JSON) |

### 3.2 Identity and authorization

| Spec | Plain meaning | Why agents care |
|---|---|---|
| **OAuth 2.1** (+ **PKCE**) | Delegated access: a client gets a token to call an API on a user's behalf; PKCE protects the code exchange | MCP authorization is based on OAuth 2.1; A2A security schemes |
| **OpenID Connect (OIDC)** | Identity layer on OAuth: who the user is (ID token) | SSO for agent UIs; auth-server discovery (MCP supports OIDC Discovery) |
| **RFC 8693 Token Exchange** | Swap a token for another, e.g. "agent acting on behalf of user"; the `act` (actor) claim records the delegation | Agents are workloads acting for users — delegation, not impersonation (Ch 36) |
| **RFC 9728 Protected Resource Metadata** | A resource server publishes which authorization server protects it | MCP servers act as OAuth resource servers and advertise their auth server |
| **RFC 8707 Resource Indicators** | The client says which resource a token is for | MCP clients must use it, so a malicious server can't obtain tokens meant for another |
| **Client registration** (Dynamic Client Registration RFC 7591; **Client ID Metadata Documents**) | How a client app identifies itself to an auth server | MCP now prefers Client ID Metadata Documents; DCR is deprecated in MCP's 2026-07-28 revision |
| **mTLS / SPIFFE** | Service-to-service identity with certificates; SPIFFE IDs for workloads | Proving *which agent service* is calling (workload identity, Ch 36) |
| **JWS (RFC 7515) + JCS (RFC 8785)** | Digital signatures over JSON; canonical JSON form for stable signatures | Signed A2A Agent Cards (anti-spoofing, Ch 30–31) |

### 3.3 Agent protocols

| Spec | Purpose | Status (Oct 2026) | Chapter |
|---|---|---|---|
| **MCP — Model Context Protocol** | Agent ↔ tools/data: servers expose **tools, resources, prompts**; hosts/clients connect | Latest revision **2026-07-28** (stateless redesign: no sessions or initialize handshake); earlier: 2024-11-05, 2025-03-26 (OAuth 2.1, Streamable HTTP), 2025-06-18 (structured output, elicitation), 2025-11-25 (tasks, URL elicitation) | Ch 29 |
| **A2A — Agent2Agent** | Agent ↔ agent: **Agent Cards** for discovery, **tasks** with lifecycle states, messages/artifacts, streaming, push notifications | **v1.0** released 2026-03-12 (1.0.1 in May 2026); Linux Foundation project; bindings: JSON-RPC, gRPC, HTTP+JSON | Ch 30 |

They're complementary. The A2A docs describe it well: **MCP is vertical** (deepens one agent with
tools), **A2A is horizontal** (connects agents across teams and organizations).

### 3.4 Agent ↔ user-interface protocols

| Spec | Purpose |
|---|---|
| **AG-UI** | An open, event-based protocol for streaming agent activity to frontends over SSE/WebSockets/etc.: run lifecycle, text messages, tool calls, state, activity, reasoning and sub-agent events (the 1.0 Python SDK enumerates ~30 types), plus **interrupts** for human approval (Ch 44) |
| **A2UI** | A format for **agent-generated, updatable UIs**: the agent describes UI components declaratively; the client renders them with its own trusted components |
| **MCP Apps** | An MCP extension for **interactive UIs for MCP tools** (charts, forms, dashboards) that render inline in compatible chat clients |

Why they matter: agents increasingly return *interfaces*, not just text — and rendering
agent-provided UI safely (no arbitrary code from the agent) is a real design problem (Ch 44).

### 3.5 Agentic commerce

| Spec | Purpose |
|---|---|
| **ACP — Agentic Commerce Protocol** | Open standard for buyers, their AI agents and businesses to complete purchases (checkout flows initiated by agents); maintained by OpenAI and Stripe; status **beta** |
| **AP2 — Agent Payments Protocol** | Google-led protocol for agent-initiated payments using verifiable "mandates" that prove what the user authorized |

Don't confuse ACP (commerce) with older uses of the same acronym (e.g. IBM's "Agent Communication
Protocol", which merged into A2A).

### 3.6 Discovery and description

| Spec / system | Purpose |
|---|---|
| **MCP Registry** | An official catalog ("app store") of public MCP servers with a standard `server.json` metadata format; launched in preview in Sept 2025, API frozen at v0.1 since Oct 2025 |
| **A2A Agent Card** | JSON at `/.well-known/agent-card.json` describing an agent's skills, endpoints, auth, capabilities; can be signed |
| **AGNTCY Directory + OASF** | Open Agentic Schema Framework: a standard schema for describing agents' capabilities and metadata, plus a directory service for publishing/discovering agent records |

Registries are covered in depth in Ch 31.

### 3.7 Instructions and know-how for agents

| Spec | Purpose |
|---|---|
| **AGENTS.md** | A simple open format: a README for coding agents (build, test, conventions) at the repo root |
| **Agent Skills** | A folder with `SKILL.md` (front-matter `name` + `description`, then instructions) plus optional `scripts/`, `references/`, `assets/` — loaded on demand (progressive disclosure, Ch 15) |
| **llms.txt** | A proposed convention: a Markdown file at a website's root summarizing it for LLMs, with links to LLM-friendly pages |

### 3.8 Observability

| Spec | Purpose |
|---|---|
| **OpenTelemetry (OTel)** | Vendor-neutral traces, metrics, logs |
| **OTel GenAI semantic conventions** | Standard attribute and span names for model calls, token usage, agents, tool calls and MCP (`gen_ai.*`) — now in a dedicated repository and **still evolving** (check status before relying on exact names) |
| **W3C Trace Context** | `traceparent`/`tracestate` headers to join traces across services — MCP's 2026-07-28 revision documents carrying them in `_meta` |

### 3.9 How to read a spec quickly

1. Read the **overview/architecture** page and the **changelog** of the latest version.
2. Find the **message examples** (JSON) — they teach faster than prose.
3. Search for **MUST** — those are the interoperability rules.
4. Check the **security considerations** section.
5. Look at an **official SDK's tests** to see real usage.
6. Note the **version you built against** in your code and docs.

---

## 4. Code

### 4.1 JSON-RPC 2.0 by hand (the framing under MCP and A2A)

```python
# jsonrpc_demo.py — a tiny JSON-RPC 2.0 dispatcher, to see the framing MCP/A2A use
import json

METHODS = {"add": lambda a, b: a + b}

def handle(raw):
    try:
        req = json.loads(raw)
    except json.JSONDecodeError:
        return {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}}
    if req.get("jsonrpc") != "2.0" or "method" not in req:
        return {"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32600, "message": "Invalid Request"}}
    fn = METHODS.get(req["method"])
    if fn is None:
        return {"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32601, "message": "Method not found"}}
    try:
        result = fn(**req.get("params", {}))
    except TypeError as e:
        return {"jsonrpc": "2.0", "id": req.get("id"), "error": {"code": -32602, "message": f"Invalid params: {e}"}}
    if "id" not in req:
        return None                        # a notification: no response
    return {"jsonrpc": "2.0", "id": req["id"], "result": result}

for raw in ['{"jsonrpc":"2.0","id":1,"method":"add","params":{"a":2,"b":3}}',
            '{"jsonrpc":"2.0","id":2,"method":"divide","params":{}}',
            '{"jsonrpc":"2.0","id":3,"method":"add","params":{"a":2}}',
            '{"jsonrpc":"2.0","method":"add","params":{"a":1,"b":1}}',
            'not json']:
    print(raw[:50], "->", handle(raw))
```

### 4.2 An RFC 8693 token-exchange request (shape only)

```python
# token_exchange_shape.py — what "agent acting on behalf of a user" looks like on the wire
import urllib.parse

form = {
    "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
    "subject_token": "<the USER's access token>",                    # on whose behalf
    "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
    "actor_token": "<the AGENT service's own token>",               # who is acting
    "actor_token_type": "urn:ietf:params:oauth:token-type:access_token",
    "resource": "https://orders.internal.example.com",               # audience for the new token
    "scope": "orders:read",                                          # least privilege
}
print("POST /oauth/token\nContent-Type: application/x-www-form-urlencoded\n")
print(urllib.parse.urlencode(form).replace("&", "\n&"))
# The issued token's claims typically include sub=<user> and act={"sub": <agent>} — delegation, not impersonation.
```

---

## 5. Production view

| Concern | Practice |
|---|---|
| Spec versions drift | Record the protocol versions you implement; test against the version your clients/servers advertise |
| Deprecations | Read the "Deprecated" section of each new revision (e.g. MCP deprecated HTTP+SSE, Roots, Sampling, Logging, DCR in 2026-07-28) |
| Security reviews | Map each spec to your threat model (Ch 36): who is authenticated, which tokens flow where |
| Vendor extensions | Prefer standard fields; isolate vendor-specific extensions behind adapters |
| Customer questions | FDEs are asked "do you support MCP/A2A/OAuth X?" — answer with version numbers and what's tested |

---

## 6. Common mistakes

- Learning a protocol from a blog post instead of the spec's changelog and examples.
- Building on a deprecated transport (e.g. MCP's old HTTP+SSE) for new work.
- Treating "supports OAuth" as one thing — which flows, which RFCs, which token audiences?
- Confusing look-alike acronyms (ACP the commerce protocol vs the old agent communication protocol).
- Assuming OTel GenAI attribute names are final.

---

## 7. Practice

**Level 1**
1. Run `jsonrpc_demo.py`. Which input got no response and why?
2. For each scenario, name the spec: (a) your agent needs a CRM's tools; (b) your agent delegates a
   task to a partner company's agent; (c) a user's agent buys shoes from your store; (d) a coding agent
   should know how to run your tests; (e) you need one trace across agent, tools and MCP servers.

**Level 2**
3. Read the MCP 2026-07-28 changelog and write, in your own words, the 5 changes that matter most
   for someone who built against 2025-06-18 — and what code they'd change.
4. Read A2A's v1.0 Agent Card example and write an Agent Card for your support agent (skills, auth,
   endpoints).

**Level 3**
5. Draw (on paper or in a diagram tool) the full token flow for: user signs in to your agent UI (OIDC)
   → agent calls your Orders MCP server on the user's behalf (OAuth 2.1 + token exchange + resource
   indicator) → MCP server calls the internal orders API. Mark where each token's audience and
   subject/actor are checked.

---

## 8. Check yourself

1. What does JSON-RPC 2.0 standardize, and which agent protocols use it?
2. MCP vs A2A in one sentence each.
3. Why does MCP require resource indicators (RFC 8707)?
4. What does the `act` claim in a token-exchange result express?
5. Name the three agent-UI specs and what each is for.
6. What's the current MCP revision and its headline change? The current A2A version?

<details>
<summary>Answers</summary>

1. Request/response/notification message framing and error codes; MCP and A2A's JSON-RPC binding.
2. MCP connects an agent to tools, resources and prompts (vertical). A2A connects agents to other
   agents across boundaries, with discovery and task lifecycles (horizontal).
3. So access tokens are bound to the intended resource server, preventing a malicious server from
   obtaining and reusing tokens meant for another resource.
4. Delegation: the token's subject is the user, and the actor (the agent) is acting on their behalf —
   not impersonating them.
5. AG-UI (event stream from agent to frontend), A2UI (declarative agent-generated UI rendered by the
   client), MCP Apps (interactive UIs for MCP tools inside chat clients).
6. MCP 2026-07-28 — a stateless protocol: no protocol sessions or initialize handshake; each request
   carries version and capabilities. A2A v1.0 (March 2026; 1.0.1 in May 2026).

</details>

---

## 9. Key terms

**JSON-RPC 2.0** · **JSON Schema 2020-12** · **OpenAPI** · **OAuth 2.1** · **PKCE** · **OIDC** ·
**token exchange (RFC 8693)** · **actor claim** · **protected resource metadata (RFC 9728)** ·
**resource indicators (RFC 8707)** · **Client ID Metadata Documents** · **mTLS / SPIFFE** ·
**JWS / JCS** · **MCP** · **A2A** · **AG-UI** · **A2UI** · **MCP Apps** · **ACP (Agentic Commerce
Protocol)** · **AP2** · **MCP Registry** · **Agent Card** · **OASF / AGNTCY** · **AGENTS.md** ·
**Agent Skills** · **llms.txt** · **OTel GenAI conventions** · **W3C trace context**

Next: [Chapter 29 — MCP deep dive →](29-mcp.md)
