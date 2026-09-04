# Learner Profile

- Language: Python (zero prior experience — will learn syntax through building, not a separate course)
- Level: has used an LLM API directly (no tool-calling loop yet)
- 90-day goal: multi-agent system
- Time: weekends full, weekdays ~3hrs evenings, 3hrs/weekday
- Hard constraint: 1 month timeline (started 2026-09-04)

# Reality check given to learner

Zero-Python to production multi-agent in 1 month is not realistic if "production" means
evals + guardrails + observability. Agreed plan: compress to a 4-week track that ships a
working orchestrator + 2 worker agents prototype, teaching Python inline as needed.
Evals (Module 6) and production hardening (Module 7) are explicitly deferred — flagged to
learner as the part that turns a demo into something safe to leave running unattended.

# Compressed 4-week roadmap

- Week 1: Module 1 (the loop, by hand, Python basics inline) + Module 2 (tool design)
- Week 2: Module 3 (context engineering, light) + start Module 10 concepts early
  (orchestrator/worker contract) applied directly — skip Module 4/5 for now
- Week 3: Build the multi-agent capstone (orchestrator + 2 isolated workers)
- Week 4: Harden minimally — max_iterations, basic tracing, one eval case per agent.
  Push to do Module 6 properly after the 1-month mark since it was deferred.

# Session log

(newest last)

- 2026-09-04 — Intake complete. Roadmap above written. Starting Module 1 next.
- 2026-09-04 — Switched from Anthropic API to local Ollama (llama3.2) per learner's choice.
  Set up venv, installed anthropic (unused now) + ollama python packages.
- 2026-09-04 — Module 1 (the loop, by hand) done. Artifacts: step0_no_tool.py (showed
  llama3.2 confidently wrong on 47*89 -> 4173, actual 4183), step1_loop.py (calculator
  tool loop, correct answer via tool use). Break exercise: learner made calculator always
  error; model did NOT infinite-loop as I predicted — it gave up after one failed tool
  call and fell back to guessing from memory (got lucky, right answer). Lesson drawn:
  error messages steer model behavior (Module 2 preview), and max_iterations is needed
  regardless of what a given model tends to do, since behavior is model-dependent.
  Learner correctly explained the core purpose of max_iterations. Next: Module 2, tool
  design (rewrite calculator to not use eval(), better error messages, measure iterations
  before/after).
- 2026-09-04 — Module 2 (tool design) done. Artifact: step2_tool_design.py — calculator
  rewritten with ast-based safe_eval instead of eval() (security), and error messages
  that give actionable guidance (division by zero -> model explained correctly instead of
  guessing). Break exercise took two tries: first attempt changed the *question* to "does
  math" instead of the *description*, which surfaced an unplanned but good lesson --
  vague input caused the model to hallucinate tool arguments (called calculator(18+13)
  out of nowhere). Second attempt correctly gutted the description to "does math" while
  keeping question "What is 47*89?" -- tool still worked, because tool/param names and a
  clear question gave enough signal. Lesson: description quality matters most exactly
  when things are ambiguous (multiple similar tools, vague phrasing), not in the easy
  case. Learner needed several explicit corrections to actually isolate the variable
  being tested -- flag for future sessions: give more literal step-by-step file edits
  up front rather than describing the change and expecting them to locate it, this
  learner is still building basic code-editing/experiment-isolation habits alongside
  Python itself. Next: Module 3, context engineering (light version per compressed plan).
- 2026-09-04 — Module 3 (context engineering, light) done. Artifact:
  step3_context_slice.py -- bad (dump all context) vs good (orchestrator picks relevant
  slice) pattern. Toy example too small to show a quality difference (both answered
  correctly), which was called out honestly -- the point was the orchestrator-picks-slice
  pattern itself, which is the actual mechanism needed for the Week 3 multi-agent
  capstone. Learner's own explanation of why full-context hurts was muddled (blended
  context-rot with tool-arg-hallucination from Module 2); gave a cleaner two-part
  correction: attention dilution vs stale/contradicting context. Skipped Module 4
  (memory/retrieval) and Module 5 (MCP/Skills) per compressed plan -- deferred to after
  the 1-month capstone. Next: build the multi-agent capstone -- orchestrator + 2 isolated
  worker agents, likely reusing calculator-style tool pattern plus the context-slice
  pattern above.
