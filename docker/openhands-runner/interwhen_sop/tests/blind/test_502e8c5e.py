"""Blind unit tests for logistics_gear_sytems_inc_502e8c5e (fixtures from the task environment seed only)."""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase

ARRIVAL = "ARRIVAL ON TIME: APPT-20260520-001, Ritter Fastener Group, Dock 2, PO #MER-PO-104903. Cleared to unload."
NOTES = ("Supplier status: Approved as of 02/20/2026 per supplier_master.xlsx. Partial PO fulfillment: this shipment "
         "covers PO line 002 only (slip claims 1,600 of 1,800; 200 back-ordered); line 001 previously fulfilled.")
ROW = {"Receipt_ID": "REC-20260520-001", "PO_Number": "MER-PO-104903", "PO_Line": "002", "SKU": "FS-10091-B1",
       "Safety_Critical": "Y", "Supplier_ID": "SUP-0155", "Carrier_Name": "XPO Logistics",
       "Arrival_Timestamp": "05/20/2026 07:02 CST", "Dock_Door": "Dock 2", "Qty_Ordered": 1800,
       "Qty_Claimed_On_Slip": 1600, "Coordinator_Initials": "CY", "Status": "Awaiting Count", "Notes": NOTES}


class Base(TaskCase):
    TASK = "logistics_gear_sytems_inc_502e8c5e"

    def dock(self, appt="APPT-20260520-001", t="07:02", status="Arrived"):
        self.edit("dock_schedule.xlsx",
                  f"for r in range(2, ws.max_row+1):\n"
                  f"    if ws.cell(r, col['Appointment_ID']).value == {appt!r}:\n"
                  f"        ws.cell(r, col['Actual_Arrival_Time']).value = {t!r}\n"
                  f"        ws.cell(r, col['Status']).value = {status!r}\n")

    def log_row(self, **over):
        vals = {**ROW, **over}
        self.edit("receiving_log.xlsx", f"vals={vals!r}\nws.append([vals.get(h) for h in hdr])\n")

    def post(self, text=ARRIVAL, channel="C001"):
        self.did("slack__post_message", {"channel_id": channel, "text": text})

    def golden(self):
        self.dock()
        self.log_row()
        self.post()


