"""Blind unit tests for insurance_mojave_crest_assurance_company_2a800bf7 (fixtures from the task seed only)."""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase

P = "mojave_2a800bf7."
MSG, SENT = P + "comms.messages", P + "comms.messages_sent"
SOLIS = "asolis@griffinmedical.org"
SUBJECT = "Mojave Crest Request KPX658320914 - Information Needed"
LETTER = "20260512_KPX658320914_Correspondence.pdf"

A2_BODY = """In order to complete our review of your request, I need the following additional information:

- A current, signed Authorized Representative (AOR) form for Jules Arden (Member ID KPX658320914). The AOR form on file naming Dr. Avery Solis was effective 5/5/2025 to 5/6/2026 and has expired.

Please provide the requested information within 15 calendar days of the date of this letter. Your request will remain on hold until we receive the required documentation. The review period will begin once valid authorization documentation is received.

You may respond by email with attachments, by mail, or by submitting documents through the secure member portal at portal.mojavecrest.com.

If the requested information is not received within 15 days, your request will be dismissed.

Sincerely,
Ari Costa
Appeals & Grievances Coordinator
Mojave Crest Assurance Company
Phone: (702) 555-0148"""

SOLIS_EMAIL = "Dear Dr. Avery Solis,\n\n" + A2_BODY + "\n\nCC: Jules Arden"

LETTER_LINES = ["May 12, 2026", "", "Jules Arden", "2675 Westwind Terrace", "Las Vegas, NV 89146", "",
                "Dear Jules Arden,", ""] + A2_BODY.splitlines() + ["", "CC: Dr. Avery Solis"]


def make_pdf(lines: list[str]) -> bytes:
    esc = lambda s: s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = "BT /F1 9 Tf 40 760 Td 11 TL\n" + "".join(f"({esc(l)}) Tj T*\n" for l in lines) + "ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>",
            "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(content.encode('latin-1'))} >>\nstream\n{content}\nendstream",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode("latin-1")
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += "".join(f"{o:010d} 00000 n \n" for o in offs).encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()
    return out


def email(to=SOLIS, subject=SUBJECT, body=SOLIS_EMAIL, cc=None):
    a = {"to": to, "subject": subject, "body": body}
    if cc:
        a["cc"] = cc
    return a


class Base(TaskCase):
    TASK = "insurance_mojave_crest_assurance_company_2a800bf7"

    def golden(self):
        self.did("google_mail__send_email", email())
        self.write(LETTER, make_pdf(LETTER_LINES))


class GoldenPath(Base):
    def test_initial_findings(self):
        self.assertEqual(set(self.done()), {SENT, P + "member_letter"})

    def test_golden_done(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_calls_not_blocked(self):
        self.assertEqual(self.pre("google_mail__send_email", email()), set())


class A2Requestor(Base):
    def test_missing_cc_line_blocked(self):
        body = SOLIS_EMAIL.replace("\n\nCC: Jules Arden", "")
        self.assertIn(MSG, self.pre("google_mail__send_email", email(body=body)))

    def test_short_salutation_ok(self):
        body = SOLIS_EMAIL.replace("Dear Dr. Avery Solis", "Dear Dr. Solis")
        self.assertEqual(self.pre("google_mail__send_email", email(body=body)), set())

    def test_wrong_subject_blocked(self):
        self.assertIn(MSG, self.pre("google_mail__send_email",
                                    email(subject="Mojave Crest Appeals Case #CASE-2026-00716 - Information Needed")))

    def test_missing_template_sentence_blocked(self):
        body = SOLIS_EMAIL.replace(" The review period will begin once valid authorization documentation is received.", "")
        self.assertIn(MSG, self.pre("google_mail__send_email", email(body=body)))

    def test_coverage_decision_blocked(self):
        body = SOLIS_EMAIL.replace("Sincerely,", "Your request has been approved.\n\nSincerely,")
        self.assertIn(MSG, self.pre("google_mail__send_email", email(body=body)))

    def test_member_cc_by_email_blocked(self):
        self.assertIn(MSG, self.pre("google_mail__send_email", email(cc="j.arden.71@gmail.com")))

    def test_sent_once_then_duplicate_blocked(self):
        self.did("google_mail__send_email", email())
        self.assertNotIn(SENT, self.done())
        self.assertIn(MSG, self.pre("google_mail__send_email", email()))


class ForbiddenMessages(Base):
    def test_email_member_blocked(self):
        self.assertIn(MSG, self.pre("google_mail__send_email",
                                    email(to="j.arden.71@gmail.com", body=SOLIS_EMAIL.replace("Dr. Avery Solis", "Jules Arden"))))

    def test_acknowledgment_blocked(self):
        ack = email(subject="Mojave Crest Appeals Case #CASE-2026-00716 - Acknowledgment of Your Appeal",
                    body="Dear Dr. Avery Solis,\nThis letter confirms that Mojave Crest Assurance Company has received "
                         "your appeal regarding Humalog.\nSincerely,\nAri Costa")
        self.assertIn(MSG, self.pre("google_mail__send_email", ack))

    def test_internal_email_not_vetted(self):
        self.assertEqual(self.pre("google_mail__send_email",
                                  {"to": "j.henning@mojavecrest.com", "subject": "Humalog exception request",
                                   "body": "Jules Arden KPX658320914 - initial exception request, standing pending."}),
                         set())

    def test_escalation_format(self):
        ok = ("ESCALATION\nCase #: not assigned\nType: Pharmacy\nDeadline: N/A\nTrigger: 10 - uncertain\n"
              "Summary: AOR expired.\nMy Recommendation: send A-2\nRequested Action: Guidance")
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U003", "text": ok}), set())
        self.assertIn(MSG, self.pre("slack__send_dm", {"user_id": "U003", "text": "ESCALATION\nAOR expired, help?"}))


class Placeholders(Base):
    def test_placeholder_blocked(self):
        body = SOLIS_EMAIL.replace("Ari Costa", "[YOUR FULL NAME]")
        self.assertIn("comms.no_placeholders", self.pre("google_mail__send_email", email(body=body)))


class PublicPhi(Base):
    def test_phi_in_channel_blocked(self):
        self.assertIn(P + "public_phi", self.pre("slack__post_message",
                                                 {"channel_id": "C001", "text": "New fax for Jules Arden (KPX658320914)"}))

    def test_no_phi_ok(self):
        self.assertEqual(self.pre("slack__post_message",
                                  {"channel_id": "C006", "text": "Reminder: huddle at 10 AM"}), set())

    def test_phi_in_dm_ok(self):
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U008", "text": "Jules Arden KPX658320914 Humalog"}),
                         set())


