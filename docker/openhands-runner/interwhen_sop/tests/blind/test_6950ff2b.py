"""Blind unit tests for hr_ridgeline_gear_co_6950ff2b (Portia Nzinga FMLA-ineligible -> FAMLI-only intake)."""

from __future__ import annotations

import json
import unittest

from interwhen_sop.tests.base import TaskCase

SEND = "google_mail__send_email"
REPLY = "google_mail__reply_email"
DRAFT = "google_mail__save_draft"
POST = "slack__post_message"
DEN, FAM = "LC-2026-0120", "LC-2026-0121"
WORK, BM, MGR = "p.nzinga@ridgelinegear.com", "r.okafor@ridgelinegear.com", "t.mbeki@ridgelinegear.com"
SIG = "\n\nBest regards,\n\nRidgeline Gear Co. — Leave Coordinator\n\nleaves@ridgelinegear.com"


def t3_body(cid: str = DEN, criterion: str | None = None) -> str:
    crit = criterion or ("Hours: FMLA requires at least 1,250 hours worked in the 12 months immediately preceding the "
                         "leave start date. Your hours worked in that period are 1,018, which is below the threshold.")
    return ("Hi Portia,\n\nThank you for submitting your FMLA leave request. I have reviewed your eligibility against "
            "the federal FMLA criteria and unfortunately must inform you that you are NOT currently eligible for FMLA "
            f"leave for the following reason:\n\n{crit}\n\nAttached is the official Notice of Eligibility (DOL Form "
            "WH-381) reflecting this determination.\n\nEven though you are not eligible for FMLA, you may still be "
            "eligible for leave under Colorado FAMLI, which has different eligibility criteria (no tenure requirement, "
            "no minimum hours requirement). I will follow up separately with any updates regarding your FAMLI case."
            "\n\nIf you believe this FMLA determination is in error, please reply to this email and I will review."
            f"\n\nCase ID: {cid}" + SIG)


def t31_body(cid: str = FAM) -> str:
    return ("Hi Portia,\n\nThank you for reaching out. I have received your leave request and opened a case at "
            f"Ridgeline (Case ID: {cid}).\n\nBased on your current eligibility, your leave will be administered under "
            "Colorado FAMLI. FAMLI claims are filed directly by you with the Colorado Department of Labor and "
            "Employment (CDLE) — Ridgeline does not file on your behalf.\n\nTo file your FAMLI claim, please contact "
            "CDLE directly:\n\n    claims@famli.colorado.gov\n\nPlease note that wage replacement under FAMLI is "
            "paid by the State of Colorado, not by Ridgeline. If you have questions about your pay or benefits, "
            "please contact our Payroll Lead, Teresa Vang, at t.vang@ridgelinegear.com." + SIG)


T3 = {"to": WORK, "cc": BM, "subject": "FMLA Eligibility Notice – Case " + DEN, "body": t3_body(),
      "attachments": [f"/workdir/EMP-1222/WH-381_{DEN}_20260413.pdf"]}
T31 = {"to": WORK, "subject": f"Leave Request Received – {FAM}", "body": t31_body()}
DENIED_POST = {"channel_id": "C001", "text": f"FMLA DENIED (INELIGIBILITY): {DEN}, Hours (1,018 < 1,250)."}

DENIED_ROW = {"Case ID": DEN, "Employee ID": "EMP-1222", "Employee Name": "Portia Nzinga", "Department": "Supply Chain",
              "Leave Type(s)": "FMLA", "Priority": "P3", "Leave Form": "Continuous", "Case Status": "Denied",
              "Start Date": "2026-05-14", "Hours Used To Date": 0, "Manager Name": "Theo Mbeki",
              "Foreseeable / Unforeseeable": "Foreseeable", "Contact Preference": "Personal Email",
              "Notes": "2026-04-13 FMLA denied: non-exempt, 1,018 hours < 1,250 (hours_worked_log.xlsx)."}
