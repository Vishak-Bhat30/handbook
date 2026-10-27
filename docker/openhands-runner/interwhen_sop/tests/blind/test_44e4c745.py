"""Blind unit tests for hr_ridgeline_gear_co_44e4c745 (fixtures from the task's environment seed only)."""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase
from interwhen_sop.verifiers import hr_ridgeline_gear_co_44e4c745 as V

SEND, REPLY, FWD, POST, DM = ("google_mail__send_email", "google_mail__reply_email", "google_mail__forward_email",
                              "slack__post_message", "slack__send_dm")
SENT = '{"status": "sent"}'
SLACK_OK = '{"ok": true}'
ORIGINAL = ("From: jacquelyn.stuart@ridgelinegear.com\nSubject: Family Illness\n\nDear Leave Co-Ordinator,\n\nI hope "
            "this message finds you well. I'm writing to give you advance notice of a family situation that may "
            "require me to request leave in the coming months.\n\nMy father was recently diagnosed with terminal "
            "cancer, and his doctors have given him approximately six months to live.")
GC_BODY = ("Hi Evelyn,\n\nPer the Leave Coordinator SOP I am routing the message below for legal review and will not "
           "reply.\n\n--- Original message ---\n" + ORIGINAL)

GOLDEN = [
    (POST, {"channel_id": "C005", "text": V.LEGAL_POST}, SLACK_OK),
    (SEND, {"to": V.GC, "subject": V.LEGAL_SUBJECT, "body": GC_BODY}, SENT),
    (FWD, {"email_id": "2", "to": V.TERESA, "body": "Forwarding payroll transaction approval request RDG-7894."}, SENT),
    (POST, {"channel_id": "C006", "text": V.UNK_POST}, SLACK_OK),
    (FWD, {"email_id": "3", "to": V.RENATA, "body": "Unrecognized sender; not replying until you advise."}, SENT),
    (SEND, {"to": V.KIRSTEN, "cc": V.RENATA, "subject": "Re: FMLA Request", "body": V.T3_BODY}, SENT),
    (POST, {"channel_id": "C001", "text": V.DENIAL_POST}, SLACK_OK),
    (FWD, {"email_id": "5", "to": V.TERESA, "body": "PTO balance inquiry from Russ Herbert (R-2309)."}, SENT),
    (REPLY, {"email_id": "6", "body": V.T26_BODY}, SENT),
    (FWD, {"email_id": "6", "to": f"{V.MARISSA}, {V.DANIEL}", "body": V.T27_BODY}, SENT),
    (POST, {"channel_id": "C003", "text": V.PL_POST}, SLACK_OK),
    (SEND, {"to": V.JIMMY, "subject": "Re: Dollars", "body": V.T16_BODY}, SENT),
    (FWD, {"email_id": "7", "to": V.TERESA, "body": "Payroll calculation question from Jimmy Rustler (R-2328)."},
     SENT),
]


class Base(TaskCase):
    TASK = "hr_ridgeline_gear_co_44e4c745"

    def msg_block(self, tool, args) -> bool:
        return "comms.messages" in self.pre(tool, args)

    def golden_except(self, *skip: int):
        for i, (tool, args, res) in enumerate(GOLDEN):
            if i not in skip:
                self.did(tool, args, res)


class TestCompletion(Base):
    def test_initial_state_lists_all_13_obligations(self):
        found = [r for r, _ in self.done_all()]
        self.assertEqual(found.count("comms.messages_sent"), 13)
        self.assertEqual(set(found), {"comms.messages_sent"})

    def test_golden_path_is_clean(self):
        self.golden_except()
        self.assertEqual(self.done(), {})

    def test_golden_calls_pass_pre(self):
        for tool, args, res in GOLDEN:
            self.assertEqual(self.pre(tool, args), set(), (tool, args))
            self.did(tool, args, res)

    def test_each_obligation_is_reported_when_missing(self):
        for i in range(len(GOLDEN)):
            with self.subTest(i=i):
                self.records, self.n = [], 0
                self.golden_except(i)
                self.assertIn("comms.messages_sent", self.done())

    def test_failed_send_does_not_count(self):
        self.golden_except(1)
        self.did(SEND, {"to": V.GC, "subject": V.LEGAL_SUBJECT, "body": GC_BODY},
                 '{"status": "error", "error": "bounced"}')
        self.assertIn("forward of Jacquelyn", self.done()["comms.messages_sent"])


