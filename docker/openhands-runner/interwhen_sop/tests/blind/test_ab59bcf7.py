"""Blind unit tests for insurance_mojave_crest_assurance_company_ab59bcf7 (fixtures from the task seed only)."""

from interwhen_sop.tests.base import TaskCase

T = "insurance_mojave_crest_assurance_company_ab59bcf7"
SIGN = "Sincerely,\nJordan Mills\nAppeals & Grievances Coordinator\nMojave Crest Assurance Company\nPhone: (702) 555-0148\n"


def ack(case, name, mid, recv, typ, due):
    return {"subject": f"Mojave Crest Appeals Case #{case} - Acknowledgment of Your Appeal",
            "body": (f"Dear {name},\n\nThis letter confirms that Mojave Crest Assurance Company has received your appeal.\n\n"
                     f"Your case details:\nCase Number: {case}\nMember Name: {name}\nMember ID: {mid}\n"
                     f"Date Received: {recv}\nAppeal Type: {typ}\nDecision Due By: {due}\n\n"
                     "If you have questions about your case, please reply to this email or call the Appeals Unit at "
                     f"(702) 555-0148, referencing your Case Number above.\n\n{SIGN}Case #: {case}")}


ACK_196 = dict(to="l.hassan.personal@gmail.com", **ack("CASE-2026-00196", "Leila Hassan", "VA-73245-13",
                                                         "February 13, 2026", "Pre-Service Standard", "March 15, 2026"))
ACK_202 = dict(to="m.soto.personal@gmail.com", **ack("CASE-2026-00202", "María Soto", "VA-64821-09",
                                                       "February 17, 2026", "Post-Service Standard", "April 18, 2026"))
ACK_203 = dict(to="h.reyes.hector@gmail.com", **ack("CASE-2026-00203", "Hector Reyes", "VA-18734-05",
                                                      "02/17/2026", "Post-Service Standard", "04/18/2026"))
ACK_GRV = {"to": "h.reyes.hector@gmail.com",
           "subject": "Mojave Crest Grievance Case #CASE-2026-00205 - Acknowledgment of Your Grievance",
           "body": ("Dear Hector Reyes,\n\nThis letter confirms that Mojave Crest Assurance Company has received your "
                    "grievance regarding your February 10, 2026 call to Member Services.\n\nCase Number: CASE-2026-00205\n"
                    "Member ID: VA-18734-05\nDate Received: February 17, 2026\nResolution Due By: March 19, 2026\n\n"
                    f"{SIGN}Case #: CASE-2026-00205")}
STATUS_201 = {"to": "h.tanaka.personal@gmail.com",
              "subject": "Mojave Crest Appeals Case #CASE-2026-00201 - Appeal Status Update",
              "body": ("Dear Mr. Tanaka,\n\nThis is a status update on your appeal, Case #CASE-2026-00201. Current status: "
                       "pending determination. The decision is due by February 21, 2026.\n\n"
                       f"{SIGN}Case #: CASE-2026-00201")}


def b1(case, typ, due):
    return {"channel_id": "C002", "text": (f"CLINICAL ROUTING\nCase #: {case}\nType: {typ}\nService Classification: "
                                           f"Medical/Surgical\nStandard of Review: Medical Necessity\nDeadline: {due}\n"
                                           f"Parity Flag: NO\nCase Folder: /appeals-repo/2026/{case}/")}


def b2(case, typ, trigger):
    return {"user_id": "U002", "text": (f"ESCALATION\nCase #: {case}\nType: {typ}\nDeadline: 2026-03-19\n"
                                        f"Trigger: {trigger}\nSummary: Details in the case file.\n"
                                        "My Recommendation: Please review.\nRequested Action: Approval")}


B2_201 = b2("CASE-2026-00201", "Pre-Service", "Exceeds Coordinator Authority ($62,800 billed); deadline at risk")
B2_202 = b2("CASE-2026-00202", "Post-Service", "Exceeds Coordinator Authority ($38,400 billed)")
B2_204 = b2("CASE-2026-00204", "Pre-Service", "Member represented by an attorney who threatened legal action")
B2_GRV = b2("CASE-2026-00205", "Grievance", "Staff conduct grievance routed to Supervisor")
B2_PARK = b2("CASE-2026-00206", "Pre-Service", "Untimely filing - good cause asserted (hospitalization)")

