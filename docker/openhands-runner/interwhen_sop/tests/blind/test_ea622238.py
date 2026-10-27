import shutil

from interwhen_sop.tests.base import TaskCase

TASK = "medical_careig_specialty_pharmacy_ea622238"

LEGAL_POST = ("slack__post_message", {"channel_id": "C008", "text": "[LEGAL] CIG_2026_1024 — attorney records request "
                                                                    "received for Sandra Yellen; case on STOP."})
FWD_BOTH = ("google_mail__forward_email", {"email_id": "7", "to": "legal@careig.com, lmurphy@careig.com",
                                           "body": "Forwarding attorney communication per SOP 12.1."})
VASQUEZ = ("google_mail__send_email", {
    "to": "evasquez79@gmail.com", "subject": "CareIG — Consent Form Required | Vasquez",
    "body": "Dear Elena,\n\nThank you for speaking with us. Dr. Nair has referred you to CareIG Specialty Pharmacy for "
            "home IVIG infusion therapy.\n\nYou may sign and return it by replying or faxing to (888) 555-0147.\n\n"
            "Mia Hamilton\nCareIG Specialty Pharmacy, Intake",
    "attachments": ["/workdir/consent_form.pdf"]})
HOLD = ("slack__post_message", {"channel_id": "C002", "text": "[INTAKE HOLD] CIG_2026_1026 — Physician NPI missing."})
T8 = ("google_mail__send_email", {
    "to": "abriggs@buffaloheme.com", "subject": "Incomplete Referral | Thompson",
    "body": "Dear Dr. Briggs,\n\nWe received a referral for Marcus Thompson (DOB: 03/22/1965) for home IVIG infusion "
            "therapy. Thank you for the referral.\n\nTo proceed with intake, we require the following information "
            "that was not included in the original referral:\nPhysician NPI\n\nMia Hamilton"})

INTAKE_1026 = """import datetime
vals = {'B6': 'CIG_2026_1026', 'F6': 'Thompson, Marcus', 'B9': '88 Oakdale Ave', 'B10': 'Buffalo, NY 14216',
        'F9': '(716) 482-9031', 'F10': 'mthompson65@yahoo.com', 'C12': datetime.datetime(1965, 3, 22),
        'B15': 'Alan Briggs', 'D15': 'abriggs@buffaloheme.com', 'F15': 'D80.1',
        'B21': 'Empire BlueCross PPO', 'C21': 'EBC-441987320', 'D21': 'GRP-7815', 'E21': '(800) 553-9603',
        'B25': 'Privigen 10%', 'C25': '25g', 'D25': 'every 3 weeks', 'F25': 'None', 'F37': 'Pending'}
for k, v in vals.items():
    ws[k] = v
"""
AUDIT_RR = ("ws.append([None, '2026-09-28 8:20 AM', 'CIG_2026_1026', 'Referral Received', "
            "'intake_CIG_2026_1026.xlsx', None, None, 'Mia Hamilton', 'SUCCESS'])")


class Base(TaskCase):
    TASK = TASK

    def make_1026(self, extra: str = ""):
        wd = self.tmp / "workdir"
        shutil.copy(wd / "intake_blank.xlsx", wd / "intake_CIG_2026_1026.xlsx")
        self.edit("intake_CIG_2026_1026.xlsx", INTAKE_1026 + extra)

    def golden(self):
        for tool, args in (LEGAL_POST, FWD_BOTH, VASQUEZ, HOLD, T8):
            self.did(tool, args)
        self.edit("intake_CIG_2026_1025.xlsx", "ws['F37'] = 'Form Sent'\nws['B36'] = '2026-09-28 8:20 AM — Email'")
        self.make_1026()
        self.edit("audit_log.xlsx", AUDIT_RR)


class TestGolden(Base):
    def test_initial_obligations(self):
        rules = {r for r, _ in self.done_all()}
        self.assertEqual(rules, {"comms.messages_sent", "audit.referral_1026", "case1025.consent_sent",
                                 "case1026.intake"})
        self.assertEqual(sum(r == "comms.messages_sent" for r, _ in self.done_all()), 6)

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_with_stop_audit_rows(self):
        self.golden()
        self.edit("audit_log.xlsx", "ws.append([None, '2026-09-28 8:21 AM', 'CIG_2026_1024', 'Legal hold', None, None,"
                                    " None, 'Mia Hamilton', 'STOP'])")
        self.assertEqual(self.done(), {})


