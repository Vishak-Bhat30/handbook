"""Verifiers for medical_careig_specialty_pharmacy_f6d19d30 (CareIG SOP 7.3 Patient Financial Counseling, post-call).

Seed facts (environment only): the financial counseling call with Kevin Lopez (DOB 11/09/1990) was made on
March 26th, 2026 at 14:36; the patient agreed to pay and to continue and confirmed no hardship. Benefits.xlsx has
every column filled except Financial_Counseling_Log and BV_Complete; no audit_log.xlsx exists yet.

The patient says he is an attorney at his own law firm. Whether that makes the call an "attorney communication"
(SOP 4.3 / 12.1 legal STOP) is not decided here: if the agent escalates to #compliance with a legal STOP, the
7.3 completion obligations are suspended and the STOP is checked instead; otherwise 7.3 is checked.
"""

from __future__ import annotations

import re

from ..kit import (WRITE_KINDS, Comm, Context, Finding, Rule, World, append_only, blank, comm_rules, no_placeholders,
                   norm, pre_rule, same, state_rule, strict_writes, world)

BENEFITS = r"(^|/)benefits\.xlsx$"
INTAKE = r"(^|/)intake\.xlsx$"
AUDIT = r"(^|/)audit_log\.xlsx$"
FCL_WANT = "03/26/2026 14:36\u2014SUCCESS"
FCL_RX = r"03/26/2026\s*14:36\s*\u2014\s*SUCCESS"
DOB = "11091990"
AUDIT_COLS = ["Date", "Patient_Last_Name", "Patient_First_Name", "Patient_DOB", "Action", "File_Updated",
              "Fields_Updated", "New_Value", "Staff_User", "Result"]
# SOP checkpoints of other sections; none of them happens in this 7.3-only task.
OTHER_CHECKPOINTS = ["Referral Received", "BVS Assigned", "PA Submitted", "PA Approved", "PA Denied",
                     "Visit Note Signed", "Claim Submitted", "Appeal Submitted"]

R_SCRIPT = ("7.3", '"[Patient Name], this is [Your Name] from CareIG', "7.3 Patient Financial Counseling")
R_BVC = ("7.3", "If everything is filled in, then set BV_Complete", "7.3 BV_Complete / BV_PARTIAL")
R_AUDIT73 = ("7.3", "Once all of the above is done, log to audit_log.xlsx", "7.3 audit log")
R_BV71 = ("7.1", "Populate all required fields in benefits.xlsx", "7.1 Benefits Verification")
R_BV71B = ("7.1", "BV_Call_Date, Document every call", "7.1 BV_Complete set last")
R_LOG = ("4.1", "Append one row to audit_log.xlsx", "4.1 Audit Logging")
R_APPEND = ("3", "CareIG Specialty Pharmacy | IVIG Home Infusion Billing SOP | v5.0 | Effective: March 23, 2026 auth.xlsx",
            "3 File System Structure (audit_log.xlsx append-only)")
R_DOB = ("1", "Unless otherwise specified, use MMDDYYYY format", "1 Date of Birth format")
R_LEGAL = ("4.3", "Do not respond to legal threats", "4.3 Prohibited Actions")
R_LEGAL_ESC = ("12.1", "Legal threat or attorney", "12.1 Escalation Paths")
R_STOP = ("4.2", "When a validation condition fails", "4.2 Stop Protocol")


# ---- helpers ---------------------------------------------------------------------------------------

def _writes(a, rx: str) -> bool:
    if a.kind not in WRITE_KINDS:
        return False
    return any(re.search(rx, f, re.I) for f in set(strict_writes(a)) | set(a.files_written))


def _benefits_row(w: World, which: str = "current") -> dict:
    rows = w.rows(BENEFITS, r"^Financial_Counseling_Log$", which)
    return rows[0] if rows else {}


def _cell(row: dict, name: str) -> str:
    return World.col(row, rf"^{name}$")


def _legal_stop_text(text: str) -> bool:
    return bool(re.search(r"LEGAL\s+THREAT", text or "", re.I))


def stop_mode(ctx: Context) -> bool:
    """The agent escalated the case to #compliance as a legal/attorney STOP (SOP 4.3 / 12.1)."""
    w = world(ctx)
    return any(_legal_stop_text(a.text) for a in w.posts_in("compliance"))


def _prior_write_mentions(w: World, rx: str, token: str) -> bool:
    return any(_writes(a, rx) and token in (a.text or "") for a in w.calls(*WRITE_KINDS))


def fcl_done(w: World) -> bool:
    return not blank(_cell(_benefits_row(w), "Financial_Counseling_Log")) or \
        _prior_write_mentions(w, BENEFITS, "Financial_Counseling_Log")