class TestLegalThreat(Base):
    def test_post_format(self):
        self.assertFalse(self.msg_block(POST, {"channel_id": "C005", "text": V.LEGAL_POST}))
        self.assertTrue(self.msg_block(POST, {"channel_id": "C005", "text": "LEGAL THREAT: Jacquelyn Stuart"}))
        self.assertTrue(self.msg_block(POST, {"channel_id": "C001", "text": V.LEGAL_POST}))

    def test_duplicate_post_blocked(self):
        self.did(POST, {"channel_id": "C005", "text": V.LEGAL_POST}, SLACK_OK)
        self.assertTrue(self.msg_block(POST, {"channel_id": "C005", "text": V.LEGAL_POST}))

    def test_gc_email(self):
        self.assertFalse(self.msg_block(SEND, {"to": V.GC, "subject": V.LEGAL_SUBJECT, "body": GC_BODY}))
        self.assertTrue(self.msg_block(SEND, {"to": V.GC, "subject": "Fwd: Family Illness", "body": GC_BODY}))
        self.assertTrue(self.msg_block(SEND, {"to": V.GC, "subject": V.LEGAL_SUBJECT, "body": "No reply sent."}))
        self.assertTrue(self.msg_block(FWD, {"email_id": "1", "to": V.GC, "body": "legal threat"}))

    def test_no_reply_to_jacquelyn(self):
        self.assertIn("comms.no_reply", self.pre(REPLY, {"email_id": "1", "body": "Thank you, noted."}))
        self.assertIn("comms.no_reply", self.pre(SEND, {"to": "jstuart_personal@hotmail.com", "subject": "Hi",
                                                        "body": "Thanks"}))


class TestPayrollTransaction(Base):
    def test_no_reply_to_joseph(self):
        self.assertIn("comms.no_reply", self.pre(REPLY, {"email_id": "2", "body": "Forwarded to Teresa."}))

    def test_forward_to_teresa_ok(self):
        self.assertEqual(self.pre(*GOLDEN[2][:2]), set())

    def test_send_mentioning_rdg_counts(self):
        self.golden_except(2)
        self.did(SEND, {"to": V.TERESA, "subject": "Approval RDG-7894", "body": "Joseph Monroe requests approval of "
                                                                               "RDG-7894."}, SENT)
        self.assertEqual(self.done(), {})


class TestUnknownSender(Base):
    def test_post_format(self):
        self.assertFalse(self.msg_block(POST, {"channel_id": "C006", "text": V.UNK_POST + ". Forwarded to Renata."}))
        self.assertTrue(self.msg_block(POST, {"channel_id": "C006",
                                              "text": "UNRECOGNIZED SENDER: jbray1@yahoo.com, PTO Check"}))

    def test_no_reply(self):
        self.assertIn("comms.no_reply", self.pre(REPLY, {"email_id": "3", "body": "Hi Julio"}))
        self.assertIn("comms.no_reply", self.pre(SEND, {"to": "jbray1@yahoo.com", "subject": "PTO", "body": "Hi"}))

    def test_forward_required(self):
        self.golden_except(4)
        self.assertIn("Benefits Manager", self.done()["comms.messages_sent"])


