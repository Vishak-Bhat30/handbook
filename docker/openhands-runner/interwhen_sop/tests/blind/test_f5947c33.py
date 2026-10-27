"""Blind unit tests for medical_careig_specialty_pharmacy_f5947c33 (seed data + SOP only)."""

import zipfile

from interwhen_sop.tests.base import TaskCase

WEBB, ROD = "Webb_03151968", "Rodriguez_07221975"
SEND, POST = "google_mail__send_email", "slack__post_message"
TEAM, ALERTS = "C001", "C003"
PA_SUBJ = "[PA REQUEST] CareIG | Webb | MemberID: BCX-447821055 | Drug: Gammagard Liquid 10% | Dose: 35g | Dx: D83.9"
PA_ATT = [f"/workdir/{WEBB}/{f}" for f in ("pa_form_BlueCrossPremier.pdf", "lmn_DrVasquez.pdf",
                                           "igglevel_09292025.pdf", "progress_note_01202026.pdf")]
FORM_POST = f"[FORMULARY ISSUE] {WEBB} | Drug: Octagam | Payer: BlueCross Premier"
PA_POST = f"[PA SUBMITTED] {WEBB} | Payer: BlueCross Premier | Drug: Gammagard Liquid 10%"
HOLD_POST = f"[PA HOLD] {WEBB} — invalid: igglevel_09292025.pdf"
UNREACH_POST = f"[UNREACHABLE] {ROD} — 3 failed attempts."
T1_SUBJ = f"Unable to Contact Patient | CASE_ID: {ROD}"
T1_BODY = ("Dear Dr. Robert Cho,\n\nWe received a referral for Carmen Rodriguez (DOB: 07221975).\n"
           "After 3 contact attempts, we have been unable to reach the patient\nat the number on file: (555) 618-9043.\n"
           "Attempt 1: 2026-03-25 10:15 — Voicemail\nAttempt 2: 2026-03-26 14:30 — No Answer\n"
           "Attempt 3: 2026-03-28 09:00 — Voicemail\nPlease provide an alternate contact or assist in connecting the "
           "patient\nwith our team. We cannot proceed until contact is established.\n"
           "Jake Morrow — CareIG Specialty Pharmacy, Intake")


class Case(TaskCase):
    TASK = "medical_careig_specialty_pharmacy_f5947c33"

    def extract(self):
        for z in (WEBB, ROD):
            with zipfile.ZipFile(self.tmp / "workdir" / f"{z}.zip") as f:
                f.extractall(self.tmp / "workdir")

    def substitute(self, drug="Gammagard Liquid 10%", dose=35):
        self.edit(f"{WEBB}/intake.xlsx", f"ws.cell(2, col['Drug_Name']).value = {drug!r}\n"
                                         f"ws.cell(2, col['Drug_Dose_Grams']).value = {dose!r}")

    def audit(self, case, *rows):
        self.edit(f"{case}/audit_log.xlsx", "".join(f"ws.append({list(r)!r})\n" for r in rows))

    def auth(self, sub="2026-03-30", status="Pending", fu="2026-03-30"):
        self.edit(f"{WEBB}/auth.xlsx", "row = [None] * len(hdr)\n"
                                       f"row[col['PA_Submission_Date'] - 1] = {sub!r}\n"
                                       f"row[col['PA_Status'] - 1] = {status!r}\n"
                                       f"row[col['Last_Followup_Date'] - 1] = {fu!r}\n"
                                       "ws.append(row)")

    def common_done(self):
        self.did(POST, {"channel_id": TEAM, "text": FORM_POST})
        self.did(POST, {"channel_id": ALERTS, "text": UNREACH_POST})
        self.did(SEND, {"to": "rcho@greenmedclinic.org", "subject": T1_SUBJ, "body": T1_BODY})

    def send_pa(self):
        self.did(SEND, {"to": "pa.submissions@bcpremier.com", "subject": PA_SUBJ, "body": "PA packet attached.",
                        "attachments": PA_ATT})


class TestInitial(Case):
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {"comms.messages_sent", "webb.formulary_substitution", "webb.pa_outcome"})