- 2026-09-04 — Multi-agent capstone core built. Artifact: step4_orchestrator.py --
  orchestrator uses a "fake tool" (route, with enum constraint) purely for structured
  output/routing decision, not a real function call; routes to math_worker (isolated
  agent, has calculator tool, reuses Module 2 loop) or writing_worker (isolated agent,
  no tools, prose only). Both workers get fresh isolated message lists, no shared
  context. Had to stop and explain JSON-schema-as-dict (type/properties/enum/required)
  and the fake-tool-for-structured-output pattern in detail -- learner flagged that I was
  moving too fast introducing new concepts inline with code without explaining syntax
  first, which was fair; adjusted to explain-before-code for new concepts going forward.
  Break exercise (vague enum description "pick one" + ambiguous tip-calculation question)
  routed to writing worker, which computed 15% tip correctly WITHOUT a calculator tool --
  worked by luck (easy math), but demonstrated the real risk: routing errors are silent,
  no eval catches a misrouted question, and a worker without the right tool will still
  confidently answer using ungrounded arithmetic. This became the motivating case for
  building an eval next. Next: build a small eval suite (5-10 cases, known correct
  routing + known correct answers) for the orchestrator, per Module 6 compressed into
  the capstone rather than deferred entirely.
- 2026-09-04 — Eval suite built (step5_eval.py), 5 cases checking routing + answer
  correctness. First run: 4/5, failure was the EVAL being wrong (expected "225.0",
  model said "225") not the agent -- important lesson landed: a failing eval doesn't
  always mean the system is broken, check why before "fixing" the agent. Learner fixed
  the eval string itself. Second run after fix: 4/5 again, but different failure --
  the SAME tagline question that passed earlier failed this run because the orchestrator
  didn't call the route tool at all (non-deterministic tool-calling behavior on
  llama3.2, a known local-model weakness vs hosted models). Decision: documented as a
  known limitation rather than adding a retry, so the capstone's failure mode is honest
  and visible rather than papered over.

  KNOWN LIMITATION (capstone documented failure mode): orchestrator's routing via the
  route tool is not 100% reliable on llama3.2 -- same question can sometimes get
  answered directly instead of routed, causing worker=None. No retry logic added
  deliberately, to keep the eval measuring real reliability rather than hiding it.

  Multi-agent capstone status: CORE COMPLETE -- orchestrator + 2 isolated workers
  (step4_orchestrator.py) + eval suite (step5_eval.py) + one documented failure mode.
  Missing vs full Module 8 rubric: no tracing/observability, no kill switch, no
  architecture doc -- all deferred, consistent with the 1-month compressed plan agreed
  at intake. Next session: ask learner whether to (a) write a short architecture doc +
  add a basic max_iterations/kill-switch guard to call the capstone genuinely done, or
  (b) continue into remaining deferred modules (4 memory/retrieval, 5 MCP, 7 production
  hardening) if timeline allows.
- 2026-09-04 — CAPSTONE CLOSED OUT. Added bounded retry (max_routing_attempts=2) to
  orchestrator with loud ERROR on final failure, replacing the silent worker=None.
  This reversed the earlier "document don't fix" decision -- flagged that explicitly
  to learner before proceeding since I made the call unilaterally; learner approved
  keeping it. Re-ran eval: 5/5 (the flaky routing case now passes via retry, but still
  fails loudly if both attempts miss, so the eval still catches real failures). Wrote
  CAPSTONE.md: architecture, why isolation over one agent with two tools, the known
  failure mode (model sometimes skips the route tool call, observed directly not
  theoretical) and its mitigation, how it's tested, and an explicit "not here on
  purpose" section (no tracing, no kill switch, no memory/MCP, no LLM-judge grading).

  MULTI-AGENT CAPSTONE: DONE. Artifacts: step4_orchestrator.py, step5_eval.py,
  CAPSTONE.md. ~3 weeks remain in the learner's 1-month window. Next session should ask
  the learner what to do with remaining time -- options in rough priority order given
  their 90-day multi-agent goal: (1) add a 3rd worker + test isolation still holds,
  (2) do the deferred production-hardening basics (tracing, kill switch) since those
  were the most-cited gap, (3) revisit Module 4/5 (memory, MCP) if a real use case
  needs them. Do not assume which without asking.

