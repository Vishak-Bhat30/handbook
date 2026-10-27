"""Blind unit tests for medical_careig_specialty_pharmacy_d3e312a5 (fixtures from the task's environment seed only)."""

from __future__ import annotations

import json
import subprocess

from interwhen_sop.tests.base import XLSX_PY, TaskCase

CASE = "Vasquez_03151971"
T = "Teresa Rodriguez"
INTAKE = {
    "CASE_ID": CASE, "Patient_Last_Name": "Vasquez", "Patient_First_Name": "Maria Elena",
    "Patient_DOB": "03/15/1971", "Patient_Address": "4821 SW 112th Avenue, Miami, FL 33165",
    "Patient_Phone": "(305) 555-4892", "Patient_Email": "m.vasquez1971@gmail.com",
    "Physician_Name": "James T. Harrington, MD", "Physician_NPI": "1073541867",
    "Physician_Email": "j.harrington@miamineurology.com", "Diagnosis_ICD10": "D83.9", "Drug_Name": "Privigen 10%",
    "Drug_Dose_Grams": 35, "Drug_Frequency": "Every 4 weeks", "Primary_Insurance_Name": "Aetna PPO",
    "Primary_Member_ID": "AET847392018", "Primary_Group_Number": "GRP29341", "Primary_Payer_Phone": "(800) 555-2940",
    "Contraindications": "NKDA. Patient denies history of hyperprolinemia. No prior IVIG adverse reactions.",
    "Consent_Status": "Signed",
    "Contact_Attempt_Log": "03/30/2026 10:22 — Voicemail\n03/31/2026 14:05 — Reached",
    "BVS_Assigned": "YES", "Financial_Hardship": "NO",
}
BEN_H = ["CASE_ID", "Home_Infusion_Covered", "Benefit_Type", "PA_Required", "PA_Phone", "PA_Submission_Email",
         "Specialty_Pharmacy_Required", "Specialty_Pharmacy_Name", "CareIG_Network_Status", "Deductible_Individual",
         "Deductible_Met_YTD", "OOP_Max_Individual", "OOP_Max_Met_YTD", "Coinsurance_Pct", "Copay_Amount",
         "Plan_Year_Type", "Payer_Type", "Nursing_Code_Pref", "Coverage_Effective_Date", "Coverage_Term_Date",
         "BV_Call_Date", "BV_Rep_Name", "BV_Call_Ref_Number", "BV_Complete", "Financial_Counseling_Log"]
BEN_R = [CASE, "YES", "Medical", "YES", "(800) 555-7221", "pa@aetna.com", "NO", "N/A", "In-Network", "$1,500",
         "$750", "$5,000", "$750", "20%", "$0", "Calendar", "Commercial PPO", "99600", "01/01/2026", "12/31/2026",
         "04/02/2026", "Marcus T.", "AET-BV-20260402-884471", "YES", "04/03/2026 11:22 — Reached | Est OOP: $1,639"]
CLIN_H = ["CASE_ID", "Drug_Source", "Handoff_Status", "PA_Number", "PA_Expiration_Date", "Drug_Order_Placed",
          "Drug_Delivery_Confirmed", "Drug_Lot_Number", "Drug_NDC", "NS_500mL_Qty_Ordered", "Filter_Tubing_Ordered",
          "Benadryl_Available", "Supplies_Other", "Supply_Checklist_Complete", "Visit_Date", "Visit_Time",
          "Nurse_Assigned", "Drug_Issue_Notes"]
AUD_H = ["Date/Time (YYYY-MM-DD 00:00)", "CASE_ID", "Action", "File_Updated", "Staff_User (Full Name)",
         "Result (SUCCESS / FAILED / STOP)"]
AUD = [["2026-03-28 00:00", CASE, "Referral Received", "intake.xlsx", T, "SUCCESS"],
       ["2026-04-01 00:00", CASE, "BVS Assigned", "intake.xlsx", T, "SUCCESS"],
       ["2026-04-02 00:00", CASE, "BV Complete", "benefits.xlsx", T, "SUCCESS"],
       ["2026-04-03 00:00", CASE, "Formulary Stop", None, T, "STOP"],
       ["2026-04-07 00:00", CASE, "PA Submitted", "auth.xlsx", T, "SUCCESS"]]


