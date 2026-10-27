"""Blind unit tests for logistics_gear_sytems_inc_74170ae1 (end-of-shift handoff, Gear Systems Meridian)."""

from __future__ import annotations

from interwhen_sop.tests.base import TaskCase

POST = "slack__post_message"
DM = "slack__send_dm"
SEND = "google_mail__send_email"

HANDOFF = """END-OF-SHIFT HANDOFF 04/14/2026 — Coordinator: SM

Receipts completed today: 4
Receipts open at handoff: 3
NCRs issued today: 3 (2 Critical, 1 Major)
Quarantines applied today: 3
Escalations open: 2

OPEN RECEIPTS:
- REC-20260414-003: Quarantined in Q-HOLD, awaiting MTR from Consolidated Forge Works (see Handoff_Notes)
- REC-20260414-005: Line 001 quarantined (Tier 2), NCR-0252 pending Theo review; line 002 accepted
- REC-20260414-007: Quarantined (Band 3 short), escalation awaiting Elizabeth Velasquez

OPEN NCRs AWAITING COORDINATOR ACTION:
- NCR-MER-2026-0252: Critical draft sent to Theo Brandt 13:30 CST, awaiting approval before sending

OPEN ESCALATIONS:
- REC-20260414-007, $7,650.00, Tier 2 + line-down override, awaiting Elizabeth Velasquez / Walter Finch since 12:35 CST
- REC-20260414-005, $5,565.00, Critical NCR override, awaiting Walter Finch / Darnell Hooks since 13:35 CST

QUARANTINE STATUS:
- Q-HOLD currently holds 4 entries totaling approximately $76,712.00. Re-inspections scheduled: REC-20260414-003, REC-20260414-005, REC-20260414-007 (04/21/2026); REC-20260408-001 (04/15/2026).

NOTES FOR TOMORROW:
- AX-04827-B2 replenishment PO MER-PO-106835 (120 units) due 04/15 09:00 at Dock 3 - line-down risk if late.
- Heartland (Probation) MER-PO-108515 due 04/15 11:00 - Reggie inspection required."""

CURTIS = ("End-of-shift status: REC-20260414-003 (FG-91144-A1, 200) in Q-HOLD awaiting MTR; REC-20260414-005 line 001 "
          "(BG-33044-A1, 144) in Q-HOLD, line 002 SL-20118-C3 accepted; REC-20260414-007 (AX-04827-B2, 78) in Q-HOLD.")

NOTES = {
    ("REC-20260414-003", "001"): "AWAITING MTR: quarantined in Q-HOLD, MTR for H-8827-A/B promised by supplier COB today. "
                                 "Verify heat numbers per 12.6 when it arrives; Coordinator owns; escalate if not by 04/21.",
    ("REC-20260414-005", "001"): "AWAITING QUALITY: Tier 2 damage, quarantined. NCR-MER-2026-0252 Critical draft pending "
                                 "Theo Brandt review; escalation awaiting Walter Finch. Do not send until approved.",
    ("REC-20260414-005", "002"): "AWAITING POSTING: Band 1 short accepted; inventory and putaway post outstanding. Coordinator.",
    ("REC-20260414-007", "001"): "AWAITING ESCALATION: Band 3 short quarantined, NCR-0253 sent; escalation awaiting "
                                 "Elizabeth Velasquez / Walter Finch. Supplier response due 04/17/2026.",
}

EVENTS = [("REC-20260414-003", "FG-91144-A1", "MER-PO-107294", "NCR-MER-2026-0251", "200", "Missing MTR"),
          ("REC-20260414-005", "BG-33044-A1", "MER-PO-108510", "NCR-MER-2026-0252", "144", "Tier 2 damage"),
          ("REC-20260414-007", "AX-04827-B2", "MER-PO-106833", "NCR-MER-2026-0253", "78", "Band 3 short")]

FILING = {"6": "General", "7": "Carriers", "8": "Suppliers - General", "9": "Receipts - In Process",
          "10": "Internal", "11": "NCRs - Open", "12": "NCRs - Open"}

BOOKS = "open_pos.xlsx\nreceiving_log.xlsx\ninventory_master.xlsx\nsupplier_master.xlsx\nncr_log.xlsx\ndock_schedule.xlsx\n"


