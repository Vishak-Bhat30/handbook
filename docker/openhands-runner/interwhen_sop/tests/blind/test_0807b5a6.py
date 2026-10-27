"""Blind unit tests for logistics_gear_sytems_inc_0807b5a6 (fixtures from the task environment seed only)."""

from __future__ import annotations

import json

from interwhen_sop.tests.base import REPO, TaskCase

TASK = "logistics_gear_sytems_inc_0807b5a6"
FG, REC1 = "FG-91144-A1", "REC-20260414-001"
NOTE = ("Partial release 04/23/2026: FG-91144-A1 released (200 units to A-09-01). Remaining on Q-HOLD: "
        "AX-04827-B2 (44 units), AX-05512-C1 (96 units).")
POST = ("QUARANTINE RELEASED: REC-20260414-001, SKU FG-91144-A1, qty 200 released from Q-HOLD to A-09-01. "
        "Authorization: Theo Brandt, 04/23/2026. Dock Crew: please move when convenient.")
INITIAL = {"gear.fg_inventory", "gear.fg_receiving_log", "gear.release_record", "gear.comms.messages_sent",
           "gear.partial_release_note"}

INV_RELEASE = """
for r in range(ws.max_row, 1, -1):
    sku = ws.cell(r, col['SKU']).value; loc = ws.cell(r, col['Location']).value
    if sku == 'FG-91144-A1' and loc == 'Q-HOLD' and DELETE_QHOLD:
        ws.delete_rows(r)
for r in range(2, ws.max_row + 1):
    if ws.cell(r, col['SKU']).value == 'FG-91144-A1' and ws.cell(r, col['Location']).value == 'A-09-01':
        ws.cell(r, col['On_Hand_Qty']).value = ONHAND
        ws.cell(r, col['Quarantine_Qty']).value = 0
        ws.cell(r, col['Quarantine_Reason']).value = None
        ws.cell(r, col['Last_Receipt_Date']).value = '04/14/2026'
        ws.cell(r, col['Last_Receipt_ID']).value = 'REC-20260414-001'
        ws.cell(r, col['Heat_Numbers_On_Hand']).value = HEAT
"""

RCV_RELEASE = """
for r in range(2, ws.max_row + 1):
    if ws.cell(r, col['Receipt_ID']).value == 'REC-20260414-001' and ws.cell(r, col['SKU']).value == 'FG-91144-A1':
        ws.cell(r, col['Status']).value = STATUS
        ws.cell(r, col['Disposition']).value = 'ACCEPTED'
        ws.cell(r, col['Documentation_Status']).value = 'COC Received and Verified'
        ws.cell(r, col['Documentation_Action']).value = 'Accepted'
        ws.cell(r, col['Putaway_Auth_Time']).value = '04/23/2026 09:30 CST'
        ws.cell(r, col['Putaway_Location']).value = 'A-09-01'
"""


def seed_event(eid: str) -> dict:
    data = json.loads((REPO / "tasks" / TASK / "environment" / "initial_external_services" / "google_calendar" /
                       "calendar_data.json").read_text())
    evs = data["events"]
    evs = evs.values() if isinstance(evs, dict) else evs
    return next(e for e in evs if e["id"] == eid)