ROW_GRV = ("['CASE-2026-00205','VA-18734-05','G-04521',2026,'Grievance','N/A','N/A','2026-02-17 15:52','2026-02-24',"
           "'2026-02-19','N',None,None,'2026-03-19','@dwhitfield (staff conduct)','N','N','CASE-2026-00203',None,None,"
           "'N','Intake','J. Mills','Staff conduct complaint re: 2/10 member services call.']")
ROW_PARK = ("['CASE-2026-00206','VA-51104-11','G-31047',2025,'Pre-Service Standard','Medical/Surgical',"
            "'Medical Necessity','2026-02-19 08:22','2026-02-26',None,'N',None,None,'2026-03-21',None,'N','N',None,None,"
            "None,'N','Intake','J. Mills','Untimely (denial 7/22/2025); good cause asserted; escalated 2/19.']")
FIND = "def r(cid):\n    return next(x for x in range(2, ws.max_row+1) if ws.cell(x,1).value==cid)\n"


class Base(TaskCase):
    TASK = T

    def golden_log(self):
        self.edit("appeals_log_master.xlsx", FIND + f"ws.append({ROW_GRV})\nws.append({ROW_PARK})\n"
                  "ws.cell(r('CASE-2026-00203'), col['Related Case ID']).value='CASE-2026-00205'\n"
                  "ws.cell(r('CASE-2026-00202'), col['Standard of Review']).value='Administrative'\n"
                  "ws.cell(r('CASE-2026-00203'), col['Standard of Review']).value='Medical Necessity'\n"
                  "for c in ('CASE-2026-00196','CASE-2026-00202','CASE-2026-00203'):\n"
                  "    ws.cell(r(c), col['Acknowledgment Sent']).value='2026-02-19'\n", sheet="Appeals Log")

    def golden_comms(self):
        for a in (ACK_196, ACK_202, ACK_203, ACK_GRV, STATUS_201):
            self.did("google_mail__send_email", a)
        self.did("slack__post_message", b1("CASE-2026-00196", "Pre-Service Standard", "2026-03-15"))
        self.did("slack__post_message", b1("CASE-2026-00203", "Post-Service", "2026-04-18"))
        for m in (B2_201, B2_202, B2_204, B2_GRV, B2_PARK):
            self.did("slack__send_dm", m)


class TestGolden(Base):
    def test_initial_state_lists_outstanding_obligations(self):
        rules = {r for r, _ in self.done_all()}
        self.assertEqual(rules, {"comms.messages_sent", "log.intake_rows", "log.case_fields"})
        self.assertEqual(sum(r == "comms.messages_sent" for r, _ in self.done_all()), 12)

    def test_golden_path_is_clean(self):
        self.golden_log()
        self.golden_comms()
        self.assertEqual(self.done(), {})

    def test_golden_messages_not_blocked(self):
        self.golden_log()
        for a in (ACK_196, ACK_202, ACK_203, ACK_GRV, STATUS_201):
            self.assertEqual(self.pre("google_mail__send_email", a), set(), a["subject"])
        for m in (B2_201, B2_202, B2_204, B2_GRV, B2_PARK):
            self.assertEqual(self.pre("slack__send_dm", m), set(), m["text"][:40])
        self.assertEqual(self.pre("slack__post_message", b1("CASE-2026-00196", "Pre-Service Standard", "2026-03-15")),
                         set())