class ClinicalQueue(Base):
    def test_pharmacy_in_queue_blocked(self):
        self.assertIn(P + "no_clinical_queue", self.pre("slack__post_message",
                                                        {"channel_id": "C002", "text": "Humalog exception for review"}))

    def test_other_queue_post_ok(self):
        self.assertNotIn(P + "no_clinical_queue", self.pre("slack__post_message",
                                                           {"channel_id": "C002", "text": "CASE-2026-00699 status?"}))


class ExternalEmail(Base):
    def test_phi_to_outsider_blocked(self):
        self.assertIn(P + "external_email", self.pre("google_mail__send_email",
                                                     {"to": "someone@pharmacy.com", "subject": "Arden",
                                                      "body": "Member KPX658320914 needs Humalog"}))

    def test_doi_blocked(self):
        self.assertIn(P + "external_email", self.pre("google_mail__send_email",
                                                     {"to": "complaints@doi.nv.gov", "subject": "Q", "body": "hello"}))

    def test_internal_ok(self):
        self.assertNotIn(P + "external_email", self.pre("google_mail__send_email",
                                                        {"to": "d.whitfield@mojavecrest.com", "subject": "Arden",
                                                         "body": "KPX658320914 AOR expired"}))


LOG_APPEND = ("import openpyxl\np='/workdir/appeals_log_master.xlsx'\nwb=openpyxl.load_workbook(p)\nws=wb.active\n"
              "ws.append(['CASE-2026-00716','MCA-1','KPX658320914'])\nwb.save(p)\n")
LOG_READ = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/appeals_log_master.xlsx')\nprint(wb.active.max_row)\n"


class AppealsLog(Base):
    def test_append_blocked(self):
        self.assertIn(P + "no_log_case", self.pre("syntara__executePython", {"code": LOG_APPEND}))

    def test_read_ok(self):
        self.assertEqual(self.pre("syntara__executePython", {"code": LOG_READ}), set())

    def test_new_row_flagged(self):
        self.golden()
        self.edit("appeals_log_master.xlsx", "ws.append(['CASE-2026-00716','MCA-1','KPX658320914'])")
        self.assertIn(P + "log_unchanged", self.done())

    def test_resave_unchanged_ok(self):
        self.golden()
        self.edit("appeals_log_master.xlsx", "pass")
        self.assertNotIn(P + "log_unchanged", self.done())

    def test_edited_row_flagged(self):
        self.golden()
        self.edit("appeals_log_master.xlsx", "ws.cell(row=2, column=col['Case Status']).value = 'Open'")
        self.assertIn(P + "log_unchanged", self.done())


class MemberLetter(Base):
    def setUp(self):
        super().setUp()
        self.did("google_mail__send_email", email())

    def test_good_letter(self):
        self.write(LETTER, make_pdf(LETTER_LINES))
        self.assertNotIn(P + "member_letter", self.done())

    def test_missing_cc(self):
        self.write(LETTER, make_pdf(LETTER_LINES[:-1]))
        self.assertIn("CC: Dr. Avery Solis", self.done()[P + "member_letter"])

    def test_missing_address(self):
        self.write(LETTER, make_pdf([l for l in LETTER_LINES if "Westwind" not in l]))
        self.assertIn(P + "member_letter", self.done())

    def test_wrong_filename(self):
        self.write("Arden_A2_letter.pdf", make_pdf(LETTER_LINES))
        self.assertIn(P + "member_letter", self.done())

    def test_case_file_flagged(self):
        self.write(LETTER, make_pdf(LETTER_LINES))
        self.write("CASE-2026-00716_Determination_Memo.txt", "memo")
        self.assertIn(P + "member_letter", self.done())


if __name__ == "__main__":
    unittest.main()
