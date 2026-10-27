"""Blind unit tests for finance_meridian_partners_331accf1 (fixtures from the environment seed only)."""

from interwhen_sop.tests.base import TaskCase

JW, MS, RP, AP = ("jennifer.walsh@meridianpartners.com", "maria.santos@meridianpartners.com",
                  "raj.patel@meridianpartners.com", "ap.team@meridianpartners.com")
MAIL, POST, DM = "google_mail__send_email", "slack__post_message", "slack__send_dm"

VM_HC = ["V-00038", "Harrison & Cole LLP", "23-7654321", "1200 Market Street, Suite 800, Philadelphia, PA 19107",
         "Sarah M. Harrison", "s.harrison@harrisoncolellp.com", "(215) 555-0340", "2/10 Net 30",
         "First National Bank of Philadelphia", "031100209", "7742851903", "Yes", "NEC", "Active", "2025-09-04", 0]
VM_WCG = ["V-00039", "Whitfield Consulting Group, Inc.", "23-7891045",
          "450 Independence Mall West, Suite 1200, Philadelphia, PA 19106", "David Whitfield",
          "d.whitfield@whitfieldcg.com", "(215) 555-0418", "2/10 Net 30", "First Republic Bank", "321081669",
          "7720194583", "Yes", "NEC", "Active", "2025-09-04", 0]
IR_HC = [1036, "V-00038", "Harrison & Cole LLP", "HC-2025-0001", "2025-09-04", None, "Non-PO", 5000,
         "1000-120-6100", "Entered", "2/10 Net 30", "2025-10-04", "T. Okonkwo", "2025-09-04", None, None, 0,
         "Employment law consultation"]
IR_WCG = [1037, "V-00039", "Whitfield Consulting Group, Inc.", "WCG-2025-0087", "2025-08-28", None, "Non-PO", 4950,
          "1000-120-6100", "Entered", "2/10 Net 30", "2025-09-27", "T. Okonkwo", "2025-09-04", None, None, 0,
          "FMLA/ADA memorandum"]

HC_SUBJ = "AP APPROVAL REQUIRED: Harrison & Cole LLP - $5,000.00 - Invoice HC-2025-0001"
HC_BODY = ("A non-PO invoice requires your approval before payment can be processed. Vendor: Harrison & Cole LLP "
           "(V-00038). Invoice: HC-2025-0001, dated 09/04/2025.\nAmount: $5,000.00. Description: Employment law "
           "consultation - Policy review and compliance assessment. GL Code: 1000-120-6100. Please reply APPROVED or "
           "REJECTED with reason. If no response is received within 3 business days, the invoice will be placed on "
           "APPR hold and the vendor will be notified of the delay.")
WCG_SUBJ = "AP APPROVAL REQUIRED: Whitfield Consulting Group, Inc. - $4,950.00 - Invoice WCG-2025-0087"
WCG_BODY = ("A non-PO invoice requires your approval before payment can be processed. Vendor: Whitfield Consulting "
            "Group, Inc. (V-00039). Invoice: WCG-2025-0087, dated 08/28/2025.\nAmount: $4,950.00. Description: "
            "Memorandum re: FMLA/ADA intersection analysis. GL Code: 1000-120-6100. Please reply APPROVED or REJECTED "
            "with reason. If no response is received within 3 business days, the invoice will be placed on APPR hold "
            "and the vendor will be notified of the delay.")
NV_HC = "NEW VENDOR ADDED: Harrison & Cole LLP, V-00038, 1099 Reportable: Yes"
NV_WCG = "NEW VENDOR ADDED: Whitfield Consulting Group, Inc., V-00039, 1099 Reportable: Yes"
DISC = "EARLY PAYMENT DISCOUNT: Harrison & Cole LLP, Invoice HC-2025-0001, Discount $100.00, Deadline 09/14/2025"
DUPV = ("DUPLICATE VENDOR SUSPECTED: ClearPath Talent Solutions matches Tax ID of existing vendor "
        "Premier Staffing Group, V-00008")


def mail(to, subject, body, cc=AP):
    return {"to": to, "cc": cc, "subject": subject, "body": body}


