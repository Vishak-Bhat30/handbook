"""Blind unit tests for medical_careig_specialty_pharmacy_d4619b8b (CASE-1001 QA from SOP Section 9 on)."""

import json

from interwhen_sop.tests.base import TaskCase

CLAIM = "claim_CASE-1001.xlsx"
CLIN = "clinical_CASE-1001.xlsx"
AUDIT = "audit_log.xlsx"
SEND = "google_mail__send_email"
POST = "slack__post_message"
CAL = "google_calendar__create_event"
SUBJ = "[CLAIM SUBMISSION] CareIG NPI: 1234567893 | Thompson | MemberID: BCX-998712 | DOS: 2026-03-15"
START = {"dateTime": "2026-04-14T12:00:00-07:00", "timeZone": "America/Los_Angeles"}
END = {"dateTime": "2026-04-14T15:00:00-07:00", "timeZone": "America/Los_Angeles"}
EVENT = {"summary": "IVIG Infusion - Thompson, Michael (CASE-1001)", "start": START, "end": END,
         "description": "Patient: Michael Thompson\nNurse: Jane Smith, RN\nCase: CASE-1001"}

CLAIM_MAIL = {"to": "claims@bluecross-ppo.example.com", "subject": SUBJ,
              "body": "Corrected claim (frequency code 7) for Thompson, DOS 2026-03-15.\n\nAngela Torres",
              "attachments": ["/workdir/claim_2026-03-15.pdf"]}
BILLING_POST = {"channel_id": "C002", "text": "[CLAIM SUBMITTED] CASE-1001 | DOS: 2026-03-15 | Payer: BlueCross "
                                              "Commercial PPO | Billed: $4,153.75"}
SCHED_POST = {"channel_id": "C005", "text": "[SCHEDULED] CASE-1001 | Date: 2026-04-14 | Nurse: Jane Smith"}
NURSE_MAIL = {"to": "j.smith@careig.com", "subject": "[VISIT ASSIGNMENT] CASE-1001 | 2026-04-14",
              "body": "Jane Smith,\n\nDate: 2026-04-14 | Time: 12:00 | Duration: approximately 3 hours\n"
                      "Address: 742 Evergreen Terrace, Beverly Hills, CA 90212\nDrug: Privigen 10%\nDose: 30g\n"
                      "Lot Number: LOT-PV-88421\nNDC: 49281-0396-05\nInfusion Rate: 30 mL/hr\n"
                      "Pre-med Orders: Diphenhydramine 75mg IV\nEmergency Contact: (310) 555-0147\n"
                      "Contraindications: None\n\nAngela Torres"}
PATIENT_MAIL = {"to": "m.thompson@email.com", "subject": "CareIG — IVIG Infusion Appointment | 2026-04-14",
                "body": "Dear Michael,\n\nYour insurance has approved your IVIG infusion.\nDate: 2026-04-14\n"
                        "Time: 12:00 pm\nApproximate Duration: 3 hours\nLocation: Your home address on file\n\n"
                        "Angela Torres"}

FIX_CLAIM = ("r=2\nws.cell(r,col['Drug_Units']).value=59\nws.cell(r,col['Nursing_Units_Addl']).value=2\n"
             "ws.cell(r,col['Premed_Units_1']).value=2\nws.cell(r,col['Claim_Frequency_Code']).value=7\n"
             "ws.cell(r,col['Total_Billed']).value=4153.75\n")
SUBMITTED = ("r=2\nws.cell(r,col['Submission_Date']).value='2026-04-02'\n"
             "ws.cell(r,col['Submission_Ref_Number']).value='15'\nws.cell(r,col['Claim_Status']).value='Submitted'\n")
NEXT_VISIT = ("r=2\nws.cell(r,col['Visit_Date']).value='2026-04-14'\nws.cell(r,col['Visit_Time']).value='12:00'\n"
              "ws.cell(r,col['Nurse_Assigned']).value='Jane Smith'\n")
