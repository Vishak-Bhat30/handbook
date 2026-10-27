from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase

TASK = "logistics_prairie_star_creamery_4a2f4b1a"
RL, ET, IM, TL = "inbound_receiving_log.xlsx", "expiry_tracker.xlsx", "inventory_master.xlsx", "temperature_log.xlsx"

M1_ROW = """
vals = {"Total Cases (Actual)": 210, "Temp Front (°F)": -10.2, "Temp Middle (°F)": -10.2, "Temp Rear (°F)": -18.7,
        "Temp Avg (°F)": -13.03, "Temp Tier": "Tier 1", "Variance (Cases)": 0, "Variance %": 0,
        "Variance Class": "Exact Match",
        "Lot Codes": "A-20260410-01 (SC-001)\\nA-20260411-01 -- MISMATCH – manifest A-20260412-01 vs received A-20260411-01.\\nB-20260408-01 (SP-001)",
        "Damage Class": "None", "Damage Notes": "No damage", "Priority": "P3", "Disposition": "Open",
        "Status": "Open – Pending Lot Code Clarification", "Notes": "P3 lot code mismatch on SC-003."}
vals.update(OVERRIDE)
for k, v in vals.items():
    ws.cell(2, col[k]).value = v
"""

VENDOR_ROWS = """
import datetime
def row(po, origin, qty, notes):
    r = ws.max_row + 1
    v = {h: "Pending" for h in hdr}
    v.update({"Receipt Date": datetime.datetime(2026, 4, 15), "Manifest / PO #": po, "Origin": origin,
              "Total Pallets (Manifest)": "X", "Total Cases (Manifest)": qty, "Temp Front (°F)": "X",
              "Temp Middle (°F)": "X", "Temp Rear (°F)": "X", "Temp Avg (°F)": "X", "Temp Tier": "X",
              "Lot Codes": "N/A", "Disposition": "Open", "Status": "Pre-arrival", "Notes": notes})
    v.update(OVERRIDE.get(str(po), {}))
    for h, x in v.items():
        ws.cell(r, col[h]).value = x
row(67204, "Lone Star Toppings Co.", 45,
    "Allergen alert: some items contain tree nuts and peanuts. Verify allergen labeling on receipt.")
row(11587, "TexPal Logistics", 50, "Inspect for splinters, broken slats, stains, pest evidence. Reject pallet that cannot hold 1,500 lbs.")
"""

EXPIRY_ROWS = """
ws.append(["SC-001", "Sweet Cream Prairie", "A-20260410-01", "H-A", "2026-04-15", "2026-04-10", 18, "2027-10-10", 543,
           "Green", 100, "Monitored", None, None, None, None])
ws.append(["SP-001", "Lavender Cream Moonrise", "B-20260408-01", "H-B", "2026-04-15", "2026-04-08", 15, "2027-07-08",
           449, "Green", 30, "Monitored", None, None, None, None])
"""

EMAIL = {"to": "jacob.patel@prairiestar.com", "cc": "carlos.mendoza@prairiestar.com",
         "subject": "P3 – Lot Code Mismatch – Inbound Waco Manifest 2026-04-15-001 – 2026-04-15",
         "body": "LOT CODE MISMATCH – 2026-04-15-001 - manifest A-20260412-01 vs received A-20260411-01. "
                 "Hold receipt open pending clarification.\n\nMichael Andrews"}
P3_POST = {"channel_id": "C004", "text": "P3 Issue Noted! – 2026-04-15-001 – Lot code mismatch on SC-003: manifest "
                                         "A-20260412-01 vs received A-20260411-01."}
DM = {"user_id": "U008", "text": "Hi Alicia — PO 67204 was scheduled for 10:00 and I haven't received a dock report. "
                                 "Can you confirm status or ETA?"}


