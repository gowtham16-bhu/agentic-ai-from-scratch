import ollama

response = ollama.embed(model="nomic-embed-text", input="What's your return policy?")
vector = response["embeddings"][0]   # a list of floats, e.g. [0.012, -0.44, ...]
print(len(vector))                    # dimensionality, e.g. 768

