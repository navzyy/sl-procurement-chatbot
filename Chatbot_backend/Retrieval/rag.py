# rag.py
from pathlib import Path
import json
import os
import requests
import uuid

import faiss
import numpy as np
import time
import random
from fastapi import HTTPException
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi

from fastapi.middleware.cors import CORSMiddleware



# ----------------------------
# Paths
# ----------------------------
BASE = Path(__file__).parent              # Retrieval/
ROOT = BASE.parent                        # PDF EXTRACTION/
CHUNK_DIR = ROOT / "Chunking"             # chunk jsons
META_DIR = ROOT / "Embedding"             # meta jsons
VDB_DIR = ROOT / "VectorDB"               # npz + faiss index

# ----------------------------
# Load guidelines files
# ----------------------------
GUIDE_META = json.loads((META_DIR / "emb_guidelines_2006_meta.json").read_text(encoding="utf-8"))
GUIDE_CHUNKS = json.loads((CHUNK_DIR / "chunk_guidelines_2006.json").read_text(encoding="utf-8"))
GUIDE_INDEX = faiss.read_index(str(VDB_DIR / "faiss_guidelines_2006.index"))

# ----------------------------
# Load manual files
# ----------------------------
MANUAL_META = json.loads((META_DIR / "emb_manual_2006_meta.json").read_text(encoding="utf-8"))
MANUAL_CHUNKS = json.loads((CHUNK_DIR / "chunk_manual_2006.json").read_text(encoding="utf-8"))
MANUAL_INDEX = faiss.read_index(str(VDB_DIR / "faiss_manual_2006.index"))


# ----------------------------
# Load embedding model (must match the model used for creating embeddings)
# ----------------------------
EMBED_MODEL_NAME = "BAAI/bge-small-en-v1.5"
embed_model = SentenceTransformer(EMBED_MODEL_NAME)

# ----------------------------
# Load cross-encoder re-ranker for precision
# ----------------------------
RERANKER_MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-12-v2"
reranker = CrossEncoder(RERANKER_MODEL_NAME)

# ----------------------------
# Build BM25 indexes for hybrid search (keyword matching)
# ----------------------------
ALL_CHUNKS_COMBINED = []
CHUNK_SOURCE_MAP = []  # track which source each chunk came from

for i, chunk in enumerate(GUIDE_CHUNKS):
    ALL_CHUNKS_COMBINED.append(chunk)
    CHUNK_SOURCE_MAP.append(("guidelines", i))

for i, chunk in enumerate(MANUAL_CHUNKS):
    ALL_CHUNKS_COMBINED.append(chunk)
    CHUNK_SOURCE_MAP.append(("manual", i))

# Tokenize for BM25
tokenized_corpus = [chunk["chunk"].lower().split() for chunk in ALL_CHUNKS_COMBINED]
bm25_index = BM25Okapi(tokenized_corpus)

