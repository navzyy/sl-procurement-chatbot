# Procurement RAG Chatbot - Frontend Interface

A Vite + React user interface connecting to the optimized Python FastAPI backend to explore the Sri Lanka Procurement Guidelines. 

## Key Features & Fixes
- **Conversational Memory:** The frontend natively extracts trailing `session_id` logic returned by the backend, dynamically binding multiple `user <> assistant` calls together, effectively mapping conversational chat histories via local storage indexing.
- **Rich Markdown Formatting:** Integrated `react-markdown` allowing LLM bullet point procedures, citations, bolded emphasis, and tables to render visually rather than parsing as flat blocks of text.
- **Session Navigation:** Complete left-sidebar navigation enabling switching quickly across older search sessions seamlessly, and options to instantly delete legacy queries.

## Getting Started

1. **Move to source directory**
   ```powershell
   cd procurement-assistant-frontend
   ```

2. **Install Dependencies** (from `package.json` locking React/Vite versions)
   ```powershell
   npm install
   ```
   *(Or refer to the `frontend_requirements.txt` file for a manual installation query)*

3. **Start the local Dev Server**
   ```powershell
   npm run dev
   ```
   The browser will display the UI locally (defaulting generally to `http://localhost:5173`). 

---
*Note: Ensure the backend `rag.py` is actively running via uvicorn on `localhost:8000` to prevent fetch socket errors upon querying!*
