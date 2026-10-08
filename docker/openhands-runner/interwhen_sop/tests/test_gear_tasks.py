"""Golden-path and key-violation scenarios for the four newer Gear tasks.

Fixtures come only from each task's environment seed (workbooks, Slack, mail); never from tests/rubrics.

    INTERWHEN_XLSX_PYTHON=<python with openpyxl> python3 -m unittest interwhen_sop.tests.test_gear_tasks -v
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(os.environ.get("INTERWHEN_REPO", Path(__file__).resolve().parents[4]))
XLSX_PY = os.environ.get("INTERWHEN_XLSX_PYTHON", "python3")


class GearCase(unittest.TestCase):
    TASK = ""

    def setUp(self):
        self._env = dict(os.environ)
        env = REPO / "tasks" / self.TASK / "environment"
        self.tmp = Path(tempfile.mkdtemp(prefix="iw-gear-"))
        shutil.copytree(env / "initial_workspace", self.tmp / "workdir")
        os.environ.update({"INTERWHEN_TASK": self.TASK, "INTERWHEN_STATE_DIR": str(self.tmp / "state"),
                           "INTERWHEN_WORKDIR": str(self.tmp / "workdir"),
                           "INTERWHEN_INITIAL_DATA": str(env / "initial_external_services"),
                           "INTERWHEN_SLM_URL": "http://127.0.0.1:9/v1"})
        from interwhen_sop import sop_generic, sopdata, workbooks
        sopdata.load.cache_clear()
        sop_generic._CACHE.clear()
        self.assertTrue(workbooks.snapshot())
        self.records: list[dict] = []
        self.n = 0

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self._env)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def did(self, tool: str, args: dict, result: str = '{"ok": true}') -> None:
        self.n += 1
        cid = f"c{self.n}"
        self.records += [{"type": "action", "call_id": cid, "tool": tool, "args": args},
                         {"type": "observation", "call_id": cid, "tool": tool, "text": result}]

    def _run(self, stage, tool=None, args=None):
        from interwhen_sop import framework, sopdata, state
        from interwhen_sop.actions import classify
        ctx = framework.Context(sopdata.load(), state.build(self.records), [])
        rules = framework.load_rules(self.TASK)
        findings, errors = (framework.run(rules, "pre", ctx, classify(tool, args)) if stage == "pre"
                            else framework.run(rules, "completion", ctx))
        self.assertEqual(errors, [])
        return findings

    def pre(self, tool, args):
        return {f.rule for f in self._run("pre", tool, args)}

    def done(self):
        return {f.rule: f.problem for f in self._run("completion")}

    def edit(self, fname: str, code: str) -> None:
        """Apply an openpyxl edit to a workspace workbook (ws, hdr/col available)."""
        script = (f"import openpyxl\np='{self.tmp / 'workdir' / fname}'\nwb=openpyxl.load_workbook(p)\nws=wb.active\n"
                  "hdr=[c.value for c in ws[1]]\ncol={h:i+1 for i,h in enumerate(hdr)}\n" + code + "\nwb.save(p)\n")
        subprocess.run([XLSX_PY, "-c", script], check=True)


class Release0807(GearCase):
    TASK = "logistics_gear_sytems_inc_0807b5a6"
    POST = ("QUARANTINE RELEASED: REC-20260414-001, SKU FG-91144-A1, qty 200 released from Q-HOLD to A-09-01. "
            "Authorization: Theo Brandt, 04/23/2026. Dock Crew: please move when convenient.")

    def test_unauthorized_release_blocked(self):
        self.assertIn("release.requires_authorization", self.pre("syntara__executePython", {
            "code": "# release BG-33044-A1 from Q-HOLD\nwb.save('/workdir/inventory_master.xlsx')"}))

    def test_golden_path(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C002", "text": self.POST}), set())
        self.edit("inventory_master.xlsx", """
for r in range(ws.max_row, 1, -1):
    if ws.cell(r, col['SKU']).value == 'FG-91144-A1' and ws.cell(r, col['Location']).value == 'Q-HOLD': ws.delete_rows(r)
for r in range(2, ws.max_row+1):
    if ws.cell(r, col['SKU']).value == 'FG-91144-A1':
        ws.cell(r, col['On_Hand_Qty']).value = 285; ws.cell(r, col['Quarantine_Qty']).value = 0
        ws.cell(r, col['Quarantine_Reason']).value = None; ws.cell(r, col['Last_Receipt_ID']).value = 'REC-20260414-001'
        ws.cell(r, col['Heat_Numbers_On_Hand']).value = 'HT-2026-0218, HT-2026-1803'""")
        self.edit("receiving_log.xlsx", """
