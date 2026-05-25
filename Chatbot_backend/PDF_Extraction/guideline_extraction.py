# guidelines_extraction.py
# Extract Sri Lanka Procurement Guidelines (chapters, numbered sections, (a)(b) bullets)
# PDFs live in ../Documents relative to this script folder.

from pathlib import Path
import fitz  # PyMuPDF
import re, json, unicodedata, glob

# --- 1) Build paths from the folder structure ---
PDF_NAME = "Guidelines 2006 goods & work.pdf"   # set exact filename (or rely on fallback)
BASE_DIR = Path(__file__).parent                # ...\pdf extraction\PDF_Extraction
DOC_DIR  = BASE_DIR.parent / "Documents"        # ...\pdf extraction\Documents
PDF_PATH = DOC_DIR / PDF_NAME                   # ...\Documents\<file>.pdf
OUT_JSON = BASE_DIR / "guidelines_2006.json"    # write next to this script

# Fallback: tolerant search if exact file isn't there
if not PDF_PATH.exists():
    cands = list(DOC_DIR.glob("*.pdf")) + list(DOC_DIR.glob("*.PDF"))
    pat = re.compile(r"guidelines.*2006.*work", re.IGNORECASE)
    picked = None
    for p in sorted(cands):
        name = p.name.replace("&", "and")
        if pat.search(name):
            picked = p
            break
    if not picked:
        names = "\n  - " + "\n  - ".join(p.name for p in cands) if cands else " (none)"
        raise FileNotFoundError(
            f"Could not find '{PDF_NAME}' in {DOC_DIR.resolve()}.\n"
            f"PDFs present:{names}\n"
            "Fix PDF_NAME or rename the file to include 'Guidelines', '2006', and 'Work(s)'."
        )
    PDF_PATH = picked

# --- 2) Cleaning helpers ---
def normalize_text(s: str) -> str:
    rep = {"\ufb01":"fi","\ufb02":"fl","\xa0":" ","–":"-","—":"-","“":'"',"”":'"',"’":"'"}
    for k,v in rep.items(): s = s.replace(k,v)
    s = unicodedata.normalize("NFKC", s)
    s = re.sub(r"[ \t]+"," ", s)
    s = re.sub(r"[ \t]*\n[ \t]*","\n", s)
    return s

 # join broken words like Procure-\nment -> Procurement
def join_hyphenated_lines(text: str) -> str:   
    return re.sub(r"(\w+)-\n(\w+)", r"\1\2", text)

#remove page no and roman numbers
def strip_headers_footers(page_text: str) -> str:
    kept=[]
    for ln in page_text.splitlines():
        t=ln.strip()
        if re.fullmatch(r"(?:Page\s*)?\d{1,4}", t): continue   # lone page numbers
        if t in {"i","ii","iii","iv","v","vi","vii","viii","ix","x"}: continue
        kept.append(ln)
    return "\n".join(kept)

# --- 3) PDF -> clean full text (block order) ---
def extract_text_blocks(pdf_path: Path) -> str:
    doc = fitz.open(pdf_path)
    pages=[]
    for page in doc:
        blocks = sorted(page.get_text("blocks"), key=lambda b:(round(b[1],1), round(b[0],1)))
        txt = "\n".join(b[4].strip() for b in blocks if b[4].strip())
        txt = strip_headers_footers(txt)
        pages.append(txt)
    full = "\n\n".join(pages)
    full = normalize_text(full)
    full = join_hyphenated_lines(full)
    return full

# --- 4) Parsers (chapters, sections, bullets) ---

# Accept "CHAPTER 1", "CHAPTER I", and allow extra text on the same line.
CHAPTER_LINE_RE = re.compile(
    r"^\s*CHAPTER\s+(?P<chap>(\d+|[ivxlc]+))\b.*$",
    re.IGNORECASE | re.MULTILINE
)

# e.g., "1.1 Title", "3.2 Title"
TOP_RE      = re.compile(r"^\s*(?P<num>\d+\.\d+)\s+(?P<title>[^\n]+?)\s*$", re.MULTILINE)
# e.g., "1.1.1 Title", "3.2.4.3 Title"
SECTION_RE  = re.compile(r"^\s*(?P<num>\d+(?:\.\d+)+)\s+(?P<title>[^\n]+?)\s*$", re.MULTILINE)

# (a)(b)(c) bullets inside a section body
BULLET_SPLIT_RE = re.compile(r"\(\s*([a-z])\s*\)\s*", re.IGNORECASE)

def roman_to_int(s: str) -> int:
    s = s.upper()
    vals = {'I':1,'V':5,'X':10,'L':50,'C':100}
    total = prev = 0
    for ch in reversed(s):
        cur = vals.get(ch, 0)
        if cur < prev: total -= cur
        else: total += cur; prev = cur
    return total

