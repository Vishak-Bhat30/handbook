"""Blind unit tests for medical_pathfinder_billing_and_coding_bbf1a560 (built from SOP + seed data only)."""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase

T = "medical_pathfinder_billing_and_coding_bbf1a560"
P = "bbf1a560"
DUPES = ["BGI-39882091", "BGI-39667288", "BGI-31199221", "BGI-33991911", "BGI-36110292", "BGI-37918822"]
TKG = "Escalated to RCM Manager - 2026-04-09"
PAYER_BODY = ("Hello Popler,\n\nWe identified an overpayment from Bullion Gold Insurance (Payer ID B8475Q). The claims "
              "below were paid twice:\n\n- BGI-39882091: $350.00\n- BGI-39667288: $350.00\n- BGI-31199221: $350.00\n"
              "- BGI-33991911: $75.00\n- BGI-36110292: $75.00\n- BGI-37918822: $75.00\n\nTotal overpaid: $1,275.00\n\n"
              "Any excess will either be re-classed to yet unpaid claims for the same patient or processed for refund "
              "back to you, subject to approval. We will provide updates as the situation evolves.\n\nJill Mayfield")
JOE_BODY = ("Hi Joe,\n\nBullion Gold Insurance (B8475Q) will require a refund.\n\nProblematic claim IDs: BGI-39882091, "
            "BGI-39667288, BGI-31199221, BGI-33991911, BGI-36110292, BGI-37918822\n\nExact overpaid amount: $1,275.00\n\n"
            "Re-class to unpaid claims:\n- BGI-38399991: $350.00\n- BGI-40001965: $75.00\n\n"
            "Expected refund: $850.00\n\nJill")
CAL = {"summary": "Escalation Attempt - Jill - RCM Manager",
       "start": {"dateTime": "2026-04-09T13:30:00", "timeZone": "America/Chicago"},
       "end": {"dateTime": "2026-04-09T15:30:00", "timeZone": "America/Chicago"}}


def draft(to, body, bcc="mayj@pathfinder.com", subject="Overpayment", cc=None):
    a = {"to": to, "subject": subject, "body": body}
    if bcc:
        a["bcc"] = bcc
    if cc:
        a["cc"] = cc
    return a


def post(ch, text):
    return {"channel_id": ch, "text": text}


class Base(TaskCase):
    TASK = T

    def log_edit(self, tkg=TKG, cat=None, extra=""):
        cat_line = f"        row[2].value={cat!r}\n" if cat else ""
        self.edit("PBC_Escalation_Log.xlsx",
                  f"ids={DUPES!r}\nfor row in ws.iter_rows(min_row=2):\n    if row[0].value in ids:\n"
                  f"        row[4].value={tkg!r}\n{cat_line}" + extra)

    def golden(self):
        self.did("google_mail__save_draft", draft("popler.wen@bulliongoldinsurance.com", PAYER_BODY))
        self.did("google_mail__save_draft", draft("joem@pathfinder.com", JOE_BODY, subject="Refund case"))
        self.did("slack__post_message", post("C004", "Refund case - AA45175 - B8475Q"))
        self.did("slack__post_message", post("C003", "Refund case - AA45175 - B8475Q"))
        self.did("slack__post_message",
                 post("C001", "Escalation: 2026-04-09. Category: Operational. Payer: Bullion Gold Insurance."))
        self.did("google_calendar__create_event", CAL)
        self.log_edit()


class TestInitialAndGolden(Base):
    def test_initial_obligations(self):
        d = self.done()
        self.assertEqual(set(d), {f"{P}.comms.messages_sent", f"{P}.calendar", f"{P}.esc_log"})

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_financial_category(self):
        self.did("google_mail__save_draft", draft("popler.wen@bulliongoldinsurance.com", PAYER_BODY))
        self.did("google_mail__save_draft", draft("joem@pathfinder.com", JOE_BODY))
        self.did("slack__post_message", post("C004", "Refund case - AA45175 - B8475Q"))
        self.did("slack__post_message", post("C003", "Refund case - AA45175 - B8475Q. Please hold postings."))
        self.did("slack__post_message",
                 post("C001", "Escalation: 2026-04-09. Category: Financial. Payer: Bullion Gold Insurance."))
        self.did("google_calendar__create_event", CAL)
        self.log_edit(cat="Financial")
        self.assertEqual(self.done(), {})


