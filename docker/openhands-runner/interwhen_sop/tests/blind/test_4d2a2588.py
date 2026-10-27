"""Blind unit tests for insurance_mojave_crest_assurance_company_4d2a2588 (fixtures from the task seed only)."""

from __future__ import annotations

import json

from interwhen_sop.tests.base import TaskCase

TASK = "insurance_mojave_crest_assurance_company_4d2a2588"
TORRES, FIERRO, CASILLAS, SWDO = ("d.torres.personal@gmail.com", "j.fierro.personal@gmail.com",
                                  "r.casillas.personal@gmail.com", "appeals@swdesertortho.com")
SIGN = "Sincerely,\nJordan Mills\nAppeals & Grievances Coordinator\nMojave Crest Assurance Company\nPhone: (702) 555-0148\n"

ACK_00441 = ("google_mail__send_email", {
    "to": FIERRO, "subject": "Mojave Crest Appeals Case #CASE-2026-00441 - Acknowledgment of Your Appeal",
    "body": "Dear Joanna Fierro,\n\n--- EXPEDITED REVIEW ---\nExpedited Basis: Concurrent care appeal (termination of "
            "ongoing authorized care)\nDecision Due By: 2026-11-05 10:00 AM\n------------------------\n\nThis letter "
            "confirms that Mojave Crest Assurance Company has received your appeal regarding the termination of your "
            "residential substance use disorder treatment.\n\nYour case details:\nCase Number: CASE-2026-00441\n"
            "Member Name: Joanna Fierro\nMember ID: VA-55219-07\nDate Received: 2026-11-03 2:15 PM\nAppeal Type: "
            "Concurrent Care (Expedited)\nDecision Due By: 2026-11-05 10:00 AM\n\nIf you have questions about your "
            "case, please reply to this email or call the Appeals Unit at (702) 555-0148.\n\n" + SIGN +
            "Case #: CASE-2026-00441"})
STATUS_00437 = ("google_mail__send_email", {
    "to": TORRES, "subject": "Mojave Crest Appeals Case #CASE-2026-00437 - Status Update",
    "body": "Dear Daniela Torres,\n\nThank you for your message regarding Case #CASE-2026-00437. Your appeal remains "
            "under clinical review, and the decision is due by December 13, 2026.\n\n" + SIGN +
            "Case #: CASE-2026-00437"})
FRAUD_00437 = ("slack__send_dm", {"user_id": "U006", "text": (
    "SUSPECTED CLAIM FRAUD\nCase #: CASE-2026-00437\nProvider NPI: 1427839501\nProvider Name: Desert Peak Specialty "
    "Group\nDates of Service in Dispute: 2026-10-12\nFraud Type: Service Not Delivered\nBasis for Suspicion: The "
    "member states she was not seen by this provider on 10/12/2026 and was out of town that week. Claim "
    "CLM-2026-040318 bills 99244 and 95819 for that date.\nAppeal Status: Will continue on regular clock\n"
    "Case Folder: /appeals/CASE-2026-00437/")})
PARITY_00441 = ("slack__send_dm", {"user_id": "U008", "text": (
    "PARITY FLAG\nCase #: CASE-2026-00441\nService Classification: Inpatient SUD\nComparable M/S Classification: "
    "Inpatient, in-network (medical inpatient rehabilitation)\nFlag Indicator: Member's letter alleges SUD "
    "residential criteria are stricter than medical rehab criteria (8.2 disparate treatment)\nCase Folder: "
    "/appeals/CASE-2026-00441/\nDecision Deadline: 2026-11-05 10:00 AM")})
ESC_00441 = ("slack__send_dm", {"user_id": "U002", "text": (
    "ESCALATION\nCase #: CASE-2026-00441\nType: Concurrent\nDeadline: 2026-11-05 10:00 AM\nTrigger: (8) parity flag "
    "raised; (12) concurrent care termination within 72 hours\nSummary: Residential SUD authorization terminates "
    "11/5 10:00 AM; member alleges stricter SUD criteria. Routed to Dr. Ontario and the Parity Review Committee.\n"
    "My Recommendation: Expedite Dr. Ontario's review before the termination time.\nRequested Action: Guidance")})
