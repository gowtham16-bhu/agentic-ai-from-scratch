# Chapter 38 — Deploying at scale

> Going from a laptop script to thousands of concurrent agent runs is mostly **classic distributed-
> systems engineering** — services, queues, autoscaling, multi-tenancy, rollouts, SLOs — with a few
> agent-specific twists: long and variable run times, provider rate limits as the real capacity
> ceiling, and behaviour that can change with a prompt edit.

**You will learn:** the four deployment stages; service design (sync, streaming, async jobs), health and
readiness; the duration ladder; queues and workers with at-least-once delivery; **Little's law** capacity
planning and provider token limits; **availability math**; the **graceful degradation ladder**; containers;
Kubernetes for agent workloads (why scale on **queue depth**, not CPU; KEDA); external state; **multi-tenancy**
(silo / pool / bridge; four boundaries); CI/CD with eval gates; shadow, canary and blue-green rollouts;
config-as-deployable (prompts, models, tools); SLOs; load and chaos testing; multi-region and DR; managed
cloud agent platforms.

**Where this fits:** builds on reliability (Ch 12), durable state (Ch 26), gateways (Ch 32), evals (Ch 33),
observability (Ch 34), guardrails and security (Ch 35–36) and cost (Ch 37). GPU serving is Ch 39. The capstone
(Ch 47) walks the same stages with one system.

---

## 1. The idea in plain words

| Stage | Shape | What gets added | Exit criterion (a number) |
|---|---|---|---|
| **S0 — Script** | One Python file, local model | The loop, tools | It works on 10 examples |
| **S1 — Service** | HTTP API in a container; hosted or local model behind roles | Streaming, timeouts, retries, idempotency, config | Runs in Docker; p95 latency measured |
| **S2 — Pilot** | One customer/tenant; real data | Evals in CI, tracing, guardrails, approvals, kill switch, shadow mode | Pass rate, cost per task, p95 — reported to the customer |
| **S3 — Scale** | Many tenants, thousands of runs | Queues + workers, autoscaling, multi-tenancy, canaries, SLOs, load/chaos tests, multi-region | SLOs met under target load; cost per successful task within budget |

Don't skip stages. Each one surfaces the problems the next one depends on.

---

## 2. Analogy

**Opening restaurants.** A home kitchen (script), a food truck (service), one restaurant with real customers
and health inspections (pilot), then a chain (scale): central kitchens, delivery queues, staffing for the
dinner rush, a recipe change rolled out to one branch first, and a plan for when a supplier fails.

---

## 3. How it works

### 3.1 Service design

- **Synchronous** endpoint for short tasks (< ~30 s p99), with an overall timeout.
- **Streaming** endpoint (SSE) for chat-like UX (Ch 12).
- **Async job** endpoint for long tasks: `POST /tasks` → `202 Accepted` + task ID → poll `GET /tasks/{id}`, or
  stream progress, or a webhook when done. Pick by **p99**, not p50 (Ch 26 duration ladder).
- **Idempotency keys** on every POST that starts work, so client retries don't start duplicate runs.
- **Liveness** probe = "process is alive" (never calls the LLM). **Readiness** = "can take traffic" (cheap
  dependency checks, queue not full). Calling the model in probes turns a provider blip into a full outage.
- **Backpressure:** when queues are full, return 429 with `Retry-After` instead of accepting work you can't do.

### 3.2 Queues and workers

```
API ──► queue (Redis streams/lists, SQS, Kafka, a durable workflow engine) ──► workers (agent runs)
                                                                                 │ checkpoints → Postgres (Ch 26)
                                                                                 └ results → DB / webhook
```

- Queues give **at-least-once** delivery → handlers must be **idempotent** (Ch 12).
- **Visibility timeouts** longer than the longest run (or heartbeats); **dead-letter queue** after N attempts.
- **Per-tenant fairness:** separate queues or weighted fair scheduling so one tenant's bulk job can't starve others.
- **Worker concurrency is capped by provider rate limits**, not by CPU.

### 3.3 Capacity planning: Little's law and token limits

```
concurrency (runs in flight) = arrival rate × duration          L = λ × W
20 tasks/s × 30 s per task = 600 concurrent runs

tokens per minute needed = arrival rate × 60 × tokens per task
20/s × 60 × 40,000 = 48M tokens/min  ← compare with your provider's TPM limits FIRST
```

What usually breaks first: **model API rate limits**, then **your tool backends** (a database sized for human
traffic meeting hundreds of concurrent agent queries), then connection pools. Plan quotas with providers early
(Ch 08), and remember caching reduces effective input tokens (Ch 12, 37).