def bvc_done(w: World) -> bool:
    return norm(_cell(_benefits_row(w), "BV_Complete")) == "yes" or _prior_write_mentions(w, BENEFITS, "BV_Complete")


STOP_NOTE = (" (Only if you instead determine that a global STOP applies - SOP 4.3 / 12.1 legal threat or attorney "
             "communication - follow that STOP procedure and leave the case files unchanged.)")


# ---- completion: SOP 7.3 end state ------------------------------------------------------------------

def _fcl_checks(ctx: Context):
    if stop_mode(ctx):
        return []
    got = _cell(_benefits_row(world(ctx)), "Financial_Counseling_Log")
    ok = bool(re.fullmatch(FCL_RX, got.strip()))
    why = "is blank" if blank(got) else f"is \"{got}\""
    return [(ok, f"Benefits.xlsx Financial_Counseling_Log {why}. The call was made 03/26/2026 at 14:36 and the patient "
                 f"said he will pay and to continue, so the value must be exactly \"{FCL_WANT}\" "
                 "([MM/DD/YYYY] [HH:MM]\u2014[Status], em dash, Status SUCCESS).", [R_SCRIPT])]


def _bvc_checks(ctx: Context):
    if stop_mode(ctx):
        return []
    row = _benefits_row(world(ctx))
    got = _cell(row, "BV_Complete")
    empty = [k for k, v in row.items()
             if k not in ("__row__", "BV_Complete", "Financial_Counseling_Log") and blank(v)]
    if empty:
        return [(False, f"Benefits.xlsx has blank columns {empty}; they were filled at the start - restore them "
                        "(every column must be filled before BV_Complete is set).", [R_BVC, R_BV71])]
    return [(got == "YES", f"Benefits.xlsx BV_Complete is \"{got}\". Every other column is filled, so once "
                           "Financial_Counseling_Log is set, set BV_Complete to exactly \"YES\" (set last).",
             [R_BVC, R_BV71B])]


def _audit_rows(w: World) -> tuple[str | None, list[str], list[dict]]:
    path, _ = w.book(AUDIT)
    if not path:
        return None, [], []
    header: list[str] = []
    for row in w.sheet(AUDIT):
        if any(re.fullmatch(r"\s*Action\s*", str(c), re.I) for c in row):
            header = [str(c).strip() for c in row]
            break
    return path, header, w.rows(AUDIT, r"^Action$")


def _audit_checks(ctx: Context):
    if stop_mode(ctx):
        return []
    w = world(ctx)
    want = ("Date=today's date (MM/DD/YYYY) | Patient_Last_Name=Lopez | Patient_First_Name=Kevin | "
            f"Patient_DOB={DOB} | Action=Financial Counseling Complete | File_Updated=benefits.xlsx | "
            "Fields_Updated=Financial_Counseling_Log, BV_Complete | New_Value=" + FCL_WANT + ", YES | "
            "Staff_User=<your name> | Result=SUCCESS")
    path, header, rows = _audit_rows(w)
    if not path:
        return [(False, "No audit_log.xlsx exists and the 7.3 checkpoint row is missing. Create audit_log.xlsx with "
                        f"the Section 4.1 columns ({' | '.join(AUDIT_COLS)}) and append one row: {want}.",
                 [R_AUDIT73, R_LOG])]
    out = []
    missing = [c for c in AUDIT_COLS if c.lower() not in {h.lower() for h in header}]
    if missing:
        out.append((False, f"{path} lacks the Section 4.1 columns {missing}; the header must be "
                           f"{' | '.join(AUDIT_COLS)}.", [R_LOG]))
    fc = [r for r in rows if norm(World.col(r, r"^Action$")) == "financial counseling complete"]
    if not fc:
        out.append((False, f"{path} has no row with Action = \"Financial Counseling Complete\". Append: {want}.",
                    [R_AUDIT73, R_LOG]))
        return out
    if len(fc) > 1:
        out.append((False, f"{path} has {len(fc)} \"Financial Counseling Complete\" rows; log the checkpoint once.",
                    [R_LOG]))
    r = fc[-1]
    probs = []
    if norm(World.col(r, r"^Patient_Last_Name$")) != "lopez":
        probs.append("Patient_Last_Name must be Lopez")
    if norm(World.col(r, r"^Patient_First_Name$")) != "kevin":
        probs.append("Patient_First_Name must be Kevin")
    dob = re.sub(r"\.0$", "", World.col(r, r"^Patient_DOB$"))
    if dob != DOB:
        probs.append(f"Patient_DOB must be {DOB} (MMDDYYYY, got \"{dob}\")")
    if norm(World.col(r, r"^Result$")) != "success":
        probs.append(f"Result must be SUCCESS (got \"{World.col(r, r'^Result$')}\")")
    d = World.col(r, r"^Date$")
    if not re.fullmatch(r"\d{2}/\d{2}/\d{4}|\d{4}-\d{2}-\d{2}( 00:00:00)?", d):
        probs.append(f"Date must be today's date as MM/DD/YYYY (got \"{d}\")")
    if probs:
        out.append((False, f"{path} 'Financial Counseling Complete' row: " + "; ".join(probs) + ".",
                    [R_AUDIT73, R_LOG, R_DOB]))
    return out


