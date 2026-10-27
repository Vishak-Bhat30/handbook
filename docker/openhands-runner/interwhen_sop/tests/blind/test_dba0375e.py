"""Blind unit tests for logistics_gear_sytems_inc_dba0375e (fixtures from environment seed only)."""

from __future__ import annotations

from interwhen_sop.tests.base import TaskCase

REC = "REC-20261124-003"
T18_DM = ("Hi Maribel,\nA new SKU was received today that does not have an existing entry in inventory_master.xlsx. "
          "Please create the master record so I can complete the receipt.\nReceipt details:\n"
          "- Receipt ID: REC-20261124-003\n- PO Number: MER-PO-204871\n- Supplier: Vantage Lubricants Inc.\n"
          "- SKU: FL-08814-A1\n- SKU description (per packing slip): Gear oil, ISO VG 220, 20L drum\n"
          "- Quantity received: 24\n- Safety-Critical: N\n- Suggested location: C-RCV-01\n"
          "Material is currently held in the receiving area pending master record creation. Please confirm when the "
          "row has been added.\nThanks,\nJR")
PUTAWAY = ("PUTAWAY AUTHORIZED: REC-20261124-003, Vantage Lubricants Inc., 1 lines.\n"
           "- Line 001: FL-08814-A1, 24 units → C-RCV-01\nCoordinator: JR")
GOLDEN = {"Qty_Received": 24, "Variance_Units": 0, "Variance_Pct": 0.0, "Variance_Band": "Exact",
          "Quantity_Action": "Accepted", "Condition_Tier": "Tier 0", "Condition_Action": "Accepted",
          "Photos_Folder": "N/A", "Documentation_Status": "Verified", "Documentation_Action": "Accepted",
          "Disposition": "ACCEPTED CLEAN", "Disposition_Timestamp": "11/24/2026 14:21 CST",
          "Notes": "Supplier status: Approved as of 03/14/2024. Actioned per SOP protocol.", "Status": "Posted"}


def _set(values: dict, row: int = 5) -> str:
    return "\n".join(f"ws.cell({row}, col[{k!r}]).value = {v!r}" for k, v in values.items())


class Base(TaskCase):
    TASK = "logistics_gear_sytems_inc_dba0375e"

    def golden_log(self, **over):
        self.edit("receiving_log.xlsx", _set({**GOLDEN, **over}))

    def golden_msgs(self):
        self.did("slack__send_dm", {"user_id": "U008", "text": T18_DM})
        self.did("slack__post_message", {"channel_id": "C001", "text": PUTAWAY})


class TestGolden(Base):
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {"comms.messages_sent", "receipt003.new_sku_request", "receipt003.quantity",
                                            "receipt003.condition", "receipt003.documentation",
                                            "receipt003.disposition", "receipt003.posted"})

    def test_golden_path(self):
        self.golden_log()
        self.golden_msgs()
        self.assertEqual(self.done(), {})

    def test_golden_with_allowed_extras(self):
        # open_pos Receipt_Status and dock Status/departure may change; number formats may differ
        self.golden_log(Variance_Pct="0.0%", Qty_Ordered=24.0)
        self.edit("open_pos.xlsx", "ws.cell(5, col['Receipt_Status']).value = 'Received'")
        self.edit("dock_schedule.xlsx", "ws.cell(5, col['Status']).value = 'Complete'")
        self.golden_msgs()
        self.assertEqual(self.done(), {})