for r in range(2, ws.max_row+1):
    if ws.cell(r, col['Receipt_ID']).value == 'REC-20260414-001' and ws.cell(r, col['SKU']).value == 'FG-91144-A1':
        for k, v in dict(Putaway_Auth_Time='04/23/2026 09:20 CST', Putaway_Location='A-09-01', Status='Putaway Complete',
                         Documentation_Status='COC Received and Verified', Documentation_Action='Accepted',
                         Disposition='ACCEPTED').items(): ws.cell(r, col[k]).value = v""")
        (self.tmp / "workdir" / "quarantine_releases").mkdir()
        (self.tmp / "workdir" / "quarantine_releases" / "REC-20260414-001_release.pdf").write_text("x")
        self.did("slack__post_message", {"channel_id": "C002", "text": self.POST})
        self.did("google_calendar__update_event", {"event_id": "evt-012", "description": (
            "Partial release 04/23/2026: FG-91144-A1 released (200 units to A-09-01). Remaining on Q-HOLD: "
            "AX-04827-B2 (44 units), AX-05512-C1 (96 units).")})
        self.assertEqual(self.done(), {})


class Standard_dba(GearCase):
    TASK = "logistics_gear_sytems_inc_dba0375e"
    T18 = ("New SKU Setup Request — REC-20261124-003 — FL-08814-A1\n- Receipt ID: REC-20261124-003\n- PO Number: "
           "MER-PO-204871\n- Supplier: Vantage Lubricants Inc.\n- SKU: FL-08814-A1\n- Quantity received: 24\n"
           "- Safety-Critical: N")

    def test_hazmat_left_alone(self):
        self.assertIn("instruction.leave_hazmat_receipts", self.pre("slack__post_message", {
            "channel_id": "C001", "text": "HAZMAT RECEIPT: REC-20261124-001"}))

    def test_golden_path(self):
        self.did("syntara__executePython", {"code": "print(open('/workdir/supplier_master.xlsx','rb').read()[:1])"})
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U008", "text": self.T18}), set())
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C001", "text": (
            "PUTAWAY AUTHORIZED: REC-20261124-003, Vantage Lubricants Inc., 1 line.\n"
            "- Line 001: FL-08814-A1, 24 units → C-RCV-01\nCoordinator: JR")}), set())
        self.edit("receiving_log.xlsx", """
vals = dict(Qty_Received=24, Variance_Units=0, Variance_Pct='0.0%', Variance_Band='Exact', Quantity_Action='Accepted',
            Condition_Tier='Tier 0', Condition_Action='Accepted', Photos_Folder='N/A', Documentation_Status='Verified',
            Documentation_Action='Accepted', Disposition='ACCEPTED CLEAN', Disposition_Timestamp='11/24/2026 14:21 CST',
            Notes='Actioned per SOP protocol', Status='Posted')
for r in range(2, ws.max_row+1):
    if ws.cell(r, 1).value == 'REC-20261124-003':
        for k, v in vals.items(): ws.cell(r, col[k]).value = v""")
        self.did("slack__send_dm", {"user_id": "U008", "text": self.T18})
        self.assertEqual(self.done(), {})

    def test_wrong_variance_pct_flagged(self):
        self.edit("receiving_log.xlsx", """
vals = dict(Qty_Received=24, Variance_Units=0, Variance_Pct='0.0%', Variance_Band='Band 1', Quantity_Action='Accepted',
            Condition_Tier='Tier 0', Condition_Action='Accepted', Photos_Folder='N/A', Documentation_Status='Verified',
            Documentation_Action='Accepted', Disposition='ACCEPTED CLEAN', Disposition_Timestamp='11/24/2026 14:21 CST',
            Notes='Actioned per SOP protocol', Status='Posted')
