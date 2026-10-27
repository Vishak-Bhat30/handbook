"""Blind unit tests for medical_pathfinder_billing_and_coding_1d8667fc (BCBS ERA 20260315_BCBS posting)."""

from __future__ import annotations

import json

from interwhen_sop.tests.base import TaskCase

REG, SHEET = "PBC_Claim_Register.xlsx", "PBC_Claim_Register"
SEND = "google_mail__send_email"


def setrow(claim: str, **vals) -> str:
    """openpyxl snippet setting columns (by header name) on a claim row."""
    lines = [f"for r in range(2, ws.max_row + 1):", f"    if ws.cell(r, 1).value == {claim!r}:"]
    lines += [f"        ws.cell(r, col[{k!r}]).value = {v!r}" for k, v in vals.items()]
    return "\n".join(lines)


POST_1008 = {"Allowed Amount": 210, "Paid Amount ($)": 180, "Contractual Adj ($)": 70, "Patient Resp ($)": 30,
             "Claim Status": "Paid - Full", "Payment Posting Status": "Posted", "ERA Batch ID": "20260315_BCBS"}
HOLD_1033 = {"Payment Posting Status": "Held - Contractual Variance", "ERA Batch ID": "20260315_BCBS"}
NOTE_1016 = {"Notes": "ERA_20260120-BCBS posted 20 Jan 2026. Clawback applied 2026-03-15: $30.00 via 20260315_BCBS."}


class Base(TaskCase):
    TASK = "medical_pathfinder_billing_and_coding_1d8667fc"

    def set(self, claim, vals):
        self.edit(REG, setrow(claim, **vals), SHEET)

    def golden(self):
        self.edit(REG, "\n".join([setrow("CLM-1008", **POST_1008), setrow("CLM-1033", **HOLD_1033),
                                  setrow("CLM-1016", **NOTE_1016)]), SHEET)


