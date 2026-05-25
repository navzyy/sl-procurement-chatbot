# manual_extraction2.py
# Robust extractor + parser for "Manual 2006.pdf" living in ./Documents

from pathlib import Path
import fitz  # PyMuPDF
import re
import json
import unicodedata

PDF_NAME = "Manual 2006.pdf"

# --- 1) Build paths from your folder structure ---
BASE_DIR = Path(__file__).parent                       # ...\pdf extraction\PDF_Extraction
DOC_DIR  = BASE_DIR.parent / "Documents"               # ...\pdf extraction\Documents
PDF_PATH = DOC_DIR / PDF_NAME                          # e.g., ...\Documents\Manual 2006.pdf
OUT_JSON = BASE_DIR / "manual_2006.json"               # write next to this script

if not DOC_DIR.exists():
    raise FileNotFoundError(f"Documents folder not found: {DOC_DIR.resolve()}")
if not PDF_PATH.exists():
    files = "\n  - " + "\n  - ".join(p.name for p in DOC_DIR.glob("*.pdf"))
    raise FileNotFoundError(
        f"Could not find '{PDF_NAME}' in {DOC_DIR.resolve()}.\n"
        f"PDFs present:{files if files.strip() else ' (none)'}"
    )
# --- 2) Helpers: normalization & cleanup ---
def normalize_text(s: str) -> str:
    # fix common ligatures & punctuation and normalize unicode
    replacements = {
        "\ufb01": "fi",  # ﬁ
        "\ufb02": "fl",  # ﬂ
        "\xa0": " ",     # NBSP
        "–": "-", "—": "-",
        "“": '"', "”": '"', "’": "'",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    s = unicodedata.normalize("NFKC", s)
    # collapse multiple spaces and tidy newlines
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"[ \t]*\n[ \t]*", "\n", s)
    return s

def join_hyphenated_lines(text: str) -> str:
    # Join hyphenated line breaks: "Procure-\nment" -> "Procurement"
    return re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

def strip_obvious_headers_footers(page_text: str) -> str:
    # Optional: remove lone page numbers / very short boilerplate lines
    lines = page_text.splitlines()
    kept = []
    for ln in lines:
        l = ln.strip()
        if re.fullmatch(r"(?:Page\s*)?\d{1,4}", l):
            continue
        if l in {"ii", "iii", "iv", "v"}:
            continue
        kept.append(ln)
    return "\n".join(kept)

# --- 3) Block-ordered text extraction (cleaner than raw get_text()) ---
def extract_text_blocks(pdf_path: Path) -> str:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found at: {pdf_path}")

    doc = fitz.open(pdf_path)
    pages_text = []

    for page in doc:
        # "blocks" preserves L->R, T->B ordering better; sort by y then x
        blocks = sorted(page.get_text("blocks"), key=lambda b: (round(b[1], 1), round(b[0], 1)))
        chunk = "\n".join(b[4].strip() for b in blocks if b[4].strip())
        chunk = strip_obvious_headers_footers(chunk)
        pages_text.append(chunk)

    full = "\n\n".join(pages_text)
    full = normalize_text(full)
    full = join_hyphenated_lines(full)
    return full

# --- 4) Parsing chapters & guideline sections ---
def parse_manual(text: str) -> dict:
    manual = {"chapters": []}

    # CHAPTER N - Title (allow en dash/space/no dash)
    chap_re = re.compile(r"(^CHAPTER\s+\d+\s*[-–]?\s*[^\n]+)", re.MULTILINE)
    chap_spans = [(m.start(), m.end(), m.group(1)) for m in chap_re.finditer(text)]
    chap_spans.append((len(text), len(text), None))  # sentinel end

    for i in range(len(chap_spans) - 1):
        _, end_curr, chap_title = chap_spans[i]
        start_next, _, _ = chap_spans[i + 1]

        chap_body = text[end_curr:start_next].strip()
        chapter_obj = {"title": chap_title.strip(), "sections": []}

        # Match "PROCUREMENT GUIDELINE REFERENCE: 2.4" (tolerate spaces, (Cont), multi-line title)
        sec_re = re.compile(
            r"(PROCUREMENT\s+GUIDELINE\s+REFERENCE:\s*\d+(?:\.\d+)*(?:\s*\(Cont\))?)\s*(.*?)\n\n",
            re.DOTALL | re.IGNORECASE
        )
        matches = list(sec_re.finditer(chap_body + "\n\n"))  # ensure trailing gap

        if not matches:
            # If no section markers found, keep raw chapter body to avoid data loss
            chapter_obj["sections"].append({
                "guideline_reference": None,
                "title": "",
                "content": chap_body
            })
        else:
            for si, m in enumerate(matches):
                sec_start = m.end()
                ref = m.group(1).strip()
                title_line = (m.group(2) or "").strip()
                sec_end = matches[si + 1].start() if si + 1 < len(matches) else len(chap_body)
                content = chap_body[sec_start:sec_end].strip()

                chapter_obj["sections"].append({
                    "guideline_reference": ref,
                    "title": title_line,
                    "content": content
                })

        manual["chapters"].append(chapter_obj)

    return manual

# --- 5) Main ---
if __name__ == "__main__":
    print(f"Reading PDF from: {PDF_PATH.resolve()}")
    text = extract_text_blocks(PDF_PATH)
    data = parse_manual(text)

    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote JSON to: {OUT_JSON.resolve()}")
