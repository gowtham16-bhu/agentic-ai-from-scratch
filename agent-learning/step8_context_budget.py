import ollama
import tiktoken
model ="llama3.2"
SYSTEM_PROMPT = "You are an ecommerce support assistant. Be concise."
enc = tiktoken.get_encoding("cl100k_base")


def token_count(data) -> int:
    token = enc.encode(data)
    return len(token)
def context_report(history) -> int:

    
    
    return token_count("".join(msg["content"] for msg in history))

   
   
   
    ... # count tokens for each part, print them, return total


def support_chat():
    messages =[{"role":"system","content":SYSTEM_PROMPT}]
    turns = [
        "Where is my order #4521?",
        "I want to return it, it arrived damaged.",
        "What's your return policy?",
        "Can you recommend something similar but cheaper?",
    ]
    for turn in turns:
        messages.append({"role":"user","content":turn})
        ...  # call the model, print the reply
        response = ollama.chat(model=model,messages=messages)
        print(response["message"]["content"])

        ...  # call context_report(...) here, after appending the reply too
   
        ...  # append the assistant's reply to messages
        messages.append({"role":"assistant","content":response["message"]["content"]})
        total=context_report(messages)
        print(f"context so far: {total} tokens")


if __name__ == "__main__":
    support_chat()