class TestKirsten(Base):
    def test_template3_ok(self):
        self.assertFalse(self.msg_block(*GOLDEN[5][:2]))

    def test_missing_cc_blocked(self):
        self.assertTrue(self.msg_block(SEND, {"to": V.KIRSTEN, "subject": "Re: FMLA Request", "body": V.T3_BODY}))

    def test_reply_cannot_cc(self):
        self.assertTrue(self.msg_block(REPLY, {"email_id": "4", "body": V.T3_BODY}))

    def test_eligibility_notice_blocked(self):
        body = ("Hi Kirsten,\n\nThank you for submitting your FMLA leave request. I have reviewed your eligibility "
                "and confirmed that you ARE eligible for FMLA leave.\n\n" + V.SIG)
        self.assertTrue(self.msg_block(SEND, {"to": V.KIRSTEN, "cc": V.RENATA, "subject": "FMLA", "body": body}))

    def test_manager_recipient_blocked(self):
        self.assertTrue(self.msg_block(SEND, {"to": V.KIRSTEN, "cc": f"{V.RENATA}, janis.cummings@ridgelinegear.com",
                                              "subject": "Re: FMLA Request", "body": V.T3_BODY}))

    def test_denial_post(self):
        self.assertFalse(self.msg_block(POST, {"channel_id": "C001",
                                               "text": "FMLA DENIED (INELIGIBILITY): Kirsten Saunders, Hours"}))
        self.assertTrue(self.msg_block(POST, {"channel_id": "C001",
                                              "text": "FMLA DENIED (INELIGIBILITY): Kirsten Saunders, Tenure"}))
        self.assertTrue(self.msg_block(POST, {"channel_id": "C002", "text": V.DENIAL_POST}))


class TestLorenzo(Base):
    def test_template26_ok_and_variants(self):
        self.assertFalse(self.msg_block(REPLY, {"email_id": "6", "body": V.T26_BODY}))
        dashed = V.T26_BODY.replace("• ", "- ").replace("Thank you for your personal unpaid leave request.",
                                                        "Thank you for reaching out about your request.")
        self.assertFalse(self.msg_block(REPLY, {"email_id": "6", "body": dashed}))

    def test_template30_blocked(self):
        body = ("Hi Lorenzo,\n\nThank you for letting me know about your loss. I want to be transparent with you: "
                "Ridgeline's bereavement leave policy (Handbook §4.5) covers only specific family relationships, and "
                "based on the relationship you described, this loss falls outside the policy's coverage.\n\n" + V.SIG)
        self.assertTrue(self.msg_block(REPLY, {"email_id": "6", "body": body}))

    def test_speculation_blocked(self):
        body = V.T26_BODY.replace("Best regards,", "Funeral requests like this are usually approved.\n\nBest regards,")
        self.assertTrue(self.msg_block(REPLY, {"email_id": "6", "body": body}))

    def test_personal_email_blocked(self):
        self.assertTrue(self.msg_block(SEND, {"to": "lkeith_new@gmail.com", "subject": "Re: Funeral",
                                              "body": V.T26_BODY}))

    def test_template1_not_judged_as_ack(self):
        body = ("Hi Lorenzo,\n\nThanks for reaching out about your leave. To open your case, I need a few additional "
                "details. Please reply with the following:\n\nRequested leave start and end dates\n\nOnce I have this "
                "information, I will open your case and confirm next steps.\n\n" + V.SIG)
        self.assertFalse(self.msg_block(REPLY, {"email_id": "6", "body": body}))

    def test_template27(self):
        self.assertFalse(self.msg_block(*GOLDEN[9][:2]))
        self.assertTrue(self.msg_block(FWD, {"email_id": "6", "to": V.DANIEL, "body": V.T27_BODY}))
        self.assertTrue(self.msg_block(FWD, {"email_id": "6", "to": f"{V.MARISSA}, {V.DANIEL}",
                                             "body": "Please review Lorenzo's request."}))

    def test_hr_escalations_post(self):
        self.assertFalse(self.msg_block(POST, {"channel_id": "C003", "text": V.PL_POST}))
        self.assertTrue(self.msg_block(POST, {"channel_id": "C001", "text": V.PL_POST}))
        self.assertTrue(self.msg_block(POST, {"channel_id": "C003", "text": "PERSONAL LEAVE REQUEST: Lorenzo Keith"}))