class TestMessages(Case):
    def test_formulary_post(self):
        self.assertEqual(self.pre(POST, {"channel_id": TEAM, "text": FORM_POST}), set())
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": ALERTS, "text": FORM_POST}))
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": TEAM, "text": f"[FORMULARY ISSUE] {WEBB}"}))

    def test_pa_email(self):
        self.assertEqual(self.pre(SEND, {"to": "pa.submissions@bcpremier.com", "subject": PA_SUBJ, "body": "x",
                                         "attachments": PA_ATT}), set())
        octagam = PA_SUBJ.replace("Gammagard Liquid 10%", "Octagam").replace("35g", "40g")
        self.assertIn("comms.messages", self.pre(SEND, {"to": "pa.submissions@bcpremier.com", "subject": octagam,
                                                        "body": "x", "attachments": PA_ATT}))
        self.assertIn("comms.messages", self.pre(SEND, {"to": "pa.submissions@bcpremier.com", "subject": PA_SUBJ,
                                                        "body": "x", "attachments": PA_ATT[:2]}))

    def test_pa_email_blocked_after_hold(self):
        self.did(POST, {"channel_id": ALERTS, "text": HOLD_POST})
        self.assertIn("comms.messages", self.pre(SEND, {"to": "pa.submissions@bcpremier.com", "subject": PA_SUBJ,
                                                        "body": "x", "attachments": PA_ATT}))

    def test_pa_submitted_post_only_after_pa(self):
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": TEAM, "text": PA_POST}))
        self.send_pa()
        self.assertEqual(self.pre(POST, {"channel_id": TEAM, "text": PA_POST}), set())
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": ALERTS, "text": PA_POST}))

    def test_pa_hold_post(self):
        self.assertEqual(self.pre(POST, {"channel_id": ALERTS, "text": HOLD_POST}), set())
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": TEAM, "text": HOLD_POST}))

    def test_unreachable_post(self):
        self.assertEqual(self.pre(POST, {"channel_id": ALERTS, "text": UNREACH_POST}), set())
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": TEAM, "text": UNREACH_POST}))

    def test_template1(self):
        ok = {"to": "rcho@greenmedclinic.org", "subject": T1_SUBJ, "body": T1_BODY}
        self.assertEqual(self.pre(SEND, ok), set())
        self.assertIn("comms.messages", self.pre(SEND, {**ok, "body": T1_BODY.replace("Attempt 2", "Attempt")}))
        self.assertIn("comms.messages", self.pre(SEND, {**ok, "cc": "compliance@careig.com"}))
        self.assertIn("comms.messages", self.pre(SEND, {**ok, "subject": "Unable to reach patient Rodriguez"}))

    def test_rodriguez_do_not_proceed(self):
        self.assertIn("comms.messages", self.pre(SEND, {"to": "c.rodriguez75@webmail.net", "subject":
                                                        "CareIG — Consent Form Required | Rodriguez", "body": "x"}))
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": TEAM, "text": f"[BVS ASSIGNED] {ROD} | Payer: "
                                                        "MedPlus Health | Drug: Privigen | Dose: 30g"}))
        self.assertIn("comms.messages", self.pre(SEND, {"to": "pa@medplushealth.com", "subject": "PA", "body": "x"}))

    def test_placeholders(self):
        self.assertIn("comms.no_placeholders", self.pre(POST, {"channel_id": ALERTS, "text":
                                                               f"[UNREACHABLE] {ROD} — 3 failed attempts. [Your Name]"}))
        self.assertNotIn("comms.no_placeholders", self.pre(POST, {"channel_id": TEAM, "text": FORM_POST}))

    def test_messages_sent_done(self):
        self.common_done()
        self.assertNotIn("comms.messages_sent", self.done())


