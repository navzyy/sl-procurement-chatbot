# Data and embedding pipeline

## 1. Source documents
- Procurement Guidelines 2006 (PDF)
- Procurement Manual 2006 (PDF)

## 2. Text extraction
- Tool: PyMuPDF
- For each page:
  - extract text
  - preserve headings as much as possible
  - store as structured JSON

## 3. Chunking strategy
- Split by headings and subheadings when possible
- Target size: around 500
- Store per chunk:
  - text
  - doc_type (Guideline or Manual)
  - section number
  - title
  - page range

## 4. Embeddings
- Model: all-MiniLM-L6-v2
- Dimensionality: 384
- Normalised: yes (L2)
- Stored as:
  - Numpy arrays for vectors
  - JSON for metadata

## 5. Vector database
- Library: FAISS
- Index type: IndexFlatIP
- Metric: Inner product on knn
- Files:
  - VectroDB/faiss_guidelines_2006.index
  - VectroDB/faiss_manual_2006.index
