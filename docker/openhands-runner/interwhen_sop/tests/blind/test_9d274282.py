"""Blind unit tests for medical_pathfinder_billing_and_coding_9d274282 (fixtures from environment/ only)."""

import json

from interwhen_sop.tests.base import TaskCase

REG = "PBC_Claim_Register.xlsx"
ESC = "PBC_Escalation_Log.xlsx"
POSTS = {"CLM-10042": 247.5, "CLM-10047": 180, "CLM-10051": 315, "CLM-10058": 92, "CLM-10061": 410}


def set_cells(changes: dict) -> str:
    """openpyxl code: {claim id: {header: value}} applied to the claim register."""
    return ("changes=" + json.dumps(changes) + "\n"
            "for r in range(2, ws.max_row+1):\n"
            "    cid=ws.cell(r,1).value\n"
            "    for h,v in changes.get(cid,{}).items():\n"
            "        ws.cell(r,col[h]).value=v\n")


GOLDEN = {**{c: {"Paid Amount": p, "Claim Status": "Paid - Full", "Payment Posting Status": "Posted"}
             for c, p in POSTS.items()},
          "CLM-10071": {"Paid Amount": 900.0, "Patient Balance": 0.0},
          "CLM-10082": {"Paid Amount": 650.0, "Patient Balance": 0.0}}


class Base(TaskCase):
    TASK = "medical_pathfinder_billing_and_coding_9d274282"

    def golden(self, **override):
        ch = json.loads(json.dumps(GOLDEN))
        for cid, cells in override.items():
            ch.setdefault(cid.replace("_", "-"), {}).update(cells)
        self.edit(REG, set_cells(ch))


class InitialAndGolden(Base):
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {"posting.era_lines", "posting.credit_balance"})
        self.assertEqual(sum(r == "posting.era_lines" for r, _ in self.done_all()), 5)

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_with_valid_escalation_row(self):
        self.golden()
        self.edit(ESC, "ws.append(['ESC-0100','2026-03-31','CLM-10033','Operational (under $5,000)',"
                       "'Payer Overpayment','Billing Specialist','RCM Manager','In Progress',None,'note'])")
        self.assertEqual(self.done(), {})


class Posting(Base):
    def test_reconciled_is_wrong(self):
        self.golden(CLM_10042={"Payment Posting Status": "Reconciled"})
        d = self.done()
        self.assertEqual(set(d), {"posting.era_lines"})
        self.assertIn("Payment Posting Status = Posted", d["posting.era_lines"])

    def test_paid_amount_missing(self):
        self.golden(CLM_10061={"Paid Amount": 0})
        self.assertIn("Paid Amount = $410.00", self.done()["posting.era_lines"])

    def test_wrong_adjustment(self):
        self.golden(CLM_10047={"Adj Amount": 0})
        self.assertIn("Adj Amount = $20.00", self.done()["posting.era_lines"])


class Credit(Base):
    def test_credit_not_applied(self):
        self.golden(CLM_10071={"Patient Balance": 900.0})
        d = self.done()
        self.assertEqual(set(d), {"posting.credit_balance"})
        self.assertIn("CLM-10071", d["posting.credit_balance"])

    def test_credit_applied_to_wrong_james_miller(self):
        self.golden(CLM_10089={"Patient Balance": 0.0, "Paid Amount": 250.0})
        d = self.done()
        self.assertEqual(set(d), {"posting.credit_balance"})
        self.assertIn("PT-9103", d["posting.credit_balance"])

    def test_era_amounts_posted_on_paid_claim(self):
        self.golden(CLM_10033={"Paid Amount": 1550.0, "Allowed Amount": 1800.0})
        d = self.done()
        self.assertEqual(set(d), {"posting.credit_balance"})
        self.assertIn("credit balance", d["posting.credit_balance"])

    def test_unapplied_marker_on_credit_claim_ok(self):
        self.golden(CLM_10033={"Payment Posting Status": "Unapplied"})
        self.assertEqual(self.done(), {})


class Invariants(Base):
    def test_other_register_row_changed(self):
        self.golden(CLM_10043={"Claim Status": "Resubmitted"})
        self.assertEqual(set(self.done()), {"register.no_unrequested_changes"})

    def test_float_to_int_rewrite_is_not_a_change(self):
        self.golden(CLM_10001={"NPI (Type 1)": 1285034671})
        self.assertEqual(self.done(), {})

    def test_reference_file_edited(self):
        self.golden()
        self.edit("PBC_Fee_Schedule.xlsx", "ws.cell(2,5).value=300")
        self.assertEqual(set(self.done()), {"files.reference_unchanged"})

    def test_controlled_values(self):
        self.golden(CLM_10042={"Payment Posting Status": "Done"})
        self.assertIn("fields.controlled_values", self.done())

    def test_escalation_reason_free_text(self):
        self.golden()
        self.edit(ESC, "ws.append(['ESC-0100','2026-03-31','CLM-10033','Operational','Overpayment',"
                       "'Billing Specialist','RCM Manager','Open',None,'x'])")
        self.assertEqual(set(self.done()), {"fields.controlled_values"})

    def test_escalation_append_only(self):
        self.golden()
        self.edit(ESC, "ws.cell(2,8).value='In Progress'")
        self.assertEqual(set(self.done()), {"escalation.append_only"})

    def test_sop_write_blocked(self):
        self.assertIn("files.sop_unmodified", self.pre("syntara__writeFile",
                                                       {"file_path": "/workdir/SOP-RCM-024_Rev3.26.html",
                                                        "content": "x"}))
        self.assertEqual(self.pre("syntara__writeFile", {"file_path": "/workdir/notes.txt", "content": "x"}), set())


class Comms(Base):
    FULL = ("CLM-10042 (Patient ID PT-3301, DOS 2026-03-10, CPT 99213, Aetna, Claim Status Acknowledged) "
            "was posted.")

    def test_phi_name_blocked(self):
        self.assertIn("comms.phi", self.pre("slack__post_message", {"channel_id": "C1",
                                                                     "text": "Patricia Nguyen " + self.FULL}))

    def test_phi_dob_blocked(self):
        self.assertIn("comms.phi", self.pre("google_mail__send_email",
                                            {"to": "x@pbc.com", "subject": "s", "body": "DOB 1990-07-22"}))

    def test_ids_only_allowed(self):
        self.assertEqual(self.pre("google_mail__send_email",
                                  {"to": "x@pbc.com", "subject": "ERA posted", "body": self.FULL}), set())

    def test_claim_fields_missing(self):
        self.assertEqual(self.pre("google_mail__send_email",
                                  {"to": "x@pbc.com", "subject": "s", "body": "CLM-10042 posted."}),
                         {"comms.claim_fields"})

    def test_claim_fields_current_status_and_alt_formats(self):
        self.golden()
        body = "CLM-10047: PT-4412, DOS 03/12/2026, CPT 93000, UHC, status Paid - Full."
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C1", "text": body}), set())
