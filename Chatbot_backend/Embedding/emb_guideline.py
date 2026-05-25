# guidelines_embed.py
from pathlib import Path
import json
import numpy as np
import torch
from sentence_transformers import SentenceTransformer

BASE = Path(__file__).parent
IN_CHUNKS = BASE.parent / "Chunking" / "chunk_guidelines_2006.json"
OUT_EMB   = BASE / "emb_guidelines_2006.npz"
OUT_META  = BASE / "emb_guidelines_2006_meta.json"
FAISS_OUT = BASE.parent / "VectorDB" / "faiss_guidelines_2006.index"

MODEL_NAME = "BAAI/bge-small-en-v1.5"  # 384-dim, high-accuracy retrieval model

def load_chunks(p: Path):
    data = json.loads(p.read_text(encoding="utf-8"))
    texts = [r["chunk"] for r in data]
    meta  = [{
        "id": i,
        "source": r.get("source", "guidelines_2006"),
        "number": r.get("number", ""),
        "title": r.get("title", ""),
        "hierarchy": r.get("hierarchy", ""),
        "chunk_index": r.get("chunk_index", 0)
    } for i, r in enumerate(data)]
    return texts, meta

if __name__ == "__main__":
    texts, meta = load_chunks(IN_CHUNKS)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(MODEL_NAME, device=device)

    # bge models recommend prepending "Represent this sentence for searching relevant passages: "
    # for passage embedding, but for indexing we just embed directly
    emb = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True
    ).astype("float32")

    np.savez_compressed(OUT_EMB, embeddings=emb)
    OUT_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Saved embeddings: {emb.shape} -> {OUT_EMB}")
    print(f"Saved metadata -> {OUT_META}")

    try:
        import faiss
        index = faiss.IndexFlatIP(emb.shape[1])
        index.add(emb)
        faiss.write_index(index, str(FAISS_OUT))
        print(f"Saved FAISS index -> {FAISS_OUT}")
    except Exception as e:
        print("(FAISS optional) Skipped index build:", e)