FAMLI_ROW = {"Case ID": FAM, "Employee ID": "EMP-1222", "Employee Name": "Portia Nzinga", "Department": "Supply Chain",
             "Leave Type(s)": "FAMLI", "Priority": "P3", "Leave Form": "Continuous", "Case Status": "Intake",
             "Start Date": "2026-05-14", "Hours Used To Date": 0, "Manager Name": "Theo Mbeki",
             "Foreseeable / Unforeseeable": "Foreseeable", "Contact Preference": "Personal Email",
             "Supporting Documentation": "None",
             "Notes": "2026-04-13 FAMLI-only intake; employee files with CDLE. Template 31 sent."}
LOG_ROW = {"Case ID (Ridgeline)": FAM, "Employee ID": "EMP-1222", "Employee Name": "Portia Nzinga",
           "Claim Start Date": "2026-05-14", "Claimed Reason Category": "Employee own serious health condition",
           "Claim Status": "Pending - Employee to file with CDLE", "Concurrent FMLA? (Y/N)": "No"}


class Base(TaskCase):
    TASK = "hr_ridgeline_gear_co_6950ff2b"

    def add_case(self, **row):
        self.edit("leave_tracker.xlsx", f"d={row!r}\nr=[None]*len(hdr)\nfor k,v in d.items(): r[col[k]-1]=v\n"
                                        "ws.append(r)", sheet="Active Cases")

    def add_log(self, **row):
        self.edit("famli_coordination_log.xlsx",
                  f"d={row!r}\nh=[c.value for c in ws[4]]\nr=[None]*len(h)\n"
                  "for k,v in d.items(): r[h.index(k)]=v\nws.append(r)")

    def golden(self, skip: tuple = ()):
        if "den" not in skip:
            self.add_case(**DENIED_ROW)
        if "fam" not in skip:
            self.add_case(**FAMLI_ROW)
        if "log" not in skip:
            self.add_log(**LOG_ROW)
        if "wh381" not in skip:
            self.write(f"EMP-1222/WH-381_{DEN}_20260413.pdf", b"%PDF-1.4 filled WH-381")
        if "t3" not in skip:
            self.did(SEND, T3)
        if "t31" not in skip:
            self.did(SEND, T31)
        if "post" not in skip:
            self.did(POST, DENIED_POST)
        if "read" not in skip:
            self.did("google_mail__mark_emails", {"email_ids": ["106"], "is_read": True})
        if "move" not in skip:
            self.did("google_mail__move_emails", {"email_ids": ["106"], "target_folder": "FAMLI Cases"})