class TestAcks(Base):
    def test_wrong_subject_blocked(self):
        bad = dict(ACK_196, subject="Your appeal CASE-2026-00196 - acknowledgment")
        self.assertIn("comms.messages", self.pre("google_mail__send_email", bad))

    def test_wrong_decision_due_blocked(self):
        bad = dict(ACK_202, body=ACK_202["body"].replace("April 18, 2026", "April 20, 2026"))
        self.assertIn("comms.messages", self.pre("google_mail__send_email", bad))

    def test_grievance_ack_wrong_id_blocked_once_logged(self):
        self.golden_log()
        bad = dict(ACK_GRV, subject=ACK_GRV["subject"].replace("00205", "00207"),
                   body=ACK_GRV["body"].replace("00205", "00207"))
        self.assertIn("comms.messages", self.pre("google_mail__send_email", bad))

    def test_ack_missing_from_completion(self):
        self.golden_log()
        self.golden_comms()
        self.records = [r for r in self.records if "CASE-2026-00196 - Ack" not in str(r)]
        self.assertIn("comms.messages_sent", self.done())


class TestCase201(Base):
    def test_status_update_ok(self):
        self.assertEqual(self.pre("google_mail__send_email", STATUS_201), set())

    def test_status_update_with_findings_blocked(self):
        bad = dict(STATUS_201, body=STATUS_201["body"] + "\nGood news: the reviewer found the claim favorable.")
        self.assertIn("comms.messages", self.pre("google_mail__send_email", bad))

    def test_decision_letter_send_blocked(self):
        a6 = {"to": "h.tanaka.personal@gmail.com",
              "subject": "Mojave Crest Appeals Case #CASE-2026-00201 - Appeal Decision",
              "body": "Dear Mr. Tanaka,\n\nYour appeal has been APPROVED.\n\n" + SIGN + "Case #: CASE-2026-00201"}
        self.assertIn("comms.messages", self.pre("google_mail__send_email", a6))

    def test_draft_without_payment_ok_with_payment_blocked(self):
        draft = {"to": "h.tanaka.personal@gmail.com",
                 "subject": "Mojave Crest Appeals Case #CASE-2026-00201 - Appeal Decision",
                 "body": ("Dear Mr. Tanaka,\n\nYour appeal has been APPROVED. This authorization is valid for 90 days "
                          "from the date of this letter.\n\n" + SIGN + "Case #: CASE-2026-00201")}
        self.assertEqual(self.pre("google_mail__save_draft", draft), set())
        bad = dict(draft, body=draft["body"] + "\nPlan Payment Amount: $35,000.00, expected 2026-02-27.")
        self.assertIn("comms.messages", self.pre("google_mail__save_draft", bad))

    def test_b2_without_trigger_value_blocked(self):
        bad = b2("CASE-2026-00201", "Pre-Service", "deadline soon")
        self.assertIn("comms.messages", self.pre("slack__send_dm", bad))

    def test_b2_followup_note_not_vetted(self):
        note = {"user_id": "U002", "text": "ESCALATION\nCase #: CASE-2026-00204 follow-up\nNote: counsel deadline 2/25."}
        self.assertEqual(self.pre("slack__send_dm", note), set())

    def test_grievance_b2_before_logging_not_taken_for_park(self):
        m = b2("CASE-2026-00205", "Grievance", "Staff conduct grievance")
        m["text"] += "\nMember alleges a dismissive representative; filed late in the day."
        self.assertEqual(self.pre("slack__send_dm", m), set())

    def test_park_b2_before_logging_vetted(self):
        m = b2("CASE-2026-00206", "Pre-Service", "Untimely appeal")
        self.assertEqual(self.pre("slack__send_dm", m), set())
        bad = b2("CASE-2026-00206", "Pre-Service", "please advise on the untimely filing")
        bad["text"] = bad["text"].replace("Requested Action: Approval", "")
        self.assertIn("comms.messages", self.pre("slack__send_dm", bad))