ROUTE_00441 = ("slack__send_dm", {"user_id": "U005", "text": (
    "CLINICAL ROUTING\nCase #: CASE-2026-00441\nType: Concurrent Care\nService Classification: SUD\nStandard of "
    "Review: Medical Necessity\nDeadline: 2026-11-05 10:00 AM\nParity Flag: YES\nCase Folder: "
    "/appeals/CASE-2026-00441/")})
URGENT_00441 = ("slack__post_message", {"channel_id": "C003", "text": (
    "@dwhitfield URGENT: CASE-2026-00441 concurrent care (expedited), decision due 2026-11-05 10:00 AM. Parity "
    "flagged; routed to Dr. Ontario and the Parity Review Committee.")})
DISMISS_00442 = ("google_mail__save_draft", {
    "to": SWDO, "subject": "Mojave Crest Appeals Case #CASE-2026-00442 - Appeal Dismissed",
    "body": "Dear Michael Osei,\n\nWe have reviewed the appeal filing submitted on November 3, 2026 by Southwest Desert "
            "Orthopedics regarding Elena Novak's post-service appeal.\n\nUnder Mojave Crest Assurance's standing "
            "rules, a provider may file an appeal only for pre-service or concurrent care matters. Post-service "
            "appeals filed by a provider require a member-executed Authorized Representative designation, and this "
            "standing requirement cannot be cured by subsequent documentation. This case is dismissed for lack of "
            "standing. Elena Novak may re-file this appeal directly within the 180-day window from the original "
            "denial date.\n\n" + SIGN + "Case #: CASE-2026-00442"})
DRAFT_RESULT = json.dumps({"status": "saved", "draft": {"draft_id": "12", "to": SWDO}})
REVIEW_00442 = ("slack__send_dm", {"user_id": "U002", "text": (
    "Dismissal draft for CASE-2026-00442 (provider post-service appeal, no AOR; Template A-4 Immediate Dismissal "
    "Variant) is saved in drafts and not sent. Please review and approve.")})
ACK_00443 = ("google_mail__send_email", {
    "to": CASILLAS, "subject": "Mojave Crest Appeals Case #CASE-2026-00443 - Acknowledgment of Your Appeal",
    "body": "Dear Roberto Casillas,\n\nThis letter confirms that Mojave Crest Assurance Company has received your "
            "appeal regarding the denial of your February 12-14, 2024 inpatient rehabilitation claim.\n\nYour case "
            "details:\nCase Number: CASE-2026-00443\nMember Name: Roberto Casillas\nMember ID: VA-88291-03\nDate "
            "Received: 2026-11-04\nAppeal Type: Post-Service Standard\nDecision Due By: 2027-01-03\n\nIf you have "
            "questions, call the Appeals Unit at (702) 555-0148.\n\n" + SIGN + "Case #: CASE-2026-00443"})
ROUTE_00443 = ("slack__post_message", {"channel_id": "C002", "text": (
    "CLINICAL ROUTING\nCase #: CASE-2026-00443\nType: Post-Service\nService Classification: Medical/Surgical\n"
    "Standard of Review: Medical Necessity\nDeadline: 2027-01-03\nParity Flag: NO\nCase Folder: "
    "/appeals/CASE-2026-00443/")})
ESC_00443 = ("slack__send_dm", {"user_id": "U002", "text": (
    "ESCALATION\nCase #: CASE-2026-00443\nType: Post-Service\nDeadline: 2027-01-03\nTrigger: Exceeds Coordinator "
    "Authority (total billed $28,400 > $25,000)\nSummary: Post-pay recoupment of a 2024 inpatient rehab claim "
    "appealed by the member; routed to the RN Reviewer team.\nMy Recommendation: Supervisor co-signature on the "
    "final letter.\nRequested Action: Approval")})
GOLDEN = [ACK_00441, STATUS_00437, FRAUD_00437, PARITY_00441, ESC_00441, ROUTE_00441, URGENT_00441, DISMISS_00442,
          REVIEW_00442, ACK_00443, ROUTE_00443, ESC_00443]

