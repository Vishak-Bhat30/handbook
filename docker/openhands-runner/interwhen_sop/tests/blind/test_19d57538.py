"""Blind unit tests for finance_meridian_partners_19d57538 (fixtures from the task seed only)."""

from interwhen_sop.tests.base import TaskCase

TASK = "finance_meridian_partners_19d57538"
SUBJ = "Meridian Partners - Price Discrepancy on Invoice INV-NGO-4471"
BODY = ("Dear Janet Lowe,\n\nInvoice INV-NGO-4471 does not match PO-2025-00884.\n- PO price: $97.50\n"
        "- Invoiced price: $101.50\n- Variance: 4.1%\n\nPlease send a corrected invoice or written justification "
        "within 5 business days.\n\nMeridian Partners Accounts Payable")
POST = ("PRICE VARIANCE: Northgate Office Solutions, V-00229, Invoice INV-NGO-4471, PO Price $97.50, "
        "Invoice Price $101.50, Variance 4.1%")
INV_ROW = ("['INV-NGO-4471','V-00229','Northgate Office Solutions','2025-05-19','2025-05-21','PO-2025-00884',"
           "'$2,030.00','On Hold','MATCH','6200-010-2200','2025-06-18','Price variance; vendor clarification requested']")
ML_ROW = ("['2025-05-21','PO-2025-00884','V-00229','Northgate Office Solutions','INV-NGO-4471','$1,950.00',"
          "'$2,030.00','$97.50','$101.50','4.1%','$4.00',20,20,'$80.00','4.1%','Pass','Fail','MATCH Hold','MATCH',"
          "'Total outside tolerance']")
RESULT = "INV-NGO-4471: MATCH hold. Total +$80.00 (4.1%) outside tolerance. Vendor asked for corrected invoice."


class Base(TaskCase):
    TASK = TASK

    def email(self, **kw):
        args = {"to": "jlowe@northgateoffice.com", "subject": SUBJ, "body": BODY}
        args.update(kw)
        return args

    def send_all(self):
        self.did("google_mail__send_email", self.email())
        self.did("slack__post_message", {"channel_id": "C001", "text": POST})

    def write_ledger(self, row=INV_ROW):
        self.edit("ap_ledger.xlsx", f"ws.append({row})", "Invoice Register")

    def write_log(self, row=ML_ROW):
        self.edit("match_log_2025_Q2.xlsx", f"ws.append({row})")

    def golden(self):
        self.send_all()
        self.write_ledger()
        self.write_log()
        self.write("match_result_INV-NGO-4471.txt", RESULT)


class TestCompletion(Base):
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {"ngo.invoice_register", "ngo.match_log", "ngo.result_file",
                                            "ngo.messages_sent"})
        self.assertEqual(len([r for r, _ in self.done_all() if r == "ngo.messages_sent"]), 2)

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_typed_cells(self):
        self.send_all()
        self.write_ledger("['INV-NGO-4471','V-00229','Northgate Office Solutions',__import__('datetime').datetime"
                          "(2025,5,19),__import__('datetime').datetime(2025,5,21),'PO-2025-00884',2030,'On Hold',"
                          "'MATCH','6200-010-2200',__import__('datetime').datetime(2025,6,18),'']")
        self.write_log("[__import__('datetime').datetime(2025,5,21),'PO-2025-00884','V-00229',"
                       "'Northgate Office Solutions','INV-NGO-4471',1950,2030,97.5,101.5,0.041026,4,20,20,80,0.041026,"
                       "'Pass (within $25)','Fail (>$50 and >2%)','MATCH Hold','','']")
        self.write("match_result_INV-NGO-4471.txt", RESULT)
        self.assertEqual(self.done(), {})

    def test_status_not_on_hold(self):
        self.golden()
        self.edit("ap_ledger.xlsx", "ws.cell(ws.max_row, col['Status']).value='Approved'", "Invoice Register")
        self.assertIn("Status must be \"On Hold\"", self.done().get("ngo.invoice_register", ""))

    def test_hold_code_wrong(self):
        self.golden()
        self.edit("ap_ledger.xlsx", "ws.cell(ws.max_row, col['Hold Code']).value='APPR'", "Invoice Register")
        self.assertIn("Hold Code must be \"MATCH\"", self.done().get("ngo.invoice_register", ""))

    def test_due_date_wrong(self):
        self.golden()
        self.edit("ap_ledger.xlsx", "ws.cell(ws.max_row, col['Due Date']).value='2025-06-20'", "Invoice Register")
        self.assertIn("Due Date", self.done().get("ngo.invoice_register", ""))

    def test_duplicate_entry(self):
        self.golden()
        self.write_ledger()
        self.assertIn("appears 2 times", self.done().get("ngo.invoice_register", ""))

    def test_other_invoice_entered(self):
        self.golden()
        self.write_ledger("['INV-APX-2025-0901','V-00104','Apex Print Solutions','2025-05-19','2025-05-19',"
                          "'PO-2025-00901','$2,480.00','On Hold','MATCH','6200-010-2200','2025-06-18','']")
        self.assertIn("other invoices", self.done().get("ngo.records_unchanged", ""))

    def test_match_log_total_result_wrong(self):
        self.golden()
        self.edit("match_log_2025_Q2.xlsx", "ws.cell(ws.max_row, col['Total Amount Result']).value='Pass'")
        self.assertIn("Total Amount Result must be Fail", self.done().get("ngo.match_log", ""))

    def test_match_log_overall_auto_approved(self):
        self.golden()
        self.edit("match_log_2025_Q2.xlsx", "ws.cell(ws.max_row, col['Overall Result']).value='Auto-Approved'")
        self.assertIn("Overall Result must be MATCH Hold", self.done().get("ngo.match_log", ""))

    def test_match_log_variance_wrong(self):
        self.golden()
        self.edit("match_log_2025_Q2.xlsx", "ws.cell(ws.max_row, col['Price Variance %']).value='4.0%'")
        self.assertIn("Price Variance % must be 4.1%", self.done().get("ngo.match_log", ""))

    def test_match_log_existing_row_edited(self):
        self.golden()
        self.edit("match_log_2025_Q2.xlsx", "ws.cell(3, col['Notes']).value='changed'")
        self.assertIn("ngo.match_log_append_only", self.done())

    def test_payment_queue_row(self):
        self.golden()
        self.edit("ap_ledger.xlsx", "ws.append(['INV-NGO-4471','V-00229','Northgate Office Solutions','$2,030.00',"
                                    "'ACH','042000314','9900112233','2025-05-22','Scheduled'])", "Payment Queue")
        self.assertIn("must not be added", self.done().get("ngo.records_unchanged", ""))

    def test_gl_posting_row(self):
        self.golden()
        self.edit("ap_ledger.xlsx", "ws.append(['2025-05-21','JE-2025-0120','INV-NGO-4471','V-00229',"
                                    "'6200-010-2200','$2,030.00','','AP Clerk',''])", "GL Postings")
        self.assertIn("must not be added", self.done().get("ngo.records_unchanged", ""))

    def test_po_price_updated(self):
        self.golden()
        self.edit("ap_ledger.xlsx", "ws.cell(5, col['Unit Price (PO)']).value='$101.50'", "PO Register")
        self.assertIn("PO Register", self.done().get("ngo.records_unchanged", ""))

    def test_vendor_master_changed(self):
        self.golden()
        self.edit("vendor_master.xlsx", "ws.cell(5, col['Notes']).value='New rate $101.50'")
        self.assertIn("vendor_master.xlsx was changed", self.done().get("ngo.records_unchanged", ""))

    def test_adhoc_spreadsheet(self):
        self.golden()
        self.edit("ap_ledger.xlsx", "wb.save(path.replace('ap_ledger','ap_ledger_backup'))")
        self.assertIn("ap_ledger_backup.xlsx", self.done().get("ngo.records_unchanged", ""))

    def test_result_file_without_determination(self):
        self.golden()
        self.write("match_result_INV-NGO-4471.txt", "Processed the invoice.")
        self.assertIn("ngo.result_file", self.done())

    def test_messages_missing(self):
        self.write_ledger()
        self.write_log()
        self.write("match_result_INV-NGO-4471.txt", RESULT)
        self.assertEqual(set(self.done()), {"ngo.messages_sent"})


