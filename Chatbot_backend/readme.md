# Procurement RAG Chatbot - Backend API

This folder contains the High-Accuracy RAG pipeline responsible for processing the Sri Lanka Procurement Guidelines & Manual (2006). 

## Architecture & Optimizations
The backend was substantially optimized for highest possible accuracy using:
1. **BAAI/bge-small-en-v1.5**: Replacing the basic `MiniLM`, this model offers top-tier retrieval performance while operating comfortably on local CPUs.
2. **Hybrid Search**: We use FAISS (Inner Product) for deep semantic search, bonded with `rank_bm25` (BM25Okapi) for exact keyword/section number matches. They are merged using Reciprocal Rank Fusion (RRF).
3. **Cross-Encoder Re-Ranking**: Over-fetches 20 initial documents and uses `ms-marco-MiniLM-L-12-v2` to aggressively score and filter down to the final 5 most relevant documents.
4. **LLM Query Rewriter**: Employs `llama-3.3-70b-versatile` (via Groq) to intelligently rewrite follow-up conversational questions (e.g. "tell me more about that") into absolute contexts to ensure vector lookup success.
5. **Contextual Document Splitting**: Chunks have been shrunk to sizes of 800 with 150 overlaps, and hard-coded with their specific `[Chapter > Section]` hierarchy to lock context.

## Setup & Running
1. **Activate Environment:**
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
2. **Install Dependencies:**
   ```powershell
   pip install -r backend_requirements_info.txt
   ```
3. **Run API Server:**
   Ensure your `GROQ_API_KEY` is set in your environment.
   
   ```powershell
   uvicorn Retrieval.rag:app --reload --port 8000
   ```

## Folder Structure
- `/PDF_Extraction`: Custom PyMuPDF extractors mapping PDFs to hierarchical JSON structures.
- `/Chunking`: `RecursiveCharacterTextSplitter` logic adding context tags to fragments.
- `/Embedding`: SentenceTransformer generation converting JSON contexts into `.npz` vector arrays and metadata.
- `/VectroDB`: Where FAISS stores its compressed search indexes.
- `/Retrieval`: Holds the core operational API script (`rag.py`) wrapping the LLM interaction.
- `/Evaluation`: Logic leveraging the modern RAGAS framework measuring precision, faithfulness, and correctness compared to Human Ground Truth metrics.