class TestInitialAndGolden(Base):
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {"posting.clm1008_posted", "posting.clm1033_variance",
                                            "posting.clm1016_clawback"})

    def test_golden(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_replaced_note_and_era_prefix(self):
        self.golden()
        self.set("CLM-1008", {"ERA Batch ID": "ERA_20260315_BCBS"})
        self.set("CLM-1016", {"Notes": "Clawback applied 2026-03-15: $30.00 via 20260315_BCBS."})
        self.assertEqual(self.done(), {})


class TestClm1008(Base):
    def test_batch_hold_is_flagged(self):
        self.golden()
        self.set("CLM-1008", {"Payment Posting Status": "Held - PLB Variance"})
        d = self.done()
        self.assertIn("posting.clm1008_posted", d)
        self.assertIn("Payment Posting Status = Posted", d["posting.clm1008_posted"])

    def test_wrong_amount(self):
        self.golden()
        self.set("CLM-1008", {"Paid Amount ($)": 210})
        self.assertIn("Paid Amount ($) = 180.00", self.done()["posting.clm1008_posted"])

    def test_wrong_batch_id(self):
        self.golden()
        self.set("CLM-1008", {"ERA Batch ID": "EFT-BCBS-20260315-00047312"})
        self.assertIn("ERA Batch ID = 20260315_BCBS", self.done()["posting.clm1008_posted"])


class TestClm1033(Base):
    def test_posted_is_flagged(self):
        self.golden()
        self.set("CLM-1033", {"Payment Posting Status": "Posted", "Claim Status": "Paid - Full"})
        self.assertIn("Held - Contractual Variance", self.done()["posting.clm1033_variance"])

    def test_sbwo_written_off_accepted(self):
        self.golden()
        self.set("CLM-1033", {"Payment Posting Status": "Posted", "Claim Status": "Written Off"})
        self.assertNotIn("posting.clm1033_variance", self.done())


class TestClm1016(Base):
    def test_wrong_amount_note(self):
        self.golden()
        self.set("CLM-1016", {"Notes": "Clawback applied 2026-03-15: $10.00 via 20260315_BCBS."})
        self.assertIn("posting.clm1016_clawback", self.done())

    def test_other_field_changed(self):
        self.golden()
        self.set("CLM-1016", {"Paid Amount ($)": 142})
        self.assertIn("update no other fields", self.done()["posting.clm1016_clawback"])


class TestOtherRowsAndFiles(Base):
    def test_other_row_changed(self):
        self.golden()
        self.set("CLM-1038", {"Claim Status": "Acknowledged"})
        self.assertIn("CLM-1038", self.done()["register.other_rows_unchanged"])

    def test_row_added(self):
        self.golden()
        self.edit(REG, "ws.cell(ws.max_row + 1, 1).value = 'CRED-2026-0315'\n"
                       "ws.cell(ws.max_row, 14).value = -125", SHEET)
        self.assertIn("register.other_rows_unchanged", self.done())

    def test_era_modified(self):
        self.golden()
        self.edit("ERA_20260315_BCBS.xlsx", "ws['B11'] = 322")
        self.assertIn("files.reference_unchanged", self.done())

    def test_fee_schedule_unchanged_ok(self):
        self.golden()
        self.assertNotIn("files.reference_unchanged", self.done())


class TestPre(Base):
    def code(self, status):
        return {"code": "import openpyxl\np='/workdir/PBC_Claim_Register.xlsx'\nwb=openpyxl.load_workbook(p)\n"
                        f"ws=wb['PBC_Claim_Register']\nws['R9']='{status}'\nwb.save(p)\n"}

    def test_batch_hold_blocked(self):
        self.assertIn("posting.no_batch_hold", self.pre("syntara__executePython", self.code("Held - PLB Variance")))
        self.assertIn("posting.no_batch_hold", self.pre("syntara__executePython", self.code("Held - Batch Mismatch")))

    def test_contractual_hold_allowed(self):
        self.assertNotIn("posting.no_batch_hold",
                         self.pre("syntara__executePython", self.code("Held - Contractual Variance")))

    def test_batch_hold_gives_up_after_two_denials(self):
        rej = {"type": "rejection", "call_id": "x", "findings": [{"problem": "[batch-hold] x"}]}
        self.records += [rej, rej]
        self.assertNotIn("posting.no_batch_hold", self.pre("syntara__executePython", self.code("Held - PLB Variance")))

    def test_claim_fields_missing(self):
        args = {"to": "m.okafor@pathfinderbilling.com", "subject": "CLM-1033 variance",
                "body": "CLM-1033 was underpaid by $3.00."}
        self.assertIn("comms.claim_fields", self.pre(SEND, args))

    def test_claim_fields_complete(self):
        args = {"to": "m.okafor@pathfinderbilling.com", "subject": "CLM-1033 contractual variance",
                "body": "Claim ID CLM-1033, Patient ID PT-119, DOS 2026-02-24, CPT 99214, Payer Blue Cross Blue "
                        "Shield, Claim Status Acknowledged. Paid $162.00 vs contracted $165.00."}
        self.assertNotIn("comms.claim_fields", self.pre(SEND, args))

    def test_claim_fields_other_date_format(self):
        args = {"to": "m.okafor@pathfinderbilling.com", "subject": "CLM-1008",
                "body": "CLM-1008 / PT-120 / DOS 05 Jan 2026 / CPT 99215 / BCBS / status Paid - Full"}
        self.assertNotIn("comms.claim_fields", self.pre(SEND, args))

    def test_phi_to_other_clinic_blocked(self):
        args = {"to": "billing@riversideclinic.com", "subject": "BCBS adjustment",
                "body": "The BCBS recoupment relates to Sarah Mitchell (PT-101)."}
        self.assertIn("comms.phi_third_party", self.pre(SEND, args))

    def test_phi_internal_ok(self):
        args = {"to": "m.okafor@pathfinderbilling.com", "subject": "ERA note",
                "body": "Posted the ERA line for Harold Jensen."}
        self.assertNotIn("comms.phi_third_party", self.pre(SEND, args))

    def test_placeholders_blocked(self):
        args = {"to": "m.okafor@pathfinderbilling.com", "subject": "Action Required for [Patient Initials]",
                "body": "Hello [Doctor/Client Office Manager Name], please sign."}
        self.assertIn("comms.no_placeholders", self.pre(SEND, args))

    def test_read_not_blocked(self):
        self.assertEqual(self.pre("google_mail__read_email", {"email_id": "1"}), set())


if __name__ == "__main__":
    import unittest
    unittest.main()
