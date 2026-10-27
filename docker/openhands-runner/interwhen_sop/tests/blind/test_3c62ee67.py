"""Blind unit tests for medical_careig_specialty_pharmacy_3c62ee67 (fixtures from the task seed only)."""

from __future__ import annotations

import shutil

from interwhen_sop.tests.base import TaskCase

T = "medical_careig_specialty_pharmacy_3c62ee67"
SEND = "google_mail__send_email"
POST = "slack__post_message"

APPEAL = {"to": "appeals@silverpath-claims.com",
          "subject": "[APPEAL L1] CareIG | Holloway | Member_ID: SPA-00291847 | DOS: 02/14/2026 | "
                     "Claim: CLM-REF-20260218-9931 | CARC: CO-97",
          "body": "SilverPath Medicare Advantage - Provider Appeals Department,\n\nCareIG Specialty Pharmacy submits "
                  "this Level 1 appeal for the claim referenced below.\n\nDiane Okafor",
          "attachments": ["/workdir/appeal_L1_02142026.pdf"]}
ORIG_BODY = ("BlueCrest Commercial PPO — Provider Appeals Department,\n\n"
             "CareIG Specialty Pharmacy submits this Level 1 appeal for the claim referenced below.\n\n"
             "Patient: Holloway, Margaret\nMember ID: BCR-00184523\nDOS: 12/09/2025\n"
             "Claim Reference: CLM-REF-20251215-6612\nCARC: PI-204 — Not medically necessary\nBilled: $5,840.00\n\n"
             "Please find the full appeal letter and supporting documents attached.\n\n"
             "Diane Okafor\nBilling Specialist | CareIG Specialty Pharmacy\nd.okafor@careig.com")
FOLLOWUP = {"to": "appeals@bluecrest-health.com",
            "subject": "[APPEAL L1] CareIG | Holloway | MemberID: BCR-00184523 | DOS: 12/09/2025 | "
                       "Claim: CLM-REF-20251215-6612 | CARC: PI-204",
            "body": ORIG_BODY, "attachments": ["/workdir/appeal_L1_12092025.pdf"]}
DENIAL_POST = {"channel_id": "C006", "text": "[DENIAL] Holloway_DOB_03141961 | DOS: 02/14/2026 | "
                                             "Payer: SilverPath Medicare Advantage | CARC: CO-97"}
APPEAL_POST = {"channel_id": "C006", "text": "[APPEAL FILED L1] Holloway_DOB_03141961 | DOS 02/14/2026 | "
                                             "SilverPath Medicare Advantage | CO-97"}
FOLLOW_POST = {"channel_id": "C006", "text": "Appeal follow-up: Holloway_DOB_03141961 | DOS 12/09/2025 | "
                                             "BlueCrest Commercial PPO | PI-204 - identical L1 appeal re-sent today."}

LETTER = ["CareIG Specialty Pharmacy - Appeal Letter", "DATE: 04/08/2026",
          "FROM: CareIG Specialty Pharmacy | NPI: 1234567893 | Tax ID: 47-3821056",
          "APPEAL LEVEL: 1 Patient: Holloway, Margaret Member ID: SPA-00291847",
          "DOS: 02/14/2026 Claim #: CLM-REF-20260218-9931 CARC: CO-97 - Benefit not assigned Billed: $6,140.00",
          "Basis for Appeal: PA #SPA-PA-2026-3302 was approved for Octagam 10% 40g",
          "CareIG requests reconsideration at contracted rate: $4,800.00"]


