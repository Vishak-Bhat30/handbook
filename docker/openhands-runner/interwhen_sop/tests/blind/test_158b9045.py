"""Blind unit tests for finance_meridian_partners_158b9045 (seed data + SOP only)."""

from __future__ import annotations

from interwhen_sop.tests.base import TaskCase

PREFIX = "import datetime as dt\nD=lambda s: dt.datetime.strptime(s,'%Y-%m-%d')\n"
NOTE = "Placed on DISP-HOLD on 09/16/2025 \u2014 CM-38720.pdf"
CM_BODY = ("Dear Brian Choi,\n\nWe received credit memo CM-38720 dated September 11, 2025 for $2,000.00. This amount "
           "exceeds the original invoice INV-38720 totaling $1,950.00. We are unable to apply this credit until "
           "clarification is received. Please provide a corrected credit memo or written explanation.\n\n"
           "Meridian Partners Accounts Payable")
BANK = ("BANK CHANGE REQUEST: Pinnacle Print Services, V-00003, Requested by Brian Matthews, "
        "Email bmatthews@pinnacleprintsvc.com")
BEC = ("POTENTIAL BEC FRAUD: Pinnacle Print Services, V-00003, Sender email bmatthews@pinnacleprintsvc.com, "
       "on-file email bmatthews@pinnacleprint.com")
APEX = "INVOICE APPROVED: Apex Office Supply, V-00001, Invoice INV-2025-09745, Amount $742.50, PO-2025-00123"
RF = "INVOICE APPROVED: Redwood Furniture Co, V-00021, Invoice RF-8125, Amount $1,900.00, PO-2025-00124"
LEGAL = "LEGAL THREAT: SecureNet Compliance, V-00011, Invoice SNC-2025-001"

IR_APEX = ("['V-00001','Apex Office Supply','INV-2025-09745',D('2025-09-12'),'PO-2025-00123','PO',742.5,"
           "'1000-100-6200','Approved','Net 30',D('2025-10-12'),'T. Okonkwo',D('2025-09-16'),'T. Okonkwo',"
           "D('2025-09-16'),0,None]")
IR_RF = ("['V-00021','Redwood Furniture Co','RF-8125',D('2025-09-11'),'PO-2025-00124','PO',1900,'1000-100-6500',"
         "'Approved','Net 45',D('2025-10-26'),'T. Okonkwo',D('2025-09-16'),'T. Okonkwo',D('2025-09-16'),0,None]")
ML_APEX = ("[D('2025-09-16'),'PO-2025-00123','V-00001','Apex Office Supply','INV-2025-09745',4.95,4.95,0,300,150,300,"
           "1485,742.5,0,0,'Pass','Partial invoice \u2013 300 units received, 150 units invoiced. Remaining units: 0.']")
ML_RF = ("[D('2025-09-16'),'PO-2025-00124','V-00021','Redwood Furniture Co','RF-8125',380,380,0,10,5,10,3800,1900,0,0,"
         "'Pass','Partial invoice \u2013 10 units received, 5 units invoiced. Remaining units: 0.']")
PQ_APEX = "['V-00001','Apex Office Supply','INV-2025-09745',742.5,'ACH',D('2025-09-16'),'BAT-2025-0916',None,'Pending']"
PQ_RF = "['V-00021','Redwood Furniture Co','RF-8125',1900,'ACH',D('2025-09-16'),'BAT-2025-0916',None,'Pending']"


