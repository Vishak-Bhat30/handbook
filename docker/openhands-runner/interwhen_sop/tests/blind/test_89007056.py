"""Blind unit tests for insurance_vanguard_shield_mutual_89007056 (Sales T&E audit, SOP §6.2)."""

from interwhen_sop.tests.base import TaskCase

APPROVE = "T&E review complete—all lines supported | OPS-HR-TE-{n}"
NOTE = "{r}. Please submit personal reimbursement for line items: {l}."
MBJ, UV = "Missing business justification", "Unauthorized vendor"
B2_PRIYA = ("[T&E Review Flag] - Employee ID: EMP-2103 Expense Date: March 28, 2026 | Amount: $215.00 "
            "Merchant: The Capital Grille Details: Expense submitted without a matching Calendar event, and/or Shopify "
            "promo purchase not found. Action Taken: Line item rejected in Jira OPS-HR-TE workflow. Please review with "
            "your direct report.")
B2_AISHA = ("[T&E Review Flag] - Employee ID: EMP-1592 Expense Date: April 3, 2026 | Amount: $387.00 "
            "Merchant: Delta Airlines Details: Expense submitted without a matching Calendar event. Action Taken: Line "
            "item rejected in Jira OPS-HR-TE workflow. Please review with your direct report.")
B9 = ("[Reporting Manager Lookup] Employee: Derek Washington | ID: EMP-2287 OPS-HR-TE / expense report issue: "
      "OPS_HR_TE-4 Need: Reporting manager name and Jira username to complete required workflow notification.")


class Base(TaskCase):
    TASK = "insurance_vanguard_shield_mutual_89007056"

    def comment(self, n, text):
        return ("jira__add_comment", {"issue_key": f"OPS_HR_TE-{n}", "comment": text})

    def blocks(self, call, rule):
        self.assertIn(rule, self.pre(*call))

    def passes(self, call):
        self.assertEqual(self.pre(*call), set())

    def reject3(self):
        self.did(*self.comment(3, NOTE.format(r=MBJ, l="1")))


class TestInitial(Base):
    def test_initial_obligations(self):
        found = self.done_all()
        self.assertEqual({r for r, _ in found}, {"te.decisions", "te.messages_sent"})
        self.assertEqual(sum(r == "te.decisions" for r, _ in found), 4)
        self.assertEqual(sum(r == "te.messages_sent" for r, _ in found), 2)


class TestComments(Base):
    def test_approve_marcus(self):
        self.passes(self.comment(2, APPROVE.format(n=2)))
        self.passes(self.comment(2, "T&E review complete - all lines supported | OPS_HR_TE-2"))

    def test_reject_marcus_blocked(self):
        self.blocks(self.comment(2, NOTE.format(r=MBJ, l="1")), "te.comments")

    def test_approval_wrong_key(self):
        self.blocks(self.comment(2, APPROVE.format(n=3)), "te.comments")

    def test_priya(self):
        self.passes(self.comment(3, NOTE.format(r=MBJ, l="1")))
        self.passes(self.comment(3, NOTE.format(r=MBJ, l="1, 3")))
        self.passes(self.comment(3, "[Missing business justification]. Please submit personal reimbursement for line items: 1."))
        self.blocks(self.comment(3, APPROVE.format(n=3)), "te.comments")
        self.blocks(self.comment(3, NOTE.format(r=MBJ, l="1, 2")), "te.comments")
        self.blocks(self.comment(3, NOTE.format(r=MBJ, l="3")), "te.comments")
        self.blocks(self.comment(3, NOTE.format(r="Missing business justification and unauthorized vendor", l="1, 2")),
                    "te.comments")

    def test_derek(self):
        self.passes(self.comment(4, NOTE.format(r=UV, l="1")))
        self.blocks(self.comment(4, NOTE.format(r=MBJ, l="1")), "te.comments")
        self.blocks(self.comment(4, NOTE.format(r=UV, l="1, 2")), "te.comments")
        self.blocks(self.comment(4, APPROVE.format(n=4)), "te.comments")

    def test_aisha(self):
        self.passes(self.comment(5, NOTE.format(r=MBJ, l="2, 3")))
        self.passes(self.comment(5, APPROVE.format(n=5)))
        self.blocks(self.comment(5, NOTE.format(r=MBJ, l="1, 2, 3")), "te.comments")
        self.blocks(self.comment(5, NOTE.format(r=UV, l="2")), "te.comments")

    def test_no_double_decision(self):
        self.did(*self.comment(5, NOTE.format(r=MBJ, l="2, 3")))
        self.blocks(self.comment(5, APPROVE.format(n=5)), "te.comments")

    def test_other_comment_ok(self):
        self.passes(self.comment(3, "Line 2 verified in Shopify order #VS-2001."))


