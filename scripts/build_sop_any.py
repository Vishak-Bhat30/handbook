"""Parse a task's SOP (.docx / .html / .pdf) into the interwhen_sop paragraph JSON.

Run (needs python-docx and pdfplumber, not in the harbor venv):
    UV_CACHE_DIR=/mnt/datadrive/t-bhatvishak/home-cache/uv uv run --no-project --with python-docx \
        --with pdfplumber python scripts/build_sop_any.py logistics_prairie_star_creamery_27470081 [sop file name]

Only the SOP file is read; graders, rubrics and job outputs are never consulted.
"""

from __future__ import annotations

import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PKG_TASKS = REPO / "docker" / "openhands-runner" / "interwhen_sop" / "tasks"

SECTION = re.compile(r"^(?:Section\s+)?(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s+(\S.{1,100})$")
CONTACT = re.compile(r"^(?P<name>[A-Z][\w.'-]+(?: [A-Z][\w.'-]+)+)\s+[—–-]\s+(?P<role>[^—–]+?)\s+[—–-]\s+"
                     r"(?P<email>[\w.+-]+@[\w.-]+\w)\s*(?:[—–-]\s*Slack:\s*@(?P<handle>[\w.-]+\w))?")


def _docx_blocks(path: Path) -> list[tuple[str, str]]:
    import docx
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    d = docx.Document(path)
    out = []
    for child in d.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, d)
            style = (p.style.name if p.style is not None else "").lower()
            kind = "heading" if style.startswith(("heading", "title")) else "bullet" if "list" in style else "text"
            out.append((kind, p.text))
        elif tag == "tbl":
            for row in Table(child, d).rows:
                cells = []
                for c in row.cells:
                    t = c.text.strip()
                    if t and (not cells or cells[-1] != t):
                        cells.append(t)
                out.append(("table_row", " | ".join(cells)))
    return out


class _HTML(HTMLParser):
    BLOCK = {"p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "div", "pre", "blockquote", "title", "dt", "dd"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, str]] = []
        self.stack: list[tuple[str, list[str]]] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in self.BLOCK:
            self.stack.append((tag, []))
        elif tag in ("td", "th") and self.stack:
            self.stack[-1][1].append(" | ")
        elif tag == "br" and self.stack:
            self.stack[-1][1].append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK and self.stack:
            # Close up to the matching tag; nested blocks emit their own text first.
            while self.stack:
                t, buf = self.stack.pop()
                self._emit(t, "".join(buf))
                if t == tag:
                    break

    def handle_data(self, data):
        if self.skip:
            return
        if self.stack:
            self.stack[-1][1].append(data)
        elif data.strip():
            self.blocks.append(("text", data))

    def _emit(self, tag, text):
        kind = {"li": "bullet", "tr": "table_row", "title": "skip"}.get(tag, "heading" if tag[0] == "h" and tag[1:].isdigit() else "text")
        if kind == "skip":
            return
        if kind == "table_row":
            text = " | ".join(c.strip() for c in text.split(" | ") if c.strip())
        for line in text.split("\n"):
            if line.strip():
                self.blocks.append((kind, line))


def _html_blocks(path: Path) -> list[tuple[str, str]]:
    p = _HTML()
    p.feed(path.read_text(encoding="utf-8", errors="replace"))
    return p.blocks


def _pdf_blocks(path: Path) -> list[tuple[str, str]]:
    import pdfplumber

    out: list[tuple[str, str]] = []
    buf: list[str] = []

    def flush():
        if buf:
            out.append(("text", " ".join(buf)))
            buf.clear()

    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for ln in (page.extract_text() or "").splitlines():
                s = ln.strip()
                if not s or re.fullmatch(r"(Page )?\d{1,3}( of \d+)?", s):
                    continue
                if SECTION.match(s) and len(s) < 90 and not s.endswith((".", ",")):
                    flush()
                    out.append(("heading", s))
                elif re.match(r"^([•●▪◦\-–]|\d{1,2}[.)])\s", s):
                    flush()
                    buf.append(s)
                else:
                    if buf and buf[-1].endswith((".", ":")) and len(buf[-1]) < 80 and not s[0].islower():
                        flush()
                    buf.append(s)
            flush()
    return out


def blocks(path: Path) -> list[tuple[str, str]]:
    suf = path.suffix.lower()
    raw = _docx_blocks(path) if suf == ".docx" else _html_blocks(path) if suf in (".html", ".htm") else _pdf_blocks(path)
    return [(k, re.sub(r"\s+", " ", html.unescape(t)).strip()) for k, t in raw if t and t.strip()]


def build(task: str, sop_name: str | None = None) -> dict:
    ws = REPO / "tasks" / task / "environment" / "initial_workspace"
    if sop_name:
        path = ws / sop_name
    else:
        cands = [p for p in ws.iterdir() if re.search(r"sop", p.name, re.I) and p.suffix.lower() in (".docx", ".html", ".htm", ".pdf")]
        path = sorted(cands)[0]
    section, title = "0", "Front matter"
    paragraphs: list[dict] = []
    toc: list[dict] = []
    for kind, text in blocks(path):
        m = SECTION.match(text)
        if m and (kind == "heading" or (len(text) < 80 and not text.endswith((".", ":", ",")))):
            section, title = m.group(1), m.group(2).strip()
            toc.append({"section": section, "title": title})
            kind = "heading"
        paragraphs.append({"id": f"P{len(paragraphs) + 1:04d}", "section": section, "section_title": title,
                           "page": 0, "kind": kind, "text": text})
    contacts = []
    for p in paragraphs:
        m = CONTACT.match(p["text"])
        if m:
            contacts.append({"name": m.group("name"), "role": m.group("role").strip(), "email": m.group("email"),
                             "handle": m.group("handle") or "", "source": p["id"]})
    return {"source_pdf": str(path.relative_to(REPO)), "toc": toc, "paragraphs": paragraphs,
            "templates": {}, "contacts": contacts, "holidays": []}


def main() -> None:
    task = sys.argv[1]
    data = build(task, sys.argv[2] if len(sys.argv) > 2 else None)
    out_dir = PKG_TASKS / task
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sop.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
    kinds: dict[str, int] = {}
    for p in data["paragraphs"]:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    print(f"{task}: {data['source_pdf']} -> {len(data['paragraphs'])} paragraphs {kinds}; "
          f"{len(data['toc'])} sections; {len(data['contacts'])} contacts")


if __name__ == "__main__":
    main()
