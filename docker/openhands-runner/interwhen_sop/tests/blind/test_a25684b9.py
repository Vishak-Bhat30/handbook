from interwhen_sop.tests.base import TaskCase

POST = "slack__post_message"
MAIL = "google_mail__send_email"
SA_TEXT = "Alex Rivera: CLM-2026-0062 special action authorized"
PFR_BODY = ("Hi Marcus, please contact the patient about new coverage or a self-pay plan. Claim ID: CLM-2026-0061, "
            "Patient ID: PAT-1006, DOS: 2026-02-20, CPT: 99214, Payer: Aetna, Claim Status: On Hold.")

GOLDEN_REG = ("ws.cell(3,col['Claim_Status']).value='Written Off'\nws.cell(3,col['Billed_Amount']).value=285\n"
              "ws.cell(3,col['Adjustment_Amount']).value=0\nws.cell(2,col['Claim_Status']).value='On Hold'")
GOLDEN_WL = ("ws.cell(2,col['Recovery_Action']).value='Route to PFR'\nws.cell(2,col['Recovery_Status']).value='In Progress'\n"
             "ws.cell(3,col['Recovery_Action']).value='Write Off'\nws.cell(3,col['Recovery_Status']).value='Written Off'")


class T(TaskCase):
    TASK = "medical_pathfinder_billing_and_coding_a25684b9"

    def golden(self, post=True):
        self.edit("PBC_Claim_Register.xlsx", GOLDEN_REG)
        self.edit("PBC_Denial_Worklist.xlsx", GOLDEN_WL)
        self.edit("PBC_RA_Queue.xlsx", "ws.cell(6,6).value='Complete'\nws.cell(7,6).value='In Progress'\n"
                                       "ws.cell(8,6).value='Complete'")
        if post:
            self.did(POST, {"channel_id": "C001", "text": SA_TEXT})

    # ---- initial state / golden path
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {"sa.messages_sent", "register.state", "worklist.state"})

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_with_pfr_email(self):
        self.golden()
        self.did(MAIL, {"to": "marcus.thompson@pathfinder.med", "subject": "CLM-2026-0061 PFR handoff", "body": PFR_BODY})
        self.assertEqual(self.done(), {})

    # ---- special-authorization post (P0057)
    def test_sa_exact_ok(self):
        self.assertEqual(self.pre(POST, {"channel_id": "C001", "text": SA_TEXT}), set())
        self.assertEqual(self.pre(POST, {"channel_id": "C001", "text": SA_TEXT + "."}), set())

    def test_sa_wrong_text_blocked(self):
        self.assertIn("sa.messages", self.pre(POST, {"channel_id": "C001",
                                                     "text": "Alex Rivera - CLM-2026-0062 write-off approved"}))

    def test_sa_wrong_channel_blocked(self):
        self.assertIn("sa.messages", self.pre(POST, {"channel_id": "C003", "text": SA_TEXT}))

    def test_sa_other_claim_blocked(self):
        self.assertIn("sa.messages", self.pre(POST, {"channel_id": "C001",
                                                     "text": "Alex Rivera: CLM-2026-0061 special action authorized"}))

    def test_sa_duplicate_blocked(self):
        self.did(POST, {"channel_id": "C001", "text": SA_TEXT})
        self.assertIn("sa.messages", self.pre(POST, {"channel_id": "C001", "text": SA_TEXT}))

    def test_sa_missing_at_completion(self):
        self.golden(post=False)
        self.assertEqual(set(self.done()), {"sa.messages_sent"})

    def test_unrelated_channel_post_ok(self):
        self.assertEqual(self.pre(POST, {"channel_id": "C003", "text": "Morning all, working the RA queue today."}), set())

    # ---- claim fields in messages (P0283)
    def test_claim_fields_ok(self):
        self.assertEqual(self.pre(MAIL, {"to": "marcus.thompson@pathfinder.med", "subject": "PFR handoff",
                                         "body": PFR_BODY}), set())

    def test_claim_fields_other_date_format_ok(self):
        body = PFR_BODY.replace("2026-02-20", "February 20, 2026").replace("Payer: Aetna", "payer Aetna")
        self.assertEqual(self.pre(MAIL, {"to": "marcus.thompson@pathfinder.med", "subject": "PFR handoff",
                                         "body": body}), set())

    def test_claim_fields_missing_blocked(self):
        body = "Please contact the patient on CLM-2026-0061 (Aetna, CO-27)."
        self.assertIn("comms.claim_fields", self.pre(MAIL, {"to": "marcus.thompson@pathfinder.med",
                                                            "subject": "PFR handoff", "body": body}))

    def test_claim_fields_slack_dm_blocked(self):
        self.assertIn("comms.claim_fields", self.pre("slack__send_dm", {"user_id": "U005",
                                                                        "text": "CLM-2026-0061 needs patient contact"}))

    def test_placeholder_blocked(self):
        self.assertIn("comms.no_placeholders", self.pre(MAIL, {"to": "marcus.thompson@pathfinder.med",
                                                               "subject": "x", "body": "Hello [PFR Name], " + PFR_BODY}))

    # ---- claim register (P0064/P0115/P0165/P0161/P0137)
    def test_register_wrong_status(self):
        self.golden()
        self.edit("PBC_Claim_Register.xlsx", "ws.cell(3,col['Claim_Status']).value='Closed'")
        self.assertIn("Written Off", self.done().get("register.state", ""))

    def test_register_billed_not_adjusted(self):
        self.golden()
        self.edit("PBC_Claim_Register.xlsx", "ws.cell(3,col['Billed_Amount']).value=340")
        self.assertIn("Billed_Amount", self.done().get("register.state", ""))

    def test_register_extra_column_changed(self):
        self.golden()
        self.edit("PBC_Claim_Register.xlsx", "ws.cell(2,col['CO_Code']).value=''")
        self.assertIn("CO_Code", self.done().get("register.state", ""))

    def test_register_unrelated_row_changed(self):
        self.golden()
        self.edit("PBC_Claim_Register.xlsx", "ws.cell(7,col['Claim_Status']).value='Closed'")
        self.assertIn("CLM-2026-0066", self.done().get("register.state", ""))

    def test_register_new_row(self):
        self.golden()
        self.edit("PBC_Claim_Register.xlsx", "ws.append(['CLM-2026-0067','PAT-1005','PRV-001','United Healthcare',"
                                             "'99215','E11.9','2026-01-27','2026-03-30','2026-04-27',340,0,0,0,"
                                             "'Resubmitted','', '7','','','CLM-2026-0062'])")
        self.assertIn("added", self.done().get("register.state", ""))

    def test_register_0065_not_judged(self):
        self.golden()
        self.edit("PBC_Claim_Register.xlsx", "ws.cell(6,col['Claim_Status']).value='Appealed'")
        self.assertEqual(self.done(), {})

    # ---- denial worklist
    def test_worklist_dispute_instead_of_writeoff(self):
        self.golden()
        self.edit("PBC_Denial_Worklist.xlsx", "ws.cell(3,col['Recovery_Action']).value='Appeal - Contractual Rate Dispute'")
        self.assertIn("Write Off", self.done().get("worklist.state", ""))

    def test_worklist_co27_wrong_status(self):
        self.golden()
        self.edit("PBC_Denial_Worklist.xlsx", "ws.cell(2,col['Recovery_Status']).value='Resolved'")
        self.assertIn("In Progress", self.done().get("worklist.state", ""))

    def test_worklist_closed_row_changed(self):
        self.golden()
        self.edit("PBC_Denial_Worklist.xlsx", "ws.cell(4,col['Recovery_Status']).value='Escalated'")
        self.assertIn("DNL-2026-003", self.done().get("worklist.state", ""))

    # ---- RA queue
    def test_ra_queue_row_deleted(self):
        self.golden()
        self.edit("PBC_RA_Queue.xlsx", "ws.delete_rows(8)")
        self.assertIn("ra_queue.rows", self.done())

    def test_ra_queue_row_added(self):
        self.golden()
        self.edit("PBC_RA_Queue.xlsx", "ws.append(['Q-2026-008','2026-03-30','CLM-2026-0061','PFR Handoff',None,'Open'])")
        self.assertIn("ra_queue.rows", self.done())

    # ---- reference files / temp files
    def test_fee_schedule_modified(self):
        self.golden()
        self.edit("PBC_Fee_Schedule.xlsx", "ws.cell(12,4).value=285")
        self.assertIn("reference.unchanged", self.done())

    def test_temp_file_left(self):
        self.golden()
        p = self.write("ra_notes.txt", "scratch")
        self.assertIn("files.temp_deleted", self.done())
        p.unlink()
        self.assertEqual(self.done(), {})