class Base(TaskCase):
    TASK = TASK

    def m1(self, **override):
        self.edit(RL, f"OVERRIDE={override!r}\n" + M1_ROW)

    def vendors(self, **override):
        self.edit(RL, f"OVERRIDE={override!r}\n" + VENDOR_ROWS)

    def golden(self, skip=()):
        if "m1" not in skip:
            self.m1()
        if "vendors" not in skip:
            self.vendors()
        if "expiry" not in skip:
            self.edit(ET, EXPIRY_ROWS)
        for tool, args, key in [("google_mail__send_email", EMAIL, "email"), ("slack__post_message", P3_POST, "p3"),
                                ("slack__send_dm", DM, "dm")]:
            if key not in skip:
                self.did(tool, args)


class GoldenPath(Base):
    def test_initial_obligations(self):
        d = self.done()
        self.assertEqual(set(d), {"comms.messages_sent", "receiving.manifest_001", "receiving.vendor_prearrival",
                                  "expiry.lots"})

    def test_golden(self):
        self.golden()
        self.assertEqual(self.done(), {})


class Messages(Base):
    def test_email_ok(self):
        self.assertEqual(self.pre("google_mail__send_email", EMAIL), set())

    def test_email_missing_cc_and_text(self):
        bad = {**EMAIL, "cc": "", "body": "LOT CODE MISMATCH on 2026-04-15-001, please check."}
        self.assertEqual(self.pre("google_mail__send_email", bad), {"comms.messages"})

    def test_email_bad_subject(self):
        self.assertEqual(self.pre("google_mail__send_email", {**EMAIL, "subject": "Lot code mismatch"}),
                         {"comms.messages"})

    def test_unrelated_email_to_carlos_not_matched(self):
        args = {"to": "carlos.mendoza@prairiestar.com", "subject": "FYI receiving update", "body": "Lot code mismatch noted."}
        self.assertEqual(self.pre("google_mail__send_email", args), set())

    def test_p3_post_ok(self):
        self.assertEqual(self.pre("slack__post_message", P3_POST), set())
        self.assertEqual(self.pre("slack__post_message", {**P3_POST, "channel_id": "C001"}), set())

    def test_p3_post_bad_format(self):
        bad = {"channel_id": "C004", "text": "P3: lot code mismatch on 2026-04-15-001."}
        self.assertEqual(self.pre("slack__post_message", bad), {"comms.messages"})

    def test_thread_reply_not_p3_not_blocked(self):
        args = {"channel_id": "C001", "thread_ts": "1776264300.000000",
                "text": "Thanks @a.nguyen. Lot code mismatch on SC-003 logged; receipt held open."}
        self.assertEqual(self.pre("slack__reply_to_thread", args), set())

    def test_dm_ok(self):
        self.assertEqual(self.pre("slack__send_dm", DM), set())
        alt = {"user_id": "U008", "text": "Hi Alicia — PO 67204 (DRY-02, Lone Star Toppings) was scheduled for 10:00 "
                                          "and I haven’t received a dock report. Can you confirm status or ETA?"}
        self.assertEqual(self.pre("slack__send_dm", alt), set())

    def test_dm_bad_wording(self):
        bad = {"user_id": "U008", "text": "Alicia, any update on PO 67204?"}
        self.assertEqual(self.pre("slack__send_dm", bad), {"comms.messages"})

    def test_duplicate_dm_blocked(self):
        self.did("slack__send_dm", DM)
        self.assertEqual(self.pre("slack__send_dm", DM), {"comms.messages"})

    def test_missing_messages_listed(self):
        self.golden(skip=("dm",))
        d = self.done_all()
        self.assertEqual([r for r, _ in d], ["comms.messages_sent"])
        self.assertIn("67204", d[0][1])

    def test_broadcast(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C001", "text": "@here receiving update"}),
                         {"comms.no_broadcast"})
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C001", "text": "receiving update"}), set())

    def test_placeholders(self):
        bad = {**EMAIL, "body": EMAIL["body"] + "\n[Manifest ID]"}
        self.assertIn("comms.no_placeholders", self.pre("google_mail__send_email", bad))