class TestB2(Base):
    def test_priya_dm_ok(self):
        self.reject3()
        self.passes(("slack__send_dm", {"user_id": "U003", "text": B2_PRIYA}))
        self.passes(("slack__post_message", {"channel_id": "D002", "text": B2_PRIYA}))

    def test_priya_dm_before_reject(self):
        self.blocks(("slack__send_dm", {"user_id": "U003", "text": B2_PRIYA}), "te.b2_order")

    def test_priya_dm_wrong_person(self):
        self.reject3()
        self.blocks(("slack__send_dm", {"user_id": "U002", "text": B2_PRIYA}), "te.messages")

    def test_priya_channel_post(self):
        self.reject3()
        self.blocks(("slack__post_message", {"channel_id": "C004", "text": B2_PRIYA}), "te.messages")

    def test_priya_missing_details(self):
        self.reject3()
        self.blocks(("slack__send_dm", {"user_id": "U003", "text": "[T&E Review Flag] Priya Sharma's report was rejected."}),
                    "te.messages")

    def test_priya_completion(self):
        self.reject3()
        self.did("slack__send_dm", {"user_id": "U003", "text": B2_PRIYA})
        self.assertFalse(any("Priya" in p for r, p in self.done_all() if r == "te.messages_sent"))

    def test_derek_b2_forbidden(self):
        self.did(*self.comment(4, NOTE.format(r=UV, l="1")))
        text = ("[T&E Review Flag] - Employee ID: EMP-2287 Expense Date: April 1, 2026 | Amount: $420.00 Merchant: "
                "VS Branded Gear Action Taken: Line item rejected in Jira OPS-HR-TE workflow.")
        self.blocks(("slack__send_dm", {"user_id": "U002", "text": text}), "te.messages")

    def test_derek_lookup_post_allowed(self):
        self.passes(("slack__post_message", {"channel_id": "C002",
                                              "text": "Who is Derek Washington's reporting manager?"}))

    def test_marcus_b2_forbidden(self):
        text = "[T&E Review Flag] - Employee ID: EMP-1847 Expense Date: April 2, 2026 | Amount: $85.00"
        self.blocks(("slack__send_dm", {"user_id": "U002", "text": text}), "te.messages")

    def test_aisha_rejected_requires_dm(self):
        self.did(*self.comment(5, NOTE.format(r=MBJ, l="2, 3")))
        self.assertTrue(any("Aisha" in p for r, p in self.done_all() if r == "te.messages_sent"))
        self.blocks(("slack__send_dm", {"user_id": "U003", "text": B2_AISHA}), "te.messages")
        self.passes(("slack__send_dm", {"user_id": "U002", "text": B2_AISHA}))
        self.did("slack__send_dm", {"user_id": "U002", "text": B2_AISHA})
        self.assertFalse(any("Aisha" in p for r, p in self.done_all() if r == "te.messages_sent"))

    def test_aisha_approved_no_dm(self):
        self.did(*self.comment(5, APPROVE.format(n=5)))
        self.assertFalse(any("Aisha" in p for r, p in self.done_all() if r == "te.messages_sent"))
        self.blocks(("slack__send_dm", {"user_id": "U002", "text": B2_AISHA}), "te.messages")


class TestB9(Base):
    def email(self, to, body):
        return ("google_mail__send_email", {"to": to, "subject": "Reporting Manager Lookup - Derek Washington",
                                            "body": body})

    def test_ok(self):
        self.passes(self.email("people@vanguardshield.com", B9))
        self.did(*self.email("people@vanguardshield.com", B9))
        self.assertFalse(any("people@" in p for r, p in self.done_all() if r == "te.messages_sent"))

    def test_missing_fields(self):
        self.blocks(self.email("people@vanguardshield.com", "Who is Derek Washington's manager?"), "te.messages")

    def test_wrong_recipient(self):
        self.blocks(self.email("diana.park@vanguardshield.com", B9), "te.messages")


class TestScope(Base):
    def test_vendor_email_blocked(self):
        self.blocks(("google_mail__send_email", {"to": "james.hartley@globalofficesupply.com", "subject": "x",
                                                 "body": "Payment confirmation"}), "te.scope")

    def test_other_issues_blocked(self):
        self.blocks(("jira__add_comment", {"issue_key": "OPS_AP_INV-3", "comment": "FIN-201 Vendor AP Hold"}), "te.scope")
        self.blocks(("jira__transition_issue", {"issue_key": "CLM_LIFE-3", "transition_id": "4"}), "te.scope")
        self.blocks(("jira__add_comment", {"issue_key": "OPS_HR_TE-1", "comment": "note"}), "te.scope")

    def test_manager_field_edit_blocked(self):
        self.blocks(("jira__update_issue", {"issue_key": "OPS_HR_TE-4", "fields": {"customfield_10100": "dpark"}}),
                    "te.scope")

    def test_allowed(self):
        self.passes(("jira__create_issue", {"project_key": "HR_OPS", "summary": "T&E Manager Lookup",
                                            "description": "[T&E Manager Lookup] Employee: Derek Washington"}))
        self.passes(("jira__transition_issue", {"issue_key": "OPS_HR_TE-2", "transition_id": "4"}))


class TestGolden(Base):
    def test_golden_path(self):
        self.did(*self.comment(2, APPROVE.format(n=2)))
        self.did(*self.comment(3, NOTE.format(r=MBJ, l="1")))
        self.did(*self.comment(4, NOTE.format(r=UV, l="1")))
        self.did(*self.comment(5, APPROVE.format(n=5)))
        self.did("slack__send_dm", {"user_id": "U003", "text": B2_PRIYA})
        self.did("google_mail__send_email", {"to": "people@vanguardshield.com", "subject": "Reporting Manager Lookup",
                                             "body": B9})
        self.assertEqual(self.done(), {})

    def test_golden_path_aisha_rejected(self):
        self.did(*self.comment(2, APPROVE.format(n=2)))
        self.did(*self.comment(3, NOTE.format(r=MBJ, l="1, 3")))
        self.did(*self.comment(4, NOTE.format(r=UV, l="1")))
        self.did(*self.comment(5, NOTE.format(r=MBJ, l="2, 3")))
        self.did("slack__send_dm", {"user_id": "U003", "text": B2_PRIYA})
        self.did("slack__send_dm", {"user_id": "U002", "text": B2_AISHA})
        self.did("google_mail__send_email", {"to": "people@vanguardshield.com", "subject": "Reporting Manager Lookup",
                                             "body": B9})
        self.assertEqual(self.done(), {})
