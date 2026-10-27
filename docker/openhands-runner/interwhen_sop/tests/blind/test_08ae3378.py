"""Blind unit tests for medical_careig_specialty_pharmacy_08ae3378 (fixtures: seed workspace only)."""

import shutil

from interwhen_sop.tests.base import TaskCase

CLAIM = "claim_CIG_2026_0341.xlsx"
SUBJECT = "CLAIM SUBMISSION CareIG NPI: 1234567893 | Thornton | MemberID: SHC-884729103 | DOS: 2026-10-05"
BODY = """DATE: 2026-10-08
TO: Sunflower Health Commercial PPO Claims | EMAIL: claims@sunflowerhealthks.com
FROM: CareIG Specialty Pharmacy — Billing | EMAIL: billing@careig.com

To Whom It May Concern,

Please find attached the claim for the following patient and date of service:
Patient: Thornton, Margaret
DOB: 1961-06-15
Member ID: SHC-884729103
Group: GRP-20145
Date of Service: 2026-10-05
PA Number: PA-2026-SHC-41092
Rendering Provider: CareIG Specialty Pharmacy
NPI: 1234567893
Tax ID: 47-3821056
Taxonomy: 3336C0003X
Referring Physician: Dr. Elena Vasquez, NPI: 1528074836 Diagnosis: D83.9
Total Billed: $6,154.80
Attached: claim_CIG_2026_0341.xlsx
For questions, contact billing@careig.com or (816) 555-0200.
Julio Martinez
CareIG Specialty Pharmacy, Billing
billing@careig.com
(816) 555-0200"""
POST = "CLAIM SUBMITTED CIG_2026_0341 | DOS: 2026-10-05 | Payer: Sunflower Health Commercial PPO | Billed: 6,154.80"
HEADER = {"CASE_ID": "CIG_2026_0341", "DOS": "2026-10-05", "Patient_Last_Name": "Thornton",
          "Patient_First_Name": "Margaret", "Patient_DOB": "1961-06-15", "Member_ID": "SHC-884729103",
          "Group_Number": "GRP-20145", "Payer_Name": "Sunflower Health Commercial PPO", "Payer_Type": "Commercial PPO",
          "PA_Number": "PA-2026-SHC-41092", "Physician_NPI": "1528074836", "CareIG_NPI": "1234567893",
          "CareIG_Tax_ID": "47-3821056", "CareIG_Taxonomy_Code": "3336C0003X", "Diagnosis_ICD10": "D83.9",
          "Drug_Source": "CareIG", "Claim_Frequency_Code": "1", "Total_Billed": 6154.80,
          "Submission_Date": "2026-10-08", "Claim_Status": "Submitted",
          "Partial_Infusion_Note": "Ordered 40g, administered 35.8g. Billed on administered dose."}
LINES = [("J1459", 71, 78.5), ("99600", 1, 185), ("99603", 2, 145), ("J7030", 2, 6.75), ("J0171", 1, 12.3),
         ("A4221", 1, 42), ("A4222", 1, 38.5)]
AUDIT = ["2026-10-08 9:45 AM", "CIG_2026_0341", "Claim Submitted", CLAIM, "Claim_Status", "Submitted",
         "Julio Martinez", "SUCCESS"]


class Base(TaskCase):
    TASK = "medical_careig_specialty_pharmacy_08ae3378"

    def build_claim(self, header=None, lines=None, submitted=True):
        h = dict(HEADER, **(header or {}))
        if not submitted:
            h.pop("Submission_Date"), h.pop("Claim_Status")
        shutil.copy(self.tmp / "workdir" / "claim_blank.xlsx", self.tmp / "workdir" / CLAIM)
        self.edit(CLAIM, f"h={h!r}\nfor k,v in h.items(): ws.cell(2, col[k], v)", sheet="Claim Header")
        rows = [["CIG_2026_0341", "2026-10-05", i, c, "", u, r, round(u * r, 2), None]
                for i, (c, u, r) in enumerate(lines if lines is not None else LINES, 1)]
        self.edit(CLAIM, f"for i,r in enumerate({rows!r}, 2):\n    for j,v in enumerate(r, 1): ws.cell(i, j, v)",
                  sheet="Claim Lines")

    def email(self, **kw):
        args = {"to": "claims@sunflowerhealthks.com", "subject": SUBJECT, "body": BODY,
                "attachments": [f"/workdir/{CLAIM}"]}
        args.update(kw)
        return args

    def audit(self, *rows):
        self.edit("audit_log.xlsx", f"for r in {list(rows)!r}: ws.append(r)")

    def golden(self):
        self.build_claim()
        self.did("google_mail__send_email", self.email())
        self.did("slack__post_message", {"channel_id": "C005", "text": POST})
        self.audit(AUDIT)