class TestMessages(Base):
    def test_t18_dm_ok(self):
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U008", "text": T18_DM}), set())

    def test_t18_dm_missing_fields(self):
        self.assertIn("comms.messages", self.pre("slack__send_dm", {
            "user_id": "U008", "text": "Hi Maribel, new SKU FL-08814-A1 arrived, please set it up."}))

    def test_t18_email_subject(self):
        body = T18_DM
        ok = {"to": "maribel.ortiz@gearsystems.com", "body": body,
              "subject": "New SKU Setup Request — REC-20261124-003 — FL-08814-A1"}
        self.assertEqual(self.pre("google_mail__send_email", ok), set())
        bad = dict(ok, subject="New SKU FL-08814-A1")
        self.assertIn("comms.messages", self.pre("google_mail__send_email", bad))

    def test_t18_completion_by_email(self):
        self.did("google_mail__send_email", {"to": "maribel.ortiz@gearsystems.com", "body": T18_DM,
                                             "subject": "New SKU Setup Request — REC-20261124-003 — FL-08814-A1"})
        self.assertNotIn("receipt003.new_sku_request", self.done())

    def test_t18_completion(self):
        self.assertIn("receipt003.new_sku_request", self.done())
        self.did("slack__send_dm", {"user_id": "U008", "text": T18_DM})
        self.assertNotIn("receipt003.new_sku_request", self.done())

    def test_putaway_ok_and_pending(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C001", "text": PUTAWAY}), set())
        pend = f"PUTAWAY PENDING: {REC}, full authorization to follow within 10 minutes."
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C001", "text": pend}), set())

    def test_putaway_wrong_channel_or_qhold(self):
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C004", "text": PUTAWAY}))
        qh = PUTAWAY.replace("C-RCV-01", "Q-HOLD")
        self.assertIn("comms.messages", self.pre("slack__post_message", {"channel_id": "C001", "text": qh}))

    def test_putaway_completion(self):
        self.assertIn("comms.messages_sent", self.done())
        self.did("slack__post_message", {"channel_id": "C001", "text": PUTAWAY})
        self.assertNotIn("comms.messages_sent", self.done())

    def test_placeholders(self):
        txt = T18_DM.replace("JR", "[Coordinator Initials]")
        self.assertIn("comms.no_placeholders", self.pre("slack__send_dm", {"user_id": "U008", "text": txt}))


class TestPreRules(Base):
    def test_no_escalation(self):
        post = {"channel_id": "C003", "text": f"ESCALATION: {REC} gear oil received"}
        self.assertIn("receipt003.no_escalation", self.pre("slack__post_message", post))
        dm = {"user_id": "U003", "text": f"FYI {REC} accepted clean"}
        self.assertIn("receipt003.no_escalation", self.pre("slack__send_dm", dm))
        unsure = {"user_id": "U002", "text": f"Uncertainty escalation — {REC}, Vantage, MER-PO-204871. New SKU."}
        self.assertEqual(self.pre("slack__send_dm", unsure), set())

    def test_no_ncr(self):
        m = {"to": "s.muth@vantagelube.com", "subject": "NCR-MER-2026-0001 | Minor | Vantage | MER-PO-204871",
             "body": "Nonconformance Report for MER-PO-204871"}
        self.assertIn("receipt003.no_ncr", self.pre("google_mail__send_email", m))
        ok = {"to": "joonho.park@gearsystems.com", "subject": "Gear oil received", "body": "MER-PO-204871 received."}
        self.assertNotIn("receipt003.no_ncr", self.pre("google_mail__send_email", ok))

    def test_no_delete(self):
        self.assertIn("records.no_delete", self.pre("google_mail__delete_email", {"email_id": "1"}))
        self.assertIn("records.no_delete", self.pre("syntara__executeBash", {"command": "rm /workdir/receiving_log.xlsx"}))
        self.assertNotIn("records.no_delete", self.pre("syntara__executeBash", {"command": "rm /tmp/scratch.txt"}))
        code = ("import openpyxl\np='/workdir/receiving_log.xlsx'\nwb=openpyxl.load_workbook(p)\n"
                "wb.active.delete_rows(3)\nwb.save(p)\n")
        self.assertIn("records.no_delete", self.pre("syntara__executePython", {"code": code}))

    def test_no_supplier_promise(self):
        m = {"to": "b.kowalski@vantagelube.com", "subject": "PO MER-PO-204871",
             "body": "Thanks - we will issue a credit for the delay."}
        self.assertIn("comms.no_supplier_promise", self.pre("google_mail__send_email", m))
        ok = dict(m, body="Thanks, the shipment was received.")
        self.assertNotIn("comms.no_supplier_promise", self.pre("google_mail__send_email", ok))

    def test_inventory_write_blocked(self):
        code = ("import openpyxl\np='/workdir/inventory_master.xlsx'\nwb=openpyxl.load_workbook(p)\n"
                "wb.active.append(['FL-08814-A1','C-RCV-01',24,'AVAILABLE'])\nwb.save(p)\n")
        self.assertIn("inventory.no_new_sku_row", self.pre("syntara__executePython", {"code": code}))
        log = ("import openpyxl\np='/workdir/receiving_log.xlsx'\nwb=openpyxl.load_workbook(p)\n"
               "wb.active['M5']=24\nwb.save(p)\n")
        self.assertEqual(self.pre("syntara__executePython", {"code": log}), set())

    def test_supplier_master_readonly(self):
        code = ("import openpyxl\np='/workdir/supplier_master.xlsx'\nwb=openpyxl.load_workbook(p)\n"
                "wb.active['M3']=48\nwb.save(p)\n")
        self.assertIn("supplier_master.readonly", self.pre("syntara__executePython", {"code": code}))


class TestStateRules(Base):
    def test_quantity_wrong(self):
        self.golden_log(Variance_Band="Band 1")
        self.golden_msgs()
        self.assertEqual(set(self.done()), {"receipt003.quantity"})

    def test_condition_wrong(self):
        self.golden_log(Photos_Folder=None)
        self.golden_msgs()
        self.assertEqual(set(self.done()), {"receipt003.condition"})

    def test_documentation_wrong(self):
        self.golden_log(Documentation_Status="Missing - packing slip requested")
        self.golden_msgs()
        self.assertEqual(set(self.done()), {"receipt003.documentation"})

    def test_disposition_timestamp_wrong(self):
        self.golden_log(Disposition_Timestamp="11/24/2026 14:35 CST")
        self.golden_msgs()
        self.assertEqual(set(self.done()), {"receipt003.disposition"})

    def test_ncr_number_not_allowed(self):
        self.golden_log(NCR_Number="NCR-MER-2026-0001")
        self.golden_msgs()
        self.assertEqual(set(self.done()), {"receipt003.disposition"})

    def test_identity_changed(self):
        self.golden_log(SKU="FL-08814-A0")
        self.golden_msgs()
        self.assertEqual(set(self.done()), {"receipt003.identity"})

    def test_posted_notes_and_status(self):
        self.golden_log(Notes="Actioned per SOP protocol", Status="OPEN — handoff")
        self.golden_msgs()
        probs = [p for r, p in self.done_all() if r == "receipt003.posted"]
        self.assertEqual(len(probs), 2)
        self.assertEqual(set(self.done()), {"receipt003.posted"})

    def test_inventory_changed(self):
        self.golden_log()
        self.golden_msgs()
        self.edit("inventory_master.xlsx", "ws.append(['FL-08814-A1','C-RCV-01',24,'AVAILABLE'])")
        self.assertEqual(set(self.done()), {"inventory.unchanged"})

    def test_inventory_a0_row_changed(self):
        self.golden_log()
        self.golden_msgs()
        self.edit("inventory_master.xlsx", "ws['C67'] = 24")
        self.assertEqual(set(self.done()), {"inventory.unchanged"})

    def test_open_pos_other_column(self):
        self.golden_log()
        self.golden_msgs()
        self.edit("open_pos.xlsx", "ws.cell(5, col['Notes']).value = 'received'")
        self.assertEqual(set(self.done()), {"open_pos.readonly"})

    def test_dock_hazmat_row_changed(self):
        self.golden_log()
        self.golden_msgs()
        self.edit("dock_schedule.xlsx", "ws.cell(3, col['Status']).value = 'Complete'")
        self.assertEqual(set(self.done()), {"dock_schedule.unchanged"})

    def test_other_receipt_rows(self):
        self.golden_log()
        self.golden_msgs()
        self.edit("receiving_log.xlsx", "ws.cell(3, col['Status']).value = 'Posted'")
        self.assertEqual(set(self.done()), {"receiving_log.no_unrequested_writes"})

    def test_extra_row(self):
        self.golden_log()
        self.golden_msgs()
        self.edit("receiving_log.xlsx", "ws.append(['REC-20261124-003-C1','MER-PO-204871','001','FL-08814-A1'])")
        self.assertEqual(set(self.done()), {"receiving_log.no_unrequested_writes"})

    def test_added_column_tolerated(self):
        self.golden_log()
        self.golden_msgs()
        self.edit("receiving_log.xlsx", "ws.cell(1, 32).value = 'Putaway_Authorized_Timestamp'\n"
                                        "ws.cell(5, 32).value = '11/24/2026 14:21 CST'")
        self.assertEqual(self.done(), {})