class TestPayerDraft(Base):
    def test_ok(self):
        self.assertEqual(self.pre("google_mail__save_draft", draft("popler.wen@bulliongoldinsurance.com", PAYER_BODY)),
                         set())

    def test_missing_amounts(self):
        body = PAYER_BODY.replace(": $350.00", "")
        self.assertIn(f"{P}.comms.messages",
                      self.pre("google_mail__save_draft", draft("popler.wen@bulliongoldinsurance.com", body)))

    def test_amount_before_id_ok(self):
        body = PAYER_BODY
        for c, v in (("BGI-39882091", "350.00"), ("BGI-39667288", "350.00"), ("BGI-31199221", "350.00"),
                     ("BGI-33991911", "75.00"), ("BGI-36110292", "75.00"), ("BGI-37918822", "75.00")):
            body = body.replace(f"- {c}: ${v}", f"- ${v} paid twice on claim {c}")
        self.assertEqual(self.pre("google_mail__save_draft", draft("popler.wen@bulliongoldinsurance.com", body)),
                         set())

    def test_may_in_cc_not_bcc(self):
        a = draft("popler.wen@bulliongoldinsurance.com", PAYER_BODY, bcc=None, cc="mayj@pathfinder.com")
        self.assertIn(f"{P}.comms.messages", self.pre("google_mail__save_draft", a))

    def test_sending_blocked(self):
        got = self.pre("google_mail__send_email", draft("popler.wen@bulliongoldinsurance.com", PAYER_BODY))
        self.assertTrue({f"{P}.comms.messages", f"{P}.no_send"} <= got)

    def test_send_draft_blocked(self):
        self.assertIn(f"{P}.no_send", self.pre("google_mail__send_draft", {"draft_id": "3"}))


class TestJoeDraft(Base):
    def test_ok(self):
        self.assertEqual(self.pre("google_mail__save_draft", draft("joem@pathfinder.com", JOE_BODY)), set())

    def test_wrong_refund(self):
        body = JOE_BODY.replace("$850.00", "$1,275.00")
        self.assertIn(f"{P}.comms.messages", self.pre("google_mail__save_draft", draft("joem@pathfinder.com", body)))

    def test_wrong_reclass_amount(self):
        body = JOE_BODY.replace("BGI-40001965: $75.00", "BGI-40001965: $90.00")
        self.assertIn(f"{P}.comms.messages", self.pre("google_mail__save_draft", draft("joem@pathfinder.com", body)))

    def test_extra_recipient(self):
        a = draft("joem@pathfinder.com, jamies@pathfinder.com", JOE_BODY)
        self.assertIn(f"{P}.comms.messages", self.pre("google_mail__save_draft", a))


class TestSlack(Base):
    def test_refund_note_ok(self):
        self.assertEqual(self.pre("slack__post_message", post("C004", "Refund case - AA45175 - B8475Q")), set())

    def test_refund_note_wrong_text(self):
        self.assertIn(f"{P}.comms.messages",
                      self.pre("slack__post_message", post("C003", "Refund case for patient AA45175 (Bullion Gold)")))

    def test_refund_note_other_channel_not_vetted(self):
        self.assertEqual(self.pre("slack__post_message", post("C001", "Refund case - AA45175 - B8475Q")), set())

    def test_coders_note_missing_at_completion(self):
        self.did("slack__post_message", post("C003", "Refund case - AA45175 - B8475Q"))
        self.did("slack__post_message", post("C001", "Refund case - AA45175 - B8475Q"))
        msgs = [p for r, p in self.done_all() if r == f"{P}.comms.messages_sent"]
        self.assertTrue(any("#coders" in m for m in msgs))
        self.assertFalse(any("#billing-specs" in m for m in msgs))

    def test_escalation_template_ok(self):
        self.assertEqual(self.pre("slack__post_message", post(
            "C001", "Escalation: 2026-04-09. Category: Operational. Payer: Bullion Gold Insurance.")), set())

    def test_escalation_template_wrong_date(self):
        self.assertIn(f"{P}.comms.messages", self.pre("slack__post_message", post(
            "C001", "Escalation: 04/09/2026. Category: Operational. Payer: Bullion Gold Insurance.")))

    def test_escalation_template_placeholder(self):
        self.assertIn("comms.no_placeholders", self.pre("slack__post_message", post(
            "C001", "Escalation: 2026-04-09. Category: [Escalation Category]. Payer: Bullion Gold Insurance.")))


class TestPHI(Base):
    def test_name_blocked(self):
        self.assertIn(f"{P}.phi", self.pre("slack__post_message",
                                           post("C003", "Refund case - AA45175 - B8475Q (Hollie Stanton)")))

    def test_dob_blocked(self):
        body = JOE_BODY + "\nDOB 1960-09-07"
        self.assertIn(f"{P}.phi", self.pre("google_mail__save_draft", draft("joem@pathfinder.com", body)))

    def test_patient_id_ok(self):
        self.assertNotIn(f"{P}.phi", self.pre("slack__post_message", post("C003", "Refund case - AA45175 - B8475Q")))