LOG = "appeals_log_master.xlsx"
EDIT_00441 = """
r=7
for k,v in {'Acknowledgment Due':'2026-11-04 14:15','Acknowledgment Sent':'2026-11-04','Tolled (Y/N)':'N',
            'Decision Due':'2026-11-05 10:00','Reviewer Assigned':'Dr. Ontario / Parity Review Committee',
            'Parity Flag':'Y','Compliance Escalation':'N','Case Status':'With Reviewer'}.items():
    ws.cell(r,col[k]).value=v
"""
EDIT_00442 = """
r=8
for k,v in {'Acknowledgment Due':'2026-11-10','Acknowledgment Sent':'N/A','Tolled (Y/N)':'N',
            'Decision Due':'2027-01-02','Reviewer Assigned':'N/A (dismissal, no clinical review)','Parity Flag':'N',
            'Compliance Escalation':'N','Case Status':'Draft Letter'}.items():
    ws.cell(r,col[k]).value=v
"""
EDIT_00437 = """
ws.cell(6,col['Notes']).value = ws.cell(6,col['Notes']).value + ' 11/04/2026: status update email sent to member.'
"""
NEW_00443 = """
vals={'Case ID':'CASE-2026-00443','Member ID':'VA-88291-03','Group ID':'G-14827','Plan Year':2024,
      'Appeal Type':'Post-Service Standard','Service Classification':'Medical/Surgical',
      'Standard of Review':'Medical Necessity','Date of Receipt':'2026-11-04 07:32','Acknowledgment Due':'2026-11-11',
      'Acknowledgment Sent':'2026-11-04','Tolled (Y/N)':'N','Decision Due':'2027-01-03',
      'Reviewer Assigned':'M. Alvarado (RN Reviewer)','Parity Flag':'N','Compliance Escalation':'N',
      'External Review Requested':'N','Case Status':'With Reviewer','Coordinator':'J. Mills'}
for k,v in vals.items():
    ws.cell(9,col[k]).value=v
"""


class Base(TaskCase):
    TASK = TASK

    def golden_log(self):
        self.edit(LOG, EDIT_00441 + EDIT_00442 + EDIT_00437 + NEW_00443, "Appeals Log")

    def send_all(self, skip=()):
        for tool, args in GOLDEN:
            if (tool, args) in skip:
                continue
            self.did(tool, args, DRAFT_RESULT if tool == "google_mail__save_draft" else '{"ok": true}')

    def log_problem(self, needle: str) -> str:
        probs = [p for r, p in self.done_all() if r == "log.appeals_log" and needle in p]
        return probs[0] if probs else ""


class TestGolden(Base):
    def test_initial_findings(self):
        d = self.done_all()
        self.assertEqual(sum(r == "msg.messages_sent" for r, _ in d), 12)
        logs = [p for r, p in d if r == "log.appeals_log"]
        self.assertEqual(len(logs), 4)
        self.assertTrue(any("CASE-2026-00443" in p for p in logs))

    def test_golden_calls_pass_pre(self):
        for tool, args in GOLDEN:
            self.assertEqual(self.pre(tool, args), set(), f"{tool} {args.get('subject') or args.get('text')[:40]}")
            self.did(tool, args, DRAFT_RESULT if tool == "google_mail__save_draft" else '{"ok": true}')

    def test_golden_path_done(self):
        self.send_all()
        self.golden_log()
        self.assertEqual(self.done(), {})

    def test_resave_and_datetime_cells_ok(self):
        self.send_all()
        self.golden_log()
        self.edit(LOG, "import datetime\nws.cell(7,col['Decision Due']).value=datetime.datetime(2026,11,5,10,0)\n"
                       "ws.cell(7,col['Acknowledgment Sent']).value=datetime.datetime(2026,11,4)", "Appeals Log")
        self.assertEqual(self.done(), {})