class Base(TaskCase):
    TASK = "finance_meridian_partners_331accf1"

    def add_vendors(self, hc=VM_HC, wcg=VM_WCG):
        self.edit("vendor_master.xlsx", "\n".join(f"ws.append({r!r})" for r in (hc, wcg) if r))

    def add_invoices(self, hc=IR_HC, wcg=IR_WCG):
        self.edit("ap_ledger.xlsx", "\n".join(f"ws.append({r!r})" for r in (hc, wcg) if r), "Invoice Register")

    def add_files(self):
        pdf = b"%PDF-1.4\n%test\n"
        for rel in ("1099/2025/W9_Harrison_Cole_LLP.pdf", "1099/2025/W9_Whitfield_Consulting_Group.pdf",
                    "Invoices/2025-09/INV-V-00038-HC-2025-0001.pdf", "Invoices/2025-09/INV-V-00039-WCG-2025-0087.pdf"):
            self.write(rel, pdf)

    def send_all(self):
        self.did(MAIL, mail(f"{JW}, {MS}", HC_SUBJ, HC_BODY))
        self.did(MAIL, mail(f"{JW}, {MS}", WCG_SUBJ, WCG_BODY))
        self.did(POST, {"channel_id": "C004", "text": NV_HC})
        self.did(POST, {"channel_id": "C004", "text": NV_WCG})
        self.did(POST, {"channel_id": "C003", "text": DISC})
        self.did(POST, {"channel_id": "C005", "text": DUPV})

    def golden(self):
        self.add_vendors()
        self.add_invoices()
        self.add_files()
        self.send_all()


class TestInitialAndGolden(Base):
    def test_initial_obligations(self):
        d = self.done_all()
        rules = {r for r, _ in d}
        self.assertEqual(rules, {"comms.messages_sent", "vendor_master.new_vendors", "ledger.invoice_entries",
                                 "files.stored_documents"})
        self.assertEqual(sum(r == "comms.messages_sent" for r, _ in d), 8)
        self.assertEqual(sum(r == "files.stored_documents" for r, _ in d), 4)

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_golden_whitfield_net30_accepted(self):
        wcg = list(VM_WCG)
        wcg[7] = "Net 30"
        inv = list(IR_WCG)
        inv[10] = "Net 30"
        self.add_vendors(wcg=wcg)
        self.add_invoices(wcg=inv)
        self.add_files()
        self.send_all()
        self.assertEqual(self.done(), {})