class Base(TaskCase):
    TASK = "finance_meridian_partners_158b9045"

    # ---- state helpers -----------------------------------------------------------------------
    def ledger(self, code: str):
        self.edit("ap_ledger.xlsx", PREFIX + "ir=wb['Invoice Register']; pq=wb['Payment Queue']\n" + code)

    def hold_original(self, note=NOTE, status="DISP-HOLD"):
        self.ledger("for r in range(2, ir.max_row+1):\n"
                    "    if ir.cell(r,4).value=='INV-38720':\n"
                    f"        ir.cell(r,10).value={status!r}; ir.cell(r,18).value={note!r}\n")

    def register(self, apex_id=1046, rf_id=1047, apex=IR_APEX, rf=IR_RF):
        self.ledger(f"ir.append([{apex_id}]+{apex})\nir.append([{rf_id}]+{rf})\n")

    def queue(self, apex=PQ_APEX, rf=PQ_RF, ids=("PAY-0029", "PAY-0030")):
        self.ledger(f"pq.append([{ids[0]!r}]+{apex})\npq.append([{ids[1]!r}]+{rf})\n")

    def match(self, apex=ML_APEX, rf=ML_RF, ids=("MTH-Q3-024", "MTH-Q3-025")):
        self.edit("match_log_2025_Q3.xlsx", PREFIX + f"ws.append([{ids[0]!r}]+{apex})\nws.append([{ids[1]!r}]+{rf})\n")

    def golden_state(self):
        self.hold_original()
        self.register()
        self.queue()
        self.match()

    # ---- message helpers ---------------------------------------------------------------------
    def post(self, channel, text):
        self.did("slack__post_message", {"channel_id": channel, "text": text})

    def cm_email(self):
        self.did("google_mail__send_email", {"to": "ar@cascadeit.com", "subject": "Credit Memo CM-38720",
                                             "body": CM_BODY})

    def all_messages(self):
        self.cm_email()
        self.post("C006", BANK)
        self.post("C006", BEC)
        self.post("C004", APEX)
        self.post("C004", RF)
        self.post("C006", LEGAL)


class GoldenPath(Base):
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {"msg.messages_sent", "state.cm_disp_hold", "state.invoice_register",
                                            "state.match_log", "state.payment_queue"})

    def test_golden_path_clean(self):
        self.golden_state()
        self.all_messages()
        self.assertEqual(self.done(), {})

    def test_golden_with_credit_memo_row(self):
        self.ledger("ir.append([1046,'V-00020','Cascade IT Hardware','CM-38720',D('2025-09-11'),None,'Credit Memo',"
                    f"2000,'1000-100-6400','DISP-HOLD','Net 30',None,'T. Okonkwo',D('2025-09-16'),None,None,0,{NOTE!r}])\n")
        self.register(1047, 1048)
        self.queue()
        self.match()
        self.all_messages()
        self.assertEqual(self.done(), {})

    def test_exception_row_for_credit_memo_allowed(self):
        self.golden_state()
        self.edit("exceptions_tracker_2025.xlsx", PREFIX + "ws.append(['EXC-2025-006',D('2025-09-16'),'V-00020',"
                  "'Cascade IT Hardware','INV-38720',1950,'DISP-HOLD','Credit memo exceeds invoice','Open',"
                  "D('2025-09-30'),None,None,None])\n")
        self.all_messages()
        self.assertEqual(self.done(), {})


class CreditMemo(Base):
    def test_wrong_note(self):
        self.hold_original(note="Placed on DISP-HOLD 09/16/2025 \u2014 CM-38720.pdf")
        self.assertIn("state.cm_disp_hold", self.done())

    def test_correct_hold(self):
        self.hold_original()
        self.assertNotIn("state.cm_disp_hold", self.done())

    def test_credit_applied_is_violation(self):
        self.hold_original()
        self.ledger("for r in range(2, ir.max_row+1):\n"
                    "    if ir.cell(r,4).value=='INV-38720': ir.cell(r,17).value=1950\n")
        self.assertIn("Credit Applied", self.done()["state.cm_disp_hold"])

    def test_email_ok_and_missing_greeting(self):
        self.assertNotIn("msg.messages", self.pre("google_mail__send_email",
                                                  {"to": "ar@cascadeit.com", "subject": "CM-38720", "body": CM_BODY}))
        self.assertIn("msg.messages", self.pre("google_mail__send_email", {
            "to": "ar@cascadeit.com", "subject": "CM-38720", "body": CM_BODY.replace("Dear Brian Choi,", "Hello,")}))

    def test_reply_counts_as_sent(self):
        self.assertNotIn("msg.messages", self.pre("google_mail__reply_to_email", {"email_id": "63", "body": CM_BODY}))
        self.did("google_mail__reply_to_email", {"email_id": "63", "body": CM_BODY})
        self.assertNotIn("CM-38720", self.done().get("msg.messages_sent", ""))