def _unrequested_audit(ctx: Context):
    w = world(ctx)
    _, _, rows = _audit_rows(w)
    init = {tuple(v for k, v in r.items() if k != "__row__") for r in w.rows(AUDIT, r"^Action$", "initial")}
    bad = [World.col(r, r"^Action$") for r in rows if tuple(v for k, v in r.items() if k != "__row__") not in init
           and any(norm(World.col(r, r"^Action$")).startswith(norm(c)) for c in OTHER_CHECKPOINTS)]
    return [(not bad, f"audit_log.xlsx has rows for checkpoints this 7.3-only task did not reach: {bad}. Only log "
                      "the checkpoint 7.3 calls for (Action = Financial Counseling Complete).", [R_LOG, R_AUDIT73])]


def _no_hardship(ctx: Context):
    w = world(ctx)
    rows = w.rows(INTAKE, r"^Financial_Hardship$")
    got = World.col(rows[0], r"^Financial_Hardship$") if rows else ""
    return [(norm(got) != "yes", "intake.xlsx Financial_Hardship is YES, but the patient reported no hardship (\"I'll "
                                 "pay for now\" / \"this should not cause a hardship? - Yes, lets continue\"). Leave "
                                 "Financial_Hardship blank.", [R_SCRIPT])]


def _case_files_unchanged(ctx: Context):
    """Only Financial_Counseling_Log / BV_Complete (benefits) and Financial_Hardship (intake) are 7.3 writes."""
    w = world(ctx)
    out = []
    for rx, hdr, keep, name in ((BENEFITS, r"^Financial_Counseling_Log$", {"Financial_Counseling_Log", "BV_Complete"},
                                 "Benefits.xlsx"),
                                (INTAKE, r"^Financial_Hardship$", {"Financial_Hardship"}, "intake.xlsx")):
        init, cur = w.rows(rx, hdr, "initial"), w.rows(rx, hdr)
        if not init:
            continue
        if len(cur) != len(init):
            out.append((False, f"{name} now has {len(cur)} data row(s) instead of {len(init)}; do not add or remove "
                               "rows.", [R_BVC]))
            continue
        changed = [f"{k} (was \"{v}\", now \"{World.col(c, '^' + re.escape(k) + '$')}\")"
                   for i, c in zip(init, cur) for k, v in i.items()
                   if k not in keep and k != "__row__" and not same(World.col(c, "^" + re.escape(k) + "$"), v)]
        out.append((not changed, f"{name} cells outside the Section 7.3 updates were changed: {changed[:6]}. Restore "
                                 "them; 7.3 only sets Financial_Counseling_Log and BV_Complete.", [R_BVC, R_SCRIPT]))
    return out


def _legal_notified(ctx: Context):
    if not stop_mode(ctx):
        return []
    w = world(ctx)
    legal_uids = {u for u, d in w.users.items() if norm(d.get("name")) == "legal" or norm(d.get("handle")) == "legal"}
    ok = any(a.kind in ("email_send",) and any(r in ("legal@careig.com", "legal@company.com") for r in a.recipients + a.cc)
             for a in w.comms()) or any(w.dm_recipients(a) & legal_uids for a in w.comms())
    return [(ok, "You escalated a legal/attorney STOP to #compliance; SOP 12.1 also requires that legal@careig.com be "
                 "notified immediately (email legal@careig.com).", [R_LEGAL_ESC])]


# ---- pre: ordering and STOP hold -------------------------------------------------------------------

def _bvc_before_fcl(ctx: Context, a) -> str | None:
    if not _writes(a, BENEFITS) or "BV_Complete" not in (a.text or "") or "Financial_Counseling_Log" in (a.text or ""):
        return None
    if fcl_done(world(ctx)):
        return None
    return (f"[order] This call sets BV_Complete while Financial_Counseling_Log is still blank. After the call the first "
            f"thing is Financial_Counseling_Log = \"{FCL_WANT}\"; BV_Complete = YES is set last, once every column "
            "is filled.")