class TestSupervisorGates(Base):
    def test_soto_decision_blocked_ack_ok(self):
        dec = {"to": "m.soto.personal@gmail.com", "subject": "Mojave Crest Appeals Case #CASE-2026-00202 - Appeal Decision",
               "body": "Dear Ms. Soto,\nDecision: Your appeal is DENIED.\n" + SIGN}
        self.assertIn("comms.messages", self.pre("google_mail__send_email", dec))
        self.assertEqual(self.pre("google_mail__send_email", ACK_202), set())

    def test_park_dismissal_blocked(self):
        a3 = {"to": "d.park.personal@gmail.com", "subject": "Mojave Crest Appeals Case #CASE-2026-00206 - Appeal Dismissed",
              "body": "Dear Mr. Park,\nThis appeal must be dismissed because it was not filed in time.\n" + SIGN}
        self.assertIn("comms.messages", self.pre("google_mail__send_email", a3))

    def test_counsel_send_blocked_draft_ok(self):
        a2 = {"to": "mwebb@webbassociateslegal.com",
              "subject": "Mojave Crest Appeals Case #CASE-2026-00204 - Information Needed",
              "body": "Dear Mr. Webb,\nPlease provide a signed AOR form.\n" + SIGN}
        self.assertIn("comms.messages", self.pre("google_mail__send_email", a2))
        self.assertEqual(self.pre("google_mail__save_draft", a2), set())

    def test_route_202_as_medical_necessity_blocked(self):
        self.assertIn("comms.messages", self.pre("slack__post_message",
                                                 b1("CASE-2026-00202", "Post-Service", "2026-04-18")))


class TestRouting(Base):
    def test_b1_wrong_channel_blocked(self):
        bad = dict(b1("CASE-2026-00203", "Post-Service", "2026-04-18"), channel_id="C001")
        self.assertIn("comms.messages", self.pre("slack__post_message", bad))

    def test_b1_missing_deadline_blocked(self):
        bad = b1("CASE-2026-00196", "Pre-Service Standard", "TBD")
        self.assertIn("comms.messages", self.pre("slack__post_message", bad))

    def test_correction_post_not_vetted(self):
        note = {"channel_id": "C002", "text": "CORRECTION to my CLINICAL ROUTING for CASE-2026-00196: type is "
                                              "Pre-Service Standard."}
        self.assertEqual(self.pre("slack__post_message", note), set())


class TestContentRules(Base):
    def test_placeholders(self):
        bad = dict(ACK_196, body=ACK_196["body"].replace("Leila Hassan", "[MEMBER NAME]"))
        self.assertIn("comms.no_placeholders", self.pre("google_mail__send_email", bad))

    def test_phi_in_public_channel(self):
        self.assertIn("slack.no_phi", self.pre("slack__post_message", {
            "channel_id": "C001", "text": "CASE-2026-00205 logged - member VA-51104-11, untimely."}))
        self.assertIn("slack.no_phi", self.pre("slack__post_message", {
            "channel_id": "C001", "text": "Logged Hector's grievance as CASE-2026-00205."}))
        self.assertEqual(self.pre("slack__post_message", {
            "channel_id": "C001", "text": "CASE-2026-00205 logged - grievance, receipt 2/17. Reminder for @treyes."}),
            set())
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U002", "text": "Kimura (VA-29567-08) counsel note"}),
                         set())

    def test_reviewer_name_external_only(self):
        bad = dict(STATUS_201, body=STATUS_201["body"] + "\nMarisol Alvarado is reviewing.")
        self.assertIn("email.no_reviewer_names", self.pre("google_mail__send_email", bad))
        internal = {"to": "d.whitfield@mojavecrest.com", "subject": "CASE-2026-00201 draft",
                    "body": "M. Alvarado overturned on 2/12."}
        self.assertNotIn("email.no_reviewer_names", self.pre("google_mail__send_email", internal))

    def test_doi_contact(self):
        self.assertIn("email.no_doi_contact", self.pre("google_mail__send_email", {
            "to": "consumerservices@doi.nv.gov", "subject": "Bulletin NV-2026-03", "body": "Question."}))
        self.assertNotIn("email.no_doi_contact", self.pre("google_mail__send_email", {
            "to": "k.dufree@mojavecrest.com", "subject": "Bulletin NV-2026-03", "body": "Question."}))

    def test_commitments(self):
        bad = dict(ACK_202, body=ACK_202["body"] + "\nWe will pay the $38,400 claim.")
        self.assertIn("email.no_commitments", self.pre("google_mail__send_email", bad))
        self.assertNotIn("email.no_commitments", self.pre("google_mail__send_email", ACK_202))

    def test_phi_leak(self):
        bad = dict(ACK_202, body=ACK_202["body"] + "\nSee also VA-18734-05.")
        self.assertIn("email.no_phi_leak", self.pre("google_mail__send_email", bad))
        self.assertNotIn("email.no_phi_leak", self.pre("google_mail__send_email", ACK_202))


