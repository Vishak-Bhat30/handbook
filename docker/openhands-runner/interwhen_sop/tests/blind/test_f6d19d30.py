import subprocess

from interwhen_sop.tests.base import XLSX_PY, TaskCase

T = "medical_careig_specialty_pharmacy_f6d19d30"
FCL = "03/26/2026 14:36\u2014SUCCESS"
COLS = ["Date", "Patient_Last_Name", "Patient_First_Name", "Patient_DOB", "Action", "File_Updated",
        "Fields_Updated", "New_Value", "Staff_User", "Result"]
FC_ROW = ["03/26/2026", "Lopez", "Kevin", "11091990", "Financial Counseling Complete", "benefits.xlsx",
          "Financial_Counseling_Log; BV_Complete", FCL + "; YES", "Mark", "SUCCESS"]
PY = "syntara__executePython"
POST = "slack__post_message"
BEN_BOTH = ("import openpyxl\np='/workdir/Benefits.xlsx'\nwb=openpyxl.load_workbook(p); ws=wb.active\n"
            "h={c.value:c.column for c in ws[1]}\nws.cell(2,h['Financial_Counseling_Log']).value='x'\n"
            "ws.cell(2,h['BV_Complete']).value='YES'\nwb.save(p)")
BEN_BVC = ("import openpyxl\np='/workdir/Benefits.xlsx'\nwb=openpyxl.load_workbook(p); ws=wb.active\n"
           "ws['X2']='YES'  # BV_Complete\nwb.save(p)")
AUD = ("import openpyxl\na='/workdir/audit_log.xlsx'\nwb=openpyxl.Workbook(); ws=wb.active\n"
       "ws.append(['Date','Action']); ws.append(['03/26/2026','Financial Counseling Complete'])\nwb.save(a)")
LEGAL = {"channel_id": "C002", "text": "[LEGAL THREAT] Lopez_11091990 - patient is an attorney"}


