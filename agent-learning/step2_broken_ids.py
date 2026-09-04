import ollama

def calculator(expression: str) -> str:
    try:
        return str(eval(expression))
    except Exception as e:
        return f"error: {e}"

def weather(city: str) -> str:
    fake_data = {"paris": "18C, rainy", "tokyo": "26C, sunny"}
    return fake_data.get(city.lower(), "unknown city")

tools = [
    {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a basic arithmetic expression like '47 * 89' and return the result.",
            "parameters": {
                "type": "object",
                "properties": {"expression": {"type": "string", "description": "e.g. '47 * 89'"}},
                "required": ["expression"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "weather",
            "description": "Get current weather for a city name.",
            "parameters": {
                "type": "object",
                "properties": {"city": {"type": "string", "description": "e.g. 'Paris'"}},
                "required": ["city"],
            },
        },
    },
]

messages = [{
    "role": "user",
    "content": "What is 47 * 89, AND what is the weather in Tokyo? Call both tools in the same turn.",
}]

max_iterations = 10
for i in range(max_iterations):
    print(f"\n--- iteration {i} ---")
    response = ollama.chat(model="llama3.2", messages=messages, tools=tools)
    msg = response["message"]
    print("date":response)
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
        elif name == "weather":
            result = weather(args["city"])
        else:
            result = f"error: unknown tool {name}"
        print(f"ran {name}({args}) -> {result}")
        # BUG: no id linking this result back to `call`. If order gets
        # scrambled or a call is skipped, the model pairs results wrong.
        messages.append({"role": "tool", "content": result})
else:
    print("hit max_iterations without finishing")