class GoldenPath(Base):
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {"dock.arrival_logged", "log.receipt_row", "comms.messages_sent"})

    def test_golden_done(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_status_unloading_accepted(self):
        self.dock(status="Unloading")
        self.log_row(Status="In Process")
        self.post()
        self.assertEqual(self.done(), {})


class DockRules(Base):
    def test_wrong_time(self):
        self.dock(t="06:30")
        self.log_row()
        self.post()
        self.assertIn("dock.arrival_logged", self.done())

    def test_wrong_status(self):
        self.dock(status="Complete")
        self.assertIn("dock.arrival_logged", self.done())

    def test_later_appointment_processed(self):
        self.golden()
        self.dock(appt="APPT-20260520-002", t="07:05", status="Arrived")
        d = self.done()
        self.assertIn("dock.other_rows_unchanged", d)
        self.assertIn("has not arrived", d["dock.other_rows_unchanged"])


class LogRules(Base):
    def test_wrong_fields(self):
        self.dock()
        self.log_row(Qty_Claimed_On_Slip=1800, Arrival_Timestamp="2026-05-20 07:02")
        self.post()
        d = self.done()
        self.assertIn("log.receipt_row", d)
        self.assertIn("Qty_Claimed_On_Slip", d["log.receipt_row"])

    def test_missing_status_note(self):
        self.dock()
        self.log_row(Notes="Partial PO fulfillment: line 002 only.")
        self.post()
        self.assertEqual(set(self.done()), {"log.supplier_status_note"})

    def test_missing_partial_note(self):
        self.dock()
        self.log_row(Notes="Supplier status: Approved as of 02/20/2026.")
        self.post()
        self.assertEqual(set(self.done()), {"log.partial_note"})

    def test_estimated_count(self):
        self.dock()
        self.log_row(Qty_Received=1600, Variance_Units=-200, Status="Posted")
        self.post()
        self.assertIn("log.no_count_yet", self.done())

    def test_packing_slip_as_coc(self):
        self.dock()
        self.log_row(COC_Filename="MER-PO-104903_packingslip_2.pdf")
        self.post()
        self.assertIn("log.no_count_yet", self.done())

    def test_extra_rows(self):
        self.golden()
        self.log_row(Receipt_ID="REC-20260520-002", PO_Number="MER-PO-105004", PO_Line="001", SKU="PK-00112-A1")
        self.assertIn("log.only_shipped_lines", self.done())

    def test_line_001_added(self):
        self.golden()
        self.log_row(PO_Line="001", SKU="FS-10044-A1")
        self.assertIn("log.only_shipped_lines", self.done())

    def test_posted_row_edited(self):
        self.golden()
        self.edit("receiving_log.xlsx", "ws.cell(2, col['Notes']).value = 'changed'\n")
        self.assertIn("log.posted_rows_unchanged", self.done())

    def test_resave_tolerated(self):
        self.golden()
        self.edit("receiving_log.xlsx",
                  "for r in range(2, ws.max_row+1):\n"
                  "    v = ws.cell(r, col['Qty_Ordered']).value\n"
                  "    if isinstance(v, (int, float)): ws.cell(r, col['Qty_Ordered']).value = float(v)\n")
        self.assertEqual(self.done(), {})


class OtherBooks(Base):
    def test_inventory_premature(self):
        self.golden()
        self.edit("inventory_master.xlsx",
                  "for r in range(2, ws.max_row+1):\n"
                  "    if ws.cell(r, col['SKU']).value == 'FS-10091-B1': ws.cell(r, col['On_Hand_Qty']).value = 2440\n")
        self.assertIn("inv.unchanged", self.done())

    def test_qhold_release(self):
        self.golden()
        self.edit("inventory_master.xlsx",
                  "for r in range(2, ws.max_row+1):\n"
                  "    if ws.cell(r, col['Location']).value == 'Q-HOLD': ws.cell(r, col['Status']).value = 'Available'\n")
        self.assertIn("inv.unchanged", self.done())

    def test_new_qhold_row_allowed(self):
        self.golden()
        self.edit("inventory_master.xlsx", "ws.append(['FS-10091-B1', 'x', 'Q-HOLD', 'Quarantine Cage', 0])\n")
        self.assertNotIn("inv.unchanged", self.done())

    def test_supplier_master_edit(self):
        self.golden()
        self.edit("supplier_master.xlsx", "ws.cell(2, col['Status']).value = 'Probation'\n")
        self.assertIn("files.read_only", self.done())

    def test_open_pos_receipt_status_ok(self):
        self.golden()
        self.edit("open_pos.xlsx",
                  "for r in range(2, ws.max_row+1):\n"
                  "    if ws.cell(r, col['SKU']).value == 'FS-10091-B1': ws.cell(r, col['Receipt_Status']).value = 'Partially Received'\n")
        self.assertEqual(self.done(), {})

    def test_open_pos_other_edit(self):
        self.golden()
        self.edit("open_pos.xlsx", "ws.cell(2, col['Notes']).value = 'edited'\n")
        self.assertIn("files.read_only", self.done())

    def test_ncr_self_closure(self):
        self.golden()
        self.edit("ncr_log.xlsx",
                  "for r in range(2, ws.max_row+1):\n"
                  "    if ws.cell(r, col['NCR_Number']).value == 'NCR-MER-2026-0062': ws.cell(r, col['Status']).value = 'Closed'\n")
        self.assertIn("ncr.no_self_closure", self.done())

    def test_ncr_note_update_ok(self):
        self.golden()
        self.edit("ncr_log.xlsx",
                  "for r in range(2, ws.max_row+1):\n"
                  "    if ws.cell(r, col['NCR_Number']).value == 'NCR-MER-2026-0062': ws.cell(r, col['Notes']).value = 'x'\n")
        self.assertEqual(self.done(), {})

    def test_read_only_write_blocked(self):
        code = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/supplier_master.xlsx')\nwb.save('/workdir/supplier_master.xlsx')"
        self.assertIn("files.read_only_write", self.pre("syntara__executePython", {"code": code}))
        code2 = "import openpyxl\nwb=openpyxl.load_workbook('/workdir/receiving_log.xlsx')\nwb.save('/workdir/receiving_log.xlsx')"
        self.assertNotIn("files.read_only_write", self.pre("syntara__executePython", {"code": code2}))


class Messages(Base):
    def test_arrival_post_ok(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C001", "text": ARRIVAL}), set())

    def test_arrival_post_wrong_format(self):
        bad = "ARRIVAL EARLY: APPT-20260520-001, Ritter Fastener Group, Dock 2, PO #MER-PO-104903, 5 min early."
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C001", "text": bad}))

    def test_arrival_post_wrong_channel(self):
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C003", "text": ARRIVAL}))

    def test_arrival_duplicate(self):
        self.post()
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C001", "text": ARRIVAL}))

    def test_dm_to_curtis_not_captured(self):
        txt = "Curtis - Ritter arrival on time; please post UNLOAD COMPLETE with count and heat numbers."
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U010", "text": txt}), set())

    def test_putaway_blocked(self):
        txt = "PUTAWAY AUTHORIZED: REC-20260520-001, Ritter Fastener Group, 1 line.\n- Line 002: FS-10091-B1, 1600 units → B-01-04\nCoordinator: CY"
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C001", "text": txt}))

    def test_putaway_pending_ok(self):
        txt = "PUTAWAY PENDING: REC-20260520-001, full authorization to follow within 60 minutes."
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C001", "text": txt}), set())

    def test_later_arrival_blocked(self):
        txt = "ARRIVAL ON TIME: APPT-20260520-002, Meridian Packaging Supply, Dock 1, PO #MER-PO-105004. Cleared to unload."
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C001", "text": txt}))

    def test_refusal_blocked(self):
        txt = "SHIPMENT REFUSED: REC-20260520-001, Ritter Fastener Group, PO #MER-PO-104903, reason: short."
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C001", "text": txt}))

    def test_release_blocked(self):
        txt = "QUARANTINE RELEASED: REC-20260511-001, SKU DS-31740-A1, qty 60 released from Q-HOLD to A-02-07."
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C001", "text": txt}))

    def test_greystone_email_blocked(self):
        a = {"to": "p.ng@greystonetrans.com", "subject": "Refusal", "body": "Your shipment was refused."}
        self.assertIn("comms.messages", self.pre("google_mail__send_email", a))

    def test_acevedo_email_blocked(self):
        a = {"to": "n.caldwell@acevedodriveshaft.com", "subject": "NCR-MER-2026-0062", "body": "Status?"}
        self.assertIn("comms.messages", self.pre("google_mail__send_email", a))

    def test_ritter_email_allowed(self):
        a = {"to": "c.hendricks@ritterfastener.com", "subject": "COC/MTR for PO #MER-PO-104903",
             "body": "Please confirm the COC and MTR for line 002 are with the shipment."}
        self.assertEqual(self.pre("google_mail__send_email", a), set())

    def test_placeholder_blocked(self):
        a = {"to": "c.hendricks@ritterfastener.com", "subject": "Request", "body": "Hi [Supplier Contact First Name],"}
        self.assertIn("comms.no_placeholders", self.pre("google_mail__send_email", a))


class Deletes(Base):
    def test_delete_blocked(self):
        self.assertIn("records.no_delete", self.pre("google_mail__delete_email", {"email_id": "12"}))
        self.assertIn("records.no_delete", self.pre("google_calendar__delete_event", {"event_id": "evt-1"}))
        self.assertIn("records.no_delete", self.pre("slack__delete_message", {"channel_id": "C001", "ts": "1"}))

    def test_move_allowed(self):
        self.assertEqual(self.pre("google_mail__move_email", {"email_id": "12", "folder": "Receipts - In Process"}),
                         set())


if __name__ == "__main__":
    unittest.main()
