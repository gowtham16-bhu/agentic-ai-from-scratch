import ollama

response = ollama.chat(
    model="llama3.2",
    messages=[{"role": "user", "content": "What is 47 * 89? Answer with just the number."}],
)
print(response["message"]["content"])
