"""Blind unit tests for insurance_mojave_crest_assurance_company_5122b4da (fixtures from the environment seed only)."""

import re
from pathlib import Path

from interwhen_sop.tests.base import TaskCase

TASK = "insurance_mojave_crest_assurance_company_5122b4da"
MOD = Path(__file__).resolve().parents[2] / "verifiers" / f"{TASK}.py"
PROVIDER = "ur@desertspringsrecovery.org"
CID = "CASE-2026-00091"

ACK_BODY = f"""Dear Utilization Review Department, Desert Springs Recovery Center,

--- EXPEDITED REVIEW ---
Expedited Basis: Treating Physician Certification
Decision Due By: 2026-04-16 12:00 PM PT

This letter confirms that Mojave Crest Assurance Company has received your appeal regarding the termination of inpatient SUD residential treatment (AUTH-2026-00441).

Your case details:
Case Number: {CID}
Member ID: MBR-2026-04471
Date Received: 2026-04-14
Appeal Type: Concurrent Care - Expedited
Decision Due By: 2026-04-16 12:00 PM PT

I will be your Appeals Coordinator throughout this case. Coverage continues through the appeal decision.

If you have questions about your case, please reply to this email or call the Appeals Unit at (702) 555-0148, referencing your Case Number above.

Sincerely, Appeals Coordinator
Appeals & Grievances Coordinator
Mojave Crest Assurance Company
Case #: {CID}"""

JIRA_DESC = """Case ID: CASE-2026-00091
MemberID: MBR-2026-04471
AppealType: Concurrent Care – Expedited
DateOfReceipt: 2026-04-14
AcknowledgmentDue: 2026-04-15 09:47 PT
DecisionDeadline: 2026-04-16 12:00 PM PT
DisputeValue: $88,500.00
StandardOfReview: Expedited
PlanYear: 2026
ParityFlag: Yes
RelatedCaseID:
AssignedCoordinator: Appeals Coordinator
ClinicalReviewer: Dr. Ayla Ontario"""

ONTARIO_DM = f"""CLINICAL ROUTING
Case #: {CID}
Type: Concurrent Care
Service Classification: SUD
Standard of Review: Medical Necessity
Deadline: 2026-04-16 12:00 PM PT
Parity Flag: YES
Case Folder: {CID}"""

PARITY_DM = f"""PARITY FLAG
Case #: {CID}
Service Classification: Inpatient SUD
Comparable M/S Classification: Inpatient, in-network (M/S) inpatient rehabilitation
Flag Indicator: provider asserts MP-018-v2.1 is more restrictive than M/S inpatient rehab criteria (MHPAEA)
Case Folder: {CID}
Decision Deadline: 2026-04-16 12:00 PM PT"""

ESC_DM = f"""ESCALATION
Case #: {CID}
Type: Concurrent
Deadline: 2026-04-16 12:00 PM PT
Trigger: Parity flag raised; Exceeds Coordinator Authority ($88,500 > $25,000); concurrent care termination with care ending within 72 hours
Summary: Provider filed an expedited concurrent care appeal of a residential SUD termination with physician certification.
My Recommendation: Dr. Ontario review before the effective time.
Requested Action: Approval"""

URGENT = f"@dwhitfield URGENT: {CID} expedited concurrent care appeal, parity flagged. Deadline 2026-04-16 12:00 PM PT."


def ack(**kw):
    a = {"to": PROVIDER, "subject": f"Mojave Crest Appeals Case #{CID} - Acknowledgment of Your Appeal", "body": ACK_BODY}
    a.update(kw)
    return a


class Base(TaskCase):
    TASK = TASK

    def jira(self, desc=JIRA_DESC):
        self.did("jira__create_issue", {"project_key": "MCA_APPEALS", "issue_type": "Service Request",
                                        "summary": "Concurrent care appeal", "description": desc},
                 '{"id":"10091","key":"MCA_APPEALS-6"}')

    def golden(self):
        self.jira()
        self.did("google_mail__send_email", ack())
        self.did("slack__send_dm", {"user_id": "U005", "text": ONTARIO_DM})
        self.did("slack__send_dm", {"user_id": "U009", "text": PARITY_DM})
        self.did("slack__send_dm", {"user_id": "U002", "text": ESC_DM})
        self.did("slack__post_message", {"channel_id": "C003", "text": URGENT})