def event(rid, sku, po, ncr, qty, reason, date="2026-04-21", guests=("darnell.hooks@gearsystems.com",
                                                                      "theo.brandt@gearsystems.com")):
    return {"summary": f"RE-INSPECTION: {rid} {sku} {reason}",
            "start": {"dateTime": f"{date}T09:00:00-05:00"}, "end": {"dateTime": f"{date}T09:30:00-05:00"},
            "description": f"Receipt {rid}, PO {po}, SKU {sku}, qty {qty} quarantined, reason {reason}, NCR {ncr}, "
                           "photos /receiving/2026-04-14/",
            "attendees": [{"email": g} for g in ("receiving.meridian@gearsystems.com", *guests)]}


class T74170ae1(TaskCase):
    TASK = "logistics_gear_sytems_inc_74170ae1"

    # ---- helpers ----
    def set_rlog(self, updates: dict):
        """updates: {(rid, line): {col: value}}"""
        code = f"U={updates!r}\n" + (
            "for r in range(2, ws.max_row+1):\n"
            "    k=(ws.cell(r,col['Receipt_ID']).value, str(ws.cell(r,col['PO_Line']).value))\n"
            "    for c,v in U.get(k,{}).items():\n"
            "        ws.cell(r,col[c]).value=v\n")
        self.edit("receiving_log.xlsx", code)

    def set_by_key(self, fname, keycol, updates):
        code = f"U={updates!r}\n" + (
            "for r in range(2, ws.max_row+1):\n"
            f"    k=ws.cell(r,col[{keycol!r}]).value\n"
            "    for c,v in U.get(k,{}).items():\n"
            "        ws.cell(r,col[c]).value=v\n")
        self.edit(fname, code)

    def good_rlog(self):
        self.set_rlog({k: {"Status": "OPEN — handoff", "Handoff_Notes": v} for k, v in NOTES.items()})

    def good_ncr(self):
        self.set_by_key("ncr_log.xlsx", "NCR_Number", {
            "NCR-MER-2026-0251": {"Supplier_Response_Due": "04/28/2026"},
            "NCR-MER-2026-0253": {"Supplier_Response_Due": "04/17/2026"},
            "NCR-MER-2026-0252": {"Severity": "Critical"}})

    def good_calendar(self):
        for e in EVENTS:
            self.did("google_calendar__create_event", event(*e))

    def good_mail(self):
        for eid, f in FILING.items():
            self.did("google_mail__move_email", {"email_id": eid, "target_folder": f})
            if eid != "6":
                self.did("google_mail__mark_email", {"email_id": eid, "is_read": True})

    def good_posts(self):
        self.did(DM, {"user_id": "U009", "text": CURTIS})
        self.did(POST, {"channel_id": "C001", "text": HANDOFF})

    def good_close(self):
        self.write("closed_workbooks.txt", BOOKS)
        self.did("syntara__writeFile", {"file_path": "/workdir/closed_workbooks.txt", "content": BOOKS})

    def golden(self):
        self.good_rlog()
        self.good_ncr()
        self.good_calendar()
        self.good_mail()
        self.good_posts()
        self.good_close()

    # ---- initial state / golden path ----
    def test_initial_findings(self):
        self.assertEqual(set(self.done()), {
            "lgs.eos.messages_sent", "lgs.open_receipts_handoff", "lgs.ncr_log", "lgs.reinspection_events",
            "lgs.email_filing", "lgs.closed_workbooks"})

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done_all(), [])

    # ---- pre rules ----
    def test_ncr0252_not_sent(self):
        bad = {"to": "kfoss@heartlandbearings.com", "cc": "theo.brandt@gearsystems.com",
               "subject": "NCR-MER-2026-0252 | Critical | Heartland Bearings LLC | MER-PO-108510 | Response Required by 04/17/2026",
               "body": "Please find attached NCR-MER-2026-0252."}
        self.assertIn("lgs.ncr0252_awaiting_theo", self.pre(SEND, bad))
        ok = {"to": "theo.brandt@gearsystems.com", "subject": "Reminder: NCR-MER-2026-0252 draft awaiting review",
              "body": "Theo, NCR-MER-2026-0252 draft is still awaiting your review."}
        self.assertNotIn("lgs.ncr0252_awaiting_theo", self.pre(SEND, ok))

    def test_escalation_hold(self):
        bad = {"to": "rpatel@meridiansteel.com", "subject": "Corrected NCR letter — MER-PO-106833",
               "body": "Raj, a corrected NCR-MER-2026-0253 letter referencing heat number H-6203-D."}
        self.assertIn("lgs.escalation_hold", self.pre(SEND, bad))
        ok = {"to": "dlinden@heartlandbearings.com", "subject": "RE: Delivery Forecast — May 2026",
              "body": "Hi Doug, thanks for the forecast; I've passed it to Procurement (Joon-ho Park)."}
        self.assertEqual(self.pre(SEND, ok), set())

    def test_no_supplier_promises(self):
        bad = {"to": "spark@conforge.com", "subject": "MTR follow-up",
               "body": "Hi Susan, we will issue a credit for the delay once the MTR arrives."}
        self.assertIn("lgs.no_supplier_promises", self.pre(SEND, bad))
        ok = {"to": "spark@conforge.com", "subject": "MTR follow-up",
              "body": "Hi Susan, please send the MTR for H-8827-A and H-8827-B as a PDF."}
        self.assertNotIn("lgs.no_supplier_promises", self.pre(SEND, ok))

    def test_no_email_delete(self):
        self.assertIn("lgs.no_email_delete", self.pre("google_mail__delete_email", {"email_id": "6"}))
        self.assertEqual(self.pre("google_mail__move_email", {"email_id": "6", "target_folder": "General"}), set())

    def test_no_record_delete(self):
        self.assertIn("lgs.no_record_delete", self.pre("syntara__executeBash", {"command": "rm /workdir/ncr_log.xlsx"}))
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/receiving_log.xlsx')\nws=wb.active\n"
                "ws.delete_rows(9)\nwb.save('/workdir/receiving_log.xlsx')\n")
        self.assertIn("lgs.no_record_delete", self.pre("syntara__executePython", {"code": code}))
        ok = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/receiving_log.xlsx')\nws=wb.active\n"
              "ws['AF9']='OPEN — handoff'\nwb.save('/workdir/receiving_log.xlsx')\n")
        self.assertNotIn("lgs.no_record_delete", self.pre("syntara__executePython", {"code": ok}))

    def test_no_slack_delete(self):
        self.assertIn("lgs.no_slack_delete", self.pre("slack__delete_message", {"channel_id": "C003", "ts": "1"}))
        self.assertEqual(self.pre(POST, {"channel_id": "C002", "text": "Noted, thanks Reggie."}), set())

    def test_quarantine_hold(self):
        bad = {"channel_id": "C001", "text": "QUARANTINE RELEASED: REC-20260414-003, SKU FG-91144-A1, qty 200 "
                                             "released from Q-HOLD to A-RCV-01."}
        self.assertIn("lgs.quarantine_hold", self.pre(POST, bad))
        ok = {"channel_id": "C001", "text": "PUTAWAY AUTHORIZED: REC-20260414-005, Heartland Bearings LLC (SUP-0312), "
                                            "2 lines.\n- Line 001: BG-33044-A1, 144 units → Q-HOLD (QUARANTINE — Tier 2)\n"
                                            "- Line 002: SL-20118-C3, 488 units → B-RCV-01\nCoordinator: SM"}
        self.assertEqual(self.pre(POST, ok), set())
        bad2 = dict(ok, text=ok["text"].replace("Q-HOLD (QUARANTINE — Tier 2)", "B-RCV-01"))
        self.assertIn("lgs.quarantine_hold", self.pre(POST, bad2))

    def test_supplier_master_readonly(self):
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/supplier_master.xlsx')\n"
                "wb.active['C6']='Suspended'\nwb.save('/workdir/supplier_master.xlsx')\n")
        self.assertIn("lgs.supplier_master_readonly", self.pre("syntara__executePython", {"code": code}))
        ok = code.replace("supplier_master", "receiving_log")
        self.assertNotIn("lgs.supplier_master_readonly", self.pre("syntara__executePython", {"code": ok}))

    def test_no_placeholders(self):
        self.assertIn("comms.no_placeholders", self.pre(POST, {"channel_id": "C003", "text": "Update on REC-[ID]."}))
        self.assertNotIn("comms.no_placeholders", self.pre(POST, {"channel_id": "C001", "text": HANDOFF}))

    def test_handoff_post_vetting(self):
        self.assertEqual(self.pre(POST, {"channel_id": "C001", "text": HANDOFF}), set())
        self.assertIn("lgs.eos.messages",
                      self.pre(POST, {"channel_id": "C001", "text": HANDOFF.replace("Escalations open: 2",
                                                                                     "Escalations open: 3")}))
        self.assertIn("lgs.eos.messages", self.pre(POST, {"channel_id": "C003", "text": HANDOFF}))
        no_ncr = HANDOFF.replace("- NCR-MER-2026-0252: Critical draft", "- None")
        self.assertIn("lgs.eos.messages", self.pre(POST, {"channel_id": "C001", "text": no_ncr}))

    def test_handoff_single_post(self):
        self.did(POST, {"channel_id": "C001", "text": HANDOFF})
        self.assertIn("lgs.eos.messages", self.pre(POST, {"channel_id": "C001", "text": HANDOFF}))

    def test_curtis_dm(self):
        self.assertEqual(self.pre(DM, {"user_id": "U009", "text": CURTIS}), set())
        self.assertIn("lgs.eos.messages",
                      self.pre(DM, {"user_id": "U009", "text": CURTIS.replace("REC-20260414-007", "the axle receipt")}))

    # ---- completion rules ----
    def test_open_receipts_compliant(self):
        self.good_rlog()
        self.assertNotIn("lgs.open_receipts_handoff", self.done())

    def test_open_receipts_wrong_status(self):
        self.good_rlog()
        self.set_rlog({("REC-20260414-007", "001"): {"Status": "AWAITING ESCALATION RESPONSE"}})
        self.assertIn("REC-20260414-007", self.done()["lgs.open_receipts_handoff"])

    def test_open_receipts_vague_note(self):
        self.good_rlog()
        self.set_rlog({("REC-20260414-003", "001"): {"Handoff_Notes": "Pending."}})
        self.assertIn("lgs.open_receipts_handoff", self.done())

    def test_line002_posted(self):
        self.good_rlog()
        self.set_rlog({("REC-20260414-005", "002"): {"Status": "Posted", "Handoff_Notes": None}})
        self.assertIn("line 002 is Posted", self.done()["lgs.open_receipts_handoff"])
        self.set_rlog({("REC-20260414-005", "002"): {"Disposition_Timestamp": "04/14/2026 14:05 CST",
                                                     "Putaway_Authorized_Timestamp": "04/14/2026 14:06 CST"}})
        self.edit("inventory_master.xlsx",
                  "for r in range(2, ws.max_row+1):\n"
                  "    if ws.cell(r,col['SKU']).value=='SL-20118-C3' and ws.cell(r,col['Location']).value=='B-RCV-01':\n"
                  "        ws.cell(r,col['On_Hand_Qty']).value=1108\n"
                  "        ws.cell(r,col['Last_Receipt_ID']).value='REC-20260414-005'\n"
                  "        ws.cell(r,col['Last_Receipt_Date']).value='04/14/2026'\n")
        self.did(POST, {"channel_id": "C001", "text": "PUTAWAY AUTHORIZED: REC-20260414-005, Heartland Bearings LLC, "
                                                      "2 lines.\n- Line 001: BG-33044-A1, 144 units → Q-HOLD\n"
                                                      "- Line 002: SL-20118-C3, 488 units → B-RCV-01\nCoordinator: SM"})
        self.assertNotIn("lgs.open_receipts_handoff", self.done())

    def test_posted_rows_unchanged(self):
        self.set_rlog({("REC-20260414-001", "001"): {"Qty_Ordered": 1000.0}})
        self.assertNotIn("lgs.posted_rows_unchanged", self.done())
        self.set_rlog({("REC-20260414-001", "001"): {"Qty_Received": 999}})
        self.assertIn("lgs.posted_rows_unchanged", self.done())

    def test_no_unrequested_rows(self):
        self.edit("receiving_log.xlsx", "ws.append(['REC-20260414-001-C1','MER-PO-107100','001','PK-50021-A1'])")
        self.assertNotIn("lgs.no_unrequested_rows", self.done())
        self.edit("ncr_log.xlsx", "ws.append(['NCR-MER-2026-0254','04/14/2026','SUP-0312'])")
        self.assertIn("NCR-MER-2026-0254", self.done()["lgs.no_unrequested_rows"])

    def test_ncr_log(self):
        self.good_ncr()
        self.assertNotIn("lgs.ncr_log", self.done())
        self.set_by_key("ncr_log.xlsx", "NCR_Number", {"NCR-MER-2026-0251": {"Status": "Closed"}})
        self.assertIn("never marks an NCR", self.done()["lgs.ncr_log"])

    def test_ncr0252_not_marked_sent(self):
        self.good_ncr()
        self.set_by_key("ncr_log.xlsx", "NCR_Number", {"NCR-MER-2026-0252": {"Status": "Sent - Awaiting Response",
                                                                             "Letter_Sent_Date": "04/14/2026"}})
        self.assertIn("must not be marked sent", self.done()["lgs.ncr_log"])

    def test_qhold_intact(self):
        self.assertNotIn("lgs.qhold_intact", self.done())
        self.edit("inventory_master.xlsx",
                  "for r in range(2, ws.max_row+1):\n"
                  "    if ws.cell(r,col['SKU']).value=='FG-91144-A1' and ws.cell(r,col['Location']).value=='Q-HOLD':\n"
                  "        ws.cell(r,col['On_Hand_Qty']).value=0\n")
        self.assertIn("lgs.qhold_intact", self.done())

    def test_readonly_data(self):
        self.edit("open_pos.xlsx", "ws.cell(2,col['Receipt_Status']).value='Received - Quarantine'")
        self.assertNotIn("lgs.readonly_data", self.done())
        self.edit("open_pos.xlsx", "ws.cell(2,col['Unit_Price']).value='$80.00'")
        self.assertIn("lgs.readonly_data", self.done())

    def test_readonly_supplier_master(self):
        self.edit("supplier_master.xlsx", "ws.cell(6,col['Status']).value='Suspended'")
        self.assertIn("supplier_master", self.done()["lgs.readonly_data"])

    def test_calendar_compliant(self):
        self.good_calendar()
        self.assertNotIn("lgs.reinspection_events", self.done())

    def test_calendar_wrong_date_and_guests(self):
        self.did("google_calendar__create_event", event(*EVENTS[0], date="2026-04-17"))
        self.did("google_calendar__create_event", event(*EVENTS[1], guests=("darnell.hooks@gearsystems.com",)))
        self.did("google_calendar__create_event", event(*EVENTS[2]))
        msg = " ".join(p for r, p in self.done_all() if r == "lgs.reinspection_events")
        self.assertIn("04/21/2026", msg)
        self.assertIn("theo.brandt", msg)
        self.assertNotIn("REC-20260414-007", msg)

    def test_email_filing_compliant_list_form(self):
        for f in set(FILING.values()):
            ids = [i for i, x in FILING.items() if x == f]
            self.did("google_mail__move_emails", {"email_ids": ids, "target_folder": f})
        self.did("google_mail__mark_emails", {"email_ids": ["7", "8", "9", "10", "11", "12"], "mark_as": "read"})
        self.assertNotIn("lgs.email_filing", self.done())

    def test_email_filing_violations(self):
        self.good_mail()
        self.did("google_mail__move_email", {"email_id": "11", "target_folder": "Internal"})
        self.did("google_mail__mark_email", {"email_id": "7", "is_read": False})
        msg = " ".join(p for r, p in self.done_all() if r == "lgs.email_filing")
        self.assertIn("Email 11", msg)
        self.assertIn("Email 7", msg)
        self.assertNotIn("Email 6", msg)

    def test_closed_workbooks(self):
        self.good_posts()
        self.good_close()
        self.assertNotIn("lgs.closed_workbooks", self.done())

    def test_closed_workbooks_missing_and_order(self):
        self.write("closed_workbooks.txt", BOOKS.replace("dock_schedule.xlsx\n", ""))
        self.did("syntara__writeFile", {"file_path": "/workdir/closed_workbooks.txt", "content": "x"})
        self.good_posts()
        msg = " ".join(p for r, p in self.done_all() if r == "lgs.closed_workbooks")
        self.assertIn("dock_schedule.xlsx", msg)
        self.assertIn("after the handoff post", msg)
