# guidelines_chunking.py
from pathlib import Path
import json
from langchain_text_splitters import RecursiveCharacterTextSplitter

BASE_DIR = Path(__file__).parent   # ...\pdf extraction\Chunking
IN_JSON  = BASE_DIR.parent / "PDF_Extraction" / "guidelines_2006.json"
OUT_JSON = BASE_DIR / "chunk_guidelines_2006.json"

# Chunking params — tuned for structured legal/procurement text
CHUNK_SIZE = 800
CHUNK_OVERLAP = 150
SEPARATORS = ["\n\n", "\n", "(a)", "(b)", "(c)", "•", " - ", "—", "–", "  "]

def load_guidelines(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Input JSON not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

#Flatten a section node (number/title/content/bullets) into a text blob and metadata.

def node_to_text(node, path_numbers):
    
    num = (node.get("number") or "").strip()
    title = (node.get("title") or "").strip()
    content = (node.get("content") or "").strip()

    bullets = node.get("bullets", []) or []
    bullet_text = ""
    if bullets:
        bullet_lines: list[str] = []
        for b in bullets:
            label = (b.get("label") or "").strip()
            txt = (b.get("text") or "").strip()
            bullet_lines.append(str(f"({label}) {txt}" if label else txt))
        bullet_text = "\n".join(bullet_lines)

    header = " ".join([v for v in [num, title] if v]).strip()
    parts = [p for p in [header, content, bullet_text] if p]
    text = "\n\n".join(parts).strip()

    hierarchy = " > ".join([p for p in path_numbers + ([num] if num else []) if p])
    meta = {
        "number": num,
        "title": title,
        "hierarchy": hierarchy
    }
    return text, meta

 #Depth-first flattening of all sections/children into (text, meta) records.
   
def walk_sections(sections, path_numbers=None):
  
   
    path_numbers = list(path_numbers or [])
    recs = []
    for n in sections or []:
        text, meta = node_to_text(n, path_numbers)
        recs.append((text, meta))
        # descend
        next_path = path_numbers + ([n.get("number")] if n.get("number") else [])
        recs.extend(walk_sections(n.get("children", []) or [], next_path))
    return recs

def chunk_records(records):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=SEPARATORS,
    )
    out = []
    for text, meta in records:
        if not text.strip():
            continue

        # Build hierarchy prefix for better retrieval context
        hierarchy_parts = []
        if meta.get("hierarchy"):
            hierarchy_parts.append(meta["hierarchy"])
        if meta.get("title"):
            hierarchy_parts.append(meta["title"])

        prefix = ""
        if hierarchy_parts:
            prefix = "[Guidelines 2006 > " + " > ".join(hierarchy_parts) + "]\n"

        for idx, ch in enumerate(splitter.split_text(text)):
            # Prepend hierarchy context to each chunk for better retrieval
            enriched_chunk = str(prefix) + str(ch) if prefix else str(ch)
            out.append({
                "source": "guidelines_2006",
                **meta,
                "chunk_index": idx,
                "chunk": enriched_chunk,
            })
    return out

if __name__ == "__main__":
    data = load_guidelines(IN_JSON)

    # The extractor produced: {"chapters": [ { "chapter_number": ..., "chapter_title": ..., "sections": [...] }, ... ]}
    chapters = data.get("chapters", [])
    all_records = []
    for ch in chapters:
        chap_num = (ch.get("chapter_number") or "").strip()
        chap_title = (ch.get("chapter_title") or "").strip()
        path_prefix = [chap_num or chap_title or "Chapter"]
        sections = ch.get("sections", []) or []
        all_records.extend(walk_sections(sections, path_prefix))

    chunks = chunk_records(all_records)
    OUT_JSON.write_text(json.dumps(chunks, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Loaded {len(chapters)} chapters, flattened {len(all_records)} section records.")
    print(f"Wrote {len(chunks)} chunks -> {OUT_JSON.resolve()}")