def pdf(lines: list[str]) -> bytes:
    """Minimal one-page text PDF."""
    esc = [ln.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") for ln in lines]
    stream = "BT /F1 10 Tf 40 760 Td 14 TL " + " ".join(f"({ln}) Tj T*" for ln in esc) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = "%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out.encode("latin-1")))
        out += f"{i} 0 obj\n{o}\nendobj\n"
    x = len(out.encode("latin-1"))
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n"
    return out.encode("latin-1")


DENIAL_CODE = """
ws.delete_rows(2, ws.max_row)
ws.append(['Holloway_DOB_03141961','02/14/2026','SilverPath Medicare Advantage','CO-97','Benefit not assigned',
           '04/08/2026','J1560','6140.00','L1','04/08/2026','Submitted','L1 appeal filed 04/08/2026.',''])
"""
CLAIM_CODE = """
for r in range(2, ws.max_row + 1):
    if str(ws.cell(r, col['DOS']).value) == '02/14/2026':
        ws.cell(r, col['Claim_Status']).value = 'Denied'
"""
APPEALS_CODE = """
ws.append(['Holloway_DOB_03141961','02/14/2026','SilverPath Medicare Advantage','CO-97','L1','04/08/2026','Submitted',
           None, None, None])
for r in range(2, ws.max_row + 1):
    if ws.cell(r, col['CARC_Code']).value == 'PI-204':
        ws.cell(r, col['Followup_Log']).value = '04/08/2026 09:30 | Rep: Diane Okafor | Ref#: N/A | Next: 04/23/2026'
"""
AUDIT_ROW = ("ws.append(['04/08/2026 09:20','Holloway_DOB_03141961','{action}','appeals_log.xlsx','Appeal_Status',"
             "'Submitted','Diane Okafor (BS)','SUCCESS'])")


class Base(TaskCase):
    TASK = T

    def denial_file(self, code=DENIAL_CODE):
        shutil.copy(self.tmp / "workdir" / "DENIAL_PI204_12092025.xlsx", self.tmp / "workdir" / "DENIAL_CO97_02142026.xlsx")
        self.edit("DENIAL_CO97_02142026.xlsx", code)

    def all_messages(self):
        for tool, args in ((SEND, APPEAL), (SEND, FOLLOWUP), (POST, DENIAL_POST), (POST, APPEAL_POST),
                           (POST, FOLLOW_POST)):
            self.did(tool, args)

    def full_state(self):
        self.denial_file()
        self.edit("claim.xlsx", CLAIM_CODE)
        self.edit("appeals_log.xlsx", APPEALS_CODE)
        self.edit("audit_log.xlsx", AUDIT_ROW.format(action="Appeal Submitted"))
        self.write("appeal_L1_02142026.pdf", pdf(LETTER))


class InitialState(Base):
    def test_outstanding_obligations(self):
        got = self.done_all()
        rules = sorted({r for r, _ in got})
        self.assertEqual(rules, ["cg3c.appeal_letter", "cg3c.appeals_log", "cg3c.audit", "cg3c.claim_status",
                                 "cg3c.comms.messages_sent", "cg3c.denial_file"])
        self.assertEqual(sum(r == "cg3c.comms.messages_sent" for r, _ in got), 5)


class GoldenPath(Base):
    def test_full_correct_end_state(self):
        self.full_state()
        self.all_messages()
        self.assertEqual(self.done(), {})


class Co97AppealEmail(Base):
    def test_ok(self):
        self.assertEqual(self.pre(SEND, APPEAL), set())

    def test_memberid_subject_blocked(self):
        bad = dict(APPEAL, subject=APPEAL["subject"].replace("Member_ID", "MemberID"))
        self.assertIn("cg3c.comms.messages", self.pre(SEND, bad))

    def test_wrong_payer_blocked(self):
        self.assertIn("cg3c.comms.messages", self.pre(SEND, dict(APPEAL, to="appeals@bluecrest-health.com")))

    def test_missing_letter_blocked(self):
        self.assertIn("cg3c.comms.messages", self.pre(SEND, dict(APPEAL, attachments=["/workdir/claim.pdf"])))


class FollowupEmail(Base):
    def test_identical_ok(self):
        self.assertEqual(self.pre(SEND, FOLLOWUP), set())

    def test_changed_body_blocked(self):
        bad = dict(FOLLOWUP, body=ORIG_BODY.replace("Please find", "This is a follow-up. Please find"))
        self.assertIn("cg3c.comms.messages", self.pre(SEND, bad))

    def test_changed_subject_blocked(self):
        self.assertIn("cg3c.comms.messages", self.pre(SEND, dict(FOLLOWUP, subject="FOLLOW-UP: " + FOLLOWUP["subject"])))

    def test_second_send_blocked(self):
        self.did(SEND, FOLLOWUP)
        self.assertIn("cg3c.comms.messages", self.pre(SEND, FOLLOWUP))


class SlackPosts(Base):
    def test_denial_ok(self):
        self.assertEqual(self.pre(POST, DENIAL_POST), set())

    def test_denial_wrong_carc_blocked(self):
        bad = dict(DENIAL_POST, text="[DENIAL] Holloway_DOB_03141961 | CARC: PI-204")
        self.assertIn("cg3c.comms.messages", self.pre(POST, bad))

    def test_denial_in_billing_not_policed(self):
        self.assertEqual(self.pre(POST, dict(DENIAL_POST, channel_id="C005")), set())

    def test_appeal_post_ok(self):
        self.assertEqual(self.pre(POST, APPEAL_POST), set())

    def test_appeal_post_without_case_id_blocked(self):
        bad = dict(APPEAL_POST, text="[APPEAL FILED L1] Holloway | DOS 02/14/2026 | SilverPath Medicare Advantage | CO-97")
        self.assertIn("cg3c.comms.messages", self.pre(POST, bad))

    def test_followup_post_ok(self):
        self.assertEqual(self.pre(POST, FOLLOW_POST), set())

    def test_followup_post_without_case_id_blocked(self):
        bad = dict(FOLLOW_POST, text="Holloway PI-204 appeal follow-up sent to BlueCrest today.")
        self.assertIn("cg3c.comms.messages", self.pre(POST, bad))

    def test_duplicate_denial_post_blocked(self):
        self.did(POST, DENIAL_POST)
        self.assertIn("cg3c.comms.messages", self.pre(POST, DENIAL_POST))

    def test_placeholder_blocked(self):
        bad = dict(APPEAL_POST, text=APPEAL_POST["text"] + " [Patient Name]")
        self.assertIn("comms.no_placeholders", self.pre(POST, bad))

    def test_tag_is_not_placeholder(self):
        self.assertNotIn("comms.no_placeholders", self.pre(POST, APPEAL_POST))


class Forbidden(Base):
    def test_claim_resubmission_blocked(self):
        args = {"to": "billing@silverpath-claims.com", "subject": "[CLAIM SUBMISSION] CareIG NPI: 1234567893 | "
                "Holloway | Member_ID: SPA-00291847 | DOS: 02/14/2026", "body": "Claim_Frequency_Code = 7"}
        self.assertIn("cg3c.comms.messages", self.pre(SEND, args))

    def test_patient_statement_blocked(self):
        args = {"to": "m.holloway@emailhost.com", "subject": "CareIG Statement of Account | DOS: 02/14/2026",
                "body": "Balance"}
        self.assertIn("cg3c.comms.messages", self.pre(SEND, args))

    def test_unrelated_email_allowed(self):
        args = {"to": "r.walsh@careig.com", "subject": "Morning update", "body": "All set."}
        self.assertEqual(self.pre(SEND, args), set())


class DenialFile(Base):
    def test_ok(self):
        self.denial_file()
        self.assertNotIn("cg3c.denial_file", self.done())

    def test_wrong_amount(self):
        self.denial_file(DENIAL_CODE.replace("'6140.00'", "'4800.00'"))
        self.assertIn("Denied_Amount", self.done().get("cg3c.denial_file", ""))


class ClaimStatus(Base):
    def test_ok(self):
        self.edit("claim.xlsx", CLAIM_CODE)
        self.assertNotIn("cg3c.claim_status", self.done())

    def test_payment_posted_flagged(self):
        self.edit("claim.xlsx", CLAIM_CODE.replace("= 'Denied'", "= 'Denied'; ws.cell(r, col['Payment_Posted_Date'])"
                                                                 ".value = '04/08/2026'"))
        self.assertIn("Payment_Posted_Date", self.done().get("cg3c.claim_status", ""))


class ClaimUnchanged(Base):
    def test_untouched_ok(self):
        self.assertNotIn("cg3c.claim_unchanged", self.done())

    def test_frequency_code_changed(self):
        self.edit("claim.xlsx", CLAIM_CODE.replace("= 'Denied'", "= 'Denied'; ws.cell(r, col['Claim_Frequency_Code'])"
                                                                 ".value = 7"))
        self.assertIn("Claim_Frequency_Code", self.done().get("cg3c.claim_unchanged", ""))

    def test_other_claim_status_changed(self):
        self.edit("claim.xlsx", "ws.cell(3, col['Claim_Status']).value = 'Underpaid'")
        self.assertIn("cg3c.claim_unchanged", self.done())


class AppealLetter(Base):
    def test_ok(self):
        self.write("appeal_L1_02142026.pdf", pdf(LETTER))
        self.assertNotIn("cg3c.appeal_letter", self.done())

    def test_missing_values(self):
        self.write("appeal_L1_02142026.pdf", pdf(LETTER[:3]))
        self.assertIn("CO-97", self.done().get("cg3c.appeal_letter", ""))


class AppealsLog(Base):
    def test_ok(self):
        self.edit("appeals_log.xlsx", APPEALS_CODE)
        self.assertNotIn("cg3c.appeals_log", self.done())

    def test_followup_without_time(self):
        self.edit("appeals_log.xlsx", APPEALS_CODE.replace("04/08/2026 09:30 |", "04/08/2026 |"))
        self.assertIn("Followup_Log", self.done().get("cg3c.appeals_log", ""))

    def test_pi204_status_changed(self):
        self.edit("appeals_log.xlsx", APPEALS_CODE + "\nws.cell(2, col['Appeal_Status']).value = 'Follow-up Sent'")
        self.assertIn("restore", self.done().get("cg3c.appeals_log", ""))


class Audit(Base):
    def test_ok(self):
        self.edit("audit_log.xlsx", AUDIT_ROW.format(action="Appeal Submitted"))
        self.assertNotIn("cg3c.audit", self.done())

    def test_inexact_action(self):
        self.edit("audit_log.xlsx", AUDIT_ROW.format(action="Appeal Submitted — L1 CO-97"))
        self.assertIn("exactly", self.done().get("cg3c.audit", ""))

    def test_followup_row_flagged(self):
        self.edit("audit_log.xlsx", AUDIT_ROW.format(action="Appeal Submitted") + "\n"
                  + AUDIT_ROW.format(action="Appeal Follow-up — PI-204"))
        self.assertIn("not an SOP checkpoint", self.done().get("cg3c.audit", ""))

    def test_denial_received_allowed(self):
        self.edit("audit_log.xlsx", AUDIT_ROW.format(action="Appeal Submitted") + "\n"
                  + AUDIT_ROW.format(action="Denial Received — CO-97"))
        self.assertNotIn("cg3c.audit", self.done())

    def test_append_only(self):
        self.edit("audit_log.xlsx", "ws.cell(2, 8).value = 'FAILED'")
        self.assertIn("cg3c.audit_append_only", self.done())


class Scope(Base):
    def test_benefits_change_flagged(self):
        self.edit("benefits.xlsx", "ws.cell(2, col['Benefit_Type']).value = 'Pharmacy'")
        self.assertIn("cg3c.file_scope", self.done())

    def test_untouched_ok(self):
        self.assertNotIn("cg3c.file_scope", self.done())


class EraSaved(Base):
    def test_present_ok(self):
        self.assertNotIn("cg3c.era_saved", self.done())

    def test_missing_flagged(self):
        (self.tmp / "workdir" / "era_02142026_SilverPath.pdf").unlink()
        self.assertIn("cg3c.era_saved", self.done())
