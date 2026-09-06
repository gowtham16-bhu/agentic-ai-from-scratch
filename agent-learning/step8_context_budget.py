import ollama
import tiktoken
from rank_bm25 import BM25Okapi
import re                              # the module, gives you re.findall
def tokenize(text):                    # a function YOU write, using re.findall inside it
    return re.findall(r"\w[\w-]*", text.lower())




model ="llama3.2"
SYSTEM_PROMPT = "You are an ecommerce support assistant. Be concise.Answer only using the provided document. If the document doesn't cover something, say so — do not invent details, After each factual claim, cite its source in brackets, e.g. [store_policy.txt]."
enc = tiktoken.get_encoding("cl100k_base")


DOC_FILES = ["store_policy.txt", "shipping_policy.txt", "warranty_policy.txt", "promotions.txt","troubleshooting.txt"]

docs = {}
for filename in DOC_FILES:
    with open(filename, "r") as f:
        docs[filename] = f.read()

doc_keys = list(docs.keys())                          # fixed order, needed to map BM25's scores back to filenames
corpus_tokens = [tokenize(docs[k]) for k in doc_keys]
bm25 = BM25Okapi(corpus_tokens)


def chunk_by_paragraph(text) -> list[str]:
    chunks =text.split("\n\n")
    chuns = [c for c in chunks if len(c) >= 30]
    return chuns
    

with open("faq.txt","r") as f:
    chunks =chunk_by_paragraph(f.read())
    for i ,c in enumerate(chunks):
        docs[f"faq.txt#{i}"] =c


with open("products.txt","r") as f:
    chunks =chunk_by_paragraph(f.read())
    for i ,c in enumerate(chunks):
        docs[f"products.txt#{i}"] =c

doc_keys = list(docs.keys())                          # fixed order, needed to map BM25's scores back to filenames
corpus_tokens = [tokenize(docs[k]) for k in doc_keys]
bm25 = BM25Okapi(corpus_tokens)



def rerank(question, candidate_keys, docs, model):
    """candidate_keys: the top-10 (or 20) keys from RRF. Returns re-sorted top-3."""
    scores = {}
    for key in candidate_keys:
        prompt = f"Question: {question}\nDocument: {docs[key]}\nRate relevance 1-10, output only the number."
        response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
        
        match_text= re.search(r"\d+",response["message"]["content"]) 
        
        if match_text:
            scores[key] = int(match_text.group())
        else:
            scores[key] = 0

        
        
        # parse response into a number -- this will need int() or float() on the reply text, which may not always be clean
    top_sorted = sorted(scores,key= lambda x:scores[x] ,reverse=True) 
    top_3 = top_sorted[:3]  # same sorted()+lambda pattern you've used three times today
    return top_3

def cosine_similarity(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = sum(x * x for x in a) ** 0.5
    mag_b = sum(y * y for y in b) ** 0.5
    return dot / (mag_a * mag_b)


def score_candidates(question, docs, doc_keys, bm25) -> list[str]:
    """Everything currently inside retrieve() up through getting top-10 RRF keys.
    Returns the top-10 list. Move your existing cosine+BM25+RRF code (lines ~68-109) into here."""
    ...
    question_res = ollama.embed(model="nomic-embed-text",input=question)  # embed the question — one ollama.embed call, get ["embeddings"][0]
    question_vec = question_res["embeddings"][0]
    scores = {}
    for filename, text in docs.items():
        doc_vec = ollama.embed(model="nomic-embed-text",input=text)     # embed this doc's text
        scores[filename] = cosine_similarity(question_vec,doc_vec["embeddings"][0])
        print(f"debug {filename} ->  {scores[filename]}")   # cosine_similarity(question_vec, doc_vec)
    
    bm25_scores ={}
    bm25_score = bm25.get_scores(tokenize(question))
    for i,c in enumerate(bm25_score):
        bm25_scores[doc_keys[i]] = c
    bm_sorts  = sorted(bm25_scores,key=lambda k:bm25_scores[k],reverse=True)
    print("bm25 rank check:", bm25_rank if False else None)  # placeholder, replace below

    # best_filename = max(scores,key=lambda k: scores[k])   # the max() + lambda pattern above
    cs_sorts  = sorted(scores,key=lambda k:scores[k],reverse=True)
    cosine_rank = {}
    for i, k in enumerate(cs_sorts):
       cosine_rank[k] = i + 1
    bm25_rank = {}
    print(f"products.txt#25 -> cosine_rank={cosine_rank.get('products.txt#25')}, bm25_rank={bm25_rank.get('products.txt#25')}, bm25_score={bm25_scores.get('products.txt#25')}")

    for i, k in enumerate(bm_sorts):
       bm25_rank[k] = i + 1
    
    rrf_score ={}
    for k in docs:
        rrf_score[k] = 1/(60+cosine_rank[k]) +1/(60+bm25_rank[k])
    
    rrf_score_sort   = sorted(rrf_score,key= lambda k:rrf_score[k],reverse=True )
    return rrf_score_sort[:10]

def expand_query(question, model) -> list[str]:
    prompt = f"Generate 2 alternate phrasings of this question, one per line, no numbering: {question}"
    response = ollama.chat(model=model, messages=[{"role": "user", "content": prompt}])
    return response["message"]["content"].split("\n")   # 2 strings, one per line

def retrieve(question, docs):
    alternates = expand_query(question, model)
    all_questions = [question] + alternates    # original + 2 alternates = 3 total

    combined_keys = set()
    for q in all_questions:
        top_10 = score_candidates(q, docs, doc_keys, bm25)
        combined_keys = combined_keys | set(top_10)

    top_n = rerank(question, list(combined_keys), docs, model)   # rerank against the ORIGINAL question, not the alternates
    return "\n\n".join(f"[{i}] {docs[i]}" for i in top_n)
    

def read_file() -> str:
    policy_text =""
    with open("store_policy.txt","r") as f:
        policy_text = f.read()
    return policy_text

def token_count(data) -> int:
    token = enc.encode(data)
    return len(token)
def context_report(history) -> int:

    
    
    return token_count("".join(msg["content"] for msg in history))

   
   
   
    ... # count tokens for each part, print them, return total

def support_chat():
    
    turns = [
       "What is the warranty on product PX-125?"
    ]
  
    for turn in turns:
        messages =[{"role":"system","content":SYSTEM_PROMPT+retrieve(turn,docs)}]
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
    # c=chunk_by_paragraph(text=docs["faq.txt"])
    # print(len(c))
    # for i in c:
    #     print(repr(i[:40])) 
    # for i,c in  docs.items():
    #     print(i,"->",repr(c[:40]))
    support_chat()
