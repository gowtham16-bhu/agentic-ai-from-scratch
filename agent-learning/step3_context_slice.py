import ollama

# Pretend this is a big pile of company data. In a real system this might be
# thousands of tokens across many files -- too much to hand every worker in full.
DATA = {
    "sales": "Q3 revenue: $420k. Q2 revenue: $390k. Top product: Widget Pro.",
    "support": "Open tickets: 12. Avg resolution time: 4.2 hours. Top issue: login bugs.",
}

def ask(question, context, model="llama3.2"):
    messages = [
        {"role": "system", "content": f"Answer using only this context:\n{context}"},
        {"role": "user", "content": question},
    ]
    response = ollama.chat(model=model, messages=messages)
    return response["message"]["content"]

# BAD: dump everything into every worker regardless of what it needs
def worker_bad(question):
    full_context = "\n".join(DATA.values())
    return ask(question, full_context)

# GOOD: orchestrator picks the one slice relevant to this question,
# worker only ever sees that slice
def orchestrator_good(question, topic):
    relevant_slice = DATA[topic]
    return ask(question, relevant_slice)

if __name__ == "__main__":
    q = "What was the top issue reported?"

    print("=== BAD: worker gets ALL context ===")
    print(worker_bad(q))

    print("\n=== GOOD: worker gets ONLY the support slice ===")
    print(orchestrator_good(q, topic="support"))