AUDIT_ROW = ("ws.append(['2026-04-02 10:30','CASE-1001','Claim Submitted','claim_CASE-1001.xlsx',"
             "'Drug_Units, Nursing_Units_Addl, Premed_Units_1, Claim_Frequency_Code, Total_Billed, Submission_Date',"
             "'59, 2, 2, 7, 4153.75, 2026-04-02','Angela Torres','SUCCESS'])\n")


def cal_result(ev: dict) -> str:
    return "[Tool 'google_calendar__create_event' executed.]" + json.dumps({"status": "success", "event": {**ev, "id": "e1"}})


class D4619(TaskCase):
    TASK = "medical_careig_specialty_pharmacy_d4619b8b"

    def golden(self, skip=()):
        if "claim" not in skip:
            self.edit(CLAIM, FIX_CLAIM + SUBMITTED)
        if "clinical" not in skip:
            self.edit(CLIN, NEXT_VISIT)
        if "audit" not in skip:
            self.edit(AUDIT, AUDIT_ROW)
        if "calendar" not in skip:
            self.did(CAL, EVENT, cal_result(EVENT))
        for key, tool, args in (("claim_mail", SEND, CLAIM_MAIL), ("billing", POST, BILLING_POST),
                                ("sched", POST, SCHED_POST), ("nurse", SEND, NURSE_MAIL), ("patient", SEND, PATIENT_MAIL)):
            if key not in skip:
                self.did(tool, args)


class TestInitialAndGolden(D4619):
    def test_initial_obligations(self):
        got = self.done()
        self.assertEqual(set(got), {"claim.lines", "claim.submission", "clinical.next_visit", "calendar.next_visit",
                                    "audit.entries", "comms.messages_sent"})
        msgs = " ".join(p for _, p in self.done_all())
        for frag in ("Drug_Units", "Nursing_Units_Addl", "Premed_Units_1", "Claim_Frequency_Code", "Total_Billed",
                     "Submission_Date", "Visit_Date", "Visit_Time"):
            self.assertIn(frag, msgs)
        self.assertNotIn("Nurse_Assigned", msgs)

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})


class TestClaim(D4619):
    def test_lines_violating(self):
        self.golden()
        self.edit(CLAIM, "ws.cell(2,col['Drug_Units']).value=60\n")
        self.assertIn("Drug_Units", self.done().get("claim.lines", ""))

    def test_lines_premed_wrong(self):
        self.golden()
        self.edit(CLAIM, "ws.cell(2,col['Premed_Units_1']).value=1\n")
        self.assertIn("Premed_Units_1", self.done().get("claim.lines", ""))

    def test_submission_violating(self):
        self.golden()
        self.edit(CLAIM, "ws.cell(2,col['Submission_Date']).value='2026-03-16'\n")
        self.assertIn("claim.submission", self.done())

    def test_submit_before_fix_blocked(self):
        self.assertIn("claim.submit_corrected_first", self.pre(SEND, CLAIM_MAIL))

    def test_submit_after_fix_allowed(self):
        self.edit(CLAIM, FIX_CLAIM)
        self.assertEqual(self.pre(SEND, CLAIM_MAIL), set())

    def test_second_resubmission_blocked(self):
        self.edit(CLAIM, FIX_CLAIM)
        self.did(SEND, CLAIM_MAIL)
        self.assertIn("comms.messages", self.pre(SEND, CLAIM_MAIL))

    def test_claim_mail_wrong_subject_and_attachment(self):
        self.edit(CLAIM, FIX_CLAIM)
        bad = {**CLAIM_MAIL, "subject": "Corrected " + SUBJ, "attachments": ["/workdir/claim_CASE-1001.pdf"]}
        self.assertIn("comms.messages", self.pre(SEND, bad))

    def test_new_row_flagged(self):
        self.golden()
        self.edit(CLAIM, "ws.append([c.value for c in ws[2]])\n")
        self.assertIn("claim.structure", self.done())

    def test_new_claim_file_flagged(self):
        self.golden()
        self.edit(CLAIM, "wb.save(path.replace('claim_CASE-1001', 'claim_CASE-1001_corrected'))\n")
        self.assertIn("claim.structure", self.done())