### 3.4 Availability multiplies down the chain

```
API 99.9% × gateway 99.9% × vector DB 99.5% × model provider 99.0% = 98.3%  ≈ 12 hours down per month
```

Serial dependencies make the whole **worse than every part** — the strongest argument against unnecessary
services and unnecessary agents. **Parallel redundancy** helps: two independent providers at 99% with fallback ≈
99.99% for that hop (Ch 12).

### 3.5 The graceful degradation ladder

```
full service ─► degraded (fewer tools, cheaper model, no reranker) ─► cached answers (clearly labelled)
            ─► queued ("we'll email you within 4 hours") ─► honest failure with a route to a human
```

Never a stack trace. Decide each step's trigger (provider down, budget exhausted, kill switch, overload) in advance.

### 3.6 Containers and Kubernetes

**Docker basics for agents:** slim pinned base image, non-root user, pinned dependencies, **no secrets in the
image**, health check, small attack surface (code-execution sandboxes are separate, Ch 43).

**Kubernetes specifics:**
- Separate **Deployments** for the API and for workers (different scaling signals).
- **Don't autoscale LLM-bound workers on CPU** — they mostly wait on network I/O. Scale on **queue depth** or
  in-flight runs, e.g. with **KEDA** (event-driven autoscaling) on Redis/SQS/Kafka lag; cap max replicas at what
  provider limits allow.
- **PodDisruptionBudgets**, generous **termination grace periods** (let runs checkpoint), readiness/liveness probes.
- Secrets from a secrets manager; **NetworkPolicies** for egress allowlists (Ch 36).
- GPU node pools only for self-hosted models (Ch 39).

### 3.7 State lives outside the pods

| State | Store |
|---|---|
| Run checkpoints, jobs, memory, audit | Postgres (or a durable workflow engine) |
| Rate limits, budgets, locks, caches | Redis |
| Files, documents, artifacts | Object storage |
| Embeddings | Vector DB / pgvector (Ch 17, 23) |
| Traces/metrics | Observability backend (Ch 34) |

Stateless pods can be killed, rescheduled and scaled freely.

### 3.8 Multi-tenancy

Traditional multi-tenancy is a data problem. Agents add four more: they **execute code** (shared kernel), hold
**in-memory state**, call **tools with real-world effects**, and have **transitive authority** — granting a tool
grants everything that tool can reach. Enforce capabilities in the runtime/gateway, not inside each tool.

| Model | How | Use |
|---|---|---|
| **Silo** | Everything per tenant (stack, DB, keys) | Regulated/large customers; strongest isolation; highest cost |
| **Pool** | Everything shared, `tenant_id` everywhere | Many small tenants; cheapest; one missing filter = leak |
| **Bridge** | **Shared control plane, dedicated data plane** (per-tenant DBs/indexes/keys) | Right for most agent SaaS |

**Four boundaries that must hold simultaneously:** **data** (own namespace; encryption stops a stolen disk,
isolation stops a *neighbour*), **compute** (sandboxes, quotas, noisy-neighbour limits), **credentials**
(per-tenant secrets and scoped tokens), **inference** (prompt caches and response caches namespaced per tenant —
or a cached prefix leaks across tenants). See Ch 36 for the leaks that actually happen.

### 3.9 CI/CD and rollouts

```
commit → unit + contract tests → eval gate (Ch 33) → security scans → build image → staging
       → smoke tests → SHADOW (new version on live traffic, output hidden) → CANARY 1% → 10% → 50% → 100%
          with automatic rollback on SLO burn, eval-score drop, cost spike, guardrail-trigger spike
```

- **Prompts, model configs and tool versions are deployable config** with their own versions (Ch 09, 31): roll
  back a prompt in seconds without a code deploy.
- **Feature flags** for new tools/capabilities per tenant.
- **Blue-green** for infrastructure changes; **canary** for behaviour changes.

### 3.10 SLOs, load tests, chaos tests

- **SLOs** on what users feel: success rate, p95 latency per route, freshness (Ch 23), availability (Ch 34).
- **Load tests** with a realistic traffic mix; use a **mock LLM** (fixed latency/tokens) for scale tests so you
  don't burn money, plus a small real-provider test to validate limits. Find the first bottleneck.
- **Chaos tests:** kill workers mid-run (do checkpoints resume?), make a provider return 529/timeout (does fallback
  work?), slow a tool (do timeouts and budgets hold?), fill the queue (does backpressure work?).

### 3.11 Multi-region, DR and data residency

- Active-passive or active-active per region; regional model endpoints; keep each tenant's data in its required
  region (Ch 08); define **RPO/RTO**; back up state stores; rehearse failover.

