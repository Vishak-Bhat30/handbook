"""Blind unit tests for insurance_mojave_crest_assurance_company_7245b8dd (fixtures from the task seed only)."""

from __future__ import annotations

import shutil

from interwhen_sop.tests.base import TaskCase

CASE = "CASE-2026-00478"
DOCS = ["Kovacs_James_ClinicalPacket_CR-2026-044721.pdf", "MCA_Denial_Letter_Kovacs_James_CR-2026-044721.pdf",
        "EOC-MCA4471-PY2026.pdf", "MP-019-v2.2-20260101.pdf", "Claims_History_Kovacs_James_44710006.pdf"]

ROW8 = """import datetime
vals = {'A': 'CASE-2026-00478', 'B': '44710006', 'C': 'MCA-4471', 'D': '2026', 'E': 'Undetermined',
        'F': 'Concurrent Care', 'G': 'Inpatient, in-network (SUD)', 'H': 'Medical Necessity',
        'I': datetime.datetime(2026, 4, 14, 9, 47), 'L': 'N',
        'P': 'Dr. Ontario (BH/SUD) + Parity Review Committee', 'Q': 'Y', 'R': 'N', 'V': 'N', 'W': 'Intake',
        'X': 'K. Whitfield'}
vals.update(OVR)
for k, v in vals.items():
    ws[k + '8'] = v
"""

SORTED_INSERT = """import datetime, copy
ncols = 24
J = lambda r: f'=IF(ISNUMBER(SEARCH("Concurrent Care",F{r})),I{r}+1,IF(OR(F{r}="Pre-Service Standard",F{r}="Post-Service Standard",F{r}="Grievance"),WORKDAY(INT(I{r}),5),INT(I{r})+1))'
O = lambda r: f'=IF(ISNUMBER(SEARCH("Concurrent Care",F{r})),I{r}+3,IF(F{r}="Post-Service Standard",INT(I{r})+60+IF(L{r}="Y",N{r}-M{r},0),IF(OR(F{r}="Pre-Service Standard",F{r}="Grievance"),INT(I{r})+30+IF(L{r}="Y",N{r}-M{r},0),"")))'
rows = [[ws.cell(r, c).value for c in range(1, ncols + 1)] for r in range(3, 8)]
new = [None] * ncols
new[0:9] = ['CASE-2026-00478', '44710006', 'MCA-4471', '2026', 'Undetermined', 'Concurrent Care',
            'Inpatient, SUD, In-Network', 'Medical Necessity', datetime.datetime(2026, 4, 14, 9, 47)]
new[11] = 'N'; new[15] = 'Dr. Ontario (BH/SUD) + Parity Review Committee'; new[16] = 'Y'; new[17] = 'N'
new[22] = 'Intake'; new[23] = 'Kara Whitfield'
order = rows[:3] + [new] + rows[3:]
for r in range(3, 10):
    for c in range(1, ncols + 1):
        ws.cell(r, c).value = None
for i, vals in enumerate(order):
    r = 3 + i
    for c in range(1, ncols + 1):
        ws.cell(r, c).value = J(r) if c == 10 else O(r) if c == 15 else vals[c - 1]
ws.cell(9, 10).value = J(9); ws.cell(9, 15).value = O(9)
"""


