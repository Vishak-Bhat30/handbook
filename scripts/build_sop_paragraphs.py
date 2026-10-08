"""Parse a task's SOP PDF into paragraph/template/contact/holiday JSON for interwhen_sop.

Run (needs pdfplumber, not in the harbor venv):
    UV_CACHE_DIR=/mnt/datadrive/t-bhatvishak/home-cache/uv uv run --no-project --with pdfplumber \
        python scripts/build_sop_paragraphs.py logistics_gear_sytems_inc_9b60992d

Only the SOP PDF is read; graders, rubrics and job outputs are never consulted.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pdfplumber

REPO = Path(__file__).resolve().parents[1]
PKG_TASKS = REPO / "docker" / "openhands-runner" / "interwhen_sop" / "tasks"

TOC_LINE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.+?)\s*\.{4,}\s*\d+\s*$")
LIST_ITEM = re.compile(r"^(\d{1,2})\.\s+\S")
BULLET = re.compile(r"^[•▪◦]\s*")
TEMPLATE_HEAD = re.compile(r"^Template (\d+) — (.+)$")
CONTACT = re.compile(
    r"^•\s*(?P<name>[A-Z][\w.'-]+(?: [A-Z][\w.'-]+)+) \((?P<role>[^)]+)\):\s*"
    r"(?P<email>[\w.]+@[\w.]+\w)\s*/\s*@(?P<handle>[\w-]+(?:\.[\w-]+)*)"
)
MONTHS = {m: i for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July", "August",
     "September", "October", "November", "December"], start=1)}


def _pages(pdf_path: Path) -> list[tuple[int, list[str]]]:
    out = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            lines = [ln.rstrip() for ln in (page.extract_text() or "").splitlines()]
            # Trailing lone number is the printed page number.
            while lines and re.fullmatch(r"\d{1,3}", lines[-1].strip()):
                lines.pop()
            out.append((i, lines))
    return _repair_glyphs(out)


# Some SOP PDFs map ligatures to wrong glyphs ("No+ce", "speciXic", "LeLer", "Shig").
GLYPH_SUBS = [(r"\+", "ti"), (r"(?<=[a-z])X(?=[a-z])", "f"), (r"(?<=[a-z])V(?=[a-z])", "f"),
              (r"(?<=[a-z])L(?=[a-z])", "tt"), (r"(?<=[A-Za-z])g", "ft")]
WORD = re.compile(r"[A-Za-z+]+")


def _repair_glyphs(pages):
    from collections import Counter

    freq = Counter(w.lower() for _, lines in pages for ln in lines for w in WORD.findall(ln) if "+" not in w)

    def candidates(tok: str) -> set[str]:
        out = {tok}
        for pat, rep in GLYPH_SUBS:
            for c in list(out):
                for m in re.finditer(pat, c):
                    out.add(c[:m.start()] + rep + c[m.end():])
                out.add(re.sub(pat, rep, c))
        return out - {tok}

    cache: dict[str, str] = {}

    def fix(tok: str) -> str:
        if tok not in cache:
            best = max(candidates(tok), key=lambda c: freq.get(c.lower(), 0), default=tok)
            gain = freq.get(best.lower(), 0) > max(freq.get(tok.lower(), 0), 0 if "+" in tok else 1)
            if not gain and re.search(r"[a-z][XV][a-z]|^X[a-z]", tok):
                # A capital inside a lowercase word is never valid; "fi"/"fl" glyphs never render correctly.
                best, gain = re.sub(r"(?<=[a-z])[XV](?=[a-z])|^X(?=[a-z])", "f", tok), True
            cache[tok] = best if gain else tok
        return cache[tok]

    return [(p, [WORD.sub(lambda m: fix(m.group(0)), re.sub(r"(?<=[a-z])<(?=[a-z])", "f", ln)) for ln in lines])
            for p, lines in pages]


def _toc(pages) -> list[tuple[str, str]]:
    toc = []
    for _, lines in pages[:8]:
        for ln in lines:
            m = TOC_LINE.match(ln.strip())
            if m:
                toc.append((m.group(1), m.group(2).strip()))
    return toc or _body_toc(pages)


BODY_HEADING = re.compile(r"^(\d{1,2})(?:\.(\d{1,2}))?\.? ([A-Z][^:;]{2,80})$")


def _body_toc(pages) -> list[tuple[str, str]]:
    """SOP variants with an empty TOC: take in-order 'N. Title' / 'N.M Title' body lines as headings."""
    toc, chap, sub = [], 0, 0
    for _, lines in pages:
        for ln in lines:
            m = BODY_HEADING.match(ln.strip())
            if not m:
                continue
            n, s, title = int(m.group(1)), m.group(2), m.group(3).strip()
            words = title.split()
            title_case = len(words) <= 10 and sum(w[0].isupper() or not w[0].isalpha() for w in words) >= len(words) - 2
            if s is None and n == chap + 1 and title_case and not title.endswith("."):
                chap, sub = n, 0
                toc.append((str(n), title))
            elif s is not None and ((n == chap and int(s) in (sub + 1, sub + 2)) or (n == chap + 1 and s == "1")):
                chap, sub = n, int(s)
                toc.append((f"{n}.{s}", title))
    return toc


def _heading_index(toc):
    index = {}
    for sid, title in toc:
        index[f"{sid}. {title}"] = (sid, title)
        index[f"{sid} {title}"] = (sid, title)
    return index


def _toc_heading(line: str, toc: dict[str, str]) -> tuple[str, str] | None:
    """Body heading whose wording drifted from the TOC (glyph damage): same id, same first title word."""
    m = re.match(r"^(\d+(?:\.\d+)+)\s+(\S+)", line)
    if m and m.group(1) in toc and toc[m.group(1)].split()[0].lower() == m.group(2).lower():
        return m.group(1), toc[m.group(1)]
    return None


SUB_HEADING = re.compile(r"^(\d+\.\d+\.\d+) ([A-Z].{2,90})$")
CHAPTER = re.compile(r"^(\d{1,2})\. ([A-Z][^.,;:]{3,60})$")


def _untracked_heading(line: str, section: str) -> tuple[str, str] | None:
    """Headings absent from the TOC: N.N.N sub-sections and trailing chapters (e.g. 23)."""
    m = SUB_HEADING.match(line)
    if m and m.group(1).rsplit(".", 1)[0] == ".".join(section.split(".")[:2]):
        return m.group(1), m.group(2).strip()
    m = CHAPTER.match(line)
    if m and int(m.group(1)) == int(section.split(".")[0]) + 1:
        words = m.group(2).split()
        if sum(w[0].isupper() for w in words) >= max(2, len(words) - 2):
            return m.group(1), m.group(2).strip()
    return None


def _starts_new(line: str) -> bool:
    return bool(LIST_ITEM.match(line) or BULLET.match(line) or TEMPLATE_HEAD.match(line))


def build(task: str) -> dict:
    pdf = next((REPO / "tasks" / task / "environment" / "initial_workspace").glob("*SOP*.pdf"))
    pages = _pages(pdf)
    toc = _toc(pages)
    headings = _heading_index(toc)
    toc_ids = dict(toc)
    toc_pages = {p for p, lines in pages[:8] if any(TOC_LINE.match(l.strip()) for l in lines)}

    paragraphs: list[dict] = []
    section, title = "0", "Front matter"
    buf: list[str] = []
    buf_page = 1
    kind = "text"

    def flush():
        nonlocal buf
        text = " ".join(s.strip() for s in buf).strip()
        text = re.sub(r"\s+", " ", text)
        if text:
            paragraphs.append({
                "id": f"P{len(paragraphs) + 1:04d}",
                "section": section,
                "section_title": title,
                "page": buf_page,
                "kind": kind,
                "text": text,
            })
        buf = []

    for page_no, lines in pages:
        if page_no in toc_pages:
            continue
        for raw in lines:
            line = raw.strip()
            if not line:
                continue
            # pdfplumber sometimes appends a "# N. Title" fragment for the next chapter.
            line = re.sub(r"\s#\s*\d+\.\s.*$", "", line).strip()
            head = headings.get(line) or _toc_heading(line, toc_ids) or _untracked_heading(line, section)
            if head:
                flush()
                section, title = head
                kind = "heading"
                buf, buf_page = [line], page_no
                flush()
                kind = "text"
                continue
            in_templates = section.startswith("23")
            if in_templates:
                # Template text is kept line-by-line; wrapped continuations start lowercase.
                if buf and (line[0].islower() or line[0] in ",;)") and kind == "template_line":
                    buf.append(line)
                    continue
                flush()
                kind = "template_line"
                buf, buf_page = [line], page_no
                continue
            if _starts_new(line):
                flush()
                kind = "list_item" if LIST_ITEM.match(line) else "bullet"
                buf, buf_page = [line], page_no
                continue
            if buf:
                prev = buf[-1]
                ends_sentence = prev.endswith((".", ":", "?", "!", '"', "”"))
                if ends_sentence and len(prev) < 85 and not line[0].islower():
                    flush()
                    kind = "text"
                    buf, buf_page = [line], page_no
                    continue
                buf.append(line)
            else:
                kind = "text"
                buf, buf_page = [line], page_no
    flush()

    return {
        "source_pdf": str(pdf.relative_to(REPO)),
        "toc": [{"section": s, "title": t} for s, t in toc],
        "paragraphs": paragraphs,
        "templates": _templates(paragraphs),
        "contacts": _contacts(paragraphs),
        "holidays": _holidays(paragraphs),
    }


def _templates(paragraphs) -> dict:
    templates: dict[str, dict] = {}
    current = None
    for p in paragraphs:
        if not p["section"].startswith("23") or p["kind"] != "template_line":
            continue
        m = TEMPLATE_HEAD.match(p["text"])
        if m:
            current = {"number": int(m.group(1)), "title": m.group(2).strip(),
                       "usage": [], "subject": None, "body": [], "paragraph_ids": [p["id"]]}
            templates[m.group(1)] = current
            continue
        if current is None:
            continue
        current["paragraph_ids"].append(p["id"])
        text = p["text"]
        if text.startswith("Templates ") and ":" in text:
            # Group header like "Templates 8–12: Documentation Requests" ends the template.
            current = None
            continue
        if current["subject"] is None and text.startswith("Subject:"):
            current["subject"] = text.split(":", 1)[1].strip()
        elif not current["body"] and current["subject"] is None and text.startswith("Used "):
            current["usage"].append(text)
        else:
            current["body"].append(text)
    return templates


class _Contact:
    def __init__(self, d):
        self.d = d

    def groupdict(self):
        return self.d


def _scrambled_contact(text: str):
    """Variants where '.com / @handle' is interleaved, e.g. 'x@gearsystems.c /o @mcyablonski.'"""
    m = re.match(r"^•\s*(?P<name>[A-Z][\w.'-]+(?: [A-Z][\w.'-]+)+) \((?P<role>[^)]+)\):\s*"
                 r"(?P<local>[\w.]+)@\s?(?P<dom>\w+)\.\s?c\s?(?P<sep>[/o m]*)@\s?(?P<handle>[\w-]+)", text)
    if not m:
        return None
    handle = m.group("handle")
    if "m" not in m.group("sep") and handle.startswith("m"):
        handle = handle[1:]
    return _Contact({"name": m.group("name"), "role": m.group("role"),
                     "email": f"{m.group('local')}@{m.group('dom')}.com", "handle": handle})


def _contacts(paragraphs) -> list[dict]:
    contacts = []
    lines = [p for p in paragraphs if p["section"].startswith("4.")]
    for p in lines:
        m = CONTACT.match(p["text"]) or _scrambled_contact(p["text"])
        if m:
            contacts.append({**m.groupdict(), "source": p["id"]})
    # Section 4.1 block format: Position / Name / Email / Slack.
    block = " ".join(p["text"] for p in lines if p["section"] == "4.1")
    for m in re.finditer(
        r"Position: (?P<role>.+?) Name: (?P<name>.+?) Email: (?P<email>\S+(?: om)?) Slack: @(?P<handle>[\w-]+(?:\.[\w-]+)*(?: [a-z]\b)?)",
        block,
    ):
        name = m.group("name").strip()
        contacts.append({
            "name": None if name.startswith("(") else name,
            "role": m.group("role").strip(),
            "email": m.group("email").replace(" ", ""),
            "handle": m.group("handle").replace(" ", ""),
            "source": "4.1",
        })
    return contacts


def _holidays(paragraphs) -> list[dict]:
    intro = next(p for p in paragraphs if re.search(r"company-\s?observed holidays", p["text"]))
    year = int(re.search(r"(\d{4}) company-\s?observed holidays", intro["text"]).group(1))
    found = []
    for p in paragraphs:
        if p["section"] != intro["section"]:
            continue
        for m in re.finditer(
            r"([A-Z][A-Za-z’' ]+?) (?:Monday|Tuesday|Wednesday|Thursday|Friday), "
            r"(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2})",
            p["text"],
        ):
            found.append({"name": re.sub(r"^(Holiday \d{4} )?Date ", "", m.group(1)).strip(),
                          "date": f"{year:04d}-{MONTHS[m.group(2)]:02d}-{int(m.group(3)):02d}",
                          "source": p["id"]})
    return found


def main() -> None:
    task = sys.argv[1]
    data = build(task)
    out_dir = PKG_TASKS / task
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sop.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
    kinds: dict[str, int] = {}
    for p in data["paragraphs"]:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    print(f"{task}: {len(data['paragraphs'])} paragraphs {kinds}; "
          f"{len(data['templates'])} templates; {len(data['contacts'])} contacts; "
          f"{len(data['holidays'])} holidays -> {out_dir / 'sop.json'}")


if __name__ == "__main__":
    main()
