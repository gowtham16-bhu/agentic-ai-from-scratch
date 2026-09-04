import ollama

def calculator(expression: str) -> str:
    return "error: calculatoe is broken "
   

tools = [{
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Evaluate a basic arithmetic expression like '47 * 89' and return the result.",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "e.g. '47 * 89'"}
            },
            "required": ["expression"],
        },
    },
}]

messages = [{"role": "user", "content": "What is 47 * 89?"}]

max_iterations = 10
for i in range(max_iterations):
    print(f"\n--- iteration {i} ---")
    response = ollama.chat(model="llama3.2", messages=messages, tools=tools)
    msg = response["message"]
    print("model said:", msg)

    if not msg.get("tool_calls"):
        print("\nFINAL ANSWER:", msg["content"])
        break

    messages.append(msg)
    for call in msg["tool_calls"]:
        name = call["function"]["name"]
        args = call["function"]["arguments"]
        if name == "calculator":
            result = calculator(args["expression"])
        else:
            result = f"error: unknown tool {name}"
        print(f"ran {name}({args}) -> {result}")
        messages.append({"role": "tool", "content": result})
else:
    print("hit max_iterations without finishing")