class TestMessages(Base):
    def test_ack_00441_needs_expedited_header(self):
        tool, args = ACK_00441
        bad = dict(args, body=args["body"].replace("--- EXPEDITED REVIEW ---\n", "").replace("Expedited Basis:", "Basis:"))
        self.assertIn("msg.messages", self.pre(tool, bad))
        self.assertEqual(self.pre(tool, args), set())

    def test_fraud_dm_not_in_compliance_channel(self):
        bad = ("slack__post_message", {"channel_id": "C005", "text": FRAUD_00437[1]["text"]})
        self.assertIn("msg.messages", self.pre(*bad))
        self.assertEqual(self.pre(*FRAUD_00437), set())

    def test_parity_flag_dm_target(self):
        self.assertIn("msg.messages", self.pre("slack__send_dm", {"user_id": "U005", "text": PARITY_00441[1]["text"]}))
        self.assertEqual(self.pre(*PARITY_00441), set())

    def test_escalation_not_public(self):
        self.assertIn("msg.messages", self.pre("slack__post_message", {"channel_id": "C001",
                                                                       "text": ESC_00441[1]["text"]}))
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C003", "text": ESC_00441[1]["text"] +
                                                          "\n@dwhitfield"}), set())

    def test_dismissal_variant_body(self):
        tool, args = DISMISS_00442
        bad = dict(args, body=args["body"].replace("cannot be cured", "can be cured"))
        self.assertIn("msg.messages", self.pre(tool, bad))

    def test_casillas_ack_deadline(self):
        tool, args = ACK_00443
        bad = dict(args, body=args["body"].replace("2027-01-03", "2026-12-04"))
        self.assertIn("msg.messages", self.pre(tool, bad))

    def test_route_00443_fields(self):
        bad = ("slack__post_message", {"channel_id": "C002", "text": ROUTE_00443[1]["text"].replace(
            "Deadline: 2027-01-03", "Deadline: 2026-12-04")})
        self.assertIn("msg.messages", self.pre(*bad))
        self.assertEqual(self.pre(*ROUTE_00443), set())

    def test_esc_00443_trigger(self):
        bad = ("slack__send_dm", {"user_id": "U002", "text": ESC_00443[1]["text"].replace(
            "Exceeds Coordinator Authority", "Classification uncertainty")})
        self.assertIn("msg.messages", self.pre(*bad))

    def test_missing_message_completion(self):
        self.send_all(skip=[FRAUD_00437])
        self.golden_log()
        d = self.done()
        self.assertIn("msg.messages_sent", d)
        self.assertIn("B-6", d["msg.messages_sent"])

    def test_placeholders(self):
        tool, args = STATUS_00437
        self.assertIn("comms.no_placeholders", self.pre(tool, dict(args, body=args["body"] + "\n[BRIEF DESCRIPTION]")))


