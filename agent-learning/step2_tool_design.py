import ast
import operator
import ollama

# eval() runs arbitrary Python -- someone could pass "__import__('os').system('rm -rf /')".
# This only allows numbers and + - * / ** ( ), nothing else.
OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg}

def safe_eval(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        return OPS[type(node.op)](safe_eval(node.left), safe_eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return OPS[type(node.op)](safe_eval(node.operand))
    raise ValueError(f"unsupported expression: {ast.dump(node)}")

def calculator(expression: str) -> str:
    try:
        tree = ast.parse(expression, mode="eval")
        result = safe_eval(tree.body)
        return str(result)
    except ZeroDivisionError:
        return "error: division by zero. Check the expression and try a valid one."
    except Exception:
        return (f"error: could not parse '{expression}' as arithmetic. "
                f"Only numbers and + - * / ** ( ) are supported, e.g. '47 * 89' or '(2+3)*4'.")

tools = [{
    "type": "function",
    "function": {
        "name": "calculator",
        "description": (
          "does math"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "e.g. '47 * 89' or '(12 + 8) / 4'"}
            },
            "required": ["expression"],
        },
    },
}]

def run(question, model="llama3.2", max_iterations=10):
    messages = [{"role": "user", "content": question}]
    for i in range(max_iterations):
        response = ollama.chat(model=model, messages=messages, tools=tools)
        msg = response["message"]
        if not msg.get("tool_calls"):
            print(f"[{i} iterations] FINAL:", msg["content"])
            return i
        messages.append(msg)
        for call in msg["tool_calls"]:
            args = call["function"]["arguments"]
            result = calculator(args["expression"])
            print(f"  iter {i}: ran calculator({args}) -> {result}")
            messages.append({"role": "tool", "content": result})
    print("hit max_iterations without finishing")
    return max_iterations

if __name__ == "__main__":
    run("What is 47 * 89?")
    print()
 