class Golden(Base):
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {"billing.messages_sent", "billing.claim_file", "audit.claim_submitted"})

    def test_golden_path_complete(self):
        self.golden()
        self.assertEqual(self.done(), {})


class ClaimEmail(Base):
    def test_correct_email_passes(self):
        self.build_claim(submitted=False)
        self.assertEqual(self.pre("google_mail__send_email", self.email()), set())

    def test_email_before_claim_file_blocked(self):
        self.assertIn("billing.claim_ready", self.pre("google_mail__send_email", self.email()))

    def test_ordered_dose_units_block_email(self):
        bad = [("J1459", 80, 78.5)] + LINES[1:]
        self.build_claim(lines=bad, header={"Total_Billed": 6835.80}, submitted=False)
        self.assertIn("billing.claim_ready", self.pre("google_mail__send_email", self.email()))

    def test_wrong_subject_blocked(self):
        self.build_claim(submitted=False)
        self.assertIn("billing.messages", self.pre("google_mail__send_email", self.email(subject="Claim for Thornton")))

    def test_wrong_recipient_blocked(self):
        self.build_claim(submitted=False)
        self.assertIn("billing.messages", self.pre("google_mail__send_email", self.email(to="pa.review@sunflowerhealthks.com")))

    def test_missing_attachment_blocked(self):
        self.build_claim(submitted=False)
        self.assertIn("billing.messages", self.pre("google_mail__send_email", self.email(attachments=[])))

    def test_wrong_total_in_body_blocked(self):
        self.build_claim(submitted=False)
        body = BODY.replace("$6,154.80", "$6,835.80")
        self.assertIn("billing.messages", self.pre("google_mail__send_email", self.email(body=body)))

    def test_duplicate_submission_blocked(self):
        self.build_claim()
        self.did("google_mail__send_email", self.email())
        self.assertIn("billing.messages", self.pre("google_mail__send_email", self.email()))

    def test_placeholder_blocked(self):
        self.build_claim(submitted=False)
        body = BODY.replace("Julio Martinez", "[Billing Specialist Full Name]")
        self.assertIn("comms.no_placeholders", self.pre("google_mail__send_email", self.email(body=body)))

    def test_unrelated_email_not_captured(self):
        self.assertEqual(self.pre("google_mail__send_email", {"to": "dpark@careig.com", "subject": "Lunch",
                                                              "body": "See you at noon."}), set())


class ClaimPost(Base):
    def test_post_after_email_passes(self):
        self.build_claim()
        self.did("google_mail__send_email", self.email())
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C005", "text": POST}), set())

    def test_post_with_dollar_sign_passes(self):
        self.build_claim()
        self.did("google_mail__send_email", self.email())
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C005", "text": POST.replace("Billed: ", "Billed: $")}),
                         set())

    def test_post_before_email_blocked(self):
        self.assertIn("billing.post_after_submit", self.pre("slack__post_message", {"channel_id": "C005", "text": POST}))

    def test_wrong_channel_blocked(self):
        self.build_claim()
        self.did("google_mail__send_email", self.email())
        self.assertIn("billing.messages", self.pre("slack__post_message", {"channel_id": "C007", "text": POST}))

    def test_wrong_amount_blocked(self):
        self.build_claim()
        self.did("google_mail__send_email", self.email())
        self.assertIn("billing.messages", self.pre("slack__post_message",
                                                   {"channel_id": "C005", "text": POST.replace("6,154.80", "6,835.80")}))

    def test_billing_hold_post_blocked(self):
        self.assertIn("billing.messages", self.pre("slack__post_message", {
            "channel_id": "C005", "text": "BILLING HOLD — DOSE EXCEEDS PA CIG_2026_0341 | PA approved: 40g | Administered: 35.8g"}))

    def test_other_billing_post_allowed(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C005", "text": "Working on CIG_2026_0341 today."}),
                         set())

    def test_messages_sent_completion(self):
        self.build_claim()
        self.audit(AUDIT)
        self.did("google_mail__send_email", self.email())
        self.assertIn("billing.messages_sent", self.done())