class TestGoldenAndInitial(Base):
    def test_golden_path_is_clean(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_path_calls_are_not_blocked(self):
        self.golden(skip=("t3", "t31", "post", "read", "move"))
        self.assertEqual(self.pre(SEND, T3), set())
        self.assertEqual(self.pre(SEND, T31), set())
        self.assertEqual(self.pre(POST, DENIED_POST), set())
        self.assertEqual(self.pre("google_mail__move_emails", {"email_ids": ["106"], "target_folder": "FAMLI Cases"}),
                         set())
        self.assertEqual(self.pre("syntara__executeBash", {
            "command": f"mkdir -p /workdir/EMP-1222 && cp /workdir/WH-381.pdf /workdir/EMP-1222/WH-381_{DEN}_20260413.pdf"}),
            set())

    def test_initial_state_lists_outstanding_obligations(self):
        got = self.done_all()
        rules = sorted({r for r, _ in got})
        self.assertEqual(rules, ["famli.messages_sent", "famli_log.row", "files.wh381_saved", "mail.housekeeping",
                                 "tracker.famli_row", "tracker.fmla_denied_row"])
        self.assertEqual(len(got), 9)


class TestMessages(Base):
    def test_t3_requires_bm_cc(self):
        self.assertIn("famli.messages", self.pre(SEND, {**T3, "cc": ""}))
        self.assertIn("famli.messages", self.pre(REPLY, {"email_id": "106", "body": t3_body()}))

    def test_t3_wrong_criterion_and_case_id(self):
        self.add_case(**DENIED_ROW)
        self.add_case(**FAMLI_ROW)
        self.assertIn("famli.messages", self.pre(SEND, {**T3, "body": t3_body(cid=FAM)}))
        self.assertIn("famli.messages", self.pre(SEND, {**T3, "body": t3_body(cid="LC-2026-0112")}))
        tenure = "Tenure: FMLA requires at least 12 months of employment. Hours 1,018 vs 1,250."
        self.assertIn("famli.messages", self.pre(SEND, {**T3, "body": t3_body(criterion=tenure)}))
        self.assertNotIn("famli.messages", self.pre(SEND, T3))

    def test_t3_draft_does_not_count(self):
        self.golden(skip=("t3",))
        self.did(DRAFT, T3)
        self.assertIn("Template 3", self.done().get("famli.messages_sent", ""))

    def test_t3_not_resent(self):
        self.did(SEND, T3)
        self.assertIn("famli.messages", self.pre(SEND, T3))

    def test_t31_subject_and_attachment(self):
        self.add_case(**DENIED_ROW)
        self.add_case(**FAMLI_ROW)
        self.assertNotIn("famli.messages", self.pre(SEND, T31))
        self.assertIn("famli.messages", self.pre(SEND, {**T31, "subject": "Your leave request"}))
        self.assertIn("famli.messages", self.pre(SEND, {**T31, "attachments": [f"EMP-1222/WH-381_{DEN}_20260413.pdf"]}))
        self.assertIn("famli.messages", self.pre(SEND, {**T31, "subject": f"Leave Request Received – {DEN}",
                                                         "body": t31_body(DEN)}))

    def test_t31_missing_is_reported(self):
        self.golden(skip=("t31",))
        self.assertIn("Template 31", self.done().get("famli.messages_sent", ""))

    def test_denied_post_format_and_channel(self):
        self.assertNotIn("famli.messages", self.pre(POST, DENIED_POST))
        self.assertIn("famli.messages", self.pre(POST, {**DENIED_POST, "channel_id": "C002"}))
        self.assertIn("famli.messages", self.pre(POST, {"channel_id": "C001", "text": f"FMLA DENIED: {DEN}, tenure"}))
        self.assertIn("famli.messages", self.pre(POST, {"channel_id": "C001",
                                                         "text": f"FMLA DENIED (INELIGIBILITY): {DEN}, Tenure"}))
        self.assertNotIn("famli.messages", self.pre(POST, {"channel_id": "C002", "text": "Weekly FMLA summary"}))

    def test_eligibility_notice_forbidden(self):
        body = "Hi Portia,\n\nI have reviewed your eligibility and confirmed that you ARE eligible for FMLA leave."
        self.assertIn("famli.messages", self.pre(SEND, {"to": WORK, "subject": "FMLA", "body": body}))
        self.assertIn("famli.messages", self.pre(SEND, {"to": WORK, "subject": "Certification", "body": "Hi Portia,",
                                                         "attachments": ["/workdir/WH-380-E.pdf"]}))

    def test_famli_denial_forbidden(self):
        body = "Hi Portia, unfortunately you are not eligible for Colorado FAMLI either."
        self.assertIn("famli.messages", self.pre(SEND, {"to": WORK, "subject": "FAMLI", "body": body}))

    def test_placeholders(self):
        self.assertIn("comms.no_placeholders", self.pre(SEND, {**T3, "body": t3_body(cid="[Case ID]")}))
        self.assertNotIn("comms.no_placeholders", self.pre(SEND, T3))


class TestConfidentiality(Base):
    def test_medical_detail_blocked(self):
        self.assertIn("conf.content", self.pre(SEND, {**T31, "body": t31_body() + "\nGood luck with the kidney "
                                                                                    "surgery."}))
        self.assertIn("conf.content", self.pre(POST, {"channel_id": "C001", "text": "Portia Nzinga - surgery 5/14"}))
        self.assertNotIn("conf.content", self.pre(SEND, T31))

    def test_manager_reason(self):
        bad = {"to": MGR, "subject": "Leave notice", "body": "Portia Nzinga will be on medical leave from 2026-05-14."}
        ok = {"to": MGR, "subject": "Leave notice", "body": "Portia Nzinga will be on approved leave from 2026-05-14."}
        self.assertIn("conf.content", self.pre(SEND, bad))
        self.assertNotIn("conf.content", self.pre(SEND, ok))

    def test_wage_and_benefits(self):
        wage = t31_body() + "\nFAMLI wage replacement is about 90% of your weekly wages."
        ok = t31_body() + "\nFAMLI requires $2,500 in wages in the base period."
        ben = t31_body() + "\nYour health insurance will continue during leave."
        route = t31_body() + "\nQuestions about health insurance premiums will be answered by Teresa Vang."
        self.assertIn("conf.content", self.pre(SEND, {**T31, "body": wage}))
        self.assertNotIn("conf.content", self.pre(SEND, {**T31, "body": ok}))
        self.assertIn("conf.content", self.pre(SEND, {**T31, "body": ben}))
        self.assertNotIn("conf.content", self.pre(SEND, {**T31, "body": route}))

    def test_payroll_and_tags(self):
        self.add_case(**FAMLI_ROW)
        self.assertIn("conf.content", self.pre(POST, {"channel_id": "C004", "text": f"LEAVE PAYROLL NOTIFICATION: {FAM},"
                                                       " Leave start, 2026-05-14, Continuous, serious health condition"}))
        self.assertNotIn("conf.content", self.pre(POST, {"channel_id": "C004", "text": f"LEAVE PAYROLL NOTIFICATION: "
                                                          f"{FAM}, Leave start, 2026-05-14, Continuous, FAMLI-only"}))
        self.assertIn("conf.content", self.pre(POST, {"channel_id": "C001", "text": f"{DEN} Portia update <@U017>"}))

    def test_recipients(self):
        self.assertIn("conf.recipients", self.pre("slack__send_dm", {"user_id": "U020", "text": "Hi Portia, case open"}))
        self.assertIn("conf.recipients", self.pre(SEND, {"to": "j.baptiste@ridgelinegear.com", "subject": "Portia",
                                                         "body": "Portia Nzinga will be out from May 14."}))
        self.assertIn("conf.recipients", self.pre(SEND, {**T31, "cc": MGR}))
        self.assertNotIn("conf.recipients", self.pre(SEND, {"to": "hrdirector@ridgelinegear.com", "subject": "Summary",
                                                            "body": "Portia Nzinga intake processed."}))
        self.assertNotIn("conf.recipients", self.pre(SEND, {"to": "j.baptiste@ridgelinegear.com", "subject": "Hi",
                                                            "body": "All-hands moved to Thursday."}))

    def test_no_cdle_filing(self):
        body = "Filing a FAMLI claim for Portia Nzinga (EMP-1222), leave from 2026-05-14."
        self.assertIn("famli.no_cdle_filing", self.pre(SEND, {"to": "claims@famli.colorado.gov", "subject": "Claim",
                                                              "body": body}))
        self.assertNotIn("famli.no_cdle_filing", self.pre(SEND, T31))


class TestFilesAndMail(Base):
    def test_protected_files(self):
        self.assertIn("files.protected", self.pre("syntara__executeBash", {"command": "rm /workdir/WH-381.pdf"}))
        self.assertIn("files.protected", self.pre("syntara__writeFile", {"file_path": "/workdir/templates.json",
                                                                          "content": "{}"}))
        self.assertNotIn("files.protected", self.pre("syntara__executePython", {
            "code": "import os\nos.remove('/tmp/t.pdf')\nprint(open('/workdir/WH-381.pdf','rb').read(4))"}))

    def test_mail_folders(self):
        self.assertIn("mail.folders", self.pre("google_mail__move_emails", {"email_ids": ["106"],
                                                                             "target_folder": "FAMLI"}))
        self.assertIn("mail.folders", self.pre("google_mail__mark_emails", {"email_ids": ["106"],
                                                                             "is_important": True}))
        self.assertEqual(self.pre("google_mail__mark_emails", {"email_ids": ["106"], "is_read": True}), set())

    def test_housekeeping(self):
        self.golden(skip=("move",))
        self.did("google_mail__move_emails", {"email_ids": ["106"], "target_folder": "FMLA Cases"})
        self.assertIn("FAMLI Cases", self.done().get("mail.housekeeping", ""))

    def test_housekeeping_unread(self):
        self.golden(skip=("read",))
        self.assertIn("unread", self.done().get("mail.housekeeping", ""))

    def test_wh381(self):
        self.golden(skip=("wh381",))
        self.assertIn("files.wh381_saved", self.done())
        self.write(f"EMP-1222/WH-381_{FAM}_20260413.pdf", b"%PDF")
        self.assertIn(DEN, self.done().get("files.wh381_saved", ""))

    def test_unchanged_files(self):
        self.golden()
        self.edit("hfwa_balance_tracker.xlsx", "ws.cell(row=5, column=6).value = 99")
        self.assertIn("hfwa_balance_tracker", self.done().get("files.unchanged", ""))


class TestRecords(Base):
    def test_denied_row(self):
        self.golden(skip=("den",))
        self.assertIn("Denied", self.done().get("tracker.fmla_denied_row", ""))

    def test_denied_row_notes(self):
        self.golden(skip=("den",))
        self.add_case(**{**DENIED_ROW, "Notes": "Denied.", "Case Status": "Closed - Denied"})
        self.assertIn("Notes", self.done().get("tracker.fmla_denied_row", ""))

    def test_famli_row_missing(self):
        self.golden(skip=("fam",))
        self.assertIn("FAMLI-only", self.done().get("tracker.famli_row", ""))

    def test_famli_row_fields(self):
        self.golden(skip=("fam",))
        self.add_case(**{**FAMLI_ROW, "Leave Type(s)": "FMLA + FAMLI", "Priority": "P2"})
        probs = [p for r, p in self.done_all() if r == "tracker.famli_row"]
        self.assertTrue(any("exactly \"FAMLI\"" in p for p in probs))
        self.assertTrue(any("P3" in p for p in probs))

    def test_case_ids(self):
        self.golden(skip=("den", "t3", "post"))
        self.add_case(**{**DENIED_ROW, "Case ID": "LC-2026-0112"})
        self.assertIn("already in use", self.done().get("tracker.case_ids", ""))

    def test_no_medical_in_records(self):
        self.golden(skip=("fam",))
        self.add_case(**{**FAMLI_ROW, "Notes": "Kidney surgery 5/14."})
        self.assertIn("records.no_medical", self.done())

    def test_tracker_append_only(self):
        self.golden()
        self.edit("leave_tracker.xlsx", "ws.cell(row=2, column=8).value = 'Closed - Returned'", sheet="Active Cases")
        self.assertIn("tracker.append_only", self.done())

    def test_absence_log_append_only(self):
        self.golden()
        self.edit("leave_tracker.xlsx", "ws.cell(row=2, column=5).value = 4", sheet="Absence Log")
        self.assertIn("tracker.absence_log_append_only", self.done())

    def test_famli_log_fields(self):
        self.golden(skip=("log",))
        self.add_log(**{**LOG_ROW, "Concurrent FMLA? (Y/N)": "Yes", "FAMLI Claim ID (CDLE)": "FAMLI-CO-2026-12345"})
        probs = [p for r, p in self.done_all() if r == "famli_log.row"]
        self.assertTrue(any("Concurrent" in p for p in probs))
        self.assertTrue(any("not issued by CDLE" in p for p in probs))

    def test_famli_log_missing_and_append_only(self):
        self.golden(skip=("log",))
        self.assertIn("famli_log.row", self.done())
        self.add_log(**LOG_ROW)
        self.edit("famli_coordination_log.xlsx", "ws.cell(row=5, column=8).value = 'Closed'")
        self.assertIn("famli_log.append_only", self.done())


if __name__ == "__main__":
    unittest.main()