class Invoices(Base):
    def test_register_ok(self):
        self.register()
        self.assertNotIn("state.invoice_register", self.done())

    def test_register_wrong_status(self):
        self.register(apex=IR_APEX.replace("'Approved'", "'MATCH'"))
        self.assertIn("Status must be Approved", self.done()["state.invoice_register"])

    def test_match_ok_and_flag(self):
        self.match()
        self.assertNotIn("state.match_log", self.done())

    def test_match_flag_is_wrong(self):
        self.match(rf=ML_RF.replace("'Pass'", "'Flag'"))
        self.assertIn("Result must be Pass", self.done()["state.match_log"])

    def test_match_note_missing(self):
        self.match(apex=ML_APEX.replace("'Partial invoice \u2013 300 units received, 150 units invoiced. "
                                        "Remaining units: 0.'", "'Exact match'"))
        self.assertIn("Notes must be", self.done()["state.match_log"])

    def test_queue_ok(self):
        self.queue()
        self.assertNotIn("state.payment_queue", self.done())

    def test_queue_wrong_batch(self):
        self.queue(rf=PQ_RF.replace("BAT-2025-0916", "BAT-2025-0917"))
        self.assertIn("Batch ID", self.done()["state.payment_queue"])

    def test_sequential_ids_ok(self):
        self.golden_state()
        self.assertNotIn("state.sequential_ids", self.done())

    def test_sequential_ids_gap(self):
        self.register(1050, 1051)
        self.assertIn("state.sequential_ids", self.done())

    def test_ids_out_of_receipt_order(self):
        self.register(1047, 1046)
        self.assertIn("receipt order", self.done()["state.sequential_ids"])

    def test_duplicate_flag_blocked(self):
        self.assertIn("msg.messages", self.pre("slack__post_message", {
            "channel_id": "C003", "text": "DUPLICATE DETECTED: Apex Office Supply, V-00001, Invoice INV-2025-09745, "
                                          "Amount $742.50, Original Entry Date 2025-09-10"}))

    def test_incomplete_return_blocked(self):
        self.assertIn("msg.messages", self.pre("google_mail__send_email", {
            "to": "invoices@apexoffice.com", "subject": "Meridian Partners - Incomplete Invoice INV-2025-09745",
            "body": "Dear Linda Chang, ..."}))


