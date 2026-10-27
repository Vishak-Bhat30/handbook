"""Blind unit tests for medical_pathfinder_billing_and_coding_c01deb6e (fixtures from the seed only)."""

from interwhen_sop.tests.base import TaskCase

TASK = "medical_pathfinder_billing_and_coding_c01deb6e"
REG, DEN, RAQ, ESC = ("PBC_Claim_Register.xlsx", "PBC_Denial_Worklist.xlsx", "PBC_RA_Queue.xlsx",
                      "PBC_Escalation_Log.xlsx")
SEND = "google_mail__send_email"
POST = "slack__post_message"

REGISTER = r"""
M = '$#,##0.00'
upd = {'CLM-2026-0845': ('Paid - Full', 142, 38, 'Reconciled'), 'CLM-2026-0878': ('Paid - Full', 228, 57, 'Reconciled'),
       'CLM-2026-1104': ('Paid - Full', 1850, 350, 'Reconciled'), 'CLM-2026-0892': ('Denied', 0, 285, 'Posted'),
       'CLM-2026-1105': ('Denied', 0, 1850, 'Posted'),
       'CLM-2026-0967': ('In Recovery', 4200, 3300, 'Held - Contractual Variance')}
carc = {'CLM-2026-0892': ('CO-16', 'N382'), 'CLM-2026-1105': ('CO-97', 'N520'), 'CLM-2026-0967': ('CO-45', 'N130')}
for r in range(2, ws.max_row + 1):
    cid = ws.cell(r, 1).value
    if cid in upd:
        s, p, a, ps = upd[cid]
        ws.cell(r, col['Claim Status']).value = s
        ws.cell(r, col['Payment Amount']).value = p
        ws.cell(r, col['Adjustment Amount']).value = a
        ws.cell(r, col['Patient Balance']).value = 0
        ws.cell(r, col['Payment Posting Status']).value = ps
        if cid in carc:
            ws.cell(r, col['CARC']).value, ws.cell(r, col['RARC']).value = carc[cid]
src = {ws.cell(r, 1).value: [c.value for c in ws[r]] for r in range(2, ws.max_row + 1)}
def corr(new, orig, mod):
    v = list(src[orig])
    v[0] = new
    v[col['Modifier'] - 1] = mod
    v[col['Claim Frequency Code'] - 1] = '7'
    v[col['Original Claim ID'] - 1] = orig
    v[col['Claim Status'] - 1] = 'Submitted'
    v[col['Payment Amount'] - 1] = v[col['Adjustment Amount'] - 1] = v[col['Patient Balance'] - 1] = 0
    v[col['Payment Posting Status'] - 1] = v[col['CARC'] - 1] = v[col['RARC'] - 1] = None
    ws.append(v)
    for h in ('Dollar Value', 'Payment Amount', 'Adjustment Amount', 'Patient Balance'):
        ws.cell(ws.max_row, col[h]).number_format = M
corr('CLM-2026-1106', 'CLM-2026-0892', None)
corr('CLM-2026-1107', 'CLM-2026-1105', 'LT')
"""
WORKLIST = r"""
T = '04/24/2026'
for r in [
 ['DEN-2026-0028','CLM-2026-0892','PAT-1042','Michael Torres','03/15/2026','BlueCross TX','CO-16','N382','Technical/Administrative','Correct and Resubmit','Resubmitted','Maria Santos',T,None],
 ['DEN-2026-0029','CLM-2026-1105','PAT-1058','Linda Park','03/20/2026','BlueCross TX','CO-97','N520','Technical/Administrative','Add Modifier and Resubmit','Resubmitted','Maria Santos',T,None],
 ['DEN-2026-0030','CLM-2026-0967','PAT-1063','Robert Daniels','03/08/2026','BlueCross TX','CO-45','N130','Contractual/Payer Error','Appeal - Contractual Rate Dispute','Escalated','Maria Santos',T,None]]:
    ws.append(r)
"""
QUEUE = r"""
T = '04/24/2026'
for r in [['RA-2026-0031',T,'CLM-2026-0892','PAT-1042','ERA Processing','Medium','Maria Santos','Open',None],
          ['RA-2026-0032',T,'CLM-2026-1105','PAT-1058','ERA Processing','High','Maria Santos','Open',None],
          ['RA-2026-0033',T,'CLM-2026-0967','PAT-1063','ERA Processing','High','Maria Santos','Open',None]]:
    ws.append(r)
"""
ESCALATIONS = r"""
T = '04/24/2026'
ws.append(['ESC-2026-0008',T,'CLM-2026-0967','Financial','Payer Dispute','Maria Santos','David Park','Open',None])
ws.append(['ESC-2026-0009',T,'CLM-2026-0234, CLM-2026-0356, CLM-2026-0489, CLM-2026-0612, CLM-2026-0892','Operational','Pattern Recurrence','Maria Santos','David Park','Open',None])
"""
SUBJECT = "Pattern Recurrence Alert: Dr. Sarah Chen \u2014 CO-16 \u2014 5 Instances"
BODY = """Pattern Recurrence Report \u2014 04/24/2026

This is Maria Santos, Resolution Auditor, reporting a pattern recurrence for Dr. Sarah Chen, NPI: 1234567890. Denial Code: CO-16 \u2014 RARC: N382 \u2014 5 instances identified. Affected Claims:

1. Claim ID: CLM-2026-0234 \u2014 Patient ID: PAT-1008 \u2014 DOS: 01/15/2026 \u2014 CPT: 99214 \u2014 Status: Resubmitted \u2014 Payer: BlueCross TX
2. Claim ID: CLM-2026-0356 \u2014 Patient ID: PAT-1012 \u2014 DOS: 01/28/2026 \u2014 CPT: 99213 \u2014 Status: Resubmitted \u2014 Payer: Aetna
3. Claim ID: CLM-2026-0489 \u2014 Patient ID: PAT-1019 \u2014 DOS: 02/10/2026 \u2014 CPT: 99214 \u2014 Status: Resubmitted \u2014 Payer: BlueCross TX
4. Claim ID: CLM-2026-0612 \u2014 Patient ID: PAT-1027 \u2014 DOS: 02/22/2026 \u2014 CPT: 99213 \u2014 Status: Resubmitted \u2014 Payer: BlueCross TX
5. Claim ID: CLM-2026-0892 \u2014 Patient ID: PAT-1042 \u2014 DOS: 03/15/2026 \u2014 CPT: 99214 \u2014 Status: Denied \u2014 Payer: BlueCross TX

Assessment: This pattern suggests a systemic submission error. Requesting management review to determine whether a corrective action plan or direct clinic intervention is warranted.

Escalation Log Entry ID: ESC-2026-0009. Escalation Category: Operational. Escalation Reason: Pattern Recurrence."""
EMAIL = {"to": "david.park@pathfinderbilling.com", "subject": SUBJECT, "body": BODY}