- 2026-09-04 — Learner explicitly asked me to decide priority order rather than choosing
  themselves; decided hardening before memory (consolidate existing system before adding
  a new architectural concept; trace logs from hardening double as a stepping stone into
  memory). Learner chose production hardening as next module.

  Module 7 (compressed) done. Artifact: step6_hardened.py, wraps step4_orchestrator.py
  (left untouched as clean reference) with: (1) tracing to traces.jsonl, one JSON line
  per run with timestamp/question/worker/answer/latency, (2) file-based kill switch
  (STOP file) checked before any model call, raises KilledError if present. Was upfront
  that this is NOT production-grade (real version: OpenTelemetry/dashboards, token+cost
  tracking not just latency, remote kill flag not local file, alerting, retries with
  backoff) -- deliberately simplified to teach the concept first. Break exercise:
  learner created STOP file, got clean refusal with no wasted model call, deleted it,
  reran successfully. Trace log incidentally revealed model warm-up effect (first math
  call 4.7s, second 1.49s) -- concrete example of why tracing surfaces things you'd
  never notice just reading terminal output.

  Learner is engaging well conceptually (asked good clarifying questions about
  route-as-fake-tool, hardening vs quality distinction) but still building basic
  code-editing hygiene (has needed literal line-by-line edit instructions multiple times
  across modules 2, 4). Continue giving exact snippets to paste rather than describing
  changes abstractly. Next: Module 4 (memory/retrieval) as agreed order, or ask learner
  given ~3 weeks remain in the 1-month window.

- 2026-09-04 — Module 4 (memory, session-level) done. Artifact: step7_memory.py --
  file-based notes.txt read/append, no vector DB (deliberately chose scratchpad-file
  memory over RAG since data is tiny, per curriculum's "defend not using a vector DB"
  done-when). Session switched to Tamil mid-session per learner request.

  Real bug surfaced and fixed: naively prepending remembered notes onto the question
  before sending to the orchestrator corrupted the ROUTING decision, not just the
  worker's answer -- a clean math question ("what is my favorite number times 10")
  wrapped in conversational memory text got routed to `writing` instead of `math`,
  and the writing worker computed the arithmetic unverified (got lucky, right answer,
  same silent-risk pattern as earlier modules). Fix: added extra_context param to
  orchestrator() (step4_orchestrator.py) -- routing always happens on the raw
  question only; extra_context is injected only into whichever worker gets picked,
  after the routing decision, never into the router's own input. Threaded extra_context
  through traced_orchestrator (step6_hardened.py) too. Re-ran: routed to math correctly,
  used the calculator tool, correct answer (70).

  General lesson for learner: adding context for one purpose (memory) can silently
  break a different decision elsewhere in the pipeline (routing) because everything
  shares the same input text -- a real, recurring multi-agent bug class, not a one-off.

  Status: Module 4 done. Remaining from original curriculum, still deferred per
  1-month scope: Module 5 (MCP/Skills), true RAG/vector retrieval (not needed yet,
  data still small), deeper Module 7 production items (cost tracking, real
  observability tooling). ~2.5 weeks left in the 1-month window. Next session: ask
  learner what's most valuable with remaining time -- MCP (Module 5) was the last
  unstarted foundational module before Track 2 (advanced/multi-agent depth).

- 2026-09-04 — Learner correctly pushed back: I had context-switched to Module 5 (MCP)
  before finishing Module 4 properly, and asked about "episodic memory" (a term they
  found browsing, not covered). Feedback logged: complete a module fully -- close known
  gaps the learner points out -- before moving to a new topic, even under time pressure.
  Answered episodic vs semantic memory distinction directly (episodic = event log with
  history, semantic = facts without event context; notes.txt as built is episodic, a
  refinement of "session memory" not a 4th separate category).

  Fixed the real gap: per-worker memory isolation. Previously notes.txt was ONE shared
  file across math_worker and writing_worker -- not actually isolated, just session
  memory shared globally. Refactored: orchestrator() now takes extra_context_by_worker
  (a dict keyed by worker name), looks up the chosen worker's entry only AFTER routing.
  step7_memory.py now uses notes_math.txt and notes_writing.txt separately. Verified
  with a 3-run test: math worker remembered "favorite number is 7" correctly on run 3,
  writing worker's separate run had zero trace of that fact -- confirmed via reading
  both note files directly, no cross-contamination.

  Module 4 (memory) now genuinely complete: session/episodic memory + per-worker
  isolation both working and verified. MCP (Module 5) work in progress before this
  detour: mcp_calculator_server.py (FastMCP, had to pin mcp<2 since installed mcp was
  v2 with renamed API -- real lesson in reading error messages for the fix) and
  mcp_client_test.py (async client, connects over stdio, lists tools, calls calculator
  and word_count successfully). Break exercise (empty docstring on word_count) was
  given but not yet run -- pick back up there next.

