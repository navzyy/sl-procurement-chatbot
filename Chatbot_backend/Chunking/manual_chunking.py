# manual_chunking.py
from pathlib import Path
import json
from langchain_text_splitters import RecursiveCharacterTextSplitter

# Folders:

BASE_DIR = Path(__file__).parent
IN_JSON = BASE_DIR.parent / "PDF_Extraction" / "manual_2006.json"
OUT_JSON = BASE_DIR / "chunk_manual_2006.json"

# Chunking params — tuned for structured legal/procurement text
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
# Add more separators if your manual has (a)(b) bullets etc.
SEPARATORS = ["\n\n", "\n", "(a)", "(b)", "(c)", "•", " - ", "—", "–", "  "]


def load_manual(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Input JSON not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_records(manual_json: dict):
    """
    Flatten chapters/sections into records:
    {"chapter_title","guideline_reference","section_title","text"}
    """
    recs = []
    for ch in manual_json.get("chapters", []) or []:
        chap_title = (ch.get("title") or "").strip()
        for sec in ch.get("sections", []) or []:
            ref = (sec.get("guideline_reference") or "").strip()
            title = (sec.get("title") or "").strip()
            content = (sec.get("content") or "").strip()
            # Skip empty sections
            if not (ref or title or content or chap_title):
                continue

            header = " ".join([v for v in [ref, title] if v]).strip()
            # Keep chapter title for context, then header, then body
            parts = [p for p in [chap_title, header, "", content] if p is not None]
            text = "\n".join(parts).strip()

            if text:
                recs.append(
                    {
                        "chapter_title": chap_title,
                        "guideline_reference": ref,
                        "section_title": title,
                        "text": text,
                    }
                )
    return recs


def chunk_records(recs):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=SEPARATORS,
    )
    out = []
    for r in recs:
        if not r["text"].strip():
            continue

        # Build hierarchy prefix for better retrieval context
        hierarchy_parts = []
        if r["chapter_title"]:
            hierarchy_parts.append(r["chapter_title"])
        if r["guideline_reference"]:
            hierarchy_parts.append(r["guideline_reference"])
        if r["section_title"]:
            hierarchy_parts.append(r["section_title"])

        prefix = ""
        if hierarchy_parts:
            prefix = "[Manual 2006 > " + " > ".join(hierarchy_parts) + "]\n"

        for idx, ch in enumerate(splitter.split_text(r["text"])):
            # Prepend hierarchy context to each chunk for better retrieval
            enriched_chunk = str(prefix) + str(ch) if prefix else str(ch)
            out.append(
                {
                    "source": "manual_2006",
                    "chapter_title": r["chapter_title"],
                    "guideline_reference": r["guideline_reference"],
                    "section_title": r["section_title"],
                    "chunk_index": idx,
                    "chunk": enriched_chunk,
                }
            )
    return out


if __name__ == "__main__":
    print("Loading:", IN_JSON.resolve())
    data = load_manual(IN_JSON)
    recs = build_records(data)
    chunks = chunk_records(recs)
    OUT_JSON.write_text(
        json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        f"Flattened {len(recs)} sections; wrote {len(chunks)} chunks -> {OUT_JSON.resolve()}"
    )