class TestPreRules(Base):
    def test_phi_public(self):
        self.assertIn("slack.phi_public", self.pre("slack__post_message", {
            "channel_id": "C001", "text": "CASE-2026-00441 (Joanna Fierro, VA-55219-07) logged."}))
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C001", "text": "CASE-2026-00443 logged."}),
                         set())
        self.assertNotIn("slack.phi_public", self.pre("slack__send_dm", {
            "user_id": "U006", "text": "Member Daniela Torres VA-62883-11 called."}))

    def test_parity_channel(self):
        self.assertIn("slack.parity_channel", self.pre("slack__post_message", {
            "channel_id": "C004", "text": "Parity flag on CASE-2026-00441."}))
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C004",
                                                          "text": "I will attend the Nov 18 training."}), set())

    def test_subject_format_reply(self):
        args = {"email_id": "8", "body": STATUS_00437[1]["body"]}
        self.assertIn("email.subject_format", self.pre("google_mail__reply_email", args))
        bad = dict(STATUS_00437[1], subject="Your appeal")
        self.assertIn("email.subject_format", self.pre("google_mail__send_email", bad))
        self.assertNotIn("email.subject_format", self.pre(*STATUS_00437))

    def test_signature(self):
        tool, args = STATUS_00437
        self.assertIn("email.signature", self.pre(tool, dict(args, body=args["body"].replace("(702) 555-0148", ""))))
        self.assertNotIn("email.signature", self.pre(tool, args))

    def test_reviewer_names(self):
        tool, args = STATUS_00437
        self.assertIn("email.reviewer_names", self.pre(tool, dict(
            args, body=args["body"].replace("under clinical review", "under review by Marisol Alvarado"))))

    def test_no_fraud_mention(self):
        tool, args = STATUS_00437
        self.assertIn("email.no_fraud_mention", self.pre(tool, dict(
            args, body=args["body"] + "\nWe have opened a fraud review.")))

    def test_cross_member(self):
        tool, args = STATUS_00437
        self.assertIn("email.cross_member_phi", self.pre(tool, dict(args, body=args["body"] + "\nRef VA-55219-07")))
        self.assertNotIn("email.cross_member_phi", self.pre(tool, dict(args, body=args["body"] + "\nVA-62883-11")))

    def test_regulator(self):
        self.assertIn("email.no_regulator", self.pre("google_mail__send_email", {
            "to": "consumerservices@doi.nv.gov", "subject": "CASE-2026-00441", "body": "FYI"}))
        self.assertNotIn("email.no_regulator", self.pre("google_mail__send_email", {
            "to": "k.dufree@mojavecrest.com", "subject": "CASE-2026-00441", "body": "FYI"}))

    def test_promises(self):
        tool, args = ACK_00443
        self.assertIn("email.no_promises", self.pre(tool, dict(args, body=args["body"] + "\nYour appeal will be "
                                                                                      "approved.")))
        self.assertIn("email.no_promises", self.pre(tool, dict(args, body=args["body"] + "\nWe apologize for the "
                                                                                      "denial.")))
        self.assertNotIn("email.no_promises", self.pre(tool, args))

    def test_outside_parties(self):
        self.assertIn("email.outside_parties", self.pre("google_mail__send_email", {
            "to": "ur@desertoaksrecovery.org", "subject": "Mojave Crest Appeals Case #CASE-2026-00441 - Update",
            "body": "Re CASE-2026-00441 appeal.\n" + SIGN + "CASE-2026-00441"}))
        self.assertNotIn("email.outside_parties", self.pre(*STATUS_00437))

    def test_mednec(self):
        tool, args = ACK_00443
        self.assertIn("letters.mednec_wording", self.pre(tool, dict(
            args, body=args["body"] + "\nThe care was not medically necessary.")))
        self.assertNotIn("letters.mednec_wording", self.pre(tool, args))

    def test_no_determination(self):
        self.assertIn("letters.no_determination", self.pre("google_mail__save_draft", {
            "to": FIERRO, "subject": "URGENT - Mojave Crest Appeals Case #CASE-2026-00441 - Expedited Decision",
            "body": "Decision: Your appeal is APPROVED.\n" + SIGN + "Case #: CASE-2026-00441"}))
        self.assertNotIn("letters.no_determination", self.pre(*ACK_00441))

    def test_dismissal_scope(self):
        self.assertIn("letters.dismissal_scope", self.pre("google_mail__save_draft", {
            "to": CASILLAS, "subject": "Mojave Crest Appeals Case #CASE-2026-00443 - Appeal Dismissed",
            "body": "Your appeal must be dismissed because it was not filed within 180 days.\n" + SIGN +
                    "Case #: CASE-2026-00443"}))
        self.assertNotIn("letters.dismissal_scope", self.pre(*DISMISS_00442))

    def test_external_review(self):
        self.assertIn("letters.no_external_review", self.pre("google_mail__send_email", {
            "to": "intake@canyonridgereview.com", "cc": "k.dufree@mojavecrest.com",
            "subject": "External Review Request - Case #CASE-2026-00437 - STANDARD", "body": "..."}))

    def test_00442_standing(self):
        self.assertIn("case00442.standing", self.pre("google_mail__send_email", {
            "to": SWDO, "subject": "Mojave Crest Appeals Case #CASE-2026-00442 - Acknowledgment of Your Appeal",
            "body": "Case CASE-2026-00442\n" + SIGN}))
        self.assertIn("case00442.standing", self.pre("slack__post_message", {
            "channel_id": "C002", "text": ROUTE_00443[1]["text"].replace("00443", "00442")}))
        self.assertNotIn("case00442.standing", self.pre(*DISMISS_00442))

    def test_00442_hold_draft(self):
        tool, args = DISMISS_00442
        self.assertIn("case00442.hold_draft", self.pre("google_mail__send_email", args))
        self.did(tool, args, DRAFT_RESULT)
        self.assertIn("case00442.hold_draft", self.pre("google_mail__send_draft", {"draft_id": "12"}))
        self.assertNotIn("case00442.hold_draft", self.pre(*ACK_00443))

    def test_00441_parity_routing(self):
        self.assertIn("case00441.parity_routing", self.pre("slack__post_message", {
            "channel_id": "C002", "text": ROUTE_00441[1]["text"]}))
        self.assertIn("case00441.parity_routing", self.pre("slack__send_dm", {
            "user_id": "U004", "text": ROUTE_00441[1]["text"]}))
        self.assertIn("case00441.parity_routing", self.pre("slack__send_dm", {
            "user_id": "U005", "text": ROUTE_00441[1]["text"].replace("Parity Flag: YES", "Parity Flag: NO")}))
        self.assertNotIn("case00441.parity_routing", self.pre(*ROUTE_00441))

    def test_00441_coverage(self):
        self.assertIn("case00441.coverage", self.pre("google_mail__send_email", {
            "to": "ur@desertoaks.org", "subject": "Mojave Crest Appeals Case #CASE-2026-00441 - Notice",
            "body": "AUTH-2026-04819 will lapse on 11/5.\n" + SIGN + "CASE-2026-00441"}))
        self.assertNotIn("case00441.coverage", self.pre(*ACK_00441))

    def test_parity_concurrence_file(self):
        self.assertIn("files.parity_concurrence", self.pre("syntara__writeFile", {
            "file_path": "/workdir/parity_concurrence.txt", "content": "PARITY CONCURRENCE ..."}))
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/appeals_log_master.xlsx')\nws=wb.active\n"
                "ws['X7']='Awaiting concurrence (parity_concurrence.txt required before letter)'\n"
                "wb.save('/workdir/appeals_log_master.xlsx')")
        self.assertNotIn("files.parity_concurrence", self.pre("syntara__executePython", {"code": code}))

    def test_casillas_case_id(self):
        tool, args = ACK_00443
        bad = dict(args, subject=args["subject"].replace("00443", "00444"), body=args["body"].replace("00443", "00444"))
        self.assertIn("email.casillas_case_id", self.pre(tool, bad))
        self.assertNotIn("email.casillas_case_id", self.pre(tool, args))


