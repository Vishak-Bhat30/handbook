"""Blind unit tests for insurance_vanguard_shield_mutual_90ff0751 (SOP §6.2 Sales T&E batch OPS-3/4/5)."""

import json

from interwhen_sop.tests.base import TaskCase

B2_OK = ("[T&E Review Flag] - Employee ID: EMP-3312\n"
         "Expense Date: Oct 1, 2026 | Amount: $144.00\n"
         "Merchant: VSM Branded Water Bottles — Qty 12\n"
         "Details: Expense submitted without a matching Calendar event, or Shopify promo purchase not found.\n"
         "Action Taken: Line item rejected in Jira OPS-HR-TE workflow. Please review with your direct report.")
B8_DESC = ("[T&E Manager Lookup]\nEmployee: Derek Huang | ID: EMP-4507\n"
           "OPS-HR-TE / expense report issue: OPS-4\n"
           "Directory / People search result: Reporting Manager field blank; people@vanguardshield.com returned no match\n"
           "Need: Correct manager Jira username or Slack handle for Template B-2 notification.")
B8_TITLE = "Manager Lookup Needed – T&E Exception – Derek Huang (EMP-4507)"
NOTE = "Missing business justification/unauthorized vendor. Please submit personal reimbursement."
PEOPLE = {"to": "people@vanguardshield.com", "subject": "Reporting manager request - Derek Huang",
          "body": "Please provide the reporting manager for Derek Huang (EMP-4507), T&E report OPS-4."}


def comment(k, text):
    return "jira__add_comment", {"issue_key": k, "comment": text}


def transition(k, tid):
    return "jira__transition_issue", {"issue_key": k, "transition_id": tid}


def labels(k, *ls):
    return "jira__update_issue", {"issue_key": k, "fields": json.dumps({"labels": list(ls)})}


def b8(title=B8_TITLE, desc=B8_DESC):
    return "jira__create_issue", {"project_key": "OPS", "summary": title, "issue_type": "Task", "description": desc}


def dm(uid, text):
    return "slack__send_dm", {"user_id": uid, "text": text}