class TestGolden(Base):
    def test_initial_obligations(self):
        got = self.done_all()
        rules = sorted({r for r, _ in got})
        self.assertEqual(rules, ["mca.comms.messages_sent", "mca.escalation", "mca.jira_case"])
        self.assertEqual(len([r for r, _ in got if r == "mca.comms.messages_sent"]), 4)

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_calls_not_blocked(self):
        self.assertEqual(self.pre("jira__create_issue", {"project_key": "MCA_APPEALS", "description": JIRA_DESC}), set())
        self.assertEqual(self.pre("google_mail__send_email", ack()), set())
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U005", "text": ONTARIO_DM}), set())
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U009", "text": PARITY_DM}), set())
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U002", "text": ESC_DM}), set())
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C003", "text": URGENT}), set())

    def test_refs_resolve(self):
        from interwhen_sop import sopdata
        sop = sopdata.load(TASK)
        src = MOD.read_text()
        refs = re.findall(r"\(\s*\"(\d+(?:\.\d+)*)\"\s*,\s*\"((?:[^\"\\]|\\.)+)\"", src)
        self.assertTrue(refs)
        for sec, prefix in refs:
            sop.find(sec, prefix.encode().decode("unicode_escape"))


class TestNonAppeal(Base):
    R = "mca.non_appeal_emails"

    def test_blocks(self):
        self.assertIn(self.R, self.pre("google_mail__send_email", {"to": "records@sunriseimaging.com", "subject": "x",
                                                                   "body": "Received"}))
        self.assertIn(self.R, self.pre("google_mail__reply_email", {"email_id": "3", "body": "Status update"}))
        self.assertIn(self.R, self.pre("slack__post_message", {"channel_id": "C001", "text": "CASE-2026-00088 status?"}))
        self.assertIn(self.R, self.pre("jira__add_comment", {"issue_key": "MCA_APPEALS-1", "comment": "records rcvd"}))
        self.assertIn(self.R, self.pre("google_mail__move_email", {"email_id": "2", "target_folder": "Archive/2026-Q1"}))

    def test_allows(self):
        self.assertNotIn(self.R, self.pre("google_mail__send_email", ack()))
        self.assertNotIn(self.R, self.pre("google_mail__move_email", {"email_id": "1", "target_folder": "Active Appeals"}))


class TestJira(Base):
    def test_pre_wrong_deadline(self):
        bad = JIRA_DESC.replace("DecisionDeadline: 2026-04-16", "DecisionDeadline: 2026-04-17")
        self.assertIn("mca.jira_case_pre", self.pre("jira__create_issue", {"project_key": "MCA_APPEALS", "description": bad}))

    def test_pre_missing_parity(self):
        bad = JIRA_DESC.replace("ParityFlag: Yes\n", "")
        self.assertIn("mca.jira_case_pre", self.pre("jira__create_issue", {"project_key": "MCA_APPEALS", "description": bad}))

    def test_pre_structured_fields_ok(self):
        fields = {"MemberID": "MBR-2026-04471", "AppealType": "Concurrent Care – Expedited", "DateOfReceipt": "2026-04-14",
                  "AcknowledgmentDue": "2026-04-15", "DecisionDeadline": "2026-04-16", "DisputeValue": 88500.0,
                  "StandardOfReview": "Expedited", "PlanYear": "2026", "ParityFlag": True,
                  "AssignedCoordinator": "Appeals Coordinator", "ClinicalReviewer": "Dr. A. Ontario"}
        import json
        self.assertNotIn("mca.jira_case_pre", self.pre("jira__create_issue", {
            "project_key": "MCA_APPEALS", "summary": "MBR-2026-04471 appeal", "additional_fields": json.dumps(fields)}))

    def test_pre_duplicate(self):
        self.jira()
        self.assertIn("mca.jira_case_pre", self.pre("jira__create_issue", {"project_key": "MCA_APPEALS", "description": JIRA_DESC}))

    def test_completion(self):
        self.assertIn("mca.jira_case", self.done())
        self.jira(JIRA_DESC.replace("StandardOfReview: Expedited", "StandardOfReview: Medical Necessity"))
        self.assertIn("StandardOfReview", self.done().get("mca.jira_case", ""))
        self.did("jira__update_issue", {"issue_key": "MCA_APPEALS-6", "fields": {"StandardOfReview": "Expedited"}})
        self.assertNotIn("mca.jira_case", self.done())


