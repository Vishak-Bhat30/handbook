"""Blind unit tests for medical_pathfinder_billing_and_coding_a70deabc (fixtures from the task seed only)."""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase

POST = "slack__post_message"
CAL = "google_calendar__create_event"
ESC48 = "RCM Manager - Claim ID: CLM-2026-0048; Reason: Payer Dispute; Escalation Category: Operational"
ESC49 = "RCM Manager - Claim ID: CLM-2026-0049; Reason: Payer Dispute; Escalation Category: Operational"
SPECIAL49 = "James W. - CLM-2026-0049 special action authorized"


def cal(summary, start="2026-02-16T15:20:00-06:00", end="2026-02-16T15:21:00-06:00"):
    return {"summary": summary, "start": {"dateTime": start}, "end": {"dateTime": end}}


def setter(key_col, updates):
    """openpyxl snippet: for rows whose key_col value is in updates, set {header: value}."""
    return (f"upd={updates!r}\n"
            f"for r in range(2, ws.max_row+1):\n"
            f"    k=ws.cell(r, col[{key_col!r}]).value\n"
            f"    if k in upd:\n"
            f"        for h,v in upd[k].items(): ws.cell(r, col[h]).value=v\n")


class A70(TaskCase):
    TASK = "medical_pathfinder_billing_and_coding_a70deabc"

    def golden_workbooks(self, billed47=175.25):
        self.edit("PBC_RA_Queue.xlsx", setter("Queue_ID", {
            "Q-2026-001": {"Priority_Level": "Level 4: Low", "Status": "Complete"},
            "Q-2026-002": {"Priority_Level": "Level 2: High", "Status": "In Progress"},
            "Q-2026-003": {"Priority_Level": "Level 2: High", "Status": "Complete"}}))
        self.edit("PBC_Claim_Register.xlsx", setter("Claim_ID", {
            "CLM-2026-0047": {"Billed_Amount": billed47, "Adjustment_Amount": 0, "Claim_Status": "Written Off"},
            "CLM-2026-0048": {"Claim_Status": "In Recovery"},
            "CLM-2026-0049": {"Claim_Status": "Written Off - RA Approved"}}))
        self.edit("PBC_Denial_Worklist.xlsx", setter("Denial_ID", {
            "DNL-2026-001": {"Recovery_Action": "Write Off", "Recovery_Status": "Written Off"},
            "DNL-2026-002": {"Recovery_Action": "Appeal - Contractual Rate Dispute", "Recovery_Status": "Escalated"},
            "DNL-2026-003": {"Recovery_Action": "Write Off", "Recovery_Status": "Written Off"}}))

    def golden_comms(self):
        self.did(POST, {"channel_id": "C002", "text": ESC48})
        self.did(POST, {"channel_id": "C001", "text": SPECIAL49})
        self.did(CAL, cal(ESC48))

    # ---- derivation / initial state ----
    def test_plan(self):
        from interwhen_sop import framework, sopdata, state
        from interwhen_sop.verifiers import medical_pathfinder_billing_and_coding_a70deabc as m
        ctx = framework.Context(sopdata.load(), state.build([]), [])
        p = m.plan(ctx)
        self.assertEqual({k: v["path"] for k, v in p.items()},
                         {"CLM-2026-0047": "sbwo", "CLM-2026-0048": "dispute", "CLM-2026-0049": "ra_writeoff"})
        self.assertEqual([p[c]["days"] for c in sorted(p)], [58, 32, 22])
        self.assertEqual([p[c]["severity"] for c in sorted(p)], ["Level 4: Low", "Level 2: High", "Level 2: High"])
        self.assertEqual(m.actor_tag(ctx), "James W.")

    def test_initial_findings(self):
        self.assertEqual(set(self.done()), {"queue.open_items", "register.co45_outcome", "worklist.co45_outcome",
                                            "comms.messages_sent", "calendar.escalation_event"})

    def test_golden(self):
        self.golden_workbooks()
        self.golden_comms()
        self.assertEqual(self.done(), {})

    def test_golden_variants_accepted(self):
        self.golden_workbooks(billed47=177.25)
        self.edit("PBC_Claim_Register.xlsx", setter("Claim_ID", {"CLM-2026-0049": {"Claim_Status": "Written Off"}}))
        self.did(POST, {"channel_id": "C002", "text": ESC48.replace("Operational", "Financial")})
        self.did(POST, {"channel_id": "C001", "text": SPECIAL49})
        self.did(CAL, cal(ESC48.replace("Operational", "Financial")))
        self.assertEqual(self.done(), {})

    # ---- queue.open_items ----
    def test_queue_escalated_item_not_complete(self):
        self.golden_workbooks()
        self.golden_comms()
        self.edit("PBC_RA_Queue.xlsx", setter("Queue_ID", {"Q-2026-002": {"Status": "Complete"}}))
        self.assertIn("In Progress", self.done()["queue.open_items"])

    def test_queue_severity(self):
        self.golden_workbooks()
        self.golden_comms()
        self.edit("PBC_RA_Queue.xlsx", setter("Queue_ID", {"Q-2026-001": {"Priority_Level": "Level 3: Medium"}}))
        self.assertIn("Level 4: Low", self.done()["queue.open_items"])

    # ---- register / worklist ----
    def test_register_sbwo_not_closed(self):
        self.golden_workbooks()
        self.golden_comms()
        self.edit("PBC_Claim_Register.xlsx", setter("Claim_ID", {"CLM-2026-0047": {"Claim_Status": "Closed"}}))
        self.assertIn("Written Off", self.done()["register.co45_outcome"])

    def test_register_sbwo_adjustment_zero(self):
        self.golden_workbooks()
        self.golden_comms()
        self.edit("PBC_Claim_Register.xlsx", setter("Claim_ID", {"CLM-2026-0047": {"Adjustment_Amount": 4.75}}))
        self.assertIn("Adjustment_Amount", self.done()["register.co45_outcome"])

    def test_register_ra_writeoff_not_in_recovery(self):
        self.golden_workbooks()
        self.golden_comms()
        self.edit("PBC_Claim_Register.xlsx", setter("Claim_ID", {"CLM-2026-0049": {"Claim_Status": "In Recovery"}}))
        self.assertIn("Written Off - RA Approved", self.done()["register.co45_outcome"])

    def test_worklist_wrong_action(self):
        self.golden_workbooks()
        self.golden_comms()
        self.edit("PBC_Denial_Worklist.xlsx", setter("Denial_ID", {
            "DNL-2026-003": {"Recovery_Action": "Appeal - Contractual Rate Dispute", "Recovery_Status": "Escalated"}}))
        probs = [p for r, p in self.done_all() if r == "worklist.co45_outcome"]
        self.assertTrue(any("Recovery_Action must be 'Write Off'" in p for p in probs), probs)

    # ---- scope / values ----
    def test_scope_other_rows(self):
        self.golden_workbooks()
        self.golden_comms()
        self.edit("PBC_RA_Queue.xlsx", setter("Queue_ID", {"Q-2026-004": {"Status": "Complete"}}))
        self.assertIn("Q-2026-004", self.done()["scope.other_rows"])

    def test_scope_new_register_row(self):
        self.golden_workbooks()
        self.golden_comms()
        self.edit("PBC_Claim_Register.xlsx", "ws.append(['CLM-2026-0049-R','PAT-1004'])")
        self.assertIn("new row", self.done()["scope.other_rows"])

    def test_values_controlled(self):
        self.golden_workbooks()
        self.golden_comms()
        self.edit("PBC_Denial_Worklist.xlsx", setter("Denial_ID", {"DNL-2026-002": {"Recovery_Status": "Sent to RCM"}}))
        d = self.done()
        self.assertIn("values.controlled", d)

    # ---- comms ----
    def test_escalation_post_ok(self):
        self.assertEqual(self.pre(POST, {"channel_id": "C002", "text": ESC48}), set())

    def test_escalation_post_wrong(self):
        self.assertEqual(self.pre(POST, {"channel_id": "C002", "text": ESC48.replace("Operational", "Critical")}),
                         {"comms.messages"})
        self.assertEqual(self.pre(POST, {"channel_id": "C003", "text": ESC48}), {"comms.messages"})

    def test_escalation_duplicate(self):
        self.did(POST, {"channel_id": "C002", "text": ESC48})
        self.assertEqual(self.pre(POST, {"channel_id": "C002", "text": ESC48}), {"comms.messages"})

    def test_no_escalation_for_writeoffs(self):
        self.assertEqual(self.pre(POST, {"channel_id": "C002", "text": ESC49}), {"comms.messages"})
        self.assertEqual(self.pre(POST, {"channel_id": "C002", "text": ESC49.replace("0049", "0047")}),
                         {"comms.messages"})

    def test_special_post(self):
        self.assertEqual(self.pre(POST, {"channel_id": "C001", "text": SPECIAL49}), set())
        self.assertEqual(self.pre(POST, {"channel_id": "C001", "text": "James Whitfield - CLM-2026-0049 approved"}),
                         {"comms.messages"})
        self.assertEqual(self.pre(POST, {"channel_id": "C001", "text": SPECIAL49.replace("0049", "0048")}),
                         {"comms.messages"})
        self.assertEqual(self.pre(POST, {"channel_id": "C001", "text": SPECIAL49.replace("0049", "0047")}), set())

    def test_placeholders(self):
        self.assertIn("comms.no_placeholders",
                      self.pre(POST, {"channel_id": "C003", "text": "James W. - [Claim ID] special action authorized"}))

    def test_claim_fields_email(self):
        to = "catherine.lawson@pathfinder.med"
        bad = {"to": to, "subject": "CLM-2026-0048 dispute", "body": "Please raise a dispute for CLM-2026-0048."}
        self.assertEqual(self.pre("google_mail__send_email", bad), {"comms.claim_fields"})
        good = dict(bad, body="CLM-2026-0048, Patient ID PAT-1003, DOS 2025-12-20, CPT 93306, Payer BlueCross "
                              "BlueShield, Claim Status In Recovery.")
        self.assertEqual(self.pre("google_mail__send_email", good), set())

    def test_phi_external(self):
        args = {"to": "appeals@bcbs.example.com", "subject": "Underpayment", "body": "Patient PAT-1003 underpaid."}
        self.assertEqual(self.pre("google_mail__send_email", args), {"comms.phi_external"})
        self.assertEqual(self.pre("google_mail__send_email", dict(args, to="catherine.lawson@pathfinder.med")), set())

    # ---- calendar ----
    def test_calendar_title(self):
        self.assertEqual(self.pre(CAL, cal(ESC48)), set())
        self.assertEqual(self.pre(CAL, cal("Escalation attempt CLM-2026-0048")), {"calendar.escalation_title"})
        self.assertEqual(self.pre(CAL, cal(ESC49)), {"calendar.escalation_title"})
        self.did(POST, {"channel_id": "C002", "text": ESC48.replace("Operational", "Financial")})
        self.assertEqual(self.pre(CAL, cal(ESC48)), {"calendar.escalation_title"})

    def test_calendar_event_required(self):
        self.golden_workbooks()
        self.did(POST, {"channel_id": "C002", "text": ESC48})
        self.did(POST, {"channel_id": "C001", "text": SPECIAL49})
        self.did(CAL, cal(ESC48), '{"status":"error","message":"Event end must be after start"}')
        self.assertIn("calendar.escalation_event", self.done())

    def test_tfl_events_kept(self):
        self.assertEqual(self.pre("google_calendar__delete_event", {"event_id": "evt-12"}), {"calendar.tfl_kept"})
        self.assertEqual(self.pre("google_calendar__delete_event", {"event_id": "abc123"}), set())

    # ---- files ----
    def test_reference_files_readonly(self):
        code = "import openpyxl\np='/workdir/PBC_Fee_Schedule.xlsx'\nwb=openpyxl.load_workbook(p)\nwb.save(p)\n"
        self.assertEqual(self.pre("syntara__executePython", {"code": code}), {"files.reference_readonly"})
        era = code.replace("PBC_Fee_Schedule.xlsx", "ERA-20260218-001.xlsx")
        self.assertEqual(self.pre("syntara__executePython", {"code": era}), {"files.reference_readonly"})
        ok = code.replace("PBC_Fee_Schedule.xlsx", "PBC_Claim_Register.xlsx")
        self.assertEqual(self.pre("syntara__executePython", {"code": ok}), set())


if __name__ == "__main__":
    unittest.main()