class TestComms(Base):
    def setUp(self):
        super().setUp()
        self.add_vendors()

    def test_compliant_messages_pass(self):
        self.assertEqual(self.pre(MAIL, mail(f"{JW}, {MS}", HC_SUBJ, HC_BODY)), set())
        self.assertEqual(self.pre(MAIL, mail(JW, WCG_SUBJ, WCG_BODY)), set())
        self.assertEqual(self.pre(POST, {"channel_id": "C004", "text": NV_HC}), set())
        self.assertEqual(self.pre(POST, {"channel_id": "C004", "text": NV_WCG + " - please acknowledge"}), set())
        self.assertEqual(self.pre(POST, {"channel_id": "C003", "text": DISC}), set())
        self.assertEqual(self.pre(POST, {"channel_id": "C005", "text": DUPV + "."}), set())

    def test_approval_bad_subject_and_body(self):
        self.assertIn("comms.messages", self.pre(MAIL, mail(JW, "Approval needed HC-2025-0001", HC_BODY)))
        body = HC_BODY.replace("within 3 business days", "within 5 business days")
        self.assertIn("comms.messages", self.pre(MAIL, mail(JW, HC_SUBJ, body)))
        self.assertIn("comms.messages", self.pre(MAIL, mail(JW, HC_SUBJ, HC_BODY, cc="")))

    def test_approval_wrong_vendor_id(self):
        self.assertIn("comms.messages", self.pre(MAIL, mail(JW, HC_SUBJ, HC_BODY.replace("V-00038", "V-00039"))))

    def test_new_vendor_wrong_1099_and_dm(self):
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C004", "text": NV_WCG.replace("Yes", "No")}))
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C003", "text": NV_HC}))
        self.assertIn("comms.messages", self.pre(DM, {"user_id": "U002", "text": NV_HC}))

    def test_discount_rules(self):
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C003", "text": DISC.replace("100.00", "98.00")}))
        wcg = "EARLY PAYMENT DISCOUNT: Whitfield Consulting Group, Inc., Invoice WCG-2025-0087, Discount $99.00, Deadline 09/07/2025"
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C003", "text": wcg}))

    def test_duplicate_vendor_exact(self):
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C005", "text": DUPV + ". Please advise, thanks!"}))
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C003", "text": DUPV}))
        self.assertIn("comms.messages", self.pre(MAIL, mail(RP, "Duplicate vendor", DUPV, cc="")))

    def test_forbidden_messages(self):
        self.assertIn("comms.messages", self.pre(MAIL, mail(
            "s.harrison@harrisoncolellp.com", "Meridian Partners - Incomplete Invoice HC-2025-0001", "missing fields", cc="")))
        self.assertIn("comms.messages", self.pre(MAIL, mail(
            f"{JW}, {MS}", "AP APPROVAL REQUIRED: ClearPath Talent Solutions - $5,050.00 - Invoice CPT-2025-0412", "x")))
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C004", "text": "NEW VENDOR ADDED: ClearPath Talent Solutions, V-00040, 1099 Reportable: Yes"}))
        self.assertIn("comms.messages", self.pre(MAIL, mail(
            "d.whitfield@whitfieldcg.com", "Invoice WCG-2025-0087", "Invoice WCG-2025-0087 for $4,950.00 is currently "
            "pending internal approval.", cc="")))
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C003", "text": "DUPLICATE DETECTED: Harrison & Cole LLP, V-00038, Invoice HC-2025-0001"}))

    def test_resend_blocked(self):
        self.did(POST, {"channel_id": "C004", "text": NV_HC})
        self.assertIn("comms.messages", self.pre(POST, {"channel_id": "C004", "text": NV_HC}))

    def test_messages_sent_completion(self):
        self.assertIn("comms.messages_sent", self.done())
        self.send_all()
        self.assertNotIn("comms.messages_sent", self.done())

    def test_approval_recipients(self):
        self.assertIn("comms.approval_recipients", self.pre(MAIL, mail(f"{JW}, {MS}, {RP}", HC_SUBJ, HC_BODY)))
        self.assertNotIn("comms.approval_recipients", self.pre(MAIL, mail(f"{JW}, {MS}", HC_SUBJ, HC_BODY)))

    def test_placeholders(self):
        self.assertIn("comms.no_placeholders", self.pre(POST, {"channel_id": "C004", "text": "NEW VENDOR ADDED: [VENDOR NAME], V-00038"}))
        self.assertNotIn("comms.no_placeholders", self.pre(POST, {"channel_id": "C004", "text": NV_HC}))


class TestVendorFirst(Base):
    def test_blocked_before_setup(self):
        self.assertIn("comms.vendor_setup_first", self.pre(POST, {"channel_id": "C004", "text": NV_HC}))
        self.assertIn("comms.vendor_setup_first", self.pre(MAIL, mail(f"{JW}, {MS}", WCG_SUBJ, WCG_BODY)))

    def test_allowed_after_setup(self):
        self.add_vendors()
        self.assertNotIn("comms.vendor_setup_first", self.pre(POST, {"channel_id": "C004", "text": NV_HC}))
        self.assertNotIn("comms.vendor_setup_first", self.pre(MAIL, mail(f"{JW}, {MS}", WCG_SUBJ, WCG_BODY)))


class TestVendorMaster(Base):
    def test_wrong_fields(self):
        hc = list(VM_HC)
        hc[11], hc[12], hc[2] = "No", "N/A", "23-7654322"
        self.add_vendors(hc=hc)
        p = self.done().get("vendor_master.new_vendors", "")
        self.assertIn("Tax ID must be 23-7654321", p)
        self.assertIn("1099 Reportable must be Yes", p)

    def test_wrong_id_and_blank_field(self):
        hc = list(VM_HC)
        hc[0], hc[9] = "V-00040", None
        self.add_vendors(hc=hc)
        p = self.done().get("vendor_master.new_vendors", "")
        self.assertIn("next sequential", p)
        self.assertIn("is blank", p)

    def test_correct_rows(self):
        self.add_vendors()
        self.assertNotIn("vendor_master.new_vendors", self.done())

    def test_no_clearpath(self):
        self.add_vendors()
        self.assertNotIn("vendor_master.no_clearpath", self.done())
        self.edit("vendor_master.xlsx", "ws.append(['V-00040','ClearPath Talent Solutions','58-8901234'])")
        self.assertIn("vendor_master.no_clearpath", self.done())

    def test_existing_rows_unchanged(self):
        self.assertNotIn("vendor_master.append_only", self.done())
        self.edit("vendor_master.xlsx", "ws.cell(row=4, column=col['Bank Name']).value='Truliant Federal Credit Union'")
        self.assertIn("vendor_master.append_only", self.done())


