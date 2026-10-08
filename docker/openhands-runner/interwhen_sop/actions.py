"""Classify a proposed tool call into an SOP-relevant action (pure Python)."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from typing import Any

READ_VERBS = ("get", "list", "search", "read", "find", "query", "lookup", "fetch", "view", "describe")
EMAIL_SEND = {"google_mail__send_email", "google_mail__reply_to_email", "google_mail__forward_email",
              "google_mail__send_draft"}
SLACK_CHANNEL_POST = {"slack__post_message", "slack__reply_to_thread"}
SLACK_DM = {"slack__send_dm", "slack__send_mpim"}
CAL_CREATE = {"google_calendar__create_event"}
CAL_UPDATE = {"google_calendar__update_event"}
CAL_DELETE = {"google_calendar__delete_event"}
EMAIL_MOVE = {"google_mail__move_emails", "google_mail__move_email"}
EMAIL_MARK = {"google_mail__mark_emails", "google_mail__mark_email"}
EMAIL_DELETE = {"google_mail__delete_emails", "google_mail__delete_email", "google_mail__trash_emails"}
CODE_TOOLS = {"syntara__executePython": "code", "syntara__executeBash": "command"}
FILE_WRITE = {"syntara__writeFile", "syntara__editFile", "syntara__appendFile"}
FILE_DELETE = {"syntara__deleteFile", "syntara__removeFile"}
CONTROL = {"think", "finish"}

XLSX = re.compile(r"[\w.-]+\.xlsx")
WRITE_MARKERS = re.compile(
    r"\.save\(|to_excel\(|\.write_text\(|\.write_bytes\(|open\([^)]*,\s*['\"][wax]b?\+?['\"]|"
    r"shutil\.(?:copy|move)|os\.rename|\.delete_rows\(|\.insert_rows\(|\.append\(\s*\[",
)
DELETE_MARKERS = re.compile(
    r"os\.remove\(|os\.unlink\(|\.unlink\(|shutil\.rmtree\(|\.delete_rows\(|(?:^|[;&|\s])rm\s+-?\w*\s*\S*/?workdir"
    r"|(?:^|[;&|\s])rm\s+\S+\.(?:xlsx|pdf|json|txt)",
)


@dataclass
class Action:
    tool: str
    args: dict[str, Any]
    kind: str
    text: str = ""
    recipients: list[str] = field(default_factory=list)
    cc: list[str] = field(default_factory=list)
    subject: str = ""
    channel: str = ""
    files_written: list[str] = field(default_factory=list)
    deletes: bool = False
    code: str = ""

    @property
    def is_write(self) -> bool:
        return self.kind not in ("read", "control")

    @property
    def is_communication(self) -> bool:
        return self.kind in ("email_send", "slack_post", "slack_dm", "calendar_create", "calendar_update")


def _split_addrs(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, list):
        parts = [str(v) for v in value]
    else:
        parts = re.split(r"[,;]", str(value))
    out = []
    for part in parts:
        m = re.search(r"[\w.+-]+@[\w.-]+\w", part)
        if m:
            out.append(m.group(0).lower())
    return out


def _python_from_bash(command: str) -> str:
    """Pull embedded python (heredoc or -c) out of a bash command for analysis."""
    chunks = re.findall(r"<<\s*'?\"?(\w+)'?\"?\n(.*?)\n\1", command, flags=re.S)
    code = "\n".join(body for _, body in chunks)
    code += "\n" + "\n".join(re.findall(r"python3?\s+-c\s+\"(.*?)\"(?:\s|$)", command, flags=re.S))
    code += "\n" + "\n".join(re.findall(r"python3?\s+-c\s+'(.*?)'(?:\s|$)", command, flags=re.S))
    return code


def _resolve_written_files(code: str) -> list[str]:
    """Workbooks a code snippet saves to, via assignment tracking; fall back to all referenced."""
    if not WRITE_MARKERS.search(code):
        return []
    referenced = sorted(set(m.split("/")[-1] for m in XLSX.findall(code)))
    var_file: dict[str, str] = {}
    targets: set[str] = set()
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return referenced

    def literal(node: ast.AST) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            m = XLSX.search(node.value)
            return m.group(0).split("/")[-1] if m else None
        if isinstance(node, ast.JoinedStr):
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    m = XLSX.search(v.value)
                    if m:
                        return m.group(0).split("/")[-1]
            return None
        if isinstance(node, ast.Name):
            return var_file.get(node.id)
        if isinstance(node, ast.BinOp):
            return literal(node.left) or literal(node.right)
        if isinstance(node, ast.Call) and node.args:
            return literal(node.args[-1]) or literal(node.args[0])
        return None

    unresolved = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            f = literal(node.value)
            if f:
                var_file[node.targets[0].id] = f
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        attr = node.func.attr
        if attr in ("save", "to_excel"):
            f = literal(node.args[0]) if node.args else None
            if f is None and isinstance(node.func.value, ast.Name):
                f = var_file.get(node.func.value.id)
            if f:
                targets.add(f)
            else:
                unresolved = True
    if unresolved and not targets:
        return referenced
    return sorted(targets)


def _shell_write_targets(command: str) -> list[str]:
    """Files written by shell redirection/mv/cp/tee/sed -i, ignoring heredoc bodies."""
    shell = re.sub(r"<<\s*'?\"?(\w+)'?\"?\n.*?\n\1", "", command, flags=re.S)
    shell = re.sub(r"python3?\s+-c\s+(\"[^\"]*\"|'[^']*')", "", shell, flags=re.S)
    targets = re.findall(r"(?:^|[\s;&|])\d?>>?\s*([^\s;&|]+)", shell)
    targets += re.findall(r"\btee\s+(?:-a\s+)?([^\s;&|]+)", shell)
    targets += [m[-1] for m in re.findall(r"\b(?:mv|cp)\s+(?:-\w+\s+)*(\S+)\s+(\S+)", shell)]
    targets += re.findall(r"\bsed\s+-i\S*\s+(?:'[^']*'|\"[^\"]*\"|\S+)\s+(\S+)", shell)
    return sorted({t.split("/")[-1] for t in targets if t and not t.startswith("/dev/") and "&" not in t})


def classify(tool: str, args: dict[str, Any] | None) -> Action:
    args = dict(args or {})
    name = tool or ""
    short = name.split("__", 1)[-1].lower()

    if name in CONTROL:
        return Action(name, args, "control", text=str(args.get("message", "")))
    if name in EMAIL_SEND:
        return Action(
            name, args, "email_send",
            text=str(args.get("body") or args.get("body_text") or ""),
            subject=str(args.get("subject") or ""),
            recipients=_split_addrs(args.get("to") or args.get("to_addr")),
            cc=_split_addrs(args.get("cc")) + _split_addrs(args.get("bcc")),
        )
    if name in SLACK_CHANNEL_POST:
        return Action(name, args, "slack_post", text=str(args.get("text", "")),
                      channel=str(args.get("channel_id") or args.get("channel") or ""))
    if name in SLACK_DM:
        users = args.get("user_id") or args.get("user_ids") or args.get("users") or ""
        if isinstance(users, (list, tuple)):
            users = ",".join(str(u) for u in users)
        return Action(name, args, "slack_dm", text=str(args.get("text", "")),
                      recipients=[u for u in re.split(r"[,\s]+", str(users)) if u])
    if name in CAL_CREATE | CAL_UPDATE:
        attendees = args.get("attendees") or []
        emails = [a.get("email", "") for a in attendees if isinstance(a, dict)] if isinstance(attendees, list) else []
        return Action(
            name, args, "calendar_create" if name in CAL_CREATE else "calendar_update",
            text=f"{args.get('summary', '')}\n{args.get('description', '')}",
            subject=str(args.get("summary", "")),
            recipients=[e.lower() for e in emails if e],
        )
    if name in CAL_DELETE:
        return Action(name, args, "calendar_delete")
    if name in EMAIL_MOVE | EMAIL_MARK | EMAIL_DELETE:
        ids = args.get("email_ids") or ([args["email_id"]] if args.get("email_id") else [])
        kind = "email_move" if name in EMAIL_MOVE else "email_mark" if name in EMAIL_MARK else "email_delete"
        return Action(name, args, kind, recipients=[str(i) for i in ids],
                      channel=str(args.get("target_folder") or args.get("folder") or ""),
                      deletes=kind == "email_delete")
    if name in CODE_TOOLS:
        raw = str(args.get(CODE_TOOLS[name], ""))
        code = raw if name == "syntara__executePython" else _python_from_bash(raw)
        files = _resolve_written_files(code)
        deletes = bool(DELETE_MARKERS.search(raw))
        if name == "syntara__executeBash":
            files = sorted(set(files) | set(_shell_write_targets(raw)))
        kind = "workbook_write" if files else ("file_delete" if deletes else "read")
        if deletes and kind == "read":
            kind = "file_delete"
        return Action(name, args, kind, text=raw, files_written=files, deletes=deletes, code=code or raw)
    if name in FILE_WRITE:
        path = str(args.get("file_path") or args.get("path") or "")
        return Action(name, args, "file_write", text=str(args.get("content", "")),
                      files_written=[path.split("/")[-1]] if path else [])
    if name in FILE_DELETE:
        return Action(name, args, "file_delete", deletes=True)
    if short.startswith(READ_VERBS) or short in ("whoami",):
        return Action(name, args, "read")
    return Action(name, args, "other_write", text=str(args))