class TestClinicalCalendar(D4619):
    def test_clinical_wrong_time(self):
        self.golden()
        self.edit(CLIN, "ws.cell(2,col['Visit_Time']).value='09:00'\n")
        self.assertIn("clinical.next_visit", self.done())

    def test_clinical_pm_format_ok(self):
        self.golden()
        self.edit(CLIN, "ws.cell(2,col['Visit_Time']).value='12:00 PM'\n")
        self.assertNotIn("clinical.next_visit", self.done())

    def test_event_ok(self):
        self.assertEqual(self.pre(CAL, EVENT), set())

    def test_event_utc_ok(self):
        ev = {**EVENT, "start": "2026-04-14T19:00:00Z", "end": "2026-04-14T22:00:00Z"}
        self.assertEqual(self.pre(CAL, ev), set())

    def test_event_meta_summary_blocked(self):
        self.assertIn("calendar.event", self.pre(CAL, {**EVENT, "summary": "Create calendar event for Thompson"}))

    def test_event_wrong_time_blocked(self):
        ev = {**EVENT, "start": {"dateTime": "2026-04-13T12:30:00-07:00"}, "end": {"dateTime": "2026-04-13T15:30:00-07:00"}}
        self.assertIn("calendar.event", self.pre(CAL, ev))

    def test_event_wrong_duration_blocked(self):
        self.assertIn("calendar.event", self.pre(CAL, {**EVENT, "end": {"dateTime": "2026-04-14T15:15:00-07:00"}}))

    def test_duplicate_create_blocked(self):
        self.did(CAL, EVENT, cal_result(EVENT))
        self.assertIn("calendar.event", self.pre(CAL, EVENT))

    def test_empty_result_not_counted(self):
        self.did(CAL, EVENT, "")
        self.assertEqual(self.pre(CAL, EVENT), set())
        self.assertIn("calendar.next_visit", self.done())

    def test_other_seed_event_untouchable(self):
        self.assertIn("calendar.event", self.pre("google_calendar__update_event",
                                                 {"eventId": "evt-js-0414", "summary": "x"}))
        self.assertIn("calendar.event", self.pre("google_calendar__delete_event", {"eventId": "evt-1004"}))

    def test_seed_visit_not_moved(self):
        self.assertIn("calendar.event", self.pre("google_calendar__update_event",
                                                 {"eventId": "evt-1001", "start": START, "end": END}))
        self.assertEqual(self.pre("google_calendar__update_event",
                                  {"eventId": "evt-1001", "summary": "IVIG Infusion - Thompson, Michael (CASE-1001)"}),
                         set())

    def test_calendar_completion_wrong_end(self):
        ev = {**EVENT, "end": {"dateTime": "2026-04-14T15:15:00-07:00"}}
        self.golden(skip=("calendar",))
        self.did(CAL, ev, cal_result(ev))
        self.assertIn("calendar.next_visit", self.done())


class TestAuditFiles(D4619):
    def test_audit_missing(self):
        self.golden(skip=("audit",))
        self.assertIn("audit.entries", self.done())

    def test_audit_non_checkpoint_row(self):
        self.golden()
        self.edit(AUDIT, "ws.append(['2026-04-02 10:35','CASE-1001','Visit Scheduled','clinical_CASE-1001.xlsx',"
                         "'Visit_Date','2026-04-14','Angela Torres','SUCCESS'])\n")
        self.assertIn("Visit Scheduled", self.done().get("audit.entries", ""))

    def test_audit_other_case_row(self):
        self.golden()
        self.edit(AUDIT, "ws.append(['2026-04-02 10:35','CASE-1004','Claim Submitted','claim_CASE-1004.xlsx',"
                         "'','','Angela Torres','SUCCESS'])\n")
        self.assertIn("CASE-1004", self.done().get("audit.entries", ""))

    def test_audit_stop_row_allowed(self):
        self.golden()
        self.edit(AUDIT, "ws.append(['2026-04-02 10:35','CASE-1001','Stop Protocol','','','','Angela Torres',"
                         "'STOP — reason'])\n")
        self.assertEqual(self.done(), {})

    def test_audit_append_only(self):
        self.golden()
        self.edit(AUDIT, "ws.cell(2,3).value='Changed'\n")
        self.assertIn("audit.append_only", self.done())

    def test_read_only_files(self):
        code = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/jcodes.xlsx')\nwb.save('/workdir/jcodes.xlsx')"
        self.assertIn("files.read_only", self.pre("syntara__executePython", {"code": code}))
        code2 = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/claim_CASE-1001.xlsx')\nwb.save('/workdir/claim_CASE-1001.xlsx')"
        self.assertNotIn("files.read_only", self.pre("syntara__executePython", {"code": code2}))

    def test_unchanged_files(self):
        self.golden()
        self.edit("auth_CASE-1001.xlsx", "ws.cell(2,4).value='Pending'\n")
        self.assertIn("files.unchanged", self.done())