### 3.12 Managed platforms

Clouds offer model catalogs and managed agent runtimes (for example AWS Bedrock with its agent runtime services,
Google Vertex AI with its agent engine, Microsoft Azure AI Foundry with its agent service), and model providers
offer hosted agent runtimes too. They can remove a lot of undifferentiated work (scaling, sandboxes, identity) —
evaluate them with the same checklist as frameworks (Ch 27): control, observability, portability, data residency,
cost.

---

## 4. Code

```bash
pip install fastapi uvicorn httpx pyyaml
```

### 4.1 An agent service: sync, streaming, async jobs, idempotency, backpressure, degradation

```python
# agent_service.py — sync, streaming (SSE) and async-job endpoints with idempotency and degradation
import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

JOBS: dict[str, dict] = {}            # production: Postgres/Redis, not process memory
IDEMPOTENCY: dict[str, str] = {}      # idempotency key -> job id
QUEUE: asyncio.Queue = asyncio.Queue(maxsize=1000)
STATE = {"provider_healthy": True}

async def run_agent(question: str) -> str:
    """Stand-in for the real agent (Ch 14). Degrades instead of failing when the provider is down."""
    await asyncio.sleep(0.01)
    if not STATE["provider_healthy"]:
        return ("Our assistant is temporarily limited. I've saved your question and a person will reply "
                "by email within 4 hours.")                     # graceful degradation: queued + honest
    return f"Answer to: {question}"

async def worker():
    while True:
        job_id = await QUEUE.get()
        job = JOBS[job_id]
        job["status"] = "running"
        try:
            job["result"], job["status"] = await asyncio.wait_for(run_agent(job["question"]), timeout=300), "done"
        except Exception as e:                                    # never a stack trace to the user
            job["status"], job["error"] = "failed", type(e).__name__
        finally:
            QUEUE.task_done()

@asynccontextmanager
async def lifespan(app):
    tasks = [asyncio.create_task(worker()) for _ in range(4)]    # worker concurrency ~ provider rate limits
    yield
    for t in tasks:
        t.cancel()

app = FastAPI(lifespan=lifespan)

class Ask(BaseModel):
    question: str

@app.get("/healthz")                      # liveness: is the process alive? (never calls the LLM)
def healthz():
    return {"ok": True}

@app.get("/readyz")                       # readiness: can we take traffic? (cheap dependency checks only)
def readyz():
    if QUEUE.full():
        raise HTTPException(503, "queue full")
    return {"ready": True, "queue_depth": QUEUE.qsize()}

@app.post("/ask")                         # < ~30s tasks: synchronous
async def ask(req: Ask):
    return {"answer": await asyncio.wait_for(run_agent(req.question), timeout=30)}

@app.post("/ask/stream")                  # streaming for perceived latency (server-sent events)
async def ask_stream(req: Ask):
    async def events():
        answer = await run_agent(req.question)
        for word in answer.split():
            yield f"data: {json.dumps({'delta': word + ' '})}\n\n"
        yield "data: [DONE]\n\n"
    return StreamingResponse(events(), media_type="text/event-stream")

@app.post("/tasks", status_code=202)      # long tasks: accept, queue, return a handle
async def create_task(req: Ask, idempotency_key: str | None = Header(default=None)):
    if idempotency_key and idempotency_key in IDEMPOTENCY:       # client retried: same job, no duplicate
        return {"task_id": IDEMPOTENCY[idempotency_key], "duplicate": True}
    if QUEUE.full():
        raise HTTPException(429, "busy, retry later", headers={"Retry-After": "30"})   # backpressure
    job_id = str(uuid.uuid4())
    JOBS[job_id] = {"status": "queued", "question": req.question}
    if idempotency_key:
        IDEMPOTENCY[idempotency_key] = job_id
    await QUEUE.put(job_id)
    return {"task_id": job_id, "duplicate": False}

@app.get("/tasks/{task_id}")
def get_task(task_id: str):
    job = JOBS.get(task_id)
    if job is None:
        raise HTTPException(404, "unknown task")
    return {k: v for k, v in job.items() if k != "question"}
```

### 4.2 Exercise it

```python
# test_service.py
import time
from fastapi.testclient import TestClient
import agent_service as svc

with TestClient(svc.app) as c:
    print(c.get("/readyz").json())
    print(c.post("/ask", json={"question": "where is A-1043?"}).json())
    print(c.post("/ask/stream", json={"question": "hi there"}).text.strip().splitlines()[:2])
    t1 = c.post("/tasks", json={"question": "audit 500 orders"}, headers={"Idempotency-Key": "k-1"}).json()
    t2 = c.post("/tasks", json={"question": "audit 500 orders"}, headers={"Idempotency-Key": "k-1"}).json()
    print(t1, t2)
    for _ in range(50):
        status = c.get(f"/tasks/{t1['task_id']}").json()
        if status["status"] in ("done", "failed"):
            break
        time.sleep(0.02)
    print(status)
    svc.STATE["provider_healthy"] = False
    print(c.post("/ask", json={"question": "where is A-1043?"}).json())
```