class TestCalendar(Base):
    def test_title_ok(self):
        self.assertEqual(self.pre("google_calendar__create_event", CAL), set())

    def test_title_wrong(self):
        self.assertIn(f"{P}.calendar_title", self.pre("google_calendar__create_event",
                                                      {**CAL, "summary": "Escalation Attempt - Jill Mayfield"}))

    def test_duration_wrong_pre(self):
        bad = {**CAL, "end": {"dateTime": "2026-04-09T14:30:00", "timeZone": "America/Chicago"}}
        self.assertIn(f"{P}.calendar_title", self.pre("google_calendar__create_event", bad))

    def test_completion_ok_after_rename(self):
        self.did("google_calendar__create_event", {**CAL, "summary": "Follow-up escalation attempt"},
                 '{"status":"success","event":{"id":"e1","summary":"Follow-up escalation attempt",'
                 '"start":{"dateTime":"2026-04-09T13:30:00"},"end":{"dateTime":"2026-04-09T15:30:00"}}}')
        self.did("google_calendar__update_event", {"eventId": "e1", "summary": CAL["summary"]},
                 '{"status":"success","event":{"id":"e1","summary":"Escalation Attempt - Jill - RCM Manager",'
                 '"start":{"dateTime":"2026-04-09T13:30:00"},"end":{"dateTime":"2026-04-09T15:30:00"}}}')
        self.assertNotIn(f"{P}.calendar", self.done())

    def test_completion_deleted(self):
        self.did("google_calendar__create_event", CAL,
                 '{"status":"success","event":{"id":"e2","summary":"Escalation Attempt - Jill - RCM Manager",'
                 '"start":{"dateTime":"2026-04-09T13:30:00"},"end":{"dateTime":"2026-04-09T15:30:00"}}}')
        self.did("google_calendar__delete_event", {"eventId": "e2"}, '{"status":"success"}')
        self.assertIn(f"{P}.calendar", self.done())

    def test_completion_all_day(self):
        self.did("google_calendar__create_event", {"summary": CAL["summary"], "start": {"date": "2026-04-09"},
                                                   "end": {"date": "2026-04-10"}})
        self.assertIn(f"{P}.calendar", self.done())

    def test_completion_fixed_offset_ok(self):
        self.did("google_calendar__create_event", {"summary": CAL["summary"],
                                                   "start": {"dateTime": "2026-04-09T13:30:00-06:00"},
                                                   "end": {"dateTime": "2026-04-09T15:30:00-06:00"}})
        self.assertNotIn(f"{P}.calendar", self.done())

    def test_completion_wrong_day(self):
        self.did("google_calendar__create_event", {**CAL, "start": {"dateTime": "2026-04-10T09:00:00"},
                                                   "end": {"dateTime": "2026-04-10T11:00:00"}})
        self.assertIn(f"{P}.calendar", self.done())


class TestEscalationLog(Base):
    def test_ok(self):
        self.log_edit()
        self.assertNotIn(f"{P}.esc_log", self.done())

    def test_wrong_tkg(self):
        self.log_edit(tkg="Escalated to RCM Manager (Joe)")
        self.assertIn(f"{P}.esc_log", self.done())

    def test_critical_category(self):
        self.log_edit(cat="Critical")
        self.assertIn(f"{P}.esc_log", self.done())

    def test_reason_changed(self):
        self.log_edit(extra="for row in ws.iter_rows(min_row=2):\n    if row[0].value=='BGI-39882091':\n"
                            "        row[3].value='High Value Claim'\n")
        self.assertIn(f"{P}.esc_log", self.done())

    def test_duplicate_row(self):
        self.log_edit(extra=f"ws.append(['BGI-39882091','B8475Q','Operational','Payer Dispute',{TKG!r}])\n")
        self.assertIn(f"{P}.esc_log", self.done())

    def test_unrelated_row_changed(self):
        self.log_edit(extra="ws.cell(row=2, column=5).value='Closed'\n")
        self.assertIn(f"{P}.esc_log", self.done())

    def test_reclass_claim_row_allowed(self):
        self.log_edit(extra=f"ws.append(['BGI-38399991','B8475Q','Operational','Payer Dispute',{TKG!r}])\n")
        self.assertNotIn(f"{P}.esc_log", self.done())


class TestFiles(Base):
    def test_qa_queue_row(self):
        self.edit("PBC_QA_Queue.xlsx", "ws.append(['BGI-39882091','Refund','2026-04-09','Open'])")
        self.assertIn(f"{P}.unrequested_rows", self.done())

    def test_qa_queue_untouched(self):
        self.assertNotIn(f"{P}.unrequested_rows", self.done())

    def test_denial_row_edited(self):
        self.edit("PBC_Denial_Worklist.xlsx", "ws.cell(row=2, column=6).value='Resolved'")
        self.assertIn(f"{P}.denial_append_only", self.done())

    def test_reference_write_blocked(self):
        code = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/PBC_Fee_Schedule.xlsx')\nwb.save('/workdir/PBC_Fee_Schedule.xlsx')"
        self.assertIn(f"{P}.reference_files", self.pre("syntara__executePython", {"code": code}))

    def test_esc_log_write_allowed(self):
        code = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/PBC_Escalation_Log.xlsx')\nwb.save('/workdir/PBC_Escalation_Log.xlsx')"
        self.assertEqual(self.pre("syntara__executePython", {"code": code}), set())


if __name__ == "__main__":
    unittest.main()