class T90ff0751(TaskCase):
    TASK = "insurance_vanguard_shield_mutual_90ff0751"

    def golden(self):
        self.did(*comment("OPS-5", "T&E review complete—all lines supported | OPSHR-TE-OPS-5"))
        self.did(*transition("OPS-5", "5"))
        self.did(*comment("OPS-3", NOTE + " Oct 1 water bottles $144.00 not in Shopify."))
        self.did(*labels("OPS-3", "te-rejected", "sales-west"))
        self.did(*comment("OPS-4", NOTE + " Oct 3 $340.00 / Oct 4 $28.00 weekend, no calendar event."))
        self.did(*labels("OPS-4", "te-rejected", "sales-midwest"))
        self.did(*dm("U002", B2_OK))
        self.did("google_mail__send_email", PEOPLE, '{"status": "sent"}')
        self.did(*b8())

    # ---- end state
    def test_initial_obligations(self):
        got = self.done()
        self.assertEqual(set(got), {"te.rejections", "te.approval", "te.b8_ticket", "te.comms.messages_sent"})
        self.assertEqual(len(self.done_all()), 9)

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_rejection_needs_state(self):
        self.did(*comment("OPS-3", NOTE))
        probs = [p for r, p in self.done_all() if r == "te.rejections" and p.startswith("OPS-3")]
        self.assertEqual(len(probs), 1)
        self.assertIn("not set to rejected", probs[0])
        self.did(*labels("OPS-3", "te-rejected", "sales-west"))
        self.assertFalse([p for r, p in self.done_all() if r == "te.rejections" and p.startswith("OPS-3")])

    def test_rejection_comment_needs_standard_note(self):
        self.did(*comment("OPS-4", "Rejected: weekend meals."))
        self.assertTrue([p for r, p in self.done_all() if r == "te.rejections" and "OPS-4: no rejection comment" in p])

    def test_approval_needs_transition(self):
        self.did(*comment("OPS-5", "T&E review complete—all lines supported | OPSHR-TE-OPS-5"))
        probs = [p for r, p in self.done_all() if r == "te.approval"]
        self.assertEqual(len(probs), 1)
        self.assertIn("not approved", probs[0])

    # ---- pre: reject / approve decisions
    def test_no_approve_rejected(self):
        self.assertIn("te.no_approve_rejected", self.pre(*transition("OPS-3", "5")))
        self.assertIn("te.no_approve_rejected", self.pre(*transition("OPS-4", "8")))
        self.assertIn("te.no_approve_rejected", self.pre(*comment("OPS-4", "T&E review complete—all lines supported")))
        self.assertEqual(self.pre(*transition("OPS-5", "5")), set())
        self.assertEqual(self.pre(*comment("OPS-5", "T&E review complete — all lines supported | OPS-5")), set())

    def test_no_reject_approved(self):
        self.assertIn("te.no_reject_approved", self.pre(*comment("OPS-5", NOTE)))
        self.assertIn("te.no_reject_approved", self.pre(*labels("OPS-5", "te-rejected")))
        self.assertEqual(self.pre(*comment("OPS-3", NOTE)), set())
        self.assertEqual(self.pre(*labels("OPS-4", "te-rejected", "sales-midwest")), set())

    def test_scope(self):
        self.assertIn("te.scope", self.pre(*transition("OPS-2", "2")))
        self.assertIn("te.scope", self.pre("jira__delete_issue", {"issue_key": "OPS-3"}))
        self.assertEqual(self.pre(*comment("OPS-2", "FYI")), set())

    # ---- B-8 ticket
    def test_b8_order_and_format(self):
        self.assertIn("te.b8_ticket_pre", self.pre(*b8()))
        self.did("google_mail__send_email", PEOPLE, '{"status": "sent"}')
        self.assertEqual(self.pre(*b8()), set())
        self.assertIn("te.b8_ticket_pre", self.pre(*b8(title="Manager lookup for Derek")))
        self.assertIn("te.b8_ticket_pre", self.pre(*b8(desc="Please find Derek Huang's manager.")))

    def test_b8_completion(self):
        self.did("google_mail__send_email", PEOPLE, '{"status": "sent"}')
        self.assertIn("te.b8_ticket", self.done())
        self.did(*b8())
        self.assertNotIn("te.b8_ticket", self.done())

    # ---- messages
    def test_b2_pkim(self):
        self.assertEqual(self.pre(*dm("U002", B2_OK)), set())
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "DU002", "text": B2_OK}), set())
        bad = B2_OK.replace("Details: Expense submitted without a matching Calendar event, or Shopify promo purchase "
                            "not found.", "Details: no Shopify order.")
        self.assertIn("te.comms.messages", self.pre(*dm("U002", bad)))
        self.assertIn("te.comms.messages", self.pre(*dm("U006", B2_OK)))
        self.assertIn("te.comms.messages", self.pre("slack__post_message", {"channel_id": "CSALESOPS", "text": B2_OK}))

    def test_b2_sent_once_extra_line_allowed(self):
        self.did("slack__post_message", {"channel_id": "DU002", "text": B2_OK})
        self.assertFalse([p for r, p in self.done_all() if r == "te.comms.messages_sent" and "Peter Kim" in p])
        self.assertIn("te.comms.messages", self.pre("slack__post_message", {"channel_id": "DU002", "text": B2_OK}))
        other = B2_OK.replace("Oct 1, 2026 | Amount: $144.00", "Oct 2, 2026 | Amount: $215.00")
        self.assertEqual(self.pre(*dm("U002", other)), set())

    def test_no_b2_for_huang_or_frost(self):
        huang = B2_OK.replace("EMP-3312", "EMP-4507")
        self.assertIn("te.comms.messages", self.pre(*dm("U006", huang)))
        self.assertIn("te.comms.messages", self.pre(*dm("U002", huang)))
        self.assertIn("te.comms.messages", self.pre(*dm("U003", B2_OK.replace("EMP-3312", "EMP-5021"))))
        self.assertEqual(self.pre(*dm("U008", "Hi Derek, your report OPS-4 was returned; see Jira.")), set())

    def test_people_email(self):
        self.assertEqual(self.pre("google_mail__send_email", PEOPLE), set())
        noname = dict(PEOPLE, subject="Manager request", body="Please provide the manager for EMP-4507.")
        self.assertIn("te.comms.messages", self.pre("google_mail__send_email", noname))

    def test_placeholders(self):
        self.assertIn("comms.no_placeholders", self.pre(*dm("U002", B2_OK.replace("EMP-3312", "[Employee ID]"))))
        self.assertEqual(self.pre(*dm("U002", B2_OK)), set())
        self.assertIn("te.jira_placeholders",
                      self.pre(*comment("OPS-5", "T&E review complete—all lines supported | OPSHR-TE-[ReportID]")))