class TestAck(Base):
    R = "mca.comms.messages"

    def test_header_before_salutation_blocked(self):
        body = ACK_BODY.replace("--- EXPEDITED REVIEW ---\nExpedited Basis: Treating Physician Certification\n"
                                "Decision Due By: 2026-04-16 12:00 PM PT\n\n", "")
        body = ("--- EXPEDITED REVIEW ---\nExpedited Basis: Treating Physician Certification\n"
                "Decision Due By: 2026-04-16 12:00 PM PT\n\n" + body)
        self.assertIn(self.R, self.pre("google_mail__send_email", ack(body=body)))

    def test_wrong_subject_and_deadline(self):
        self.assertIn(self.R, self.pre("google_mail__send_email", ack(subject="Acknowledgment of appeal")))
        self.assertIn(self.R, self.pre("google_mail__send_email",
                                       ack(body=ACK_BODY.replace("2026-04-16 12:00 PM PT", "2026-04-17 09:47 AM PT"))))

    def test_reply_blocked(self):
        self.assertIn(self.R, self.pre("google_mail__reply_email", {"email_id": "1", "body": ACK_BODY}))

    def test_em_dash_subject_ok(self):
        self.assertEqual(self.pre("google_mail__send_email",
                                  ack(subject=f"Mojave Crest Appeals Case #{CID} — Acknowledgment of Your Appeal")), set())

    def test_completion(self):
        self.golden()
        self.records = [r for r in self.records if r.get("tool") != "google_mail__send_email"]
        self.assertIn("A-1", self.done().get("mca.comms.messages_sent", ""))


class TestSlackFormats(Base):
    R = "mca.comms.messages"

    def test_ontario(self):
        self.assertIn(self.R, self.pre("slack__send_dm", {"user_id": "U005", "text": ONTARIO_DM.replace("Parity Flag: YES", "Parity Flag: NO")}))
        self.assertIn(self.R, self.pre("slack__send_dm", {"user_id": "U005", "text": ONTARIO_DM.replace("CLINICAL ROUTING", "ROUTING NOTE")}))

    def test_parity(self):
        self.assertIn(self.R, self.pre("slack__send_dm", {"user_id": "U009", "text": PARITY_DM.replace("Inpatient SUD", "Outpatient BH")}))

    def test_urgent(self):
        self.assertIn(self.R, self.pre("slack__post_message", {"channel_id": "C003", "text": URGENT.replace("@dwhitfield ", "")}))
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C003", "text": URGENT.replace("@dwhitfield", "<@U002>")}), set())


class TestEscalation(Base):
    def test_format(self):
        self.assertIn("mca.escalation_format", self.pre("slack__send_dm", {"user_id": "U002", "text": ESC_DM.split("Requested Action")[0]}))
        self.assertIn("mca.escalation_format", self.pre("slack__post_message", {"channel_id": "C001", "text": ESC_DM}))
        self.assertNotIn("mca.escalation_format", self.pre("slack__post_message", {"channel_id": "C003", "text": ESC_DM + " @dwhitfield"}))

    def test_completion_triggers(self):
        self.did("slack__send_dm", {"user_id": "U002", "text": ESC_DM.replace("Exceeds Coordinator Authority ($88,500 > $25,000); ", "")})
        self.assertIn("Exceeds Coordinator Authority", self.done().get("mca.escalation", ""))
        self.did("slack__send_dm", {"user_id": "U002", "text": f"ESCALATION add-on for {CID}: total dispute value exceeds the $25,000 coordinator tier."})
        self.assertNotIn("mca.escalation", self.done())