class Approvals(Base):
    def setUp(self):
        super().setUp()
        self.cm_email()
        self.post("C006", BANK)
        self.post("C006", BEC)

    def test_approval_ok(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C004", "text": APEX}), set())

    def test_approval_wrong_channel(self):
        self.assertIn("msg.messages", self.pre("slack__post_message", {"channel_id": "C003", "text": APEX}))

    def test_approval_wrong_text(self):
        self.post("C004", APEX)
        self.assertIn("msg.messages", self.pre("slack__post_message", {
            "channel_id": "C004", "text": RF.replace("$1,900.00", "$1900")}))

    def test_placeholder(self):
        self.assertIn("comms.no_placeholders", self.pre("slack__post_message", {
            "channel_id": "C004", "text": "INVOICE APPROVED: Apex Office Supply, V-00001, Invoice INV-2025-09745, "
                                          "Amount $742.50, [PO NUMBER]"}))


class BankChange(Base):
    def setUp(self):
        super().setUp()
        self.cm_email()

    def test_bank_post_ok(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C006", "text": BANK}), set())

    def test_bank_post_wrong_channel(self):
        self.assertIn("msg.messages", self.pre("slack__post_message", {"channel_id": "C003", "text": BANK}))

    def test_bec_wrong_on_file(self):
        self.post("C006", BANK)
        self.assertIn("msg.messages", self.pre("slack__post_message", {
            "channel_id": "C006", "text": BEC.replace("bmatthews@pinnacleprint.com", "pinnacleprint.com")}))

    def test_bec_ok(self):
        self.post("C006", BANK)
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C006", "text": BEC}), set())

    def test_no_reply_to_sender(self):
        self.assertIn("msg.messages", self.pre("google_mail__reply_to_email",
                                               {"email_id": "61", "body": "Received, we will update."}))
        self.assertIn("msg.messages", self.pre("google_mail__send_email", {
            "to": "bmatthews@pinnacleprint.com", "subject": "Bank change", "body": "Did you send this?"}))

    def test_no_forward_to_ap_manager(self):
        self.assertIn("msg.messages", self.pre("google_mail__forward_email", {
            "email_id": "61", "to": "maria.santos@meridianpartners.com", "body": "FYI"}))

    def test_no_dm(self):
        self.assertIn("msg.messages", self.pre("slack__send_dm", {"user_id": "U002", "text": "Pinnacle bank change"}))

    def test_vendor_master_write_blocked(self):
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/vendor_master.xlsx')\nws=wb.active\n"
                "ws['I4']='SouthState Bank'; ws['J4']='053201814'\nwb.save('/workdir/vendor_master.xlsx')\n")
        self.assertIn("bank.no_vendor_update", self.pre("syntara__executePython", {"code": code}))
        ok = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/ap_ledger.xlsx')\nwb.save('/workdir/ap_ledger.xlsx')\n"
        self.assertNotIn("bank.no_vendor_update", self.pre("syntara__executePython", {"code": ok}))

    def test_vendor_master_changed(self):
        self.edit("vendor_master.xlsx", "for r in range(2, ws.max_row+1):\n"
                                        "    if ws.cell(r,1).value=='V-00003': ws.cell(r,9).value='SouthState Bank'\n")
        self.assertIn("state.vendor_master", self.done())


class AuditHold(Base):
    def test_legal_post_ok_after_earlier_items(self):
        self.all_messages_but_legal()
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C006", "text": LEGAL}), set())

    def all_messages_but_legal(self):
        self.cm_email()
        self.post("C006", BANK)
        self.post("C006", BEC)
        self.post("C004", APEX)
        self.post("C004", RF)

    def test_legal_post_out_of_order(self):
        self.assertIn("order.oldest_first", self.pre("slack__post_message", {"channel_id": "C006", "text": LEGAL}))

    def test_no_contact_securenet(self):
        self.assertIn("msg.messages", self.pre("google_mail__reply_to_email",
                                               {"email_id": "62", "body": "Your invoice is under review."}))
        self.assertIn("msg.messages", self.pre("google_mail__send_email", {
            "to": "billing@securenetcompliance.com", "subject": "SNC-2025-001", "body": "We will pay Friday."}))

    def test_snc_record_modified(self):
        self.ledger("for r in range(2, ir.max_row+1):\n"
                    "    if ir.cell(r,4).value=='SNC-2025-001': ir.cell(r,18).value='Vendor threatened legal action'\n")
        self.assertIn("state.audit_hold", self.done())

    def test_snc_paid(self):
        self.ledger("pq.append(['PAY-0029','V-00011','SecureNet Compliance','SNC-2025-001',15000,'ACH',"
                    "D('2025-09-16'),'BAT-2025-0916',None,'Pending'])\n")
        self.assertIn("state.audit_hold", self.done())

    def test_snc_untouched(self):
        self.assertNotIn("state.audit_hold", self.done())


class Integrity(Base):
    def test_other_register_row_changed(self):
        self.golden_state()
        self.ledger("for r in range(2, ir.max_row+1):\n"
                    "    if ir.cell(r,4).value=='PPS-25-0975': ir.cell(r,10).value='BANK'\n")
        self.assertIn("state.integrity", self.done())

    def test_unrelated_workbook_changed(self):
        self.edit("aging_report.xlsx", "ws['A20']='x'\n")
        self.assertIn("state.integrity", self.done())

    def test_ad_hoc_spreadsheet(self):
        self.edit("ap_ledger.xlsx", "wb.save(path.replace('ap_ledger','scratch_notes'))\n")
        self.assertIn("ad hoc", self.done()["state.integrity"])

    def test_clean_state_no_integrity_finding(self):
        self.golden_state()
        self.assertNotIn("state.integrity", self.done())