# ----------------------------
# FastAPI setup
# ----------------------------
app = FastAPI(title="Procurement RAG API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # in production restrict this to your frontend origin
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# In-memory conversation store
# ----------------------------
# Stores chat history per session: { session_id: [ {role, content}, ... ] }
CONVERSATIONS: dict[str, list[dict]] = {}
MAX_HISTORY_TURNS = 6  # keep last 6 exchanges (12 messages) for context

# ----------------------------
# Pydantic models
# ----------------------------
class Query(BaseModel):
    question: str
    session_id: str | None = None  # optional: pass to enable chat history

class SourceChunk(BaseModel):
    score: float
    source: str
    number: str | None = None
    title: str | None = None

class AnswerResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    session_id: str  # return so frontend can track the session


# ----------------------------
# System prompt (separated from user content)
# ----------------------------
SYSTEM_PROMPT = """You are an expert, friendly, and helpful research assistant specialized exclusively in
Sri Lanka Government Procurement Guidelines 2006 (Goods & Works)
and the Procurement Manual 2006.

Your task is to answer user questions using the information provided in the retrieved context from these documents.

RULES AND CONSTRAINTS:

1. CONVERSATIONAL VS PROCUREMENT QUESTIONS
   - If the user input is a greeting (e.g., "hi", "hello"), a pleasantry, or a general conversational question, respond naturally, concisely, and in a friendly, helpful manner acknowledging your role as a procurement chatbot.
   - For any question related to procurement, rules, definitions, procedures, or the documents, you MUST strictly use ONLY the provided context.

2. SOURCE RESTRICTION
   - For procurement questions, use ONLY the provided context from the Guidelines and Manual.
   - Do NOT use prior knowledge, assumptions, examples, or external sources.

3. NO HALLUCINATION POLICY
   - If a procurement-related question is not clearly, explicitly, and directly supported by the provided context, respond with:
     "I do not have that information based on the available procurement documents."
   - Do NOT guess, infer, paraphrase beyond the text, or fill gaps.

4. MANDATORY CITATIONS
   - When an answer is derived from the context, always reference the relevant guideline or manual section number in square brackets at the end of the point or sentence.
   - Examples: [Guidelines 1.3.3], [Manual 2.7.1]

5. ANSWER STYLE
   - Be concise, clear, and human-friendly.
   - Do NOT produce overly lengthy responses unless specifically requested by the user.
   - When asked for steps or procedures, provide a summarized, easy-to-read numbered list that retains all critical conditions without unnecessary verbosity.
   - If providing a definition or explanation, use simple bullet points.

6. COMPLETENESS REQUIREMENT
   - Combine relevant information from multiple context chunks to ensure accuracy, but synthesize it concisely.

7. DEFINITIONS AND TERMINOLOGY
   - Use terminology exactly as written in the documents (e.g., Procuring Entity, TEC, MPC).

8. QUESTION SCOPE CONTROL
   - If a specific procurement question goes beyond Goods & Works procurement (e.g., consultancy selection), respond:
     "This is not covered in the Procurement Guidelines 2006 (Goods & Works) or the Procurement Manual 2006."

PRIMARY OBJECTIVE:
Provide accurate, concise, citation-grounded answers for procurement questions with zero hallucination, while maintaining a friendly, natural conversational tone for general inquiries."""


# ----------------------------
# Vector retrieval - Guidelines + Manual
# ----------------------------
def retrieve_vector(query: str, k: int = 15):
    """Retrieve top-k chunks from both Guidelines and Manual FAISS indexes."""
    # bge models recommend "Represent this sentence: " prefix for queries
    q_vec = embed_model.encode(
        [query],
        normalize_embeddings=True,
        convert_to_numpy=True
    ).astype("float32")

    # Search Guidelines
    Dg, Ig = GUIDE_INDEX.search(q_vec, k)
    # Search Manual
    Dm, Im = MANUAL_INDEX.search(q_vec, k)

    results = []

    # Collect guideline chunks
    for dist, idx in zip(Dg[0], Ig[0]):
        if idx < 0:
            continue  # FAISS returns -1 if not enough results
        meta = GUIDE_META[idx]
        chunk_text = GUIDE_CHUNKS[idx]["chunk"]
        results.append({
            "score": float(dist),
            "chunk": chunk_text,
            "source": meta.get("source", "Guidelines 2006"),
            "number": meta.get("number", ""),
            "title": meta.get("title", "")
        })

    # Collect manual chunks
    for dist, idx in zip(Dm[0], Im[0]):
        if idx < 0:
            continue
        meta = MANUAL_META[idx]
        chunk_text = MANUAL_CHUNKS[idx]["chunk"]
        results.append({
            "score": float(dist),
            "chunk": chunk_text,
            "source": meta.get("source", "Manual 2006"),
            "number": meta.get("number", ""),
            "title": meta.get("title", "")
        })

    return results


# ----------------------------
# BM25 keyword retrieval
# ----------------------------
def retrieve_bm25(query: str, k: int = 15):
    """Retrieve top-k chunks using BM25 keyword matching."""
    tokenized_query = query.lower().split()
    scores = bm25_index.get_scores(tokenized_query)
    top_indices = scores.argsort()[-k:][::-1]

    results = []
    for idx in top_indices:
        if scores[idx] <= 0:
            continue
        chunk_data = ALL_CHUNKS_COMBINED[idx]
        source_type, original_idx = CHUNK_SOURCE_MAP[idx]

        if source_type == "guidelines":
            meta = GUIDE_META[original_idx] if original_idx < len(GUIDE_META) else {}
        else:
            meta = MANUAL_META[original_idx] if original_idx < len(MANUAL_META) else {}

        results.append({
            "score": float(scores[idx]),
            "chunk": chunk_data["chunk"],
            "source": meta.get("source", chunk_data.get("source", "")),
            "number": meta.get("number", ""),
            "title": meta.get("title", chunk_data.get("section_title", ""))
        })

    return results


# ----------------------------
# Reciprocal Rank Fusion (RRF) to merge vector + BM25 results
# ----------------------------
def reciprocal_rank_fusion(vector_results: list[dict], bm25_results: list[dict], k_rrf: int = 60):
    """Merge two ranked lists using RRF. Higher is better."""
    chunk_scores: dict[str, float] = {}
    chunk_map: dict[str, dict] = {}

    for rank, r in enumerate(vector_results):
        chunk_key = r["chunk"][:200]  # use first 200 chars as dedup key
        rrf_score = 1.0 / (k_rrf + rank + 1)
        chunk_scores[chunk_key] = chunk_scores.get(chunk_key, 0) + rrf_score
        chunk_map[chunk_key] = r

    for rank, r in enumerate(bm25_results):
        chunk_key = r["chunk"][:200]
        rrf_score = 1.0 / (k_rrf + rank + 1)
        chunk_scores[chunk_key] = chunk_scores.get(chunk_key, 0) + rrf_score
        if chunk_key not in chunk_map:
            chunk_map[chunk_key] = r

    # Sort by combined RRF score
    sorted_keys = sorted(chunk_scores.keys(), key=lambda k: chunk_scores[k], reverse=True)

    results = []
    for key in sorted_keys:
        item = chunk_map[key].copy()
        item["score"] = chunk_scores[key]
        results.append(item)

    return results


# ----------------------------
# Hybrid retrieval: Vector + BM25 + RRF
# ----------------------------
def retrieve_hybrid(query: str, k: int = 20):
    """Hybrid search combining vector similarity and BM25 keyword matching."""
    vector_results = retrieve_vector(query, k=k)
    bm25_results = retrieve_bm25(query, k=k)
    combined = reciprocal_rank_fusion(vector_results, bm25_results)
    return combined[:k]


# ----------------------------
# Cross-encoder re-ranking
# ----------------------------
def rerank(query: str, results: list[dict], top_n: int = 5) -> list[dict]:
    """Re-rank retrieved chunks using a cross-encoder for higher precision."""
    if not results:
        return results

    pairs = [(query, r["chunk"]) for r in results]
    scores = reranker.predict(pairs)

    for r, s in zip(results, scores):
        r["rerank_score"] = float(s)

    results.sort(key=lambda x: x["rerank_score"], reverse=True)
    return results[:top_n]


# ----------------------------
# Build context text from retrieved chunks
# ----------------------------
def build_context_text(contexts: list[dict]) -> str:
    """Format retrieved chunks into a labeled context string."""
    context_blocks = []

    for ctx in contexts:
        label_parts = []
        if ctx.get("source"):
            label_parts.append(ctx["source"])
        if ctx.get("number"):
            label_parts.append(ctx["number"])
        if ctx.get("title"):
            label_parts.append(ctx["title"])

        label = " - ".join(p for p in label_parts if p)

        text = ctx["chunk"]

        block = f"[{label}]\n{text}"
        context_blocks.append(block)

    return "\n\n".join(context_blocks)


# ----------------------------
# Groq LLM call
# ----------------------------
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def call_llm_groq(messages: list[dict]) -> str:
    """
    Call Groq LLM with retry handling for rate limits.
    """
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY is not set."

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 800,
    }

    max_retries = 6

    for attempt in range(max_retries):
        try:
            res = requests.post(url, json=payload, headers=headers, timeout=120)

            if res.status_code == 429:
                wait_time = 20 + (attempt * 10)
                print(f"Groq rate limit hit. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue

            if res.status_code != 200:
                return f"Groq error {res.status_code}: {res.text}"

            data = res.json()

            choices = data.get("choices", [])
            if not choices:
                return f"Groq returned no choices: {data}"

            message = choices[0].get("message", {})
            content = message.get("content", "")

            if not content:
                return f"Groq returned empty content: {data}"

            return content.strip()

        except Exception as e:
            wait_time = 10 + (attempt * 5)
            print(f"Groq exception: {e}. Waiting {wait_time} seconds...")
            time.sleep(wait_time)

    return "Groq error: maximum retries exceeded due to rate limits."


# ----------------------------
# Query rewriting for follow-up questions
# ----------------------------
def rewrite_query(question: str, history: list[dict]) -> str:
    """
    Use LLM to rewrite follow-up questions into self-contained queries.
    This fixes retrieval for questions like "tell me more about that".
    """
    if not history:
        return question

    # Only rewrite if the question seems like a follow-up
    follow_up_indicators = [
        "that", "this", "it", "those", "these", "above", "mentioned",
        "more", "detail", "explain", "elaborate", "what about",
        "how about", "same", "previous", "earlier"
    ]

    question_lower = question.lower()
    is_follow_up = any(indicator in question_lower for indicator in follow_up_indicators)

    if not is_follow_up:
        return question

    # Build a concise history summary for the rewrite prompt
    recent = history[-4:]  # last 2 exchanges
    history_text = "\n".join(
        f"{m['role'].upper()}: {m['content'][:300]}" for m in recent
    )

    rewrite_prompt = f"""Given this conversation history, rewrite the latest question 
to be a fully self-contained, specific query about Sri Lanka procurement guidelines/manual.
Do NOT answer the question. Only rewrite it.

Conversation:
{history_text}

Latest question: {question}

Rewritten self-contained question:"""

    rewritten = call_llm_groq([{"role": "user", "content": rewrite_prompt}])

    # Sanity check: if rewrite is too long or looks like an answer, use original
    if len(rewritten) > 300 or "\n" in rewritten.strip():
        return question

    return rewritten.strip()


# ----------------------------
# Retrieve all relevant chunks (used by RAGAS evaluation scripts)
# ----------------------------
def retrieve_all(query: str, k: int = 10) -> list[dict]:
    """Retrieve and re-rank chunks without calling the LLM.
    Returns the top-k re-ranked context dicts."""
    candidates = retrieve_hybrid(query, k=20)
    return rerank(query, candidates, top_n=k)


# ----------------------------
# Full RAG pipeline with all optimizations
# ----------------------------
def answer_rag(question: str, session_id: str | None = None) -> AnswerResponse:
    """
    Optimized RAG pipeline:
    1. Rewrite query if it's a follow-up question
    2. Hybrid retrieval (Vector + BM25 with RRF)
    3. Cross-encoder re-ranking to top-5
    4. Build messages with system prompt + chat history + context
    5. Call LLM for answer
    6. Store in conversation history
    """
    # Create or reuse session
    if not session_id:
        session_id = str(uuid.uuid4())
    
    if session_id not in CONVERSATIONS:
        CONVERSATIONS[session_id] = []
    
    history = CONVERSATIONS[session_id]

    # Step 1: Rewrite follow-up questions for better retrieval
    retrieval_query = rewrite_query(question, history)

    # Step 2: Hybrid retrieval (vector + BM25)
    candidates = retrieve_hybrid(retrieval_query, k=20)

    # Step 3: Cross-encoder re-ranking to top-5 most relevant
    contexts = rerank(retrieval_query, candidates, top_n=5)
    context_text = build_context_text(contexts)

    # Step 4: Build message list: system + history + current question with context
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    # Add recent conversation history (last N turns)
    # This lets the LLM understand follow-up questions like "tell me more"
    recent_history = history[-(MAX_HISTORY_TURNS * 2):]
    messages.extend(recent_history)

    # Add current user question with retrieved context
    user_message = f"""Context from documents:
{context_text}

Question:
{question}

Answer concisely and in a human-friendly tone. For procurement matters, use ONLY the context above."""

    messages.append({"role": "user", "content": user_message})

    # Step 5: Call LLM
    answer = call_llm_groq(messages)

    # Step 6: Store this exchange in conversation history
    # (store without the context to keep history clean)
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": answer})

    # Trim old history to avoid token overflow
    if len(history) > MAX_HISTORY_TURNS * 2:
        CONVERSATIONS[session_id] = history[-(MAX_HISTORY_TURNS * 2):]

    # Build source list
    srcs: list[SourceChunk] = [
        SourceChunk(
            score=ctx.get("rerank_score", ctx["score"]),
            source=ctx.get("source", ""),
            number=ctx.get("number", "") or None,
            title=ctx.get("title", "") or None,
        )
        for ctx in contexts
    ]

    return AnswerResponse(answer=answer, sources=srcs, session_id=session_id)


# ----------------------------
# FastAPI endpoints
# ----------------------------

@app.get("/")
def root():
    return {"message": "Procurement RAG API is running"}

@app.post("/ask", response_model=AnswerResponse)
def ask_endpoint(q: Query):
    return answer_rag(q.question, q.session_id)

origins = [
    "http://localhost:5173",
    "https://your-frontend-name.vercel.app"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)