class TestWorkbooks(Case):
    def setUp(self):
        super().setUp()
        self.extract()

    def test_formulary_substitution(self):
        self.assertIn("webb.formulary_substitution", self.done())
        self.substitute(dose=40)
        self.assertIn("webb.formulary_substitution", self.done())
        self.substitute()
        self.assertNotIn("webb.formulary_substitution", self.done())

    def test_pa_outcome(self):
        self.assertIn("webb.pa_outcome", self.done())
        self.did(POST, {"channel_id": ALERTS, "text": HOLD_POST})
        self.assertNotIn("webb.pa_outcome", self.done())

    def test_auth_after_pa(self):
        self.send_pa()
        self.assertIn("webb.auth", self.done())
        self.auth(sub="03/30/2026")
        self.assertIn("webb.auth", self.done())

    def test_auth_ok(self):
        self.send_pa()
        self.auth()
        self.assertNotIn("webb.auth", self.done())

    def test_auth_on_hold_shows_no_submission(self):
        self.did(POST, {"channel_id": ALERTS, "text": HOLD_POST})
        self.auth()
        self.assertIn("webb.auth", self.done())

    def test_audit_pa_submitted(self):
        self.send_pa()
        self.assertIn("webb.audit", self.done())
        self.audit(WEBB, ["2026-03-30", WEBB, "PA Submitted", "auth.xlsx", "PA_Status", "Pending", "J. Morrow",
                          "SUCCESS"])
        self.assertNotIn("webb.audit", self.done())

    def test_audit_unrequested_row(self):
        self.audit(WEBB, ["2026-03-30", WEBB, "Drug Substitution", "intake.xlsx", "Drug_Name",
                          "Gammagard Liquid 10%", "Jake Morrow", "SUCCESS"])
        self.assertIn("webb.audit", self.done())

    def test_audit_pa_row_without_pa(self):
        self.audit(WEBB, ["2026-03-30", WEBB, "PA Submitted", "auth.xlsx", "PA_Status", "Pending", "J. Morrow",
                          "SUCCESS"])
        self.assertIn("webb.audit", self.done())

    def test_audit_append_only(self):
        self.edit(f"{WEBB}/audit_log.xlsx", "ws.cell(3, 8).value = 'FAILED'")
        self.assertIn("webb.audit", self.done())

    def test_audit_hold(self):
        self.did(POST, {"channel_id": ALERTS, "text": HOLD_POST})
        self.audit(WEBB, ["2026-03-30", WEBB, "Stop Protocol", "N/A", "N/A", "N/A", "Jake Morrow",
                          "STOP — IgG too old"])
        self.assertIn("webb.audit", self.done())

    def test_audit_hold_ok(self):
        self.did(POST, {"channel_id": ALERTS, "text": HOLD_POST})
        self.audit(WEBB, ["2026-03-30", WEBB, "Stop Protocol", "N/A", "N/A", "N/A", "Jake Morrow",
                          "STOP — invalid file: igglevel_09292025.pdf"])
        self.assertNotIn("webb.audit", self.done())

    def test_audit_stop_row_format(self):
        self.did(POST, {"channel_id": ALERTS, "text": HOLD_POST})
        self.audit(WEBB, ["2026-03-30", WEBB, "Stop Protocol", "auth.xlsx", "PA_Status", "Hold", "Jake Morrow",
                          "STOP — invalid file: igglevel_09292025.pdf"])
        self.assertIn("webb.audit", self.done())

    def test_rodriguez_hold(self):
        self.audit(ROD, ["2026-03-30", ROD, "Stop Protocol", "N/A", "N/A", "N/A", "Jake Morrow",
                         "STOP — patient unreachable after 3 attempts"])
        self.assertNotIn("rod.hold", self.done())
        self.edit(f"{ROD}/intake.xlsx", "ws.cell(2, col['Consent_Status']).value = 'Form Sent'")
        self.assertIn("rod.hold", self.done())

    def test_rodriguez_unrequested_row(self):
        self.audit(ROD, ["2026-03-30", ROD, "BVS Assigned", "intake.xlsx", "BVS_Assigned", "S. Kim", "Jake Morrow",
                         "SUCCESS"])
        self.assertIn("rod.hold", self.done())

    def test_payer_rules_unchanged(self):
        self.assertNotIn("files.payer_rules", self.done())
        self.edit("payer_rules.xlsx", "ws.cell(2, 2).value = 'Octagam'")
        self.assertIn("files.payer_rules", self.done())


class TestGolden(Case):
    def setUp(self):
        super().setUp()
        self.extract()
        self.substitute()
        self.common_done()

    def test_golden_submit(self):
        self.send_pa()
        self.did(POST, {"channel_id": TEAM, "text": PA_POST})
        self.auth()
        self.audit(WEBB, ["2026-03-30", WEBB, "PA Submitted", "auth.xlsx", "PA_Submission_Date; PA_Status",
                          "2026-03-30; Pending", "J. Morrow", "SUCCESS"])
        self.assertEqual(self.done(), {})

    def test_golden_hold(self):
        self.did(POST, {"channel_id": ALERTS, "text": HOLD_POST})
        self.audit(WEBB, ["2026-03-30", WEBB, "Stop Protocol", "N/A", "N/A", "N/A", "Jake Morrow",
                          "STOP — invalid file: igglevel_09292025.pdf"])
        self.audit(ROD, ["2026-03-30", ROD, "Stop Protocol", "N/A", "N/A", "N/A", "Jake Morrow",
                         "STOP — patient unreachable after 3 attempts"])
        self.assertEqual(self.done(), {})