class C01deb6eCase(TaskCase):
    TASK = TASK

    def golden(self, email=True):
        self.edit(REG, REGISTER)
        self.edit(DEN, WORKLIST)
        self.edit(RAQ, QUEUE)
        self.edit(ESC, ESCALATIONS)
        if email:
            self.did(SEND, EMAIL, '{"status": "sent"}')


class TestInitialAndGolden(C01deb6eCase):
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {
            "pbc.post_clean_lines", "pbc.post_denied_lines", "pbc.contractual_variance", "pbc.denial_worklist",
            "pbc.corrected_claims", "pbc.ra_queue", "pbc.escalation_payer_dispute", "pbc.escalation_pattern",
            "pbc.pattern_report.messages_sent"})

    def test_golden_path_is_clean(self):
        self.golden()
        self.assertEqual(self.done_all(), [])

    def test_paid_partial_and_posted_accepted(self):
        self.golden()
        self.edit(REG, "for r in range(2, ws.max_row+1):\n"
                       "    if ws.cell(r,1).value=='CLM-2026-1104': ws.cell(r,col['Claim Status']).value='Paid - Partial'\n"
                       "    if ws.cell(r,1).value=='CLM-2026-0845': ws.cell(r,col['Payment Posting Status']).value='Posted'")
        self.assertEqual(self.done_all(), [])


def set_reg(claim, field, value):
    return (f"for r in range(2, ws.max_row+1):\n"
            f"    if ws.cell(r,1).value=={claim!r}: ws.cell(r,col[{field!r}]).value={value!r}")


def set_row(id_value, field, value):
    return (f"for r in range(2, ws.max_row+1):\n"
            f"    if ws.cell(r,1).value=={id_value!r}: ws.cell(r,col[{field!r}]).value={value!r}")


class TestPostingRules(C01deb6eCase):
    def test_clean_line_held_is_flagged(self):
        self.golden()
        self.edit(REG, set_reg("CLM-2026-0845", "Payment Posting Status", "Held - Contractual Variance"))
        self.assertIn("pbc.post_clean_lines", self.done())

    def test_denied_line_amount_missing(self):
        self.golden()
        self.edit(REG, set_reg("CLM-2026-0892", "Adjustment Amount", 0))
        self.assertIn("pbc.post_denied_lines", self.done())

    def test_variance_written_off(self):
        self.golden()
        self.edit(REG, set_reg("CLM-2026-0967", "Claim Status", "Written Off"))
        self.assertIn("pbc.contractual_variance", self.done())

    def test_variance_not_held(self):
        self.golden()
        self.edit(REG, set_reg("CLM-2026-0967", "Payment Posting Status", "Posted"))
        self.assertIn("pbc.contractual_variance", self.done())