class TestLog(Base):
    def setUp(self):
        super().setUp()
        self.send_all()

    def test_00441_decision_due(self):
        self.golden_log()
        self.edit(LOG, "ws.cell(7,col['Decision Due']).value='2026-11-06 14:15'", "Appeals Log")
        self.assertIn("2026-11-05 10:00", self.log_problem("CASE-2026-00441"))

    def test_00441_tolled_and_reviewer(self):
        self.golden_log()
        self.edit(LOG, "ws.cell(7,col['Tolled (Y/N)']).value='Y'\nws.cell(7,col['Reviewer Assigned']).value="
                       "'M. Alvarado'", "Appeals Log")
        p = self.log_problem("CASE-2026-00441")
        self.assertIn("Tolled", p)
        self.assertIn("Reviewer Assigned", p)

    def test_00442_status_and_ack(self):
        self.golden_log()
        self.edit(LOG, "ws.cell(8,col['Case Status']).value='Closed'\nws.cell(8,col['Acknowledgment Sent']).value="
                       "'2026-11-04'", "Appeals Log")
        p = self.log_problem("CASE-2026-00442")
        self.assertIn("Case Status", p)
        self.assertIn("Acknowledgment Sent", p)

    def test_00437_clock_and_notes(self):
        self.golden_log()
        self.edit(LOG, "ws.cell(6,col['Tolled (Y/N)']).value='Y'\nws.cell(6,col['Decision Due']).value='2027-01-15'",
                  "Appeals Log")
        p = self.log_problem("CASE-2026-00437")
        self.assertIn("Tolled", p)
        self.assertIn("Decision Due", p)

    def test_00443_values(self):
        self.golden_log()
        self.edit(LOG, "ws.cell(9,col['Plan Year']).value=2026\nws.cell(9,col['Decision Due']).value='2026-12-04'\n"
                       "ws.cell(9,col['Date of Receipt']).value='2026-11-03 07:32'", "Appeals Log")
        p = self.log_problem("CASE-2026-00443")
        for k in ("Plan Year", "Decision Due", "Date of Receipt"):
            self.assertIn(k, p)

    def test_00443_wrong_case_id(self):
        self.golden_log()
        self.edit(LOG, "ws.cell(9,col['Case ID']).value='CASE-2026-00444'", "Appeals Log")
        self.assertIn("CASE-2026-00443", self.log_problem("Casillas"))

    def test_closed_row_edit_and_extra_row(self):
        self.golden_log()
        self.edit(LOG, "ws.cell(3,col['Outcome']).value='Upheld'\nws.cell(10,1).value='CASE-2026-00444'\n"
                       "ws.cell(10,2).value='VA-62883-11'", "Appeals Log")
        self.assertIn("CASE-2026-00391", self.log_problem("integrity"))
        self.assertIn("CASE-2026-00444", self.log_problem("Unexpected"))

    def test_columns(self):
        self.golden_log()
        self.edit(LOG, "ws.cell(1,25).value='Extra'", "Appeals Log")
        self.assertTrue(self.log_problem("columns"))
