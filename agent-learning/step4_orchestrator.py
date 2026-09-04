import ast
import operator
import ollama

MODEL = "llama3.2"

# ---------- Math worker (has the calculator tool) ----------

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg}

def safe_eval(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        return OPS[type(node.op)](safe_eval(node.left), safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return OPS[type(node.op)](safe_eval(node.operand))
    raise ValueError("unsupported")

def calculator(expression: str) -> str:
    try:
        return str(safe_eval(ast.parse(expression, mode="eval").body))
    except Exception:
        return f"error: could not parse '{expression}' as arithmetic."

MATH_TOOLS = [{
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Evaluate arithmetic. Example: '47 * 89' -> '4183'. Supports + - * / ** ().",
        "parameters": {
            "type": "object",
            "properties": {"expression": {"type": "string"}},
            "required": ["expression"],
        },
    },
}]

def math_worker(question, max_iterations=5):
    """Isolated agent: only sees the math question, only has the calculator tool."""
    messages = [{"role": "user", "content": question}]
    for _ in range(max_iterations):
        response = ollama.chat(model=MODEL, messages=messages, tools=MATH_TOOLS)
        msg = response["message"]
        if not msg.get("tool_calls"):
            return msg["content"]
        messages.append(msg)
        for call in msg["tool_calls"]:
            result = calculator(call["function"]["arguments"]["expression"])
            messages.append({"role": "tool", "content": result})
    return "math worker: hit max_iterations"

# ---------- Writing worker (no tools, just prose) ----------

def writing_worker(question):
    """Isolated agent: only sees the writing question, no tools at all."""
    messages = [
        {"role": "system", "content": "You are a concise writing assistant. Answer in 2-3 sentences."},
        {"role": "user", "content": question},
    ]
    response = ollama.chat(model=MODEL, messages=messages)
    return response["message"]["content"]

# ---------- Orchestrator ----------

ROUTER_TOOLS = [{
    "type": "function",
    "function": {
        "name": "route",
        "description": "Decide which worker should handle the user's question.",
        "parameters": {
            "type": "object",
            "properties": {
                "worker": {
                    "type": "string",
                    "enum": ["math", "writing"],
                    "description": "pick one",
                }
            },
            "required": ["worker"],
        },
    },
}]

def orchestrator(question, max_routing_attempts=2, extra_context_by_worker=None):
    """Known limitation: llama3.2 sometimes answers directly instead of calling
    'route'. We retry once with a stronger instruction before giving up loudly.

    IMPORTANT: routing decision is made on the raw `question` only. `extra_context_by_worker`
    (a dict like {"math": "...", "writing": "..."}, e.g. per-worker remembered notes)
    is looked up ONLY AFTER routing, and only the chosen worker's own entry is
    injected -- mixing notes into the routing decision confused the router in
    testing (a clean math question wrapped in conversational memory text got
    routed to the writing worker instead of math). Each worker also only ever
    sees ITS OWN notes, never another worker's -- that's the actual isolation:
    math_worker never sees writing_worker's memory and vice versa."""
    messages = [
        {"role": "system", "content": "Route every question to exactly one worker by calling 'route'."},
        {"role": "user", "content": question},
    ]
    for attempt in range(max_routing_attempts):
        response = ollama.chat(model=MODEL, messages=messages, tools=ROUTER_TOOLS)
        msg = response["message"]
        if msg.get("tool_calls"):
            break
        messages.append({"role": "user", "content": "You must call the 'route' tool. Do not answer directly."})
    else:
        return "ERROR: orchestrator failed to route after retry", None

    worker = msg["tool_calls"][0]["function"]["arguments"]["worker"]
    print(f"[orchestrator routed to: {worker}]")

    extra_context = (extra_context_by_worker or {}).get(worker)
    worker_input = question if not extra_context else f"{extra_context}\n\n{question}"

    if worker == "math":
        return math_worker(worker_input), worker
    elif worker == "writing":
        return writing_worker(worker_input), worker
    else:
        return f"unknown worker: {worker}", worker

if __name__ == "__main__":
    for q in [
        "What is 128 * 37?",
        "Write a one-sentence tagline for a coffee shop.",
        "Explain how you'd calculate a 15% tip",
    ]:
        print(f"\nQ: {q}")
        answer, worker = orchestrator(q)
        print(f"A ({worker}): {answer}")