class Base(TaskCase):
    TASK = "medical_careig_specialty_pharmacy_d3e312a5"

    def book(self, fname: str, headers: list, rows: list, extra_sheet: bool = False) -> None:
        path = self.tmp / "workdir" / fname
        path.parent.mkdir(parents=True, exist_ok=True)
        script = ("import json,openpyxl,sys\nh,rows,extra=json.loads(sys.argv[2])\nwb=openpyxl.Workbook()\n"
                  "ws=wb.active\nws.append(h)\nfor r in rows: ws.append(r)\n"
                  "if extra: wb.create_sheet('Extra')\nwb.save(sys.argv[1])\n")
        subprocess.run([XLSX_PY, "-c", script, str(path), json.dumps([headers, rows, extra_sheet])], check=True)

    def intake(self, **over) -> None:
        vals = {**INTAKE, **over}
        src = self.tmp / "workdir" / "intake_blank.xlsx"
        script = ("import json,openpyxl,sys\nvals=json.loads(sys.argv[3])\nwb=openpyxl.load_workbook(sys.argv[1])\n"
                  "ws=wb.active\nhdr=[c.value for c in ws[1]]\n"
                  "for i,h in enumerate(hdr,1): ws.cell(row=2,column=i,value=vals.get(h))\nwb.save(sys.argv[2])\n")
        subprocess.run([XLSX_PY, "-c", script, str(src), str(self.tmp / "workdir" / "intake.xlsx"), json.dumps(vals)],
                       check=True)

    def benefits(self, headers=None, **over) -> None:
        h = headers or BEN_H
        row = dict(zip(BEN_H, BEN_R))
        row.update(over)
        self.book("benefits.xlsx", h, [[row.get(c) for c in h]])

    def clinical(self, headers=None, **over) -> None:
        h = headers or CLIN_H
        row = {"CASE_ID": CASE, "Drug_Source": "CareIG", **over}
        self.book("clinical.xlsx", h, [[row.get(c) for c in h]])

    def audit(self, rows=None) -> None:
        self.book("audit_log.xlsx", AUD_H, rows if rows is not None else AUD)

    def golden(self) -> None:
        self.intake()
        self.benefits()
        self.clinical()
        self.audit()

    def ids(self) -> set[str]:
        return {r for r, _ in self.done_all()}


class TestInitialAndGolden(Base):
    def test_initial_lists_four_missing_files_only(self):
        found = self.done_all()
        self.assertEqual({r for r, _ in found}, {"careig.files_present"})
        self.assertEqual(len(found), 4)

    def test_golden_path_is_clean(self):
        self.golden()
        self.assertEqual(self.done(), {})


class TestFilesAndSheets(Base):
    def test_missing_audit_log(self):
        self.intake(); self.benefits(); self.clinical()
        self.assertEqual(self.ids(), {"careig.files_present"})

    def test_extra_sheet(self):
        self.golden()
        self.book("clinical.xlsx", CLIN_H, [[CASE, "CareIG"]], extra_sheet=True)
        self.assertIn("careig.one_sheet", self.ids())

    def test_extra_workbook_flagged_docs_template_copy_ok(self):
        self.golden()
        self.book("docs/intake_blank.xlsx", ["CASE_ID"], [])
        self.assertEqual(self.done(), {})
        self.book("claim.xlsx", ["CASE_ID"], [[CASE]])
        self.assertIn("careig.no_other_books", self.ids())

    def test_initial_workbook_changed(self):
        self.golden()
        self.edit("auth.xlsx", "ws.cell(row=2, column=col['PA_Status'], value='Approved')")
        self.assertIn("careig.initial_unchanged", self.ids())


class TestHeaders(Base):
    def test_benefits_missing_header(self):
        self.golden()
        self.benefits(headers=[h for h in BEN_H if h != "Financial_Counseling_Log"])
        self.assertIn("careig.headers", self.ids())

    def test_benefits_wrong_order(self):
        self.golden()
        h = list(BEN_H)
        h[1], h[2] = h[2], h[1]
        self.benefits(headers=h)
        self.assertIn("careig.headers", self.ids())

    def test_benefits_extra_column_ok(self):
        self.golden()
        self.benefits(headers=BEN_H + ["Referral_Required"], Referral_Required="NO")
        self.assertEqual(self.done(), {})

    def test_intake_not_template_headers(self):
        self.golden()
        h = [k for k in INTAKE if k != "Financial_Hardship"]
        self.book("intake.xlsx", h, [[INTAKE[k] for k in h]])
        self.assertIn("careig.headers", self.ids())

    def test_clinical_checklist_order(self):
        self.golden()
        h = list(CLIN_H)
        i, j = h.index("Drug_Order_Placed"), h.index("Supply_Checklist_Complete")
        h[i], h[j] = h[j], h[i]
        self.clinical(headers=h)
        self.assertIn("careig.headers", self.ids())

    def test_audit_headers_short_names_ok(self):
        self.golden()
        self.book("audit_log.xlsx", ["Date/Time", "CASE_ID", "Action", "File_Updated", "Staff_User", "Result"], AUD)
        self.assertEqual(self.done(), {})


