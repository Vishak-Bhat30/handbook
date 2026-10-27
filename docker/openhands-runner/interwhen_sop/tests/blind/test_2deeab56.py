"""Blind verifier tests for hr_ridgeline_gear_co_2deeab56 (Taylor Gonzalez HFWA request = legal threat, SOP 12.5)."""

from __future__ import annotations

from interwhen_sop.tests.base import TaskCase

GC = "evelyn.marchetti@ridgelineholdings.com"
POST = ("LEGAL THREAT: Taylor Gonzalez, New Case, Leave Request - HFWA, employee email references a legal "
        "professional and DOL guidelines regarding a new HFWA leave request \u2014 do not reply")
SUBJECT = "LEGAL THREAT \u2014 Taylor Gonzalez \u2014 New Case"
FWD_BODY = ("Evelyn, forwarding the employee's email per SOP 12.5. No reply sent, no case opened.\n\n"
            "---------- Forwarded message ---------\nFrom: taylor.gonzalez@ridgelinegear.com\n"
            "Subject: Leave Request - HFWA\n\nHello Harper, ... I discussed my leave situation with a legal professional ...")
SAVE_TRACKER = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/leave_tracker.xlsx')\nws=wb.active\n"
                "ws.append(['LC-2025-1053','R-0014'])\nwb.save('/workdir/leave_tracker.xlsx')\n")


class Base(TaskCase):
    TASK = "hr_ridgeline_gear_co_2deeab56"

    def post(self, channel, text, **kw):
        return self.pre("slack__post_message", {"channel_id": channel, "text": text, **kw})

    def gc_email(self, subject=SUBJECT, body=FWD_BODY, **kw):
        return {"to": GC, "subject": subject, "body": body, **kw}

    def golden(self):
        self.did("google_mail__read_email", {"email_id": "1"})
        self.did("google_mail__read_email", {"email_id": "33"})
        self.did("slack__post_message", {"channel_id": "C005", "text": POST})
        self.did("google_mail__send_email", self.gc_email())
        self.did("google_mail__mark_emails", {"email_ids": ["1"], "is_read": True, "is_important": True})


