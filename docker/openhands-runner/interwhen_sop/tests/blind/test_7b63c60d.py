"""Blind unit tests for logistics_prairie_star_creamery_7b63c60d verifiers (seed data only)."""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase

LOG = "inbound_receiving_log.xlsx"
SUBJ = "P2 – Compound Event – 2026-05-20-001 – 2026-05-20"
BODY = ("Manifest number: 2026-05-20-001.\nTemperature readings (front/middle/rear): -6.0°F / -4.5°F / -7.5°F. "
        "Warmest -4.5°F rounds to -4°F: Tier 3.\nVariance: SC-003 -6 cases (-1.25%), Moderate.\n"
        "Product disposition: quarantined to H-Q.\nAction required: Director assessment required.")
POST = ("P2 escalation. Compound. Manifest/Reference 2026-05-20-001. Detail: Tier 3 temp (-6.0/-4.5/-7.5°F) plus "
        "Moderate variance (SC-003 short 6 cases, -1.25%). Escalated to Director of Supply Chain. Incident report: "
        "awaiting director decision. Action required: Director assessment; product held in H-Q.")
GOOD_ROW = ("vals={6:24,7:474,8:-6.0,9:-4.5,10:-7.5,11:-6,12:'A-20260519-01',13:'None',"
            "14:'Quarantined – H-Q pending Director assessment',15:'P2 – Compound event.'}\n"
            "for c,v in vals.items(): ws.cell(row=2,column=c,value=v)")


def email(**kw):
    args = {"to": "daniel.reyes@prairiestar.com", "cc": "carlos.mendoza@prairiestar.com, jacob.patel@prairiestar.com",
            "subject": SUBJ, "body": BODY}
    args.update(kw)
    return args


def post(text=POST, channel="C002"):
    return {"channel_id": channel, "text": text}


class Base(TaskCase):
    TASK = "logistics_prairie_star_creamery_7b63c60d"

    def problems(self, rule):
        return " | ".join(p for r, p in self.done_all() if r == rule)

    def finish_all(self):
        self.edit(LOG, GOOD_ROW)
        self.did("google_mail__send_email", email())
        self.did("slack__post_message", post())


class TestGolden(Base):
    def test_initial_obligations(self):
        rules = {r for r, _ in self.done_all()}
        self.assertEqual(rules, {"receipt.messages_sent", "receipt.receiving_log"})

    def test_golden_path(self):
        self.finish_all()
        self.assertEqual(self.done(), {})


class TestCompoundEmail(Base):
    def test_good_email_passes(self):
        self.assertEqual(self.pre("google_mail__send_email", email()), set())

    def test_wrong_subject_blocked(self):
        self.assertIn("receipt.messages", self.pre("google_mail__send_email",
                                                   email(subject="P3 Update – Manifest 2026-05-20-001")))

    def test_missing_planner_cc_blocked(self):
        self.assertIn("receipt.messages", self.pre("google_mail__send_email",
                                                   email(cc="carlos.mendoza@prairiestar.com")))

    def test_missing_fields_blocked(self):
        self.assertIn("receipt.messages", self.pre("google_mail__send_email",
                                                   email(body="Manifest 2026-05-20-001 has a compound event.")))

    def test_separate_variance_email_blocked(self):
        args = {"to": "jacob.patel@prairiestar.com", "cc": "carlos.mendoza@prairiestar.com",
                "subject": "P3 – Variance Notification – 2026-05-20-001 – 2026-05-20", "body": "Short 6 cases."}
        self.assertIn("receipt.messages", self.pre("google_mail__send_email", args))

    def test_unrelated_email_ignored(self):
        args = {"to": "brandon.keller@prairiestar.com", "subject": "Routes", "body": "Any holds tomorrow?"}
        self.assertEqual(self.pre("google_mail__send_email", args), set())

    def test_second_email_blocked(self):
        self.did("google_mail__send_email", email())
        self.assertIn("receipt.messages", self.pre("google_mail__send_email", email()))

    def test_completion_requires_email(self):
        self.edit(LOG, GOOD_ROW)
        self.did("slack__post_message", post())
        self.assertIn("compound-event email", self.done().get("receipt.messages_sent", ""))