- 2026-09-04 — Deep MCP mechanics session (learner pushed hard on "black box" feeling,
  correctly, multiple times). Corrected an earlier mistake: I'd said stdio transport was
  like HTTPS -- wrong, stdio uses subprocess stdin/stdout pipes, no network involved.
  Walked through, with exact code line references: (1) stdin/stdout as OS-level process
  concepts, (2) server lifecycle -- lives for the duration of the client's `async with`
  block, not "forever" and not "restarted per call" (corrected my own earlier imprecise
  wording), (3) FastMCP is a helper class in the official mcp SDK, not a new framework,
  auto-generates JSON schema from function signature + docstring, (4) full step-by-step
  execution trace from list_tools() JSON-RPC message through LLM tool_call through
  session.call_tool() through the server running the real function and returning result
  -- mapped explicitly onto the Module 1 loop the learner already knows, showing MCP only
  changes WHERE the function executes, not the loop logic itself. Clarified the
  route/fake-tool trick is NOT an MCP concept -- MCP tools are always real; a fake
  structured-output tool can be mixed into the same `tools=` list at the CLIENT level
  regardless of whether other tools came from MCP or were hardcoded.

  Then built HTTP/SSE transport as a second real, working example (not just described):
  mcp_http_server.py (mcp.run(transport="sse"), port=8765, only one line different from
  the stdio version) and mcp_http_client_test.py (sse_client(url) instead of
  stdio_client(subprocess params)). Ran both successfully -- server visibly listening on
  a real port via Uvicorn, client called calculator over real HTTP, got 4183. Comparison
  table given: stdio = local, subprocess-spawned by client, no address; HTTP = can be
  remote, already running independently, has a real URL.

  FLAGGED FOR FUTURE CURRICULUM ADDITION (learner explicitly asked this be tracked):
  multiple MCP servers + a gateway/aggregator that decides which server owns which tool
  and merges their tool lists before handing to the LLM -- explained as a real, named
  pattern (sometimes called an MCP gateway), conceptually explained as an extension of
  the orchestrator-routing pattern already built (route to a SERVER instead of a WORKER),
  but not implemented -- deliberately deferred, single-MCP-server understanding still
  fresh. Revisit after remaining curriculum if learner has time or a real use case needs
  multiple tool sources.

  Meta-note on teaching pace: learner has repeatedly (memory module, MCP module) needed
  me to slow down and fully resolve mechanics before moving forward, and has been right
  to push back both times a real gap existed. Continue prioritizing full resolution over
  covering more modules given the 1-month timeline -- depth over breadth is working
  better for this learner than my original compressed-speed plan assumed.

- 2026-09-04 — Learner asked about isolation semantics (correctly noted current workers
  run sequentially, one at a time -- no concurrency, so "isolation" here means
  context/memory separation, not execution/concurrency isolation) and then asked whether
  future curriculum covers concurrency/parallelism (LangGraph) and, separately, whether
  a production system would need parallel fan-out to multiple subagents + a synthesizer
  step to aggregate results (map-reduce / fan-out-fan-in orchestration pattern).

  FLAGGED FOR FUTURE CURRICULUM (learner explicitly wants this tracked, do not lose):
  parallel subagent fan-out + synthesizer/aggregator pattern -- distinct from current
  orchestrator (routes to exactly ONE worker sequentially). Real production use cases to
  reference when teaching it: multi-source research aggregation, latency reduction for
  independent subtasks, ensemble/voting for correctness-critical answers, splitting a
  single multi-part question into concurrent sub-questions. Agreed this belongs together
  with the concurrency/parallelism module already deferred to the LangGraph phase (native
  parallel graph edges + reduce/merge node), not retrofitted into the current sequential
  step4_orchestrator.py. Also still pending from earlier: MCP gateway (multiple MCP
  servers + tool-list aggregator), flagged 2026-09-04 in the MCP mechanics session above.

