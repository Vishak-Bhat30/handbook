"""SOP Section 23 template conformance (pure Python)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .sopdata import SOP

PLACEHOLDER = re.compile(r"\[[A-Z][A-Za-z0-9 #/&'.,()\-–—]*\]")
BULLET = re.compile(r"^\s*(?:[-*•▪◦·]|\d+[.)])\s+")


def norm(text: str) -> str:
    text = text.replace("\u2014", "-").replace("\u2013", "-").replace("\u2012", "-")
    text = text.replace("\u2018", "'").replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    text = BULLET.sub("• ", text)
    return re.sub(r"\s+", " ", text).strip()


def _pattern(line: str, fill: dict[str, str]) -> re.Pattern:
    out, pos = [], 0
    n = norm(line)
    for m in PLACEHOLDER.finditer(n):
        out.append(re.escape(n[pos:m.start()]))
        key = m.group(0)
        out.append(re.escape(norm(fill[key])) if key in fill else r"(?![\[]).+?")
        pos = m.end()
    out.append(re.escape(n[pos:]))
    return re.compile("".join(out), re.I)


def render(line: str, fill: dict[str, str]) -> str:
    for k, v in fill.items():
        line = line.replace(k, v)
    return line


# Bracketed text that a domain's SOP templates use literally (e.g. "[Suspense Escalation]").
LITERAL: set[str] = set()
LITERAL_RX: list[re.Pattern] = []


def unfilled_placeholders(text: str) -> list[str]:
    return sorted(p for p in set(PLACEHOLDER.findall(text)) - LITERAL if not any(rx.fullmatch(p) for rx in LITERAL_RX))


@dataclass
class TemplateCheck:
    problems: list[str] = field(default_factory=list)
    expected_subject: str = ""
    expected_body: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def check(sop: SOP, number: int, subject: str, body: str, *, fill: dict[str, str],
          required_bullets: list[str], first_name: str | None,
          initials_rule: tuple[str | None, str]) -> TemplateCheck:
    """Validate an email against SOP Template ``number`` as written.

    ``required_bullets`` are the template bullet lines that apply to the situation
    (Template 31: "Delete all list line items that do not apply").
    """
    tpl = sop.template(number)
    res = TemplateCheck()
    lines = tpl["body"]
    signoff = [norm(s) for s in sop.standard_signoff()]
    initials, initials_note = initials_rule

    # Expected rendering (used for feedback).
    res.expected_subject = render(tpl["subject"], fill)
    for ln in lines:
        if ln.startswith("•") and ln not in required_bullets:
            continue
        if ln == "[Coordinator Initials]":
            res.expected_body.append(initials or "[Coordinator Initials]")
        elif ln.startswith("Hi [First Name]"):
            res.expected_body.append(f"Hi {first_name or '[First Name]'},")
        else:
            res.expected_body.append(render(ln, fill))

    if not _pattern(tpl["subject"], fill).fullmatch(norm(subject)):
        res.problems.append(
            f"Subject must be exactly the Template {number} subject: \"{res.expected_subject}\" (got \"{subject}\").")

    body_lines = [ln for ln in (s.strip() for s in body.splitlines()) if ln]
    matched: list[int] = []
    extras: list[str] = []
    cursor = 0
    i = 0
    while i < len(body_lines):
        hit = None
        for span in (1, 2, 3):
            if i + span > len(body_lines):
                break
            candidate = norm(" ".join(body_lines[i:i + span]))
            for j in range(cursor, len(lines)):
                tl = lines[j]
                if tl.startswith("Hi [First Name]"):
                    ok = bool(re.fullmatch(r"(hi|hello|dear) [^,]+,", candidate, re.I))
                elif tl == "[Coordinator Initials]":
                    ok = bool(re.fullmatch(r"[A-Z]{2,4}", candidate))
                else:
                    ok = bool(_pattern(tl, fill).fullmatch(candidate))
                if ok:
                    hit = (j, span)
                    break
            if hit:
                break
        if hit:
            matched.append(hit[0])
            cursor = hit[0] if lines[hit[0]].startswith("•") else hit[0] + 1
            i += hit[1]
            continue
        if norm(body_lines[i]) in signoff:
            i += 1
            continue
        extras.append(body_lines[i])
        i += 1

    if extras:
        shown = "; ".join(f"\"{e[:90]}\"" for e in extras[:6])
        res.problems.append(
            f"Template {number} must be used as written (Section 23): remove text that is not part of the "
            f"template ({len(extras)} extra line(s): {shown}).")

    got = {lines[j] for j in matched}
    for ln in lines:
        required = not ln.startswith("•") or ln in required_bullets
        if required and ln not in got:
            res.problems.append(f"Missing template line: \"{render(ln, fill)}\".")

    greeting = next((norm(b) for b in body_lines if re.match(r"(hi|hello|dear)\b", b, re.I)), None)
    if first_name and greeting and first_name.lower() not in greeting.lower():
        res.problems.append(f"Greeting must address the recipient by first name: \"Hi {first_name},\".")

    sign = [b for b in body_lines if re.fullmatch(r"[A-Z]{2,4}", b.strip())]
    if initials and sign and sign[-1].strip() != initials:
        res.problems.append(f"Sign-off initials must be the Coordinator's initials \"{initials}\" ({initials_note}).")
    if "[Coordinator Initials]" in lines and not sign:
        res.problems.append(
            "Replace [Coordinator Initials] with the Coordinator's initials"
            + (f" \"{initials}\" ({initials_note})." if initials else
               " as recorded in the Coordinator_Initials column of the workbooks."))

    left = unfilled_placeholders(f"{subject}\n{body}")
    if left:
        res.problems.append(f"Unfilled placeholders {left}: replace every [bracketed placeholder] (Section 23).")
    return res