class TestEscalationPost(Base):
    def test_good_post_passes(self):
        self.assertEqual(self.pre("slack__post_message", post()), set())

    def test_missing_status_blocked(self):
        self.assertIn("receipt.messages", self.pre("slack__post_message",
                                                   post(POST.replace("awaiting director decision", "pending"))))

    def test_missing_prefix_blocked(self):
        self.assertIn("receipt.messages", self.pre("slack__post_message",
                                                   post(POST.replace("P2 escalation.", "Escalation:"))))

    def test_other_channel_not_captured(self):
        txt = "@a.nguyen 2026-05-20-001: P2 compound event. Hold all 474 cases in H-Q pending Director decision."
        self.assertEqual(self.pre("slack__post_message", post(txt, "C001")), set())

    def test_completion_requires_post(self):
        self.edit(LOG, GOOD_ROW)
        self.did("google_mail__send_email", email())
        self.assertIn("#dc-escalations", self.done().get("receipt.messages_sent", ""))


class TestCommsGuards(Base):
    def test_placeholder_blocked(self):
        self.assertIn("comms.no_placeholders", self.pre("google_mail__send_email", email(body=BODY + " [Date]")))

    def test_no_placeholder_passes(self):
        self.assertNotIn("comms.no_placeholders", self.pre("google_mail__send_email", email()))

    def test_here_blocked(self):
        self.assertIn("comms.no_channel_mention", self.pre("slack__post_message", post("@here " + POST)))

    def test_mention_person_ok(self):
        self.assertNotIn("comms.no_channel_mention", self.pre("slack__post_message", post("@c.mendoza " + POST)))

    def test_putaway_direction_blocked(self):
        txt = "@a.nguyen Manifest 2026-05-20-001 accepted. Proceed with put-away to H-A."
        self.assertIn("receipt.no_putaway", self.pre("slack__post_message", post(txt, "C001")))

    def test_hold_instruction_ok(self):
        txt = "@a.nguyen Manifest 2026-05-20-001: do not put away. Hold all 474 cases in H-Q pending Director decision."
        self.assertEqual(self.pre("slack__post_message", post(txt, "C001")), set())


class TestFiles(Base):
    def test_pdf_write_blocked(self):
        self.assertIn("files.read_only", self.pre("syntara__writeFile",
                                                  {"file_path": "/workdir/2026-05-20-001.pdf", "content": "x"}))

    def test_log_write_allowed(self):
        code = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/inbound_receiving_log.xlsx')\nwb.save('/workdir/inbound_receiving_log.xlsx')"
        self.assertEqual(self.pre("syntara__executePython", {"code": code}), set())

    def test_new_workbook_flagged(self):
        self.finish_all()
        self.edit(LOG, "wb.save(path.replace('inbound_receiving_log', 'my_tracker'))")
        self.assertIn("files.no_new_workbooks", self.done())

    def test_no_new_workbook_ok(self):
        self.finish_all()
        self.assertNotIn("files.no_new_workbooks", self.done())


class TestReceivingLog(Base):
    def test_good_row_ok(self):
        self.finish_all()
        self.assertNotIn("receipt.receiving_log", self.done())

    def test_closed_status_flagged(self):
        self.finish_all()
        self.edit(LOG, "ws.cell(row=2,column=15,value='Closed – Accepted')")
        self.assertIn("P2 – Compound event.", self.problems("receipt.receiving_log"))

    def test_status_with_extra_text_ok(self):
        self.finish_all()
        self.edit(LOG, "ws.cell(row=2,column=15,value='P2 - Compound event. Awaiting director decision')")
        self.assertNotIn("receipt.receiving_log", self.done())

    def test_positive_variance_flagged(self):
        self.finish_all()
        self.edit(LOG, "ws.cell(row=2,column=11,value=6)")
        self.assertIn("Variance", self.problems("receipt.receiving_log"))

    def test_wrong_temp_flagged(self):
        self.finish_all()
        self.edit(LOG, "ws.cell(row=2,column=9,value=-4)")
        self.assertIn("Temp Reading", self.problems("receipt.receiving_log"))

    def test_accept_disposition_flagged(self):
        self.finish_all()
        self.edit(LOG, "ws.cell(row=2,column=14,value='Accepted – put away H-A')")
        self.assertIn("Disposition", self.problems("receipt.receiving_log"))

    def test_appended_row_flagged(self):
        self.finish_all()
        self.edit(LOG, "ws.append(['20 May 2026','2026-05-20-001','Waco',24,480,24,474])")
        self.assertIn("exactly one row", self.problems("receipt.receiving_log"))


if __name__ == "__main__":
    unittest.main()