class Gear0807(TaskCase):
    TASK = TASK

    # ---- helpers ----
    def release_inventory(self, delete_qhold=True, onhand=285, heat="HT-2026-0218, HT-2026-1803"):
        self.edit("inventory_master.xlsx", f"DELETE_QHOLD={delete_qhold!r}\nONHAND={onhand!r}\nHEAT={heat!r}\n"
                  + INV_RELEASE)

    def release_rcv(self, status="Putaway Complete"):
        self.edit("receiving_log.xlsx", f"STATUS={status!r}\n" + RCV_RELEASE)

    def post(self, text=POST, channel="C002"):
        self.did("slack__post_message", {"channel_id": channel, "text": text})

    def cal_note(self, eid="evt-012"):
        self.did("google_calendar__update_event",
                 {"event_id": eid, "description": seed_event(eid)["description"] + "\n" + NOTE})

    def golden(self, skip=()):
        if "inv" not in skip:
            self.release_inventory()
        if "rcv" not in skip:
            self.release_rcv()
        if "file" not in skip:
            self.write("quarantine_releases/REC-20260414-001_release.pdf", b"%PDF-1.4 release email 0041")
        if "post" not in skip:
            self.post()
        if "cal" not in skip:
            self.cal_note()

    # ---- initial state / golden path ----
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), INITIAL)

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})

    def test_resave_without_changes_is_clean(self):
        for f in ("inventory_master.xlsx", "receiving_log.xlsx", "ncr_log.xlsx", "open_pos.xlsx",
                  "supplier_master.xlsx", "dock_schedule.xlsx"):
            self.edit(f, "pass")
        self.assertEqual(set(self.done()), INITIAL)

    # ---- gear.fg_inventory ----
    def test_fg_inventory_qhold_row_must_be_deleted(self):
        self.golden(skip=("inv",))
        self.release_inventory(delete_qhold=False)
        self.assertIn("Q-HOLD row", self.done().get("gear.fg_inventory", ""))

    def test_fg_inventory_heat_overwritten(self):
        self.golden(skip=("inv",))
        self.release_inventory(heat="HT-2026-1803")
        self.assertIn("HT-2026-0218", self.done().get("gear.fg_inventory", ""))

    def test_fg_inventory_wrong_qty(self):
        self.golden(skip=("inv",))
        self.release_inventory(onhand=200)
        self.assertIn("285", self.done().get("gear.fg_inventory", ""))

    # ---- gear.fg_receiving_log ----
    def test_receiving_log_status(self):
        self.golden(skip=("rcv",))
        self.release_rcv(status="Posted")
        self.assertIn("Putaway Complete", self.done().get("gear.fg_receiving_log", ""))

    # ---- gear.release_record ----
    def test_release_record_missing(self):
        self.golden(skip=("file",))
        self.assertEqual(set(self.done()), {"gear.release_record"})

    # ---- gear.comms ----
    def test_release_post_ok(self):
        self.assertNotIn("gear.comms.messages", self.pre("slack__post_message", {"channel_id": "C002", "text": POST}))

    def test_release_post_wrong_channel(self):
        self.assertIn("gear.comms.messages", self.pre("slack__post_message", {"channel_id": "C003", "text": POST}))

    def test_release_post_missing_authorization(self):
        bad = POST.replace("Authorization: Theo Brandt, 04/23/2026. ", "")
        self.assertIn("gear.comms.messages", self.pre("slack__post_message", {"channel_id": "C002", "text": bad}))

    def test_release_post_required(self):
        self.golden(skip=("post",))
        self.assertEqual(set(self.done()), {"gear.comms.messages_sent"})

    def test_bg_release_post_blocked(self):
        txt = ("QUARANTINE RELEASED: REC-20260414-002, SKU BG-33044-A1, qty 144 released from Q-HOLD to B-02-08. "
               "Authorization: Darnell Hooks, 04/23/2026.")
        self.assertIn("gear.comms.messages", self.pre("slack__post_message", {"channel_id": "C002", "text": txt}))

    def test_ax_release_post_blocked(self):
        txt = POST.replace("SKU FG-91144-A1, qty 200", "SKU AX-04827-B2, qty 44")
        self.assertIn("gear.comms.messages", self.pre("slack__post_message", {"channel_id": "C002", "text": txt}))

    def test_unrelated_post_allowed(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C002", "text": "Morning all - dock 1 clear."}),
                         set())

    def test_placeholder_blocked(self):
        txt = POST.replace("A-09-01", "[Location]")
        self.assertIn("comms.no_placeholders", self.pre("slack__post_message", {"channel_id": "C002", "text": txt}))

    # ---- gear.calendar_guard / gear.partial_release_note ----
    def test_calendar_note_ok(self):
        args = {"event_id": "evt-012", "description": seed_event("evt-012")["description"] + "\n" + NOTE}
        self.assertEqual(self.pre("google_calendar__update_event", args), set())

    def test_calendar_overwrite_blocked(self):
        self.assertIn("gear.calendar_guard",
                      self.pre("google_calendar__update_event", {"event_id": "evt-012", "description": NOTE}))

    def test_calendar_delete_blocked(self):
        self.assertIn("gear.calendar_guard", self.pre("google_calendar__delete_event", {"event_id": "evt-012"}))

    def test_calendar_completed_blocked(self):
        self.assertIn("gear.calendar_guard", self.pre("google_calendar__update_event",
                                                      {"event_id": "evt-016", "summary": "[COMPLETED] NCR Issued"}))

    def test_calendar_unrelated_event_allowed(self):
        self.assertEqual(self.pre("google_calendar__delete_event", {"event_id": "evt-038"}), set())

    def test_partial_release_note_required(self):
        self.golden(skip=("cal",))
        self.assertEqual(set(self.done()), {"gear.partial_release_note"})

    def test_partial_release_note_incomplete(self):
        self.golden(skip=("cal",))
        self.did("google_calendar__update_event",
                 {"event_id": "evt-012", "description": seed_event("evt-012")["description"] +
                  "\nPartial release 04/23/2026: FG-91144-A1 released (200 units to A-09-01)."})
        self.assertIn("gear.partial_release_note", self.done())

    # ---- gear.no_unauthorized_release ----
    def test_bg_release_flagged(self):
        self.golden()
        self.edit("inventory_master.xlsx", """
for r in range(ws.max_row, 1, -1):
    if ws.cell(r, col['SKU']).value == 'BG-33044-A1' and ws.cell(r, col['Location']).value == 'Q-HOLD':
        ws.delete_rows(r)
""")
        self.assertIn("BG-33044-A1", self.done().get("gear.no_unauthorized_release", ""))

    def test_ax_receiving_rows_flagged(self):
        self.golden()
        self.edit("receiving_log.xlsx", """
for r in range(2, ws.max_row + 1):
    if ws.cell(r, col['SKU']).value == 'AX-04827-B2':
        ws.cell(r, col['Status']).value = 'Putaway Complete'
""")
        self.assertIn("gear.no_unauthorized_release", self.done())

    # ---- gear.ncr_not_closed ----
    def test_ncr_closed_flagged(self):
        self.golden()
        self.edit("ncr_log.xlsx", """
for r in range(2, ws.max_row + 1):
    if ws.cell(r, col['NCR_Number']).value == 'NCR-MER-2026-0247':
        ws.cell(r, col['Status']).value = 'Resolved'
""")
        self.assertEqual(set(self.done()), {"gear.ncr_not_closed"})

    def test_ncr_note_allowed(self):
        self.golden()
        self.edit("ncr_log.xlsx", """
for r in range(2, ws.max_row + 1):
    if ws.cell(r, col['NCR_Number']).value == 'NCR-MER-2026-0247':
        ws.cell(r, col['Resolution_Notes']).value = 'Partial release 04/23/2026: FG-91144-A1 released.'
""")
        self.assertEqual(self.done(), {})

    # ---- gear.readonly_books / gear.supplier_master_readonly ----
    def test_open_pos_change_flagged(self):
        self.golden()
        self.edit("open_pos.xlsx", "ws.cell(4, col['PO_Status']).value = 'Closed'")
        self.assertEqual(set(self.done()), {"gear.readonly_books"})

    def test_supplier_master_write_blocked(self):
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/supplier_master.xlsx')\n"
                "wb.active['C2']='Probation'\nwb.save('/workdir/supplier_master.xlsx')")
        self.assertIn("gear.supplier_master_readonly", self.pre("syntara__executePython", {"code": code}))

    def test_supplier_master_read_allowed(self):
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/supplier_master.xlsx')\n"
                "print(list(wb.active.values))")
        self.assertEqual(self.pre("syntara__executePython", {"code": code}), set())

    # ---- gear.no_unrequested_rows ----
    def test_new_inventory_row_flagged(self):
        self.golden()
        self.edit("inventory_master.xlsx", "ws.append(['FG-91144-A1', 'Forged Gear Blank', 'Y', 'FG', 'Zone A', "
                                           "'A-09-03', 0])")
        self.assertIn("gear.no_unrequested_rows", self.done())

    def test_new_receiving_row_flagged(self):
        self.golden()
        self.edit("receiving_log.xlsx", "ws.append(['REC-20260414-001-C1', '04/23/2026 09:30 CST'])")
        self.assertIn("gear.no_unrequested_rows", self.done())

    def test_unrelated_inventory_edit_flagged(self):
        self.golden()
        self.edit("inventory_master.xlsx", """
for r in range(2, ws.max_row + 1):
    if ws.cell(r, col['SKU']).value == 'TR-67801-D1':
        ws.cell(r, col['On_Hand_Qty']).value = 24
""")
        self.assertEqual(set(self.done()), {"gear.no_unrequested_rows"})

    # ---- gear.no_delete ----
    def test_email_delete_blocked(self):
        self.assertIn("gear.no_delete", self.pre("google_mail__delete_email", {"email_id": "0042"}))

    def test_slack_delete_blocked(self):
        self.assertIn("gear.no_delete", self.pre("slack__delete_message", {"channel_id": "C002", "ts": "1.0"}))

    def test_workbook_file_delete_blocked(self):
        self.assertIn("gear.no_delete", self.pre("syntara__executeBash", {"command": "rm /workdir/ncr_log.xlsx"}))

    def test_temp_file_delete_allowed(self):
        self.assertEqual(self.pre("syntara__executeBash", {"command": "rm /tmp/release_note.txt"}), set())

    def test_release_write_with_delete_rows_allowed(self):
        code = ("import openpyxl\np='/workdir/inventory_master.xlsx'\nwb=openpyxl.load_workbook(p)\nws=wb.active\n"
                "ws.delete_rows(21)\nwb.save(p)")
        self.assertEqual(self.pre("syntara__executePython", {"code": code}), set())