class TestRoutingRules(C01deb6eCase):
    def test_worklist_status_pending_review(self):
        self.golden()
        self.edit(DEN, set_row("DEN-2026-0028", "Recovery Status", "Pending Review"))
        self.assertIn("pbc.denial_worklist", self.done())

    def test_worklist_wrong_category(self):
        self.golden()
        self.edit(DEN, set_row("DEN-2026-0030", "Denial Category", "Technical/Administrative"))
        self.assertIn("pbc.denial_worklist", self.done())

    def test_corrected_claim_modifier_59_only(self):
        self.golden()
        self.edit(REG, set_reg("CLM-2026-1107", "Modifier", "59"))
        self.assertIn("pbc.corrected_claims", self.done())

    def test_corrected_claim_modifier_variants_ok(self):
        self.golden()
        self.edit(REG, set_reg("CLM-2026-1107", "Modifier", "-LT"))
        self.assertNotIn("pbc.corrected_claims", self.done())

    def test_corrected_claim_wrong_frequency(self):
        self.golden()
        self.edit(REG, set_reg("CLM-2026-1106", "Claim Frequency Code", "1"))
        self.assertIn("pbc.corrected_claims", self.done())

    def test_ra_queue_missing_row(self):
        self.golden()
        self.edit(RAQ, "ws.delete_rows(ws.max_row)")
        self.assertIn("pbc.ra_queue", self.done())

    def test_payer_dispute_reason(self):
        self.golden()
        self.edit(ESC, set_row("ESC-2026-0008", "Escalation Reason", "High Value Claim"))
        self.assertIn("pbc.escalation_payer_dispute", self.done())

    def test_payer_dispute_category(self):
        self.golden()
        self.edit(ESC, set_row("ESC-2026-0008", "Escalation Category", "Operational"))
        self.assertIn("pbc.escalation_payer_dispute", self.done())

    def test_pattern_category(self):
        self.golden()
        self.edit(ESC, set_row("ESC-2026-0009", "Escalation Category", "Financial"))
        self.assertIn("pbc.escalation_pattern", self.done())

    def test_pattern_email_cites_wrong_log_id(self):
        self.golden(email=False)
        self.did(SEND, {**EMAIL, "body": BODY.replace("ESC-2026-0009", "ESC-2026-0008")}, '{"status": "sent"}')
        self.assertIn("pbc.escalation_pattern", self.done())


class TestPatternEmail(C01deb6eCase):
    def test_compliant_email_allowed(self):
        self.assertEqual(self.pre(SEND, EMAIL), set())

    def test_subject_with_extra_text_blocked(self):
        bad = {**EMAIL, "subject": "Pattern Recurrence Alert: Dr. Sarah Chen (NPI 1234567890) \u2014 CO-16 \u2014 5 Instances"}
        self.assertIn("pbc.pattern_report.messages", self.pre(SEND, bad))

    def test_wrong_role_blocked(self):
        bad = {**EMAIL, "body": BODY.replace("Resolution Auditor", "Billing Specialist")}
        self.assertIn("pbc.pattern_report.messages", self.pre(SEND, bad))

    def test_missing_claim_blocked(self):
        bad = {**EMAIL, "body": BODY.replace("CLM-2026-0356", "CLM-2026-0357")}
        self.assertIn("pbc.pattern_report.messages", self.pre(SEND, bad))

    def test_not_sent_is_flagged(self):
        self.golden(email=False)
        self.assertEqual(set(self.done()), {"pbc.pattern_report.messages_sent"})

    def test_placeholder_blocked(self):
        bad = {**EMAIL, "body": BODY + "\n[Continue for all instances]"}
        self.assertIn("comms.no_placeholders", self.pre(SEND, bad))