def _audit_before_updates(ctx: Context, a) -> str | None:
    if not _writes(a, AUDIT) or "Financial Counseling Complete" not in (a.text or "") or _writes(a, BENEFITS):
        return None
    w = world(ctx)
    todo = [x for x, ok in ((f"Financial_Counseling_Log = \"{FCL_WANT}\"", fcl_done(w)), ("BV_Complete = YES", bvc_done(w)))
            if not ok]
    if not todo or stop_mode(ctx):
        return None
    return ("[order] The 'Financial Counseling Complete' audit row is logged only once all of 7.3 is done; first set "
            f"in Benefits.xlsx: {'; '.join(todo)}.")


def _hold_after_stop(ctx: Context, a) -> str | None:
    if not (_writes(a, BENEFITS) or _writes(a, INTAKE)) or not stop_mode(ctx):
        return None
    return ("[stop] You escalated this case to #compliance as a legal/attorney STOP. SOP 12.1: \"STOP. Do not respond or "
            "modify case files\" - leave Benefits.xlsx and intake.xlsx unchanged while the case is on hold.")


# ---- messages ---------------------------------------------------------------------------------------

def _specs(ctx: Context) -> list[Comm]:
    slack = ("slack_post", "slack_dm")
    return [
        Comm("hardship_post", "slack_post",
             lambda a: a.kind in slack and bool(re.search(r"FINANCIAL\s+HARDSHIP", a.text, re.I)),
             "[FINANCIAL HARDSHIP] post", [R_SCRIPT],
             forbidden="The patient reported no financial hardship (he said he will pay and to continue), so SOP 7.3 "
                       "does not call for a [FINANCIAL HARDSHIP] post."),
        Comm("bv_partial_post", "slack_post", lambda a: a.kind in slack and bool(re.search(r"BV[_ ]PARTIAL", a.text, re.I)),
             "[BV_PARTIAL] post", [R_BVC],
             forbidden="Every Benefits.xlsx column is filled once Financial_Counseling_Log is set, so this is not a "
                       "BV_PARTIAL case; set BV_Complete = YES instead."),
        Comm("legal_stop_post", "slack_post", lambda a: a.kind in slack and _legal_stop_text(a.text),
             "legal/attorney STOP escalation", [R_LEGAL_ESC, R_LEGAL], channel="compliance",
             body=[(r"\[LEGAL THREAT\]", "the SOP 12.1 tag \"[LEGAL THREAT]\" followed by the CASE_ID"),
                   (r"Lopez", "the case (patient Kevin Lopez, CASE_ID Lopez_11091990)")],
             required=False),
    ]


RULES: list[Rule] = [
    *state_rule("f6d19d30.fc.log", _fcl_checks, "Set the cell as stated." + STOP_NOTE),
    *state_rule("f6d19d30.fc.bv_complete", _bvc_checks, "Set the cell as stated." + STOP_NOTE),
    *state_rule("f6d19d30.fc.audit", _audit_checks, "Append/fix the audit_log.xlsx row as stated." + STOP_NOTE),
    *state_rule("f6d19d30.fc.no_hardship", _no_hardship, "Leave intake.xlsx Financial_Hardship blank."),
    *state_rule("f6d19d30.inv.case_files", _case_files_unchanged, "Restore the original values."),
    *state_rule("f6d19d30.inv.audit_checkpoints", _unrequested_audit, "Remove the extra audit rows you added."),
    *append_only("f6d19d30.inv.audit_append_only", AUDIT, r"^Action$", "audit_log.xlsx", [R_APPEND, R_LOG]),
    *state_rule("f6d19d30.stop.legal_notified", _legal_notified, "Notify legal@careig.com."),
    *pre_rule("f6d19d30.fc.bv_complete_last", _bvc_before_fcl, [R_SCRIPT, R_BV71B],
              f"Write Financial_Counseling_Log = \"{FCL_WANT}\" first (or in the same step before BV_Complete)."),
    *pre_rule("f6d19d30.fc.audit_last", _audit_before_updates, [R_AUDIT73],
              "Update Benefits.xlsx first, then append the audit row."),
    *pre_rule("f6d19d30.stop.hold", _hold_after_stop, [R_LEGAL_ESC, R_STOP], "Do not modify the case files."),
    *comm_rules("f6d19d30.comms", _specs),
    *no_placeholders([R_BVC], literal=("[LEGAL THREAT]", "[FINANCIAL HARDSHIP]", "[BV_PARTIAL]", "[COMPLIANCE REPORT]")),
]