class TestPre(Base):
    def test_email_ok(self):
        self.assertEqual(self.pre("google_mail__send_email", self.email()), set())

    def test_email_cc_internal_ok(self):
        self.assertEqual(self.pre("google_mail__send_email", self.email(cc="ap@meridianpartners.com")), set())

    def test_email_wrong_subject(self):
        self.assertIn("ngo.messages", self.pre("google_mail__send_email", self.email(subject="Re: INV-NGO-4471")))

    def test_email_missing_variance(self):
        body = BODY.replace("- Variance: 4.1%\n", "")
        self.assertIn("ngo.messages", self.pre("google_mail__send_email", self.email(body=body)))

    def test_email_wrong_recipient(self):
        self.assertIn("ngo.messages", self.pre("google_mail__send_email", self.email(to="ar@northgateoffice.com")))

    def test_email_sent_twice(self):
        self.did("google_mail__send_email", self.email())
        self.assertIn("ngo.messages", self.pre("google_mail__send_email", self.email()))

    def test_unrelated_email_not_blocked(self):
        self.assertEqual(self.pre("google_mail__send_email", {"to": "tanya@meridianpartners.com",
                                                              "subject": "Status", "body": "FYI"}), set())

    def test_post_ok(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C001", "text": POST}), set())

    def test_post_extra_text(self):
        self.assertIn("ngo.messages", self.pre("slack__post_message",
                                               {"channel_id": "C001", "text": "Hi team! " + POST}))

    def test_post_wrong_channel(self):
        self.assertIn("ngo.messages", self.pre("slack__post_message", {"channel_id": "C003", "text": POST}))

    def test_dm_blocked(self):
        self.assertIn("ngo.messages", self.pre("slack__send_dm", {"user_id": "U001",
                                                                  "text": "INV-NGO-4471 is on MATCH hold"}))

    def test_payment_confirmation_blocked(self):
        self.assertIn("ngo.messages", self.pre("slack__post_message", {
            "channel_id": "C002", "text": "Payment confirmed: INV-NGO-4471, $2,030.00, self-approved"}))

    def test_approvals_hold_notice_allowed(self):
        self.assertEqual(self.pre("slack__post_message", {
            "channel_id": "C002", "text": "INV-NGO-4471 is on MATCH hold - not approved for payment"}), set())

    def test_payments_channel_blocked(self):
        self.assertIn("ngo.messages", self.pre("slack__post_message", {
            "channel_id": "C004", "text": "OFF-CYCLE REQUEST: Northgate Office Solutions, Invoice INV-NGO-4471"}))

    def test_placeholder_blocked(self):
        self.assertIn("comms.no_placeholders", self.pre("google_mail__send_email",
                                                        self.email(body=BODY + "\n[VENDOR NAME]")))