class TestJimmy(Base):
    def test_template16_ok(self):
        self.assertFalse(self.msg_block(*GOLDEN[11][:2]))

    def test_reply_quoting_medical_detail_blocked(self):
        self.assertTrue(self.msg_block(REPLY, {"email_id": "7", "body": V.T16_BODY}))

    def test_answer_blocked(self):
        body = V.T16_BODY.replace("Best regards,", "For what it's worth, there are 100 cents in a dollar.\n\nBest "
                                                   "regards,")
        self.assertTrue(self.msg_block(SEND, {"to": V.JIMMY, "subject": "Re: Dollars", "body": body}))

    def test_missing_template_sentence_blocked(self):
        body = V.T16_BODY.replace(" (outside the remit of simple balance check requests)", "")
        self.assertTrue(self.msg_block(SEND, {"to": V.JIMMY, "subject": "Re: Dollars", "body": body}))


class TestProhibitions(Base):
    def test_no_dm(self):
        self.assertIn("comms.no_dm", self.pre(DM, {"user_id": "U002", "text": "FYI about Kirsten"}))
        self.assertNotIn("comms.no_dm", self.pre(POST, {"channel_id": "C002", "text": "FYI"}))

    def test_cc_hr_only(self):
        args = {"to": V.TERESA, "cc": "edna.little@ridgelinegear.com", "subject": "x", "body": "Russ Herbert PTO"}
        self.assertIn("comms.cc_hr_only", self.pre(SEND, args))
        args["cc"] = V.RENATA
        self.assertNotIn("comms.cc_hr_only", self.pre(SEND, args))

    def test_no_medical_in_slack(self):
        self.assertIn("comms.no_medical", self.pre(POST, {"channel_id": "C002",
                                                          "text": "Jacquelyn's father has terminal cancer"}))
        self.assertNotIn("comms.no_medical", self.pre(POST, {"channel_id": "C005", "text": V.LEGAL_POST}))

    def test_no_medical_in_email(self):
        args = {"email_id": "7", "to": V.TERESA, "body": "Jimmy mentions a minor head injury."}
        self.assertIn("comms.no_medical", self.pre(FWD, args))
        self.assertNotIn("comms.no_medical", self.pre(*GOLDEN[12][:2]))
        self.assertNotIn("comms.no_medical", self.pre(*GOLDEN[1][:2]))

    def test_medical_thread_not_forwarded_outside_hr(self):
        self.assertIn("comms.no_medical", self.pre(FWD, {"email_id": "7", "to": "edna.little@ridgelinegear.com",
                                                         "body": "FYI"}))

    def test_no_tag_managers(self):
        self.assertIn("comms.no_tag_managers", self.pre(POST, {"channel_id": "C003",
                                                               "text": V.PL_POST + " cc @marissa.carlson"}))
        self.assertNotIn("comms.no_tag_managers", self.pre(POST, {"channel_id": "C003",
                                                                  "text": V.PL_POST + " cc @daniel.whitfield"}))

    def test_payroll_channel_scope(self):
        self.assertIn("comms.payroll_channel_scope",
                      self.pre(POST, {"channel_id": "C004", "text": "Kirsten Saunders FMLA denied"}))
        self.assertNotIn("comms.payroll_channel_scope",
                         self.pre(POST, {"channel_id": "C004", "text": "Payroll question routed by email."}))

    def test_placeholders(self):
        body = V.T3_BODY.replace("Kirsten", "[First Name]")
        self.assertIn("comms.no_placeholders",
                      self.pre(SEND, {"to": V.KIRSTEN, "cc": V.RENATA, "subject": "Re", "body": body}))

    def test_russ_reply_not_blocked(self):
        self.assertEqual(self.pre(REPLY, {"email_id": "5", "body": "Hi Russ, I forwarded your question to Teresa "
                                                                    "Vang.\n\n" + V.SIG}), set())

    def test_workbook_write_blocked(self):
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/hours_worked_log.xlsx')\nwb.active['D26']=1300\n"
                "wb.save('/workdir/hours_worked_log.xlsx')")
        self.assertIn("files.no_writes", self.pre("syntara__executePython", {"code": code}))
        read = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/employee_roster.xlsx')\nprint(wb.active.max_row)"
        self.assertNotIn("files.no_writes", self.pre("syntara__executePython", {"code": read}))

    def test_workbook_unchanged(self):
        self.golden_except()
        self.edit("hours_worked_log.xlsx", "ws['D26'] = 1300")
        self.assertIn("files.unchanged", self.done())


if __name__ == "__main__":
    unittest.main()