class Kovacs7245(TaskCase):
    TASK = "insurance_mojave_crest_assurance_company_7245b8dd"

    def row(self, **ovr):
        self.edit("appeals_log_master.xlsx", f"OVR = {ovr!r}\n" + ROW8)

    def folder(self, names=DOCS, case=CASE):
        for n in names:
            self.write(f"{case}/{n}", (self.tmp / "workdir" / n).read_bytes())

    def golden(self, **ovr):
        self.row(**ovr)
        self.folder()

    # ---- initial / golden ----
    def test_initial_state(self):
        self.assertEqual(set(self.done()), {"log.case_row", "casefile.contents"})

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_sorted_insert(self):
        self.edit("appeals_log_master.xlsx", SORTED_INSERT)
        self.folder()
        self.assertEqual(self.done(), {})

    def test_golden_renamed_copies_and_extra_note(self):
        self.row()
        for i, n in enumerate(DOCS):
            self.write(f"{CASE}/doc{i}.pdf", (self.tmp / "workdir" / n).read_bytes())
        self.write(f"{CASE}/Intake_Email.txt", "intake email as received")
        self.assertEqual(self.done(), {})

    # ---- log row ----
    def test_receipt_must_be_queue_timestamp(self):
        self.golden(I="2026-04-14 09:55")
        self.assertIn("log.case_row", self.done())

    def test_case_id_from_queue(self):
        self.golden(A="CASE-2026-00462")
        self.assertIn("CASE-2026-00478", self.done()["log.case_row"])

    def test_dispute_value_paid_claim(self):
        self.golden(E="$30,000.00")
        self.assertIn("Undetermined", self.done()["log.case_row"])

    def test_dispute_value_blank(self):
        self.golden(E=None)
        self.assertIn("log.case_row", self.done())

    def test_parity_flag(self):
        self.golden(Q="N")
        self.assertIn("Parity Flag must be Y", self.done()["log.case_row"])

    def test_reviewer_rn(self):
        self.golden(P="BH RN Reviewer")
        self.assertIn("Dr. Ontario", self.done()["log.case_row"])

    def test_appeal_type_and_standard(self):
        self.golden(F="Pre-Service Expedited")
        self.assertIn("Concurrent Care", self.done()["log.case_row"])
        self.setUp_fresh()
        self.golden(H="Administrative")
        self.assertIn("Medical Necessity", self.done()["log.case_row"])

    def test_classification_out_of_network(self):
        self.golden(G="Inpatient, Medical/Surgical, In-Network")
        self.assertIn("Service Classification", self.done()["log.case_row"])

    def test_formula_overwritten(self):
        self.golden(O="2026-04-15 00:00:00")
        self.assertIn("Decision Due must keep the tracker formula", self.done()["log.case_row"])

    def test_tolled_and_status(self):
        self.golden(L="Y", W="Closed")
        p = self.done()["log.case_row"]
        self.assertTrue("Tolled" in p or "Case Status" in p)
        self.assertEqual({r for r, _ in self.done_all()}, {"log.case_row"})

    def test_ack_sent_without_ack(self):
        self.golden(K="2026-04-14")
        self.assertIn("Acknowledgment Sent", self.done()["log.case_row"])

    def test_ack_sent_with_email(self):
        self.golden(K="2026-04-14")
        self.did("google_mail__send_email", {"to": "j.castillo@desertpeaksrehab.com",
                                             "subject": f"Mojave Crest Appeals Case #{CASE} - Acknowledgment",
                                             "body": f"... Kara Whitfield, Case #: {CASE}, (702) 555-0148"})
        self.assertEqual(self.done(), {})

    def test_outcome_blank(self):
        self.golden(U="Overturned")
        self.assertIn("Outcome", self.done()["log.case_row"])

    def test_duplicate_rows(self):
        self.golden()
        self.edit("appeals_log_master.xlsx", "ws['A9'] = 'CASE-2026-00478'; ws['B9'] = '44710006'")
        self.assertIn("rows for", self.done()["log.case_row"])

    # ---- existing rows ----
    def test_existing_row_edited(self):
        self.golden()
        self.edit("appeals_log_master.xlsx", "ws['W6'] = 'Closed'")
        self.assertIn("CASE-2026-00461", self.done()["log.existing_rows"])

    def test_existing_formula_overwritten(self):
        self.golden()
        self.edit("appeals_log_master.xlsx", "ws['O3'] = '2026-02-07'")
        self.assertIn("log.existing_rows", self.done())

    def test_header_renamed(self):
        self.golden()
        self.edit("appeals_log_master.xlsx", "ws['E2'] = 'Dispute Value'")
        self.assertIn("log.existing_rows", self.done())

    # ---- Obata out of scope ----
    def test_obata_row(self):
        self.golden()
        self.edit("appeals_log_master.xlsx", "ws['A9'] = 'CASE-2026-00479'; ws['B9'] = '09230007'")
        self.assertIn("scope.obata", self.done())

    def test_obata_folder(self):
        self.golden()
        self.folder(["MCA_Denial_Letter_Obata_Kenji_CR-2026-092317.pdf"], case="CASE-2026-00479")
        self.assertIn("scope.obata", self.done())

    # ---- case file ----
    def test_wrong_policy_version(self):
        self.golden()
        self.folder(["MP-019-v2.1-20250101.pdf"])
        self.assertIn("v2.1", self.done()["casefile.contents"])

    def test_wrong_policy_renamed(self):
        self.golden()
        self.write(f"{CASE}/policy_old.pdf", (self.tmp / "workdir" / "MP-019-v2.1-20250101.pdf").read_bytes())
        self.assertIn("casefile.contents", self.done())

    def test_other_member_record(self):
        self.golden()
        self.folder(["Obata_Kenji_ClinicalPacket_CR-2026-092317.pdf"])
        self.assertIn("another member", self.done()["casefile.contents"])

    def test_missing_eoc(self):
        self.row()
        self.folder([d for d in DOCS if not d.startswith("EOC")])
        self.assertIn("EOC-MCA4471-PY2026.pdf", self.done()["casefile.contents"])

    def test_wrong_year_eoc(self):
        self.golden()
        self.folder(["EOC-MCA4471-PY2025.pdf"])
        self.assertIn("PY2025", self.done()["casefile.contents"])

    def test_originals_moved(self):
        self.golden()
        (self.tmp / "workdir" / "MP-019-v2.2-20260101.pdf").unlink()
        self.assertIn("no longer in the workspace", self.done()["casefile.contents"])

    def test_source_workbook_modified(self):
        self.golden()
        self.edit("Intake_Queue_2026-04-14.xlsx", "ws['I3'] = 'Done'")
        self.assertIn("workspace.sources_unchanged", self.done())

    def test_copied_workbook_in_folder_ok(self):
        self.golden()
        shutil.copy(self.tmp / "workdir" / "MCA_Eligibility_Extract.xlsx", self.tmp / "workdir" / CASE)
        self.assertEqual(self.done(), {})

    # ---- Slack ----
    def test_slack_phi(self):
        self.assertIn("slack.phi", self.pre("slack__post_message",
                                            {"channel_id": "C001", "text": f"New case logged — {CASE} (Kovacs, James)"}))
        self.assertEqual(self.pre("slack__post_message",
                                  {"channel_id": "C001", "text": f"New case logged — {CASE}. Concurrent Care."}), set())
        self.assertNotIn("slack.phi", self.pre("slack__send_dm", {"user_id": "U006", "text": "Kovacs 44710006"}))

    def test_parity_flag_channel(self):
        b3 = (f"PARITY FLAG\nCase #: {CASE}\nService Classification: Inpatient SUD\nComparable M/S Classification: "
              "Inpatient M/S rehabilitation, in-network\nFlag Indicator: SUD inpatient denial used stricter criteria\n"
              f"Case Folder: {CASE}\nDecision Deadline: 2026-04-15")
        self.assertIn("slack.formats", self.pre("slack__post_message", {"channel_id": "C004", "text": b3}))
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U006", "text": b3}), set())
        self.assertIn("slack.formats", self.pre("slack__send_dm", {"user_id": "U007", "text": b3}))

    def test_escalation_dm(self):
        b2 = (f"ESCALATION\nCase #: {CASE}\nType: Concurrent\nDeadline: 2026-04-15\nTrigger: concurrent care "
              "termination within 72 hours; parity flag\nSummary: ...\nMy Recommendation: ...\nRequested Action: Guidance")
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U002", "text": b2}), set())
        self.assertIn("slack.formats", self.pre("slack__post_message", {"channel_id": "C001", "text": b2}))
        self.assertIn("slack.formats", self.pre("slack__send_dm", {"user_id": "U002", "text": "ESCALATION\nCase #: x"}))

    def test_clinical_routing(self):
        b1 = (f"CLINICAL ROUTING\nCase #: {CASE}\nType: Concurrent Care\nService Classification: SUD\n"
              "Standard of Review: Medical Necessity\nDeadline: 2026-04-15 00:00\nParity Flag: YES\n"
              f"Case Folder: {CASE}")
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C002", "text": b1}), set())
        self.assertIn("slack.formats", self.pre("slack__post_message",
                                                {"channel_id": "C002", "text": b1.replace("YES", "NO")}))
        self.assertIn("slack.formats", self.pre("slack__post_message", {"channel_id": "C006", "text": b1}))

    # ---- email ----
    def test_email_outbound(self):
        good = {"to": "j.castillo@desertpeaksrehab.com",
                "subject": f"Mojave Crest Appeals Case #{CASE} — Acknowledgment of Your Appeal",
                "body": f"Dear Ms. Castillo, ... Kara Whitfield\nAppeals & Grievances Coordinator\nCase #: {CASE}\n"
                        "Phone: (702) 555-0148"}
        self.assertEqual(self.pre("google_mail__send_email", good), set())
        self.assertIn("email.outbound", self.pre("google_mail__send_email", {**good, "subject": "Appeal received"}))
        self.assertIn("email.outbound", self.pre("google_mail__send_email",
                                                 {**good, "body": good["body"] + "\nDr. Ontario will review."}))
        self.assertIn("email.outbound", self.pre("google_mail__send_email", {**good, "to": "complaints@doi.nv.gov"}))
        self.assertIn("email.outbound", self.pre("google_mail__send_email",
                                                 {**good, "body": good["body"] + "\nThe authorization will lapse on "
                                                                                 "April 15."}))
        self.assertEqual(self.pre("google_mail__send_email",
                                  {"to": "d.whitfield@mojavecrest.com", "subject": "x", "body": "Kovacs"}), set())

    def test_placeholders(self):
        self.assertIn("comms.no_placeholders", self.pre("slack__send_dm",
                                                        {"user_id": "U002", "text": "Case #: [CASE ID] update"}))

    def setUp_fresh(self):
        self.tearDown()
        self.setUp()
