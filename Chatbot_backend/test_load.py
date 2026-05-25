import time
print("1. Importing libraries...", flush=True)
t0 = time.time()
from sentence_transformers import SentenceTransformer, CrossEncoder
print(f"Libraries imported in {time.time() - t0:.2f}s", flush=True)

print("2. Loading BAAI/bge-small-en-v1.5 from cache/hub...", flush=True)
t1 = time.time()
embed_model = SentenceTransformer("BAAI/bge-small-en-v1.5")
print(f"BGE model loaded in {time.time() - t1:.2f}s", flush=True)

print("3. Loading cross-encoder/ms-marco-MiniLM-L-12-v2 from cache/hub...", flush=True)
t2 = time.time()
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-12-v2")
print(f"Cross encoder loaded in {time.time() - t2:.2f}s", flush=True)

print("SUCCESS: All models loaded into RAM seamlessly!", flush=True)