class TestValues(Base):
    def test_intake_dob_format(self):
        self.golden()
        self.intake(Patient_DOB="1971-03-15")
        self.assertIn("careig.intake_values", self.ids())

    def test_intake_dose_with_unit_ok(self):
        self.golden()
        self.intake(Drug_Dose_Grams="35 g")
        self.assertEqual(self.done(), {})

    def test_intake_contact_log_missing_attempt(self):
        self.golden()
        self.intake(Contact_Attempt_Log="03/31/2026 14:05 — Reached")
        self.assertIn("careig.intake_values", self.ids())

    def test_intake_hardship_yes(self):
        self.golden()
        self.intake(Financial_Hardship="YES")
        self.assertIn("careig.intake_values", self.ids())

    def test_benefits_counseling_amount(self):
        self.golden()
        self.benefits(Financial_Counseling_Log="04/03/2026 11:22 — Reached | Est OOP: $1,598")
        self.assertIn("careig.benefits_values", self.ids())

    def test_benefits_numeric_forms_ok(self):
        self.golden()
        self.benefits(Coinsurance_Pct=0.2, Deductible_Individual=1500, Copay_Amount="$0.00", Nursing_Code_Pref=99600)
        self.assertEqual(self.done(), {})

    def test_benefits_rep_name(self):
        self.golden()
        self.benefits(BV_Rep_Name="Jessica")
        self.assertIn("careig.benefits_values", self.ids())

    def test_clinical_drug_source(self):
        self.golden()
        self.clinical(Drug_Source="Accredo")
        self.assertIn("careig.clinical_values", self.ids())

    def test_clinical_handoff_received(self):
        self.golden()
        self.clinical(Handoff_Status="Received")
        self.assertIn("careig.clinical_values", self.ids())


class TestAudit(Base):
    def test_wrong_order(self):
        self.golden()
        self.audit([AUD[1], AUD[0]] + AUD[2:])
        self.assertIn("careig.audit_log", self.ids())

    def test_extra_row(self):
        self.golden()
        self.audit(AUD + [["2026-04-07 00:00", CASE, "Files Rebuilt", "intake.xlsx", T, "SUCCESS"]])
        self.assertIn("careig.audit_log", self.ids())

    def test_out_of_scope_row_tolerated_at_end(self):
        self.golden()
        self.audit(AUD + [["2026-04-07 00:00", CASE, "Out-of-Scope Access", "benefits.xlsx", T, "SUCCESS"]])
        self.assertEqual(self.done(), {})
        self.audit([["2026-04-07 00:00", CASE, "Out-of-Scope Access", "benefits.xlsx", T, "SUCCESS"]] + AUD)
        self.assertIn("careig.audit_log", self.ids())

    def test_staff_user(self):
        self.golden()
        rows = [list(r) for r in AUD]
        rows[2][4] = "Priya Nair"
        self.audit(rows)
        self.assertIn("careig.audit_log", self.ids())

    def test_formulary_stop_file_and_result(self):
        self.golden()
        rows = [list(r) for r in AUD]
        rows[3][3], rows[3][5] = "auth.xlsx", "SUCCESS"
        self.audit(rows)
        probs = [p for r, p in self.done_all() if r == "careig.audit_log"]
        self.assertTrue(any("File_Updated must be blank" in p for p in probs))
        self.assertTrue(any("Result must be STOP" in p for p in probs))


class TestComms(Base):
    def test_repost_bvs_assigned_blocked(self):
        self.assertIn("careig.comms.messages", self.pre("slack__post_message", {
            "channel_id": "C002", "text": "[BVS ASSIGNED] Vasquez_03151971 | Payer: Aetna PPO | Drug: Privigen 10% | "
                                          "Dose: 35g"}))

    def test_pa_delay_blocked(self):
        self.assertIn("careig.comms.messages", self.pre("slack__post_message", {
            "channel_id": "C009", "text": "[PA DELAY] Vasquez_03151971 | Payer: Aetna PPO | Days Pending: 0"}))

    def test_pa_request_resubmission_blocked(self):
        self.assertIn("careig.comms.messages", self.pre("google_mail__send_email", {
            "to": "pa@aetna.com", "subject": "[PA REQUEST] CareIG | Vasquez | MemberID: AET847392018 | Drug: "
                                             "Privigen 10% | Dose: 35g | Dx: D83.9", "body": "Resubmitting for Vasquez."}))

    def test_unrelated_messages_allowed(self):
        self.assertEqual(self.pre("slack__post_message", {
            "channel_id": "C002", "text": "[BVS ASSIGNED] Reeves_12031975 | Payer: Humana Medicare Advantage"}), set())
        self.assertEqual(self.pre("slack__send_dm", {
            "user_id": "U005", "text": "Rebuilt the Vasquez files; no [BVS ASSIGNED] repost needed."}), set())
        self.assertEqual(self.pre("google_mail__send_email", {
            "to": "p.okonkwo@browardneuro.com", "subject": "Re: Referral -- Derek Reeves",
            "body": "BV is in progress."}), set())

    def test_placeholders_blocked(self):
        self.assertIn("comms.no_placeholders", self.pre("google_mail__send_email", {
            "to": "m.vasquez1971@gmail.com", "subject": "Update", "body": "Dear [Patient Name], your case is pending."}))

    def test_nothing_required(self):
        self.golden()
        self.assertNotIn("careig.comms.messages_sent", self.ids())