Verified output (task ID shortened):

```
{'ready': True, 'queue_depth': 0}
{'answer': 'Answer to: where is A-1043?'}
['data: {"delta": "Answer "}', '']
{'task_id': '0700b1c2-…', 'duplicate': False} {'task_id': '0700b1c2-…', 'duplicate': True}
{'status': 'done', 'result': 'Answer to: audit 500 orders'}
{'answer': "Our assistant is temporarily limited. I've saved your question and a person will reply by email within 4 hours."}
```

### 4.3 Capacity and availability planner

```python
# capacity.py — Little's law, provider token limits, availability math (offline)
def plan(arrival_per_s, seconds_per_task, tokens_per_task, provider_tpm, availabilities):
    concurrency = arrival_per_s * seconds_per_task                     # Little's law: L = λ × W
    tpm_needed = arrival_per_s * 60 * tokens_per_task
    chain = 1.0
    for a in availabilities:
        chain *= a                                                     # serial dependencies multiply
    downtime_h = (1 - chain) * 30 * 24
    print(f"concurrent runs in flight: {concurrency:,.0f}")
    print(f"tokens/minute needed: {tpm_needed:,.0f} vs provider limit {provider_tpm:,.0f} "
          f"-> {'OK' if tpm_needed <= provider_tpm else 'BOTTLENECK: raise tier, add provider, cache, or queue'}")
    print(f"chain availability {chain:.2%} -> ~{downtime_h:.1f} hours down per 30 days")

plan(arrival_per_s=20, seconds_per_task=30, tokens_per_task=40_000, provider_tpm=20_000_000,
     availabilities=[0.999, 0.999, 0.995, 0.990])

two_providers = 1 - (1 - 0.990) * (1 - 0.990)                          # parallel redundancy adds nines
print(f"one provider 99.0% -> two independent providers with fallback {two_providers:.2%}")
```

Verified output:

```
concurrent runs in flight: 600
tokens/minute needed: 48,000,000 vs provider limit 20,000,000 -> BOTTLENECK: raise tier, add provider, cache, or queue
chain availability 98.31% -> ~12.2 hours down per 30 days
one provider 99.0% -> two independent providers with fallback 99.99%
```

### 4.4 Dockerfile

```dockerfile
FROM python:3.12-slim
RUN useradd --create-home app
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt     # pinned versions in requirements.txt
COPY . .
USER app                                               # never run as root
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/healthz')"
CMD ["uvicorn", "agent_service:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4.5 Kubernetes: API + workers scaled on queue depth (KEDA)

```yaml
# k8s.yaml — API + workers; workers scale on QUEUE DEPTH (KEDA), not CPU
apiVersion: apps/v1
kind: Deployment
metadata: {name: agent-api}
spec:
  replicas: 3
  selector: {matchLabels: {app: agent-api}}
  template:
    metadata: {labels: {app: agent-api}}
    spec:
      securityContext: {runAsNonRoot: true}
      containers:
        - name: api
          image: registry.example.com/agent-api:1.4.2          # pinned tag, never :latest
          ports: [{containerPort: 8000}]
          envFrom: [{secretRef: {name: agent-secrets}}]         # synced from a secrets manager
          resources: {requests: {cpu: "250m", memory: "512Mi"}, limits: {memory: "1Gi"}}
          readinessProbe: {httpGet: {path: /readyz, port: 8000}, periodSeconds: 5}
          livenessProbe: {httpGet: {path: /healthz, port: 8000}, periodSeconds: 10}
---
apiVersion: apps/v1
kind: Deployment
metadata: {name: agent-worker}
spec:
  selector: {matchLabels: {app: agent-worker}}
  template:
    metadata: {labels: {app: agent-worker}}
    spec:
      terminationGracePeriodSeconds: 300                      # let in-flight runs checkpoint
      containers:
        - name: worker
          image: registry.example.com/agent-worker:1.4.2
          envFrom: [{secretRef: {name: agent-secrets}}]
          resources: {requests: {cpu: "250m", memory: "512Mi"}, limits: {memory: "1Gi"}}