class TestCrossRef(Base):
    def test_message_crossref_blocked(self):
        bad = dict(ACK_GRV, body=ACK_GRV["body"] + "\nThis is separate from your appeal, Case #CASE-2026-00203.")
        self.assertIn("mixed.crossref", self.pre("google_mail__send_email", bad))
        self.assertNotIn("mixed.crossref", self.pre("google_mail__send_email", ACK_GRV))

    def test_log_notes_crossref(self):
        self.golden_log()
        self.golden_comms()
        self.edit("appeals_log_master.xlsx", FIND + "ws.cell(r('CASE-2026-00203'), col['Notes']).value="
                  "'Companion grievance CASE-2026-00205.'", sheet="Appeals Log")
        self.assertIn("mixed.crossref_log", self.done())


class TestLog(Base):
    def setUp(self):
        super().setUp()
        self.golden_log()
        self.golden_comms()

    def test_deadline_overwrite_flagged(self):
        self.edit("appeals_log_master.xlsx", FIND + "ws.cell(r('CASE-2026-00199'), col['Decision Due']).value="
                  "'2026-04-18'", sheet="Appeals Log")
        self.assertIn("log.integrity", self.done())

    def test_datetime_resave_tolerated(self):
        self.edit("appeals_log_master.xlsx", "import datetime\n" + FIND +
                  "ws.cell(r('CASE-2026-00199'), col['Decision Due']).value=datetime.datetime(2026,4,3)\n"
                  "ws.cell(r('CASE-2026-00196'), col['Acknowledgment Sent']).value=datetime.datetime(2026,2,19)",
                  sheet="Appeals Log")
        self.assertEqual(self.done(), {})

    def test_row_deleted_flagged(self):
        self.edit("appeals_log_master.xlsx", FIND + "ws.delete_rows(r('CASE-2026-00188'))", sheet="Appeals Log")
        self.assertIn("log.integrity", self.done())

    def test_grievance_related_id_wrong(self):
        self.edit("appeals_log_master.xlsx", FIND + "ws.cell(r('CASE-2026-00205'), col['Related Case ID']).value=None",
                  sheet="Appeals Log")
        self.assertIn("log.intake_rows", self.done())

    def test_park_receipt_wrong(self):
        self.edit("appeals_log_master.xlsx", FIND + "ws.cell(r('CASE-2026-00206'), col['Date of Receipt']).value="
                  "'2026-02-18'", sheet="Appeals Log")
        self.assertIn("log.intake_rows", self.done())

    def test_case_id_gap_flagged(self):
        self.edit("appeals_log_master.xlsx", FIND + "ws.cell(r('CASE-2026-00206'), 1).value='CASE-2026-00210'",
                  sheet="Appeals Log")
        self.assertIn("log.intake_rows", self.done())

    def test_standard_of_review_wrong(self):
        self.edit("appeals_log_master.xlsx", FIND + "ws.cell(r('CASE-2026-00202'), col['Standard of Review']).value="
                  "'Medical Necessity'", sheet="Appeals Log")
        self.assertIn("log.case_fields", self.done())

    def test_ack_sent_missing(self):
        self.edit("appeals_log_master.xlsx", FIND + "ws.cell(r('CASE-2026-00196'), col['Acknowledgment Sent']).value="
                  "None", sheet="Appeals Log")
        self.assertIn("log.case_fields", self.done())

    def test_201_closed_without_letter(self):
        self.edit("appeals_log_master.xlsx", FIND + "ws.cell(r('CASE-2026-00201'), col['Case Status']).value='Closed'\n"
                  "ws.cell(r('CASE-2026-00201'), col['Decision Date']).value='2026-02-19'", sheet="Appeals Log")
        self.assertIn("log.case_fields", self.done())
