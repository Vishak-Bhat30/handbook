"""Print a task's parsed SOP paragraphs (id, section, kind, text). Usage: sop_dump.py <task> [out.txt]"""
import json
import sys
from pathlib import Path

P = Path("/mnt/datadrive/t-bhatvishak/Vishak_Handbook/docker/openhands-runner/interwhen_sop/tasks")
d = json.loads((P / sys.argv[1] / "sop.json").read_text())
lines = [f"{p['id']}\t[{p['section']}] {p.get('section_title', '')}\t{p['kind']}\t{p['text']}" for p in d["paragraphs"]]
out = "\n".join(lines)
if len(sys.argv) > 2:
    Path(sys.argv[2]).write_text(out)
    print(f"{len(lines)} paragraphs -> {sys.argv[2]}")
else:
    print(out)