def find_chapters(text: str):
    """
    Return list of (start_idx, end_idx, chap_token, chap_title, chap_num_for_sections).
    - chap_token: original ('I' or '1')
    - chap_num_for_sections: numeric string ('1','2',...) used to match 1.x, 2.x ...
    """
    hits = list(CHAPTER_LINE_RE.finditer(text))
    if not hits:
        return [(0, len(text), "0", "", "0")]

    out=[]
    for i,m in enumerate(hits):
        chap_token = m.group("chap")
        end = hits[i+1].start() if i+1 < len(hits) else len(text)

        # chapter title = first non-empty line after header
        after = text[m.end(): end]
        chap_title=""
        for ln in after.splitlines():
            t=ln.strip()
            if t:
                chap_title=t
                break

        # numeric chapter used for matching "N." prefixes in section numbers
        chap_num_for_sections = (
            str(int(chap_token)) if chap_token.isdigit() else str(roman_to_int(chap_token))
        )

        out.append((m.start(), end, chap_token, chap_title, chap_num_for_sections))
    return out

def split_letter_bullets(body: str):
    """
    Extract (a)(b)... bullets but KEEP the original body intact.
    Returns: (preface_text, bullets_list)
    """
    parts = BULLET_SPLIT_RE.split(body)
    preface = parts[0].strip() if parts else body.strip()
    bullets=[]
    if len(parts) >= 3:
        it = iter(parts[1:])
        for label, txt in zip(it, it):
            bullets.append({"label": label.lower(), "text": txt.strip()})
    return preface, bullets

def build_tree_for_chapter(chap_num_for_sections: str, chap_text: str):
    """
    Build a numbered hierarchy for one chapter.
    Returns: (chapter_intro_text, sections_list)
    """
    matches=[]
    # top level (1.1, 2.1, 3.2, ...)
    for m in TOP_RE.finditer(chap_text):
        if m.group("num").startswith(chap_num_for_sections + "."):
            matches.append((m.start(), m.end(), m.group("num"), m.group("title")))
    # deeper (1.1.1, 2.1.2, ...)
    for m in SECTION_RE.finditer(chap_text):
        if m.group("num").startswith(chap_num_for_sections + "."):
            matches.append((m.start(), m.end(), m.group("num"), m.group("title")))

    if not matches:
        return chap_text.strip(), []  # chapter has no numbered sections; all is intro

    matches = sorted(set(matches), key=lambda x: x[0])
    matches.append((len(chap_text), len(chap_text), None, None))

    chapter_intro = chap_text[:matches[0][0]].strip()

    # slice each section
    items=[]
    for i in range(len(matches)-1):
        start, end, num, title = matches[i]
        next_start = matches[i+1][0]
        body = chap_text[end:next_start].strip()

        preface, bullets = split_letter_bullets(body)
        node = {
            "number": num,
            "title": (title or "").strip(),
            "content": body,               # FULL content kept (including bullets)
            "content_preface": preface,    # text before first bullet
            "bullets": bullets,
            "children": []
        }
        items.append((num, node))

    # hierarchy by dot-depth: 1.1 -> depth 2; 1.1.1 -> depth 3
    root=[]
    stack=[]
    for num, node in items:
        depth = num.count(".") + 1
        while stack and stack[-1][0] >= depth:
            stack.pop()
        if not stack:
            root.append(node)
        else:
            stack[-1][1]["children"].append(node)
        stack.append((depth, node))

    return chapter_intro, root

# --- 5) Main ---
if __name__ == "__main__":
    print(f"Reading Guidelines PDF from: {PDF_PATH.resolve()}")
    full_text = extract_text_blocks(PDF_PATH)

    chapters=[]
    for (start, end, chap_token, chap_title, chap_num_for_sections) in find_chapters(full_text):
        chap_slice = full_text[start:end]
        chap_intro, sections = build_tree_for_chapter(chap_num_for_sections, chap_slice)
        chapters.append({
            "chapter_number": chap_token,     # keep original label (e.g., I, II, 1, 2)
            "chapter_title": chap_title,
            "chapter_intro": chap_intro,
            "sections": sections
        })

    # Tidy whitespace recursively
    def trim_node(n):
        for k in ("title","content","content_preface"):
            if k in n and isinstance(n[k], str):
                n[k] = n[k].strip()
        for b in n.get("bullets", []):
            if "text" in b: b["text"] = b["text"].strip()
        for c in n.get("children", []):
            trim_node(c)

    for ch in chapters:
        ch["chapter_title"] = ch.get("chapter_title","").strip()
        ch["chapter_intro"] = ch.get("chapter_intro","").strip()
        for s in ch["sections"]:
            trim_node(s)

    data = {"chapters": chapters}
    OUT_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote JSON to: {OUT_JSON.resolve()}")