class TestLedger(Base):
    def setUp(self):
        super().setUp()
        self.add_vendors()

    def test_correct_entries(self):
        self.add_invoices()
        self.assertNotIn("ledger.invoice_entries", self.done())

    def test_approved_too_early_and_wrong_category(self):
        hc = list(IR_HC)
        hc[9], hc[14], hc[6] = "Approved", "M. Santos", "PO Invoice"
        self.add_invoices(hc=hc)
        p = self.done().get("ledger.invoice_entries", "")
        self.assertIn("not approved yet", p)
        self.assertIn("Category must be Non-PO", p)

    def test_hc_net30_rejected(self):
        hc = list(IR_HC)
        hc[10] = "Net 30"
        self.add_invoices(hc=hc)
        self.assertIn("Payment Terms", self.done().get("ledger.invoice_entries", ""))

    def test_clearpath_not_entered(self):
        self.add_invoices()
        self.edit("ap_ledger.xlsx", "ws.append([1038,'V-00008','Premier Staffing Group','CPT-2025-0412','2025-09-02',None,"
                                    "'Non-PO',5050,'1000-100-6100','Entered'])", "Invoice Register")
        self.assertIn("CPT-2025-0412", self.done().get("ledger.invoice_entries", ""))

    def test_register_append_only(self):
        self.assertNotIn("ledger.register_append_only", self.done())
        self.edit("ap_ledger.xlsx", "ws.cell(row=34, column=col['Status']).value='Approved'", "Invoice Register")
        self.assertIn("ledger.register_append_only", self.done())

    def test_payment_queue_untouched(self):
        self.assertNotIn("ledger.other_sheets_unchanged", self.done())
        self.edit("ap_ledger.xlsx", "ws.append(['PAY-2025-0821',1036,'V-00038','Harrison & Cole LLP','HC-2025-0001',4900,"
                                    "'ACH','2025-09-09','2025-09-09','Scheduled',''])", "Payment Queue")
        self.assertIn("ledger.other_sheets_unchanged", self.done())


class TestFiles(Base):
    def test_exceptions_append_only(self):
        self.edit("exceptions_tracker_2025.xlsx", "ws.append(['EXC-2025-004','2025-09-04','V-00008'])")
        self.assertNotIn("exceptions.append_only", self.done())
        self.edit("exceptions_tracker_2025.xlsx", "ws.cell(row=2, column=col['Status']).value='Open'")
        self.assertIn("exceptions.append_only", self.done())

    def test_unrequested_workbook_changes(self):
        self.assertNotIn("files.no_unrequested_changes", self.done())
        self.edit("match_log_2025_Q3.xlsx", "ws.append(['MTH-Q3-018','2025-09-04'])")
        self.assertIn("files.no_unrequested_changes", self.done())

    def test_adhoc_spreadsheet(self):
        self.edit("vendor_master.xlsx", "wb.save(path.replace('vendor_master','new_vendor_setup'))")
        self.assertIn("files.no_unrequested_changes", self.done())

    def test_stored_documents(self):
        self.add_vendors()
        self.assertIn("files.stored_documents", self.done())
        self.add_files()
        self.assertNotIn("files.stored_documents", self.done())

    def test_stored_documents_not_pdf(self):
        self.add_vendors()
        self.add_files()
        self.write("Invoices/2025-09/INV-V-00038-HC-2025-0001.pdf", "JVBERi0xLjQK")
        self.assertIn("INV-V-00038-HC-2025-0001.pdf", self.done().get("files.stored_documents", ""))