- 2026-09-05 — Pushed full repo to GitHub (public):
  https://github.com/gowtham16-bhu/agentic-ai-from-scratch -- added root README.md
  (setup/run instructions, concepts table, architecture diagram, "what's deliberately
  not here" section written for an outside/interviewer reader) and .gitignore
  (venv/__pycache__ excluded). Learner chose LangGraph as next module.

  FLAGGED FOR FUTURE CURRICULUM: agentic design-pattern vocabulary -- learner asked
  about OODA loop (Observe-Orient-Decide-Act, continuous perceive/act cycle -- formalizes
  what step1_loop.py already does but framed around an environment, not one-shot Q&A),
  goal-oriented/planning agents (BDI -- belief-desire-intention -- persistent goal,
  decomposes into sub-tasks, keeps working until goal state satisfied, vs current
  workers which just answer one question and stop), reactive agents (pure
  stimulus->response, no persistent goal -- writing_worker already fits this), and
  scheduler/trigger-driven agents (cron/event/queue triggered instead of human-turn
  triggered -- ties into existing kill-switch/tracing hardening in step6_hardened.py).
  Agreed placement: after LangGraph module, since goal-oriented/planning patterns are
  typically implemented as LangGraph state machines in practice -- teach the graph
  mechanics first, then the pattern vocabulary maps onto concrete graph shapes instead
  of staying abstract.

- 2026-09-05 — CORRECTION via /agentic-ai-coach skill verification. I had written a
  non-canonical CURRICULUM.md and jumped straight to "LangGraph next," skipping the
  skill's actual Module 6/7/8 done-when bars, which are NOT met yet. Deleted that file.
  Canonical curriculum lives in the skill's curriculum.md, not a project file. Verified
  gaps against it:
  - Module 3 (context): never actually measured tokens/cost, toy example showed no
    quality difference -- done-when NOT met, but not re-opening given compressed scope.
  - Module 5 (MCP): only called own server from own test client, never from Claude Code
    or a separate agent -- done-when NOT met.
  - Module 6 (evals): 5 cases, skill wants 20, and have never actually refused to ship a
    change because the eval dropped -- done-when NOT met.
  - Module 7 (hardening): have latency tracing + local kill switch only. Missing:
    cost/token tracking per run, guardrails, PII handling, prompt-injection defense,
    approval gate on destructive actions -- done-when NOT met.
  - Module 8 (product/shipping): no real external user has completed a task with the
    capstone -- done-when NOT met.
  - Module 12 (LangGraph) is explicitly gated behind Module 8 shipping per the skill.
    Not unlocked yet -- LangGraph work is ON HOLD until 6/7/8 close.
  - OODA/BDI/reactive/scheduler pattern vocabulary flagged earlier is NOT part of the
    skill's canonical curriculum -- parked as optional enrichment, not a real module.

  NEXT (in order, per skill): (1) grow eval suite to ~20 cases + actually block one
  shipped change on a dropped pass rate, (2) add per-run cost/token tracking + one
  approval gate on a destructive-style tool call, (3) get one real external user to
  complete a task with the capstone. Only then does Module 12 unlock.

- 2026-09-05 — SKILL UPGRADED (rewritten, 24 modules M0-M23 + 7 projects P1-P7, plus
  ~20 reference files that did not exist in the old install: patterns.md, production.md,
  scaling.md, runtime-architecture.md, saas-platform.md, agent-security.md,
  langgraph.md, python-primer.md, decisions.md, coverage.md, projects.md,
  long-documents.md, multimodal.md, personalization.md, interfaces.md,
  improvement.md, build-in-public.md, templates/).

  CRITICAL PROCESS CORRECTION: the new skill's top rule is CODE OWNERSHIP -- the LEARNER
  writes the code, the tutor does not. I have violated this for every module so far: I
  wrote step0-step7, both MCP servers, both MCP clients, the README, CAPSTONE.md. Learner
  has artifacts but did not build them, which is exactly why they reported the material
  feeling like "school book examples" -- they were reading, not writing. From here:
  provide design, function shape with `...` bodies, ONE reference example per NEW concept,
  and review. Use the 6-rung escalation ladder; rung 6 (giving the block) requires
  evidence of attempt. Log every rung-5/rung-6 escalation here.

  Re-mapped progress onto the new 24-module curriculum:
  - M1 loop by hand: done (tutor-written)
  - M2 tool design: done (learner drove the error-message experiment themselves)
  - M3 the loop deeply: NOT STARTED <- current module
  - M4 memory: partial (episodic only; curriculum wants 4 memory types + bi-temporal)
  - M5 context + caching: NOT STARTED (no prompt caching at all -- biggest cost lever)
  - M8 evals + CI: partial (5 cases, no CI)
  - M9 production hardening: partial (latency trace + kill switch; no token budget,
    no guardrails, no approval gate)
  - M10 orchestration + isolation: partial (shape only; no return contract, no cost
    measurement, no hallucination-cascade handling)
  - M14 MCP: partial (server built, no gateway/registry/A2A)
  - M6, M7, M11-M13, M15-M23: untouched

  Started M3. Prevents: agent works at 5 turns, silently degrades at 20. Taught the four
  termination conditions (natural finish / no tool wanted / max_iterations / token
  budget) -- learner's math_worker currently has only max_iterations. Assigned as THEIR
  build: add all four + a resumable checkpoint to math_worker, and find where Ollama
  reports token counts themselves. Break-it question asked: "50 turns, last tool result
  correct, repeated same call 5 times -- name the two most likely causes." Awaiting
  their answer + their code.
