"""Blind unit tests for medical_pathfinder_billing_and_coding_ec505b6b (seed data only)."""

from __future__ import annotations

import json

from interwhen_sop.tests.base import TaskCase

SEND = "google_mail__send_email"
CAL = "google_calendar__create_event"
PY = "syntara__executePython"

APPEAL = {
    "to": "appeals@aetna-sim.com",
    "subject": "Appeal \u2014 CLM-2026-00001 \u2014 Medical Necessity",
    "body": ("To the Appeals Department,\n\nPlease find attached a formal appeal for the above-referenced claim, denied "
             "under reason code CO-50.\n\nClaim ID: CLM-2026-00001\nDate of Service: 2026-03-18\n\nAttached:\n"
             "1. Letter of Medical Necessity\n2. Clinical chart notes for the date of service\n\nWe respectfully "
             "request reconsideration and reprocessing of this claim.\n\nThank you,\nNatalie Simmons\nPathfinder "
             "Billing and Coding\n\nClaim ID: CLM-2026-00001\nPatient ID: PAT-10342\nDOS: 2026-03-18\n"
             "CPT Code(s): 99214\nPayer: Aetna\nClaim Status: Denied"),
    "attachments": ["/workdir/LMN_CLM-2026-00001.txt", "/workdir/ChartNotes_PAT-10342_2026-03-18.txt"],
}
FOLLOWUP = {
    "to": "catherine.lawson@pathfinder.med",
    "subject": "HIGH PRIORITY - Escalation Follow-Up - ESC-00001",
    "body": ("Hi Catherine,\n\nThis is a follow-up regarding ESC-00001, which was escalated to you on 2026-04-08 at "
             "13:31. I have not yet received email confirmation that this escalation is active. Please reply to "
             "confirm receipt and acknowledge the escalation at your earliest convenience.\n\nThank you,\nNatalie"),
}
TFL = {"summary": "TFL - CLM-2026-00022", "start": {"date": "2026-09-19"}, "end": {"date": "2026-09-20"},
       "description": "Timely Filing Limit for CLM-2026-00022. Payer: Blue Cross Blue Shield (180 days). DOS: 2026-03-23."}
CORR_ROW = ("ws.append(['CLM-2026-00022','PAT-10587','PRV-2081','Blue Cross Blue Shield','99213-25','L82.1',"
            "'2026-03-23',None,225,0,0,0,'New',None,7,None,None,'CLM-2026-00003'])")


def set_cell(key_col: str, key: str, column: str, value) -> str:
    return (f"for r in range(2, ws.max_row+1):\n"
            f"    if ws.cell(r, col[{key_col!r}]).value == {key!r}:\n"
            f"        ws.cell(r, col[{column!r}]).value = {value!r}\n")


class Base(TaskCase):
    TASK = "medical_pathfinder_billing_and_coding_ec505b6b"

    def queue(self, sev=True, closed=True):
        code = ""
        for q in ("QUE-00005", "QUE-00006", "QUE-00007"):
            if sev:
                code += set_cell("Queue_ID", q, "Severity_Level", "Level 3: Medium")
            if closed and q != "QUE-00007":
                code += set_cell("Queue_ID", q, "Status", "Closed")
        self.edit("PBC_RA_Queue.xlsx", code)

    def register(self, corr=CORR_ROW):
        self.edit("PBC_Claim_Register.xlsx",
                  set_cell("Claim_ID", "CLM-2026-00001", "Claim_Status", "In Recovery")
                  + set_cell("Claim_ID", "CLM-2026-00003", "Claim_Status", "Resubmitted") + (corr or ""))

    def worklist(self):
        self.edit("PBC_Denial_Worklist.xlsx",
                  set_cell("Denial_ID", "DNL-00006", "Recovery_Action", "Appeal - Medical Necessity")
                  + set_cell("Denial_ID", "DNL-00006", "Recovery_Status", "Appealed")
                  + set_cell("Denial_ID", "DNL-00005", "Recovery_Action", "Add Modifier and Resubmit")
                  + set_cell("Denial_ID", "DNL-00005", "Recovery_Status", "Resubmitted"))

    def golden(self):
        self.did(SEND, APPEAL)
        self.did(SEND, FOLLOWUP)
        self.did(CAL, TFL, '{"status": "created"}')
        self.queue()
        self.register()
        self.worklist()


class InitialState(Base):
    def test_outstanding_obligations(self):
        got = set(self.done())
        self.assertEqual(got, {"comms.messages_sent", "ra_queue.severity", "ra_queue.status", "register.co50_status",
                               "register.modifier_resubmission", "worklist.co50", "worklist.modifier",
                               "calendar.tfl_corrected_claim"})

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})


