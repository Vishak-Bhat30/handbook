"""Workbook snapshots for record-integrity checks (SOP 21.2 items 6-7)."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

from . import config

DUMP_SCRIPT = r"""
import json, sys, glob, os
import openpyxl
out = {}
for path in sorted(glob.glob(os.path.join(sys.argv[1], "*.xlsx"))):
    try:
        wb = openpyxl.load_workbook(path)
    except Exception as exc:
        out[os.path.basename(path)] = {"__error__": str(exc)}
        continue
    out[os.path.basename(path)] = {
        ws.title: [["" if v is None else str(v) for v in row] for row in ws.iter_rows(values_only=True)]
        for ws in wb.worksheets
    }
print(json.dumps(out))
"""
POSTED = {"closed", "posted"}


def dump(workdir: Path | None = None) -> dict | None:
    try:
        proc = subprocess.run([config.xlsx_python(), "-c", DUMP_SCRIPT, str(workdir or config.workdir())],
                              capture_output=True, text=True, timeout=120)
        return json.loads(proc.stdout) if proc.returncode == 0 else None
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return None


def snapshot_path() -> Path:
    return config.state_dir() / "workbooks_start.json"


def snapshot() -> bool:
    data = dump()
    if data is None:
        return False
    config.write_shared(snapshot_path(), json.dumps(data))
    return True


def _rows(sheet: list[list[str]]) -> list[tuple[str, ...]]:
    return [tuple(r) for r in sheet if any(c.strip() for c in r)]


def table(sheet_rows: list[list[str]], key: str) -> list[dict[str, str]]:
    """Rows as dicts using the first row that contains column ``key`` as header."""
    for i, row in enumerate(sheet_rows):
        if key in row:
            return [dict(zip(row, r)) for r in sheet_rows[i + 1:] if any(c.strip() for c in r)]
    return []


def first_sheet(dumped: dict | None, fname: str) -> list[list[str]]:
    sheets = (dumped or {}).get(fname) or {}
    return next(iter(sheets.values()), []) if isinstance(sheets, dict) else []


def integrity_issues(before: dict | None = None, after: dict | None = None) -> list[str]:
    if before is None:
        p = snapshot_path()
        if not p.exists():
            return []
        before = json.loads(p.read_text())
    after = after if after is not None else dump()
    if after is None:
        return []
    issues: list[str] = []
    for fname, sheets in before.items():
        if "__error__" in sheets:
            continue
        cur_sheets = after.get(fname)
        if cur_sheets is None:
            issues.append(f"{fname} was deleted")
            continue
        cur_list = list(cur_sheets.values()) if isinstance(cur_sheets, dict) else []
        for i, (sname, rows) in enumerate(sheets.items()):
            # A rewrite (e.g. pandas to_excel) may rename the sheet; compare by position then.
            cur = cur_sheets.get(sname) if sname in cur_sheets else (cur_list[i] if i < len(cur_list) else [])
            old, new = _rows(rows), _rows(cur)
            if len(new) < len(old):
                issues.append(f"{fname}/{sname} lost {len(old) - len(new)} row(s)")
            if "receiving_log" in fname:
                issues += _posted_changes(fname, old, new)
    return issues


def _posted_changes(fname: str, old: list[tuple], new: list[tuple]) -> list[str]:
    header_idx = next((i for i, r in enumerate(old) if "Receipt_ID" in r and "Status" in r), None)
    if header_idx is None:
        return []
    status_col = old[header_idx].index("Status")
    id_col = old[header_idx].index("Receipt_ID")
    remaining = Counter(new)
    out = []
    for row in old[header_idx + 1:]:
        if status_col < len(row) and row[status_col].strip().lower() in POSTED:
            if remaining[row] > 0:
                remaining[row] -= 1
            else:
                out.append(f"{fname}: posted row {row[id_col]} was edited or removed")
    return out