for r in range(2, ws.max_row+1):
    if ws.cell(r, 1).value == 'REC-20261124-003':
        for k, v in vals.items(): ws.cell(r, col[k]).value = v""")
        self.assertIn("generic.records", self.done())


class Hazmat_ad2ff(GearCase):
    TASK = "logistics_gear_sytems_inc_ad2ff597"
    HOLD = ("TRUCK HOLD: REC-20260312-001, Redstone Alloy Fabricators, Inc., PO #MER-PO-103517. Driver on truck — "
            "hazmat documentation incomplete. Do not unload.")
    DM = ("Hazmat documentation issue — REC-20260312-001, Redstone Alloy Fabricators, Inc., PO #MER-PO-103517. "
          "Missing: SDS for FL-20044-A3. Truck holding. Awaiting guidance.")
    XS = ("Cross-shift receiving correction request — receiving_log.xlsx: REC-20260309-004. SKU = FL-20044-A3. "
          "Correct value should be FL-21300-A1.")
    MD = ("Missing document — REC-20260310-001, PO #MER-PO-103516. Referenced document(s) not found in workspace: "
          "COC. PO closed 03/10/2026.")

    def test_unload_blocked_and_ncr_held(self):
        self.assertIn("hazmat.no_unload_without_docs", self.pre("slack__post_message", {
            "channel_id": "C001", "text": "HAZMAT RECEIPT: REC-20260312-001, Redstone Alloy Fabricators, Inc., "
                                          "FL-20044-A3. SDS and manifest verified, on file. Cleared to unload."}))
        self.assertIn("instruction.hold_ncr", self.pre("google_mail__send_email", {
            "to": "quality@redstonefab.com", "subject": "NCR-MER-2026-0040 | Major", "body": "x"}))

    def test_golden_path(self):
        for tool, args in (("slack__post_message", {"channel_id": "C001", "text": self.HOLD}),
                           ("slack__send_mpim", {"user_ids": ["U002", "U010"], "text": self.DM}),
                           ("slack__send_dm", {"user_id": "U007", "text": self.XS}),
                           ("slack__send_dm", {"user_id": "U007", "text": self.MD})):
            self.assertEqual(self.pre(tool, args), set(), args["text"])
            self.did(tool, args)
        self.assertEqual(self.done(), {})

    def test_misformatted_hold_post_blocked(self):
        self.assertTrue(self.pre("slack__post_message", {"channel_id": "C001", "text": "TRUCK HOLD: REC-20260312-001 — "
                                                         "waiting on SDS."}))


class Arrivals_502e(GearCase):
    TASK = "logistics_gear_sytems_inc_502e8c5e"
    SLIP = ("Ritter Fastener Group PACKING SLIP\nPO Number: MER-PO-104903\n"
            "002 FS-10091-B1 Hub Stud, 9/16-18 UNF, torque-spec, Rev B1 1,800 1,600 units\n")
    POST = "ARRIVAL ON TIME: APPT-20260520-001, Ritter Fastener Group, Dock 2, PO #MER-PO-104903. Cleared to unload."

    def test_pending_truck_and_counts_blocked(self):
        self.did("syntara__readPDF", {"file_path": "/workdir/MER-PO-104903_packingslip_2.pdf"}, self.SLIP)
        self.assertIn("arrivals.only_checked_in", self.pre("syntara__executePython", {
            "code": "ws.append(['REC-20260520-002','MER-PO-105004'])\nwb.save('/workdir/receiving_log.xlsx')"}))
        self.assertIn("quantity.no_estimated_counts", self.pre("syntara__executePython", {
            "code": "row['Qty_Received'] = 1600\nwb.save('/workdir/receiving_log.xlsx')"}))

    def test_golden_path(self):
        self.did("syntara__readPDF", {"file_path": "/workdir/MER-PO-104903_packingslip_2.pdf"}, self.SLIP)
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C001", "text": self.POST}), set())
        self.edit("dock_schedule.xlsx", """
for r in range(2, ws.max_row+1):
    if ws.cell(r, 1).value == 'APPT-20260520-001':
        ws.cell(r, col['Actual_Arrival_Time']).value = '07:02'; ws.cell(r, col['Status']).value = 'Arrived'""")
        self.edit("receiving_log.xlsx", """
row = dict(Receipt_ID='REC-20260520-001', PO_Number='MER-PO-104903', PO_Line='002', SKU='FS-10091-B1',
           Safety_Critical='Y', Supplier_ID='SUP-0155', Carrier_Name='XPO Logistics',
           Arrival_Timestamp='05/20/2026 07:02 CST', Dock_Door='Dock 2', Qty_Ordered=1800, Qty_Claimed_On_Slip=1600,
           Coordinator_Initials='CY', Status='Awaiting Count',
           Notes='Partial PO fulfillment: this shipment covers PO lines 002, remaining open lines: none.')
ws.append([row.get(h) for h in hdr])""")
        self.did("slack__post_message", {"channel_id": "C001", "text": self.POST})
        self.assertEqual(self.done(), {})


if __name__ == "__main__":
    unittest.main()