class TestComms(D4619):
    def test_patient_subject_wrong(self):
        bad = {**PATIENT_MAIL, "subject": "CareIG IVIG Infusion Appointment | 2026-04-14"}
        self.assertIn("comms.messages", self.pre(SEND, bad))
        self.assertEqual(self.pre(SEND, {**PATIENT_MAIL, "subject": "CareIG - IVIG Infusion Appointment | 2026-04-14"}),
                         set())

    def test_patient_time_format(self):
        self.assertIn("comms.messages", self.pre(SEND, {**PATIENT_MAIL, "body": PATIENT_MAIL["body"].replace("12:00 pm", "12:00")}))

    def test_nurse_mail_ok_and_missing_phone(self):
        self.assertEqual(self.pre(SEND, NURSE_MAIL), set())
        bad = {**NURSE_MAIL, "body": NURSE_MAIL["body"].replace("(310) 555-0147", "on file")}
        self.assertIn("comms.messages", self.pre(SEND, bad))

    def test_nurse_mail_wrong_nurse(self):
        self.assertIn("comms.messages", self.pre(SEND, {**NURSE_MAIL, "to": "m.garcia@careig.com"}))

    def test_billing_post_ok_and_wrong_amount(self):
        self.assertEqual(self.pre(POST, BILLING_POST), set())
        bad = {**BILLING_POST, "text": BILLING_POST["text"].replace("4,153.75", "4,340.25")}
        self.assertIn("comms.messages", self.pre(POST, bad))

    def test_billing_post_wrong_channel(self):
        self.assertIn("comms.messages", self.pre(POST, {**BILLING_POST, "channel_id": "C003"}))

    def test_scheduled_post(self):
        self.assertEqual(self.pre(POST, SCHED_POST), set())
        self.assertIn("comms.messages", self.pre(POST, {**SCHED_POST, "text": SCHED_POST["text"].replace("Jane Smith", "Maria Garcia")}))

    def test_other_case_blocked(self):
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C003", "text": "[PA EXPIRED] CASE-1004 needs review"}))

    def test_supply_hold_blocked(self):
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C005", "text": "[SUPPLY HOLD] CASE-1001 — checklist incomplete"}))

    def test_billing_hold_blocked(self):
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C002", "text": "[BILLING HOLD — PA EXPIRED ON DOS] CASE-1001"}))

    def test_signature_required(self):
        self.assertIn("comms.signature", self.pre(SEND, {**PATIENT_MAIL, "body": PATIENT_MAIL["body"].replace("Angela Torres", "Billing")}))

    def test_placeholder_blocked(self):
        self.assertIn("comms.no_placeholders",
                      self.pre(SEND, {**PATIENT_MAIL, "body": PATIENT_MAIL["body"] + "\n[Staff Name]"}))

    def test_missing_messages_listed(self):
        self.golden(skip=("nurse", "patient"))
        msgs = [p for r, p in self.done_all() if r == "comms.messages_sent"]
        self.assertEqual(len(msgs), 2)