class TestGolden(Base):
    def test_initial_obligations(self):
        d = self.done_all()
        self.assertEqual({r for r, _ in d}, {"legal.messages_sent", "mail.housekeeping"})
        self.assertEqual(sum(r == "legal.messages_sent" for r, _ in d), 2)

    def test_golden_path_complete(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_calls_not_blocked(self):
        self.assertEqual(self.post("C005", POST), set())
        self.assertEqual(self.pre("google_mail__send_email", self.gc_email()), set())
        self.assertEqual(self.pre("google_mail__mark_emails", {"email_ids": ["1"], "is_read": True,
                                                               "is_important": True}), set())
        self.assertEqual(self.pre("google_mail__forward_email", {"email_id": "1", "to": GC}), set())


class TestLegalPost(Base):
    def test_variants_accepted(self):
        self.assertEqual(self.post("C005", "<@U026> " + POST), set())
        alt = POST.replace(" \u2014 do not reply", ". Do not reply.")
        self.assertEqual(self.post("C005", alt), set())

    def test_wrong_format_blocked(self):
        self.assertIn("legal.messages", self.post("C005", "Taylor Gonzalez mentioned a lawyer, please advise."))
        self.assertIn("legal.messages", self.post("C005", POST.replace("New Case", "LC-2024-1052")))

    def test_wrong_channel_blocked(self):
        self.assertIn("legal.messages", self.post("C003", POST))

    def test_medical_detail_blocked(self):
        bad = POST.replace("regarding a new", "about surgery complications and a")
        got = self.post("C005", bad)
        self.assertIn("legal.messages", got)
        self.assertIn("slack.no_phi", got)

    def test_duplicate_blocked(self):
        self.did("slack__post_message", {"channel_id": "C005", "text": POST})
        self.assertIn("legal.messages", self.post("C005", POST))

    def test_post_missing_until_done(self):
        self.did("slack__post_message", {"channel_id": "C005", "text": "LEGAL THREAT: Taylor Gonzalez"})
        self.assertIn("legal.messages_sent", self.done())


class TestGcEmail(Base):
    def test_wrong_subject_blocked(self):
        self.assertIn("legal.messages", self.pre("google_mail__send_email",
                                                 self.gc_email(subject="Legal threat - Taylor")))

    def test_fwd_prefix_and_cc_ok(self):
        args = self.gc_email(subject="Fwd: " + SUBJECT, cc="renata.okafor@ridgelinegear.com")
        self.assertEqual(self.pre("google_mail__send_email", args), set())

    def test_missing_thread_blocked(self):
        self.assertIn("legal.messages", self.pre("google_mail__send_email", self.gc_email(body="See Slack.")))

    def test_forward_tool_does_not_satisfy_subject(self):
        self.did("google_mail__forward_email", {"email_id": "1", "to": GC, "body": SUBJECT})
        d = self.done_all()
        self.assertTrue(any(r == "legal.messages_sent" and "General Counsel" in p for r, p in d))


class TestLegalHold(Base):
    def test_reply_to_employee_blocked(self):
        self.assertIn("legal.hold", self.pre("google_mail__reply_email", {"email_id": "1", "body": "Received."}))

    def test_email_employee_or_manager_blocked(self):
        self.assertIn("legal.hold", self.pre("google_mail__send_email", {
            "to": "taylor.gonzalez@ridgelinegear.com", "subject": "Your request", "body": "Approved"}))
        self.assertIn("legal.hold", self.pre("google_mail__send_email", {
            "to": "charlie.szabo@ridgelinegear.com", "subject": "Taylor Gonzalez leave", "body": "Update"}))

    def test_manager_unrelated_email_ok(self):
        self.assertNotIn("legal.hold", self.pre("google_mail__send_email", {
            "to": "charlie.szabo@ridgelinegear.com", "subject": "Warehouse safety training", "body": "Reminder."}))

    def test_slack_thread_reply_and_intake_post_blocked(self):
        self.assertIn("legal.hold", self.post("C001", "Hi Charlie, processing.", thread_ts="1744156800.001300"))
        self.assertIn("legal.hold", self.post("C001", "HFWA intake: Taylor Gonzalez, April 8-9"))
        self.assertIn("legal.hold", self.post("C005", "<@U022> FYI " + POST))

    def test_unrelated_post_ok(self):
        self.assertNotIn("legal.hold", self.post("C001", "Reminder: office closed Memorial Day."))

    def test_dm_blocked(self):
        self.assertIn("legal.hold", self.pre("slack__send_dm", {"user_id": "U022", "text": "Got it"}))
        self.assertIn("legal.hold", self.pre("slack__send_dm", {"user_id": "U026", "text": "Taylor Gonzalez legal"}))

    def test_calendar_blocked(self):
        self.assertIn("legal.hold", self.pre("google_calendar__create_event", {
            "summary": "Taylor Gonzalez HFWA return", "start": "2025-04-10"}))


class TestWrites(Base):
    def test_tracker_write_blocked(self):
        self.assertIn("legal.no_case_writes", self.pre("syntara__executePython", {"code": SAVE_TRACKER}))

    def test_other_file_ok(self):
        self.assertEqual(self.pre("syntara__writeFile", {"file_path": "/workdir/notes.txt", "content": "x"}), set())

    def test_blank_form_blocked(self):
        self.assertIn("files.blank_forms", self.pre("syntara__writeFile",
                                                    {"file_path": "/workdir/WH-381.pdf", "content": "x"}))

    def test_workbook_changed_finding(self):
        self.golden()
        self.edit("hfwa_balance_tracker.xlsx", "ws.cell(row=15, column=3).value = 16")
        self.assertIn("legal.workbooks_unchanged", self.done())

    def test_workbooks_untouched_ok(self):
        self.assertNotIn("legal.workbooks_unchanged", self.done())


class TestEmailScope(Base):
    def test_outside_hr_blocked(self):
        self.assertIn("email.hr_only", self.pre("google_mail__send_email",
                                                self.gc_email(cc="mark.rogers@ridgelinegear.com")))

    def test_hr_and_legal_ok(self):
        args = self.gc_email(cc="daniel.whitfield@ridgelinegear.com, marcus.webb@ridgelineholdings.com")
        self.assertNotIn("email.hr_only", self.pre("google_mail__send_email", args))


class TestSlackPhi(Base):
    def test_medical_in_other_channel_blocked(self):
        self.assertIn("slack.no_phi", self.post("C003", "Taylor Gonzalez hospitalization next week - legal review"))

    def test_no_medical_ok(self):
        self.assertNotIn("slack.no_phi", self.post("C003", "Taylor Gonzalez request escalated to legal review"))


class TestHousekeeping(Base):
    def test_move_p1_blocked(self):
        self.assertIn("mail.keep_in_inbox", self.pre("google_mail__move_emails",
                                                     {"email_ids": ["1"], "target_folder": "Sick Time"}))
        self.assertIn("mail.keep_in_inbox", self.pre("google_mail__delete_emails", {"email_ids": ["1"]}))

    def test_move_other_ok(self):
        self.assertEqual(self.pre("google_mail__move_emails", {"email_ids": ["2"], "target_folder": "Archive/2022"}),
                         set())

    def test_flags_required(self):
        self.did("google_mail__mark_emails", {"email_ids": ["1"], "is_read": True})
        probs = [p for r, p in self.done_all() if r == "mail.housekeeping"]
        self.assertTrue(any("important" in p for p in probs))
        self.assertTrue(any("id 33" in p for p in probs))
        self.assertFalse(any("not marked as read" in p and "id 1)" in p for p in probs))

    def test_moved_finding(self):
        self.golden()
        self.did("google_mail__move_emails", {"email_ids": ["1"], "target_folder": "Sick Time"})
        self.assertIn("mail.housekeeping", self.done())


class TestPlaceholders(Base):
    def test_placeholder_blocked(self):
        text = "LEGAL THREAT: Taylor Gonzalez, New Case, Leave Request - HFWA, [Brief Description] \u2014 do not reply"
        self.assertIn("comms.no_placeholders", self.post("C005", text))


if __name__ == "__main__":
    import unittest
    unittest.main()