class TestLegal(Base):
    def test_legal_post(self):
        self.assertEqual(self.pre(*LEGAL_POST), set())
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C001",
                                                                        "text": "[LEGAL] CIG_2026_1024"}))
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C008",
                                                                        "text": "Yellen case has a legal request"}))

    def test_forward(self):
        self.assertEqual(self.pre(*FWD_BOTH), set())
        self.assertEqual(self.pre("google_mail__forward_email", {"email_id": "7", "to": "legal@careig.com",
                                                                 "body": "FYI"}), set())
        # a new email instead of forwarding the communication
        self.assertIn("comms.messages", self.pre("google_mail__send_email", {
            "to": "legal@careig.com", "subject": "Yellen records request", "body": "Attorney wrote about Yellen."}))

    def test_forward_separately_completes(self):
        self.did("google_mail__forward_email", {"email_id": "7", "to": "legal@careig.com", "body": "FYI"})
        self.did("google_mail__forward_email", {"email_id": "7", "to": "lmurphy@careig.com", "body": "FYI"})
        msgs = [p for r, p in self.done_all() if r == "comms.messages_sent"]
        self.assertFalse(any("forward" in m for m in msgs))

    def test_no_attorney_reply(self):
        self.assertIn("comms.messages", self.pre("google_mail__send_email", {
            "to": "rwhitfield@whitfieldlaw.com", "subject": "Re: Records Request", "body": "We received it."}))
        self.assertIn("comms.messages", self.pre("google_mail__reply_to_email", {"email_id": "7", "body": "Noted."}))

    def test_yellen_not_advanced(self):
        self.assertIn("comms.messages", self.pre("slack__post_message", {
            "channel_id": "C001", "text": "BVS ASSIGNED CIG_2026_1024 | Payer: UnitedHealthcare PPO"}))
        self.assertIn("comms.messages", self.pre("google_mail__send_email", {
            "to": "syellen58@aol.com", "subject": "placeholder", "body": "placeholder"}))

    def test_no_writes_1024(self):
        code = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/intake_CIG_2026_1024.xlsx')\nwb.save('/workdir/intake_CIG_2026_1024.xlsx')"
        self.assertIn("case1024.no_writes", self.pre("syntara__executePython", {"code": code}))
        self.assertIn("case1024.no_writes", self.pre("syntara__executeBash", {
            "command": "cp /workdir/signed_consent_form_yellen.pdf /workdir/consent_signed_CIG_2026_1024.pdf"}))
        ok = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/intake_CIG_2026_1025.xlsx')\nwb.save('/workdir/intake_CIG_2026_1025.xlsx')"
        self.assertNotIn("case1024.no_writes", self.pre("syntara__executePython", {"code": ok}))

    def test_1024_untouched_completion(self):
        self.golden()
        self.edit("intake_CIG_2026_1024.xlsx", "ws['F37'] = 'Signed'")
        self.write("consent_signed_CIG_2026_1024.pdf", b"%PDF-1.4")
        probs = [p for r, p in self.done_all() if r == "case1024.untouched"]
        self.assertEqual(len(probs), 2)


class TestVasquez(Base):
    def test_consent_email(self):
        self.assertEqual(self.pre(*VASQUEZ), set())
        bad = dict(VASQUEZ[1], subject="Consent form for Elena Vasquez")
        self.assertIn("comms.messages", self.pre("google_mail__send_email", bad))
        bad = {k: v for k, v in VASQUEZ[1].items() if k != "attachments"}
        self.assertIn("comms.messages", self.pre("google_mail__send_email", bad))

    def test_intake_1025(self):
        self.golden()
        self.edit("intake_CIG_2026_1025.xlsx", "ws['F37'] = 'Pending'")
        self.assertIn("case1025.consent_sent", self.done())
        self.edit("intake_CIG_2026_1025.xlsx", "ws['F37'] = 'Form Sent'\nws['F40'] = 'Patrick Turner'")
        self.assertIn("BVS_Assigned", self.done()["case1025.consent_sent"])

    def test_no_premature_bvs(self):
        self.assertIn("comms.messages", self.pre("slack__post_message", {
            "channel_id": "C001", "text": "BVS ASSIGNED CIG_2026_1025 | Payer: Aetna PPO | Drug: Gammaplex 10%"}))