class Appeal(Base):
    def test_compliant(self):
        self.assertEqual(self.pre(SEND, APPEAL), set())
        self.did(SEND, APPEAL)
        self.assertNotIn("Aetna Appeals", json.dumps(self.done_all()))

    def test_wrong_department(self):
        self.assertIn("comms.messages", self.pre(SEND, {**APPEAL, "to": "claims@aetna-sim.com"}))

    def test_missing_chart_notes(self):
        self.assertIn("comms.messages", self.pre(SEND, {**APPEAL, "attachments": ["/workdir/LMN_CLM-2026-00001.txt"]}))

    def test_wrong_subject(self):
        self.assertIn("comms.messages", self.pre(SEND, {**APPEAL, "subject": "Appeal for CLM-2026-00001"}))

    def test_missing_claim_fields(self):
        body = APPEAL["body"].replace("Patient ID: PAT-10342\n", "")
        self.assertIn("comms.messages", self.pre(SEND, {**APPEAL, "body": body}))


class FollowUp(Base):
    def test_compliant(self):
        self.assertEqual(self.pre(SEND, FOLLOWUP), set())
        self.did(SEND, FOLLOWUP)
        self.assertNotIn("ESC-00001", json.dumps(self.done_all()))

    def test_wrong_subject(self):
        self.assertIn("comms.messages", self.pre(SEND, {**FOLLOWUP, "subject": "Follow-up on ESC-00001"}))

    def test_wrong_time(self):
        body = FOLLOWUP["body"].replace("13:31", "15:43")
        self.assertIn("comms.messages", self.pre(SEND, {**FOLLOWUP, "body": body}))


class Redundant(Base):
    SIGNOFF = {"to": "catherine.lawson@pathfinder.med", "subject": "LMN sign-off request - CLM-2026-00001",
               "body": "Hi Catherine, please review and approve the LMN for CLM-2026-00001."}
    MODQ = {"to": "david.nguyen@pathfinder.med", "subject": "Modifier Verification Request - CLM-2026-00003",
            "body": "Hi David, please confirm whether Modifier 25 is supported for CLM-2026-00003."}
    NOTES = {"to": "david.nguyen@pathfinder.med", "subject": "Chart notes - CLM-2026-00001",
             "body": "Hi David, could you send the chart notes for CLM-2026-00001?"}

    def test_signoff_blocked_before_appeal(self):
        self.assertIn("comms.messages", self.pre(SEND, self.SIGNOFF))

    def test_signoff_not_blocked_after_appeal(self):
        self.did(SEND, APPEAL)
        self.assertEqual(self.pre(SEND, self.SIGNOFF), set())

    def test_modifier_query_blocked(self):
        self.assertIn("comms.messages", self.pre(SEND, self.MODQ))

    def test_modifier_query_not_blocked_after_correction(self):
        self.register()
        self.assertEqual(self.pre(SEND, self.MODQ), set())

    def test_notes_request_blocked(self):
        self.assertIn("comms.messages", self.pre(SEND, self.NOTES))

    def test_unrelated_internal_mail_allowed(self):
        msg = {"to": "marcus.thompson@pathfinder.med", "subject": "Follow-up: Patient Contact Needed - CLM-2026-00004",
               "body": "Hi Marcus, checking whether you reached the patient for CLM-2026-00004. Thanks, Natalie"}
        self.assertEqual(self.pre(SEND, msg), set())

    def test_placeholder_blocked(self):
        msg = {"to": "marcus.thompson@pathfinder.med", "subject": "Update", "body": "Hi [First Name], update."}
        self.assertIn("comms.no_placeholders", self.pre(SEND, msg))


class Queue(Base):
    def test_severity_and_status_ok(self):
        self.queue()
        d = self.done()
        self.assertNotIn("ra_queue.severity", d)
        self.assertNotIn("ra_queue.status", d)
        self.assertNotIn("ra_queue.unchanged", d)

    def test_wrong_severity(self):
        self.edit("PBC_RA_Queue.xlsx", set_cell("Queue_ID", "QUE-00005", "Severity_Level", "Level 2: High"))
        self.assertTrue(any(r == "ra_queue.severity" and "QUE-00005" in p for r, p in self.done_all()))

    def test_co27_item_closed(self):
        self.edit("PBC_RA_Queue.xlsx", set_cell("Queue_ID", "QUE-00007", "Status", "Closed"))
        self.assertIn("co27.await_pfr", self.done())

    def test_closed_row_edited(self):
        self.edit("PBC_RA_Queue.xlsx", set_cell("Queue_ID", "QUE-00001", "Status", "In Progress"))
        self.assertIn("ra_queue.unchanged", self.done())

    def test_new_row(self):
        self.edit("PBC_RA_Queue.xlsx", "ws.append(['QUE-00008','2026-04-08','CLM-2026-00004','Level 3: Medium','New'])")
        self.assertIn("ra_queue.unchanged", self.done())