class TestIntegrityRules(C01deb6eCase):
    def test_extra_escalation_row(self):
        self.golden()
        self.edit(ESC, "ws.append(['ESC-2026-0010','04/24/2026','CLM-2026-1105','Operational','Payer Dispute',"
                       "'Maria Santos','David Park','Open',None])")
        self.assertIn("pbc.no_extra_rows", self.done())

    def test_extra_worklist_row(self):
        self.golden()
        self.edit(DEN, "ws.append(['DEN-2026-0031','CLM-2026-0845','PAT-1021','Jennifer Walsh','03/10/2026',"
                       "'BlueCross TX','CO-45','N130','Contractual/Payer Error','Write Off','Resolved','Maria Santos',"
                       "'04/24/2026',None])")
        self.assertIn("pbc.no_extra_rows", self.done())

    def test_unrelated_claim_edited(self):
        self.golden()
        self.edit(REG, set_reg("CLM-2026-0234", "Claim Status", "Closed"))
        self.assertIn("pbc.register_untouched", self.done())

    def test_batch_claim_identity_edited(self):
        self.golden()
        self.edit(REG, set_reg("CLM-2026-1105", "Modifier", "LT"))
        self.assertIn("pbc.register_untouched", self.done())

    def test_era_modified(self):
        self.golden()
        self.edit("ERA_20260417.xlsx", "ws.cell(8, 12).value = 'Posted'")
        self.assertIn("pbc.reference_files_unchanged", self.done())

    def test_escalation_log_append_only(self):
        self.golden()
        self.edit(ESC, set_row("ESC-2026-0003", "Status", "Open"))
        self.assertIn("pbc.escalation_log_append_only", self.done())

    def test_worklist_append_only(self):
        self.golden()
        self.edit(DEN, set_row("DEN-2026-0015", "Recovery Status", "Resolved"))
        self.assertIn("pbc.denial_worklist_append_only", self.done())

    def test_ra_queue_append_only(self):
        self.golden()
        self.edit(RAQ, set_row("RA-2026-0030", "Status", "Open"))
        self.assertIn("pbc.ra_queue_append_only", self.done())

    def test_ids_not_sequential(self):
        self.golden()
        self.edit(REG, set_reg("CLM-2026-1107", "Claim ID", "CLM-2026-1200"))
        self.assertIn("pbc.new_ids_sequential", self.done())

    def test_date_format(self):
        self.golden()
        self.edit(DEN, set_row("DEN-2026-0029", "Date Opened", "2026-04-24"))
        self.assertIn("pbc.field_formats", self.done())

    def test_name_format(self):
        self.golden()
        self.edit(ESC, set_row("ESC-2026-0008", "Escalated To", "David Park (RCM Manager)"))
        self.assertIn("pbc.field_formats", self.done())

    def test_free_text_status(self):
        self.golden()
        self.edit(REG, set_reg("CLM-2026-1106", "Claim Status", "Pending resubmission"))
        self.assertIn("pbc.field_formats", self.done())

    def test_money_format_general(self):
        self.golden()
        self.edit(REG, "ws.cell(ws.max_row, col['Dollar Value']).number_format = 'General'")
        self.assertIn("pbc.money_format", self.done())

    def test_money_as_text_ok(self):
        self.golden()
        self.edit(REG, "ws.cell(ws.max_row, col['Dollar Value']).value = '$1,850.00'")
        self.assertNotIn("pbc.money_format", self.done())


class TestMessageRules(C01deb6eCase):
    def test_slack_with_patient_name_blocked(self):
        self.assertIn("pbc.phi_in_messages", self.pre(POST, {"channel_id": "C002",
                                                             "text": "CO-16 on Michael Torres's claim CLM-2026-0892"}))

    def test_slack_without_phi_allowed(self):
        self.assertEqual(self.pre(POST, {"channel_id": "C002", "text": "ERA_20260417 is posted; 3 denials routed."}),
                         set())

    def test_external_email_with_patient_id_blocked(self):
        self.assertIn("pbc.phi_in_messages", self.pre(SEND, {
            "to": "provideroperations@bcbstx.com", "subject": "Appeal",
            "body": "Appeal for PAT-1063 claim CLM-2026-0967, DOS 03/08/2026, CPT 27447, BlueCross TX, In Recovery."}))

    def test_internal_email_with_name_not_phi_blocked(self):
        got = self.pre(SEND, {"to": "david.park@pathfinderbilling.com", "subject": "CO-45 dispute",
                              "body": "Robert Daniels claim CLM-2026-0967 (PAT-1063), DOS 03/08/2026, CPT 27447, "
                                      "BlueCross TX, status In Recovery."})
        self.assertEqual(got, set())

    def test_claim_reference_missing_fields_blocked(self):
        got = self.pre(SEND, {"to": "david.park@pathfinderbilling.com", "subject": "CO-45 dispute",
                              "body": "FYI CLM-2026-0967 was underpaid and is In Recovery."})
        self.assertIn("pbc.claim_reference_fields", got)