class ClaimFile(Base):
    def done_claim(self):
        self.golden_rest()
        return self.done().get("billing.claim_file", "")

    def golden_rest(self):
        self.did("google_mail__send_email", self.email())
        self.did("slack__post_message", {"channel_id": "C005", "text": POST})
        self.audit(AUDIT)

    def test_correct_claim(self):
        self.build_claim()
        self.assertEqual(self.done_claim(), "")

    def test_ordered_dose_units(self):
        self.build_claim(lines=[("J1459", 80, 78.5)] + LINES[1:], header={"Total_Billed": 6835.80})
        self.assertIn("J1459", self.done_claim())

    def test_missing_pump_line(self):
        self.build_claim(lines=LINES[:-1], header={"Total_Billed": 6116.30})
        self.assertIn("A4222", self.done_claim())

    def test_missing_partial_note(self):
        self.build_claim(header={"Partial_Infusion_Note": None})
        self.assertIn("Partial_Infusion_Note", self.done_claim())

    def test_partial_note_variant_ok(self):
        self.build_claim(header={"Partial_Infusion_Note": "Ordered 40.0g, administered 35.80g. Billed on administered dose."})
        self.assertEqual(self.done_claim(), "")

    def test_split_billing_model_wrong(self):
        self.build_claim(header={"Billing_Model": "Split"})
        self.assertIn("Billing_Model", self.done_claim())

    def test_not_submitted_status(self):
        self.build_claim(submitted=False)
        self.golden_rest()
        probs = " ".join(p for r, p in self.done_all() if r == "billing.claim_file")
        self.assertIn("Submission_Date", probs)
        self.assertIn("Claim_Status", probs)


class Audit(Base):
    def setUp(self):
        super().setUp()
        self.build_claim()
        self.did("google_mail__send_email", self.email())
        self.did("slack__post_message", {"channel_id": "C005", "text": POST})

    def test_ok(self):
        self.audit(AUDIT)
        self.assertNotIn("audit.claim_submitted", self.done())

    def test_missing(self):
        self.assertIn("audit.claim_submitted", self.done())

    def test_duplicate(self):
        self.audit(AUDIT, AUDIT[:4] + ["Submission_Date", "2026-10-08"] + AUDIT[6:])
        self.assertIn("audit.claim_submitted", self.done())

    def test_wrong_field(self):
        self.audit(AUDIT[:4] + ["Submission_Date"] + AUDIT[5:])
        self.assertIn("Field_Updated", self.done().get("audit.claim_submitted", ""))

    def test_extra_substep_row(self):
        self.audit(["2026-10-08 9:35 AM", "CIG_2026_0341", "Pre-Billing Validation", CLAIM, "All", "PASS",
                    "Julio Martinez", "SUCCESS"], AUDIT)
        self.assertIn("not an SOP checkpoint", self.done().get("audit.claim_submitted", ""))

    def test_append_only(self):
        self.audit(AUDIT)
        self.edit("audit_log.xlsx", "ws.cell(7, 8, 'FAILED')")
        self.assertIn("audit.append_only", self.done())


class Scope(Base):
    def setUp(self):
        super().setUp()
        self.golden()

    def test_ok(self):
        self.assertNotIn("files.scope", self.done())

    def test_case_file_edit(self):
        self.edit("visit_note_CIG_2026_0341.xlsx", "ws.cell(2, col['Dose_Administered_Grams'], 40)")
        self.assertIn("visit_note_CIG_2026_0341.xlsx", self.done().get("files.scope", ""))

    def test_template_edited_in_place(self):
        self.edit("claim_blank.xlsx", "ws.cell(2, 1, 'CIG_2026_0341')", sheet="Claim Header")
        self.assertIn("claim_blank.xlsx", self.done().get("files.scope", ""))

    def test_extra_workbook(self):
        shutil.copy(self.tmp / "workdir" / CLAIM, self.tmp / "workdir" / "claim.xlsx")
        self.assertIn("claim.xlsx", self.done().get("files.scope", ""))