class TestChannels(Base):
    def test_parity_channel(self):
        self.assertIn("mca.parity_channel", self.pre("slack__post_message", {"channel_id": "C004", "text": PARITY_DM}))
        self.assertNotIn("mca.parity_channel", self.pre("slack__post_message", {"channel_id": "C004", "text": "Thanks for the FAQ link"}))

    def test_public_phi(self):
        self.assertIn("mca.public_phi", self.pre("slack__post_message", {"channel_id": "C003", "text": URGENT + " Member MBR-2026-04471"}))
        self.assertNotIn("mca.public_phi", self.pre("slack__send_dm", {"user_id": "U005", "text": ONTARIO_DM + "\nMember ID: MBR-2026-04471"}))


class TestEmails(Base):
    def test_regulator(self):
        self.assertIn("mca.no_regulator", self.pre("google_mail__send_email", {"to": "consumer@doi.nv.gov", "subject": "x", "body": "y"}))
        self.assertNotIn("mca.no_regulator", self.pre("google_mail__send_email", ack()))

    def test_external_banned(self):
        R = "mca.external_email"
        self.assertIn(R, self.pre("google_mail__send_email", ack(body=ACK_BODY + "\nDr. Ontario is reviewing your case.")))
        self.assertIn(R, self.pre("google_mail__send_email", ack(body=ACK_BODY + "\nThe authorization will lapse on April 16.")))
        self.assertIn(R, self.pre("google_mail__send_email", ack(body=ACK_BODY + "\nThe treatment is medically necessary.")))
        self.assertIn(R, self.pre("google_mail__send_email", ack(body=ACK_BODY + "\nYour appeal will be approved.")))
        self.assertIn(R, self.pre("google_mail__send_email", ack(subject="Appeal received")))
        self.assertNotIn(R, self.pre("google_mail__send_email", ack()))

    def test_no_determination(self):
        args = ack(subject=f"URGENT - Mojave Crest Appeals Case #{CID} - Expedited Decision",
                   body="Dear provider,\nDecision: Your appeal is APPROVED.")
        self.assertIn("mca.no_determination", self.pre("google_mail__send_email", args))
        self.assertNotIn("mca.no_determination", self.pre("google_mail__send_email", ack()))

    def test_placeholders(self):
        self.assertIn("comms.no_placeholders", self.pre("slack__send_dm", {"user_id": "U008", "text": "Case [CASE ID] note"}))
        self.assertNotIn("comms.no_placeholders", self.pre("slack__send_dm", {
            "user_id": "U008", "text": f"Could not locate EOC[GRP-00892][2026].pdf for {CID}."}))


class TestWorkbooks(Base):
    def test_log_readonly(self):
        code = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/appeals_log_master.xlsx')\nws=wb.active\nws.append(['CASE-2026-00091'])\nwb.save('/workdir/appeals_log_master.xlsx')"
        self.assertIn("mca.log_readonly", self.pre("syntara__executePython", {"code": code}))
        self.assertNotIn("mca.log_readonly", self.pre("syntara__executePython", {
            "code": "import pandas as pd\nprint(pd.read_excel('/workdir/appeals_log_master.xlsx'))"}))

    def test_unchanged(self):
        self.golden()
        self.edit("prior_auth_history.xlsx", "pass")
        self.edit("appeals_log_master.xlsx", "pass")
        self.assertNotIn("mca.workbooks_unchanged", self.done())
        self.edit("prior_auth_history.xlsx", "ws.cell(row=2, column=7).value='Active'")
        self.assertIn("prior_auth_history", self.done().get("mca.workbooks_unchanged", ""))