class ReceivingLog(Base):
    def _m1_findings(self, **override):
        self.golden(skip=("m1",))
        self.m1(**override)
        return [p for r, p in self.done_all() if r == "receiving.manifest_001"]

    def test_wrong_average(self):
        f = self._m1_findings(**{"Temp Avg (°F)": -12.37})
        self.assertEqual(len(f), 1)
        self.assertIn("-13.03", f[0])

    def test_closed_status(self):
        f = self._m1_findings(Status="Closed – Accepted", Disposition="Accepted")
        self.assertEqual(len(f), 2)

    def test_damage_notes_and_lot_codes(self):
        f = self._m1_findings(**{"Damage Notes": "No damage.", "Lot Codes": "A-20260410-01, A-20260411-01, B-20260408-01"})
        self.assertEqual(len(f), 2)

    def test_p3_status_variant_ok(self):
        self.assertEqual(self._m1_findings(Status="P3 – Lot code mismatch SC-003"), [])

    def test_manifest_002_fabricated(self):
        self.golden()
        self.edit(RL, "ws.cell(3, col['Temp Front (°F)']).value = -15")
        self.assertEqual(set(self.done()), {"receiving.manifest_002"})

    def test_vendor_row_wrong_status(self):
        self.golden(skip=("vendors",))
        self.vendors(**{"67204": {"Status": "Pending", "Total Pallets (Manifest)": "Pending"}})
        d = self.done_all()
        self.assertEqual([r for r, _ in d], ["receiving.vendor_prearrival"])
        self.assertIn("Pre-arrival", d[0][1])

    def test_vendor_rows_po_prefix_ok(self):
        self.golden(skip=("vendors",))
        self.vendors(**{"67204": {"Manifest / PO #": "PO 67204"}})
        self.assertEqual(self.done(), {})

    def test_history_edit(self):
        self.golden()
        self.edit(RL, "ws.cell(4, col['Notes']).value = 'edited'")
        self.assertEqual(set(self.done()), {"receiving.history"})


class Records(Base):
    def test_mismatch_lot_in_expiry(self):
        self.golden()
        self.edit(ET, 'ws.append(["SC-003", "Midnight Chocolate Range", "A-20260411-01", "H-A", "2026-04-15", '
                      '"2026-04-11", 18, "2027-10-11", 544, "Green", 80, "Monitored"])')
        self.assertEqual(set(self.done()), {"expiry.lots"})

    def test_expiry_wrong_values(self):
        self.golden(skip=("expiry",))
        self.edit(ET, EXPIRY_ROWS.replace('"Monitored"', '"Standard"', 1))
        d = self.done_all()
        self.assertEqual([r for r, _ in d], ["expiry.lots"])
        self.assertIn("Monitored", d[0][1])

    def test_inventory_master_premature(self):
        self.golden()
        self.edit(IM, 'ws.append(["SC-001", "Sweet Cream Prairie", "A-20260410-01", "2027-10-10", 100, "H-A", "", '
                      '"Active", "2026-04-15", "", ""])')
        self.assertEqual(set(self.done()), {"inventory.put_away_pending"})

    def test_temperature_log_premature(self):
        self.golden()
        self.edit(TL, 'ws.append(["2026-04-15", "09:45:00", "Inbound — Manifest 2026-04-15-001 (Front)", -10.2, '
                      '"Inbound receipt", "Y", "Tier 1.", "Analyst"])')
        self.assertEqual(set(self.done()), {"temperature.put_away_pending"})

    def test_vendor_master_untouched(self):
        self.golden()
        self.edit("vendor_master.xlsx", "ws.cell(2, 11).value = 'changed'")
        self.assertEqual(set(self.done()), {"files.unrequested"})

    def test_no_new_workbooks(self):
        self.golden()
        self.edit(IM, "wb.save(path.replace('inventory_master', 'my_tracker'))\nwb = openpyxl.load_workbook(path)")
        self.assertEqual(set(self.done()), {"files.unrequested"})


if __name__ == "__main__":
    unittest.main()