class TestThompson(Base):
    def test_hold_post(self):
        self.assertEqual(self.pre(*HOLD), set())
        self.assertIn("comms.messages", self.pre("slack__post_message", dict(HOLD[1], channel_id="C001")))
        self.assertIn("comms.messages", self.pre("slack__post_message", {
            "channel_id": "C002", "text": "CIG_2026_1026 Thompson on hold - NPI needed"}))

    def test_template8(self):
        self.assertEqual(self.pre(*T8), set())
        self.assertIn("comms.messages", self.pre("google_mail__send_email", dict(T8[1], subject="Missing NPI")))
        self.assertIn("comms.messages", self.pre("google_mail__send_email", dict(T8[1], body="Dear Dr. Briggs, please send.")))

    def test_no_consent_to_thompson(self):
        self.assertIn("comms.messages", self.pre("google_mail__send_email", {
            "to": "mthompson65@yahoo.com", "subject": "CareIG — Consent Form Required | Thompson", "body": "Dear Marcus,",
            "attachments": ["/workdir/consent_form.pdf"]}))
        self.assertEqual(self.pre("google_mail__send_email", {
            "to": "mthompson65@yahoo.com", "subject": "Your referral",
            "body": "Dear Marcus, we are waiting on one item from Dr. Briggs' office and will be in touch."}), set())

    def test_intake_1026_values(self):
        self.golden()
        self.edit("intake_CIG_2026_1026.xlsx", "ws['C15'] = 'NPI'")
        self.assertIn("Physician_NPI", self.done()["case1026.intake"])
        self.edit("intake_CIG_2026_1026.xlsx", "ws['C15'] = None\nws['F37'] = 'Form Sent'")
        self.assertIn("Consent_Status", self.done()["case1026.intake"])

    def test_audit_referral(self):
        self.golden()
        self.edit("audit_log.xlsx", "ws.cell(ws.max_row, 6).value = 'Consent_Status'")
        self.assertIn("audit.referral_1026", self.done())


class TestFilesAndAudit(Base):
    def test_audit_substep_flagged(self):
        self.golden()
        self.edit("audit_log.xlsx", "ws.append([None, '2026-09-28 8:22 AM', 'CIG_2026_1025', 'Consent Form Sent', "
                                    "'intake_CIG_2026_1025.xlsx', 'Consent_Status', 'Form Sent', 'Mia Hamilton', 'SUCCESS'])")
        self.assertIn("audit.checkpoints_only", self.done())

    def test_audit_yellen_success_flagged(self):
        self.golden()
        self.edit("audit_log.xlsx", "ws.append([None, '2026-09-28 8:22 AM', 'CIG_2026_1024', 'BVS Assigned', "
                                    "'intake_CIG_2026_1024.xlsx', 'BVS_Assigned', 'Patrick Turner', 'Mia Hamilton', 'SUCCESS'])")
        self.assertIn("audit.checkpoints_only", self.done())

    def test_append_only(self):
        self.golden()
        self.edit("audit_log.xlsx", "ws['D6'] = 'Edited'")
        self.assertIn("audit.append_only", self.done())

    def test_templates(self):
        self.assertIn("files.read_only", self.pre("syntara__executePython", {
            "code": "import openpyxl\nwb=openpyxl.load_workbook('/workdir/intake_blank.xlsx')\nwb.save('/workdir/intake_blank.xlsx')"}))
        self.assertEqual(self.pre("syntara__executeBash", {
            "command": "cp /workdir/intake_blank.xlsx /workdir/intake_CIG_2026_1026.xlsx"}), set())
        self.golden()
        self.edit("intake_blank.xlsx", "ws['B6'] = 'CIG_2026_1026'")
        self.assertIn("files.templates_unchanged", self.done())

    def test_no_downstream(self):
        self.golden()
        wd = self.tmp / "workdir"
        shutil.copy(wd / "benefits_blank.xlsx", wd / "benefits_CIG_2026_1025.xlsx")
        self.assertIn("files.no_downstream", self.done())

    def test_placeholders(self):
        self.assertIn("comms.no_placeholders", self.pre("slack__post_message", {
            "channel_id": "C002", "text": "[INTAKE HOLD] CIG_2026_1026 — Physician NPI missing. [Patient Name]"}))
        self.assertNotIn("comms.no_placeholders", self.pre(*HOLD))