---
apiVersion: keda.sh/v1alpha1
kind: ScaledObject
metadata: {name: agent-worker-scaler}
spec:
  scaleTargetRef: {name: agent-worker}
  minReplicaCount: 2
  maxReplicaCount: 50                                          # cap = what provider rate limits allow
  triggers:
    - type: redis
      metadata: {address: redis:6379, listName: agent-jobs, listLength: "20"}   # ~20 queued jobs per worker
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: {name: agent-api-pdb}
spec:
  minAvailable: 2
  selector: {matchLabels: {app: agent-api}}
```

(The YAML parses as four valid documents; deploying the `ScaledObject` requires KEDA installed in the cluster.)

---

## 5. Production view

| Signal | Action |
|---|---|
| Queue depth and age of oldest job | Scale workers (up to provider limits); alert if age exceeds SLO |
| 429s from providers | Lower concurrency, add quota, cache more, add a second provider |
| Error budget burn rate | Freeze risky releases; roll back |
| Canary vs baseline: eval scores, cost/task, latency, guardrail triggers | Auto-promote or auto-rollback |
| Per-tenant usage and noisy neighbours | Fair queuing, quotas, move big tenants to silo/bridge |
| Restore drills | Prove DR works before you need it |

---

## 6. Common mistakes

- Running long agent tasks as synchronous HTTP requests.
- Readiness probes that call the LLM.
- CPU-based autoscaling for I/O-bound workers.
- In-memory state in pods (lost on every deploy).
- Non-idempotent job handlers on at-least-once queues.
- Shared prompt/response caches across tenants.
- Shipping prompt changes with code deploys only (no fast rollback).
- Load testing against the real provider at full scale (and paying for it) — or never load testing at all.

---

## 7. Practice

**Level 1**
1. Run `test_service.py`. Then set the queue `maxsize` to 1 and fire 5 tasks quickly — what status codes do you get?
2. Run `capacity.py` for your own numbers: 5 tasks/s, 12 s per task, 25K tokens per task.

**Level 2**
3. Replace the in-memory queue and job store with **Redis** (lists or streams) and **Postgres**, run the API and
   two worker processes with `docker compose`, and kill a worker in the middle of a job. Does the job complete?
4. Write a **load test** (e.g. with Locust or k6) against the service with a mock agent that sleeps 2–20 s.
   Find the first bottleneck and fix it.

**Level 3**
5. Deploy to a local Kubernetes cluster (kind or minikube) with KEDA: API + workers + Redis + Postgres. Configure
   a canary (two worker Deployments with different prompt versions, traffic split by queue), run your eval suite
   against both, and write the promotion/rollback rule you'd automate.

---

## 8. Check yourself

1. Which endpoint style fits a task with p99 = 4 minutes, and why?
2. State Little's law and use it: 10 tasks/s, 45 s each.
3. Why is 99.9% × 99.9% × 99.5% × 99.0% a strong argument against extra services?
4. Why shouldn't agent workers autoscale on CPU?
5. Describe the bridge multi-tenancy model and the four boundaries.
6. What should trigger an automatic canary rollback for an agent release?

<details>
<summary>Answers</summary>

1. An async job (202 + task ID, then polling/streaming/webhook): a synchronous request would time out or tie up
   connections for minutes.
2. L = λ × W = 10 × 45 = 450 runs in flight.
3. Serial availability multiplies to ~98.3% (~12 hours/month down), worse than any single component; each extra
   dependency lowers it further.
4. They mostly wait on network I/O (model/tool calls), so CPU stays low even when overloaded; scale on queue depth
   or in-flight runs, capped by provider limits.
5. Shared control plane with dedicated per-tenant data plane (DBs, indexes, keys). Boundaries: data, compute,
   credentials, inference (including prompt/response caches).
6. SLO burn (errors/latency), eval-score drop vs baseline, cost-per-task spike, guardrail-trigger spike, or rising
   human-override rate.

</details>

---

## 9. Key terms

**deployment stages** · **sync / streaming / async job endpoints** · **202 Accepted** · **idempotency key** ·
**liveness vs readiness probe** · **backpressure** · **queue / worker** · **at-least-once delivery** · **dead-letter
queue** · **Little's law** · **TPM limits** · **availability multiplication** · **graceful degradation ladder** ·
**KEDA / queue-depth autoscaling** · **PodDisruptionBudget** · **silo / pool / bridge** · **four tenancy boundaries** ·
**eval gate** · **shadow / canary / blue-green** · **config as deployable** · **SLO / error budget** · **load test /
chaos test** · **RPO / RTO** · **data residency**

Next: [Chapter 39 — Serving open models: vLLM and inference engineering →](39-serving-open-models-vllm.md)