class Register(Base):
    def test_correct(self):
        self.register()
        d = self.done()
        for r in ("register.co50_status", "register.modifier_resubmission", "register.unchanged", "co27.await_pfr"):
            self.assertNotIn(r, d)

    def test_wrong_cpt(self):
        self.register(CORR_ROW.replace("'99213-25'", "'99213'"))
        self.assertIn("CPT_Code", self.done()["register.modifier_resubmission"])

    def test_submitted_date_filled(self):
        self.register(CORR_ROW.replace("'2026-03-23',None", "'2026-03-23','2026-04-08'"))
        self.assertIn("Date_Submitted", self.done()["register.modifier_resubmission"])

    def test_wrong_id(self):
        self.register(CORR_ROW.replace("CLM-2026-00022", "CLM-2026-00023"))
        self.assertIn("Claim_ID", self.done()["register.modifier_resubmission"])

    def test_other_row_edited(self):
        self.edit("PBC_Claim_Register.xlsx", set_cell("Claim_ID", "CLM-2026-00019", "Paid_Amount", 0))
        self.assertIn("register.unchanged", self.done())

    def test_co27_corrected_claim(self):
        self.edit("PBC_Claim_Register.xlsx",
                  "ws.append(['CLM-2026-00022','PAT-10891','PRV-3044','UnitedHealthcare','99203','J06.9','2026-03-25',"
                  "None,275,0,0,275,'New',None,7,None,None,'CLM-2026-00004'])")
        self.assertIn("co27.await_pfr", self.done())

    def test_co27_original_changed(self):
        self.edit("PBC_Claim_Register.xlsx", set_cell("Claim_ID", "CLM-2026-00004", "Claim_Status", "Resubmitted"))
        self.assertIn("co27.await_pfr", self.done())


class Worklist(Base):
    def test_correct(self):
        self.worklist()
        d = self.done()
        for r in ("worklist.co50", "worklist.modifier", "worklist.unchanged", "co27.await_pfr"):
            self.assertNotIn(r, d)

    def test_co50_escalated_instead_of_appealed(self):
        self.edit("PBC_Denial_Worklist.xlsx", set_cell("Denial_ID", "DNL-00006", "Recovery_Status", "Escalated"))
        self.assertIn("Appealed", self.done()["worklist.co50"])

    def test_co27_resolved_early(self):
        self.edit("PBC_Denial_Worklist.xlsx", set_cell("Denial_ID", "DNL-00007", "Recovery_Action", "Correct and Resubmit"))
        self.assertIn("co27.await_pfr", self.done())

    def test_co27_allowed_after_pfr_reply(self):
        reply = {"emails": [{"email_id": "9", "from_addr": "marcus.thompson@pathfinder.med",
                             "to_addr": "natalie.simmons@pathfinder.med",
                             "subject": "Re: Patient Contact Needed \u2014 CLM-2026-00004",
                             "body_text": "Reached the patient; payment plan set up.", "folder": "INBOX"}]}
        self.did("google_mail__get_emails", {}, json.dumps(reply))
        self.edit("PBC_Denial_Worklist.xlsx", set_cell("Denial_ID", "DNL-00007", "Recovery_Status", "Resolved"))
        self.assertNotIn("co27.await_pfr", self.done())

    def test_other_row_edited(self):
        self.edit("PBC_Denial_Worklist.xlsx", set_cell("Denial_ID", "DNL-00001", "Recovery_Status", "Resolved"))
        self.assertIn("worklist.unchanged", self.done())


class EscalationLog(Base):
    def test_duplicate_pattern_row(self):
        self.edit("PBC_Escalation_Log.xlsx", "ws.append(['ESC-00002','RA','RCM','Financial','Pattern Recurrence'])")
        self.assertIn("escalation_log.no_new_rows", self.done())

    def test_existing_row_edited(self):
        self.edit("PBC_Escalation_Log.xlsx", set_cell("Escalation_ID", "ESC-00001", "Escalation_Category", "Operational"))
        self.assertIn("escalation_log.append_only", self.done())

    def test_untouched(self):
        d = self.done()
        self.assertNotIn("escalation_log.no_new_rows", d)
        self.assertNotIn("escalation_log.append_only", d)


class Calendar(Base):
    def test_tfl_ok(self):
        self.register()
        self.assertEqual(self.pre(CAL, TFL), set())
        self.did(CAL, TFL, '{"status": "created"}')
        self.assertNotIn("calendar.tfl_corrected_claim", self.done())

    def test_tfl_wrong_date(self):
        bad = {**TFL, "start": {"date": "2026-10-05"}, "end": {"date": "2026-10-06"}}
        self.assertIn("calendar.tfl_date", self.pre(CAL, bad))
        self.register()
        self.did(CAL, bad, '{"status": "created"}')
        self.assertIn("calendar.tfl_corrected_claim", self.done())

    def test_unrelated_event_allowed(self):
        ev = {"summary": "ESC-00001", "start": {"dateTime": "2026-04-08T15:43:00-04:00"},
              "end": {"dateTime": "2026-04-08T15:44:00-04:00"}}
        self.assertEqual(self.pre(CAL, ev), set())


class ReferenceData(Base):
    def test_eligibility_changed(self):
        self.edit("PBC_Eligibility_Responses.xlsx", "ws.cell(2, 4).value = '2026-12-31'")
        self.assertIn("files.reference_unchanged", self.done())

    def test_untouched(self):
        self.assertNotIn("files.reference_unchanged", self.done())