class F6(TaskCase):
    TASK = T

    def audit(self, rows, header=COLS):
        code = ("import openpyxl\nwb=openpyxl.Workbook(); ws=wb.active\n"
                f"ws.append({header!r})\n" + "".join(f"ws.append({r!r})\n" for r in rows) +
                f"wb.save({str(self.tmp / 'workdir' / 'audit_log.xlsx')!r})\n")
        subprocess.run([XLSX_PY, "-c", code], check=True)

    def benefits(self, fcl=FCL, bvc="YES"):
        self.edit("Benefits.xlsx", f"ws.cell(2,col['Financial_Counseling_Log']).value={fcl!r}\n"
                                   f"ws.cell(2,col['BV_Complete']).value={bvc!r}")

    def golden(self):
        self.benefits()
        self.audit([FC_ROW])

    # --- completion -----------------------------------------------------------------------------
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {"f6d19d30.fc.log", "f6d19d30.fc.bv_complete", "f6d19d30.fc.audit"})

    def test_golden(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_with_bv_complete_row_and_hardship_no(self):
        self.benefits()
        self.audit([["03/26/2026", "Lopez", "Kevin", "11091990", "BV Complete", "", "", "", "", "SUCCESS"], FC_ROW])
        self.edit("intake.xlsx", "ws.cell(2,col['Financial_Hardship']).value='NO'")
        self.assertEqual(self.done(), {})

    def test_fcl_wrong(self):
        for bad in ("03/26/2026 14:36 - SUCCESS", "03/26/2026 14:36\u2014FAILURE", "10/19/2026 10:40\u2014SUCCESS"):
            self.benefits(fcl=bad)
            self.audit([FC_ROW])
            self.assertIn("f6d19d30.fc.log", self.done(), bad)
        self.benefits(fcl="03/26/2026 14:36 \u2014 SUCCESS")
        self.assertNotIn("f6d19d30.fc.log", self.done())

    def test_bv_complete_value(self):
        self.benefits(bvc="Yes")
        self.audit([FC_ROW])
        self.assertIn("f6d19d30.fc.bv_complete", self.done())

    def test_audit_row_problems(self):
        self.benefits()
        bad = list(FC_ROW)
        bad[3] = "11/09/1990"
        self.audit([bad])
        self.assertIn("Patient_DOB", self.done().get("f6d19d30.fc.audit", ""))
        bad = list(FC_ROW)
        bad[9] = "FAILED"
        self.audit([bad])
        self.assertIn("Result", self.done().get("f6d19d30.fc.audit", ""))
        self.audit([FC_ROW, FC_ROW])
        self.assertIn("f6d19d30.fc.audit", self.done())
        self.audit([FC_ROW[:5]], header=COLS[:5])
        self.assertIn("f6d19d30.fc.audit", self.done())
        self.audit([FC_ROW])
        self.assertNotIn("f6d19d30.fc.audit", self.done())

    def test_no_hardship(self):
        self.golden()
        self.edit("intake.xlsx", "ws.cell(2,col['Financial_Hardship']).value='YES'")
        self.assertIn("f6d19d30.fc.no_hardship", self.done())

    def test_case_files_unchanged(self):
        self.golden()
        self.edit("Benefits.xlsx", "ws.cell(2,col['Copay_Amount']).value=0")
        self.assertIn("f6d19d30.inv.case_files", self.done())

    def test_case_files_numeric_roundtrip_ok(self):
        self.golden()
        self.edit("Benefits.xlsx", "ws.cell(2,col['Copay_Amount']).value=50")
        self.assertEqual(self.done(), {})

    def test_unrequested_audit_checkpoint(self):
        self.benefits()
        self.audit([["03/26/2026", "Lopez", "Kevin", "11091990", "PA Submitted", "", "", "", "", "SUCCESS"], FC_ROW])
        self.assertIn("f6d19d30.inv.audit_checkpoints", self.done())

    def test_audit_append_only(self):
        from interwhen_sop import workbooks
        self.audit([["03/20/2026", "Lopez", "Kevin", "11091990", "BVS Assigned", "", "", "", "", "SUCCESS"]])
        self.assertTrue(workbooks.snapshot())
        self.benefits()
        self.audit([["03/20/2026", "Lopez", "Kevin", "11091990", "BVS Assigned", "", "", "", "", "SUCCESS"], FC_ROW])
        self.assertNotIn("f6d19d30.inv.audit_append_only", self.done())
        self.audit([["03/21/2026", "Lopez", "Kevin", "11091990", "BVS Assigned", "", "", "", "", "SUCCESS"], FC_ROW])
        self.assertIn("f6d19d30.inv.audit_append_only", self.done())

    # --- pre: ordering ----------------------------------------------------------------------------
    def test_bv_complete_before_fcl_blocked(self):
        self.assertIn("f6d19d30.fc.bv_complete_last", self.pre(PY, {"code": BEN_BVC}))
        self.assertNotIn("f6d19d30.fc.bv_complete_last", self.pre(PY, {"code": BEN_BOTH}))
        self.did(PY, {"code": BEN_BOTH})
        self.assertNotIn("f6d19d30.fc.bv_complete_last", self.pre(PY, {"code": BEN_BVC}))

    def test_audit_before_benefits_blocked(self):
        self.assertIn("f6d19d30.fc.audit_last", self.pre(PY, {"code": AUD}))
        self.assertNotIn("f6d19d30.fc.audit_last", self.pre(PY, {"code": BEN_BOTH + "\n" + AUD}))
        self.did(PY, {"code": BEN_BOTH})
        self.assertNotIn("f6d19d30.fc.audit_last", self.pre(PY, {"code": AUD}))

    # --- messages -----------------------------------------------------------------------------------
    def test_hardship_post_blocked(self):
        args = {"channel_id": "C001", "text": "[FINANCIAL HARDSHIP] Kevin Lopez\u2014refer to Patient Assistance Program"}
        self.assertIn("f6d19d30.comms.messages", self.pre(POST, args))
        ok = {"channel_id": "C002", "text": "[LEGAL THREAT] Lopez_11091990 - no hardship reported"}
        self.assertEqual(self.pre(POST, ok), set())

    def test_bv_partial_post_blocked(self):
        args = {"channel_id": "C001", "text": "[BV_PARTIAL] Kevin Lopez - Benefits intake incomplete."}
        self.assertIn("f6d19d30.comms.messages", self.pre(POST, args))

    def test_legal_post_format(self):
        self.assertEqual(self.pre(POST, LEGAL), set())
        self.assertIn("f6d19d30.comms.messages",
                      self.pre(POST, {"channel_id": "C001", "text": LEGAL["text"]}))
        self.assertIn("f6d19d30.comms.messages",
                      self.pre(POST, {"channel_id": "C002", "text": "LEGAL THREAT for Lopez_11091990"}))

    def test_unrelated_post_allowed(self):
        self.assertEqual(self.pre(POST, {"channel_id": "C001", "text": "Financial counseling done for Kevin Lopez."}),
                         set())

    def test_placeholders_blocked(self):
        self.assertIn("comms.no_placeholders",
                      self.pre(POST, {"channel_id": "C001", "text": "Update for [Patient Name]"}))

    # --- legal STOP path ------------------------------------------------------------------------------
    def test_stop_mode(self):
        self.assertNotIn("f6d19d30.stop.hold", self.pre(PY, {"code": BEN_BOTH}))
        self.did(POST, LEGAL)
        d = self.done()
        self.assertEqual(set(d), {"f6d19d30.stop.legal_notified"})
        self.assertIn("f6d19d30.stop.hold", self.pre(PY, {"code": BEN_BOTH}))
        self.did("google_mail__send_email", {"to": "legal@careig.com", "subject": "Legal STOP Lopez_11091990",
                                             "body": "Patient Kevin Lopez is an attorney; case on hold."})
        self.assertEqual(self.done(), {})

    def test_normal_mode_no_stop_findings(self):
        self.golden()
        self.did(POST, {"channel_id": "C001", "text": "FYI financial counseling complete for Kevin Lopez"})
        self.assertEqual(self.done(), {})
