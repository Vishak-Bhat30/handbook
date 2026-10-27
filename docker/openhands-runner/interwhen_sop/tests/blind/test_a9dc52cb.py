"""Blind unit tests for logistics_prairie_star_creamery_a9dc52cb (fixtures from the task environment only)."""

from __future__ import annotations

from interwhen_sop.tests.base import TaskCase

LOG, INV, EXP, TEMP = "inbound_receiving_log.xlsx", "inventory_master.xlsx", "expiry_tracker.xlsx", "temperature_log.xlsx"
ROW = 17  # pre-filled row for manifest 2026-04-02-001
PLANNER, DC_MGR = "jacob.patel@prairiestar.com", "carlos.mendoza@prairiestar.com"
SUBJECT = "P3 – Variance Notification – 2026-04-02-001 – 2026-04-02"
E2_BODY = ("Manifest: 2026-04-02-001\nSKU affected: SC-003\nManifest qty: 120 cases\nActual qty: 119 cases\n"
           "Overall Variance: -1 cases (-0.25%)\nClassification: Minor\n"
           "Pattern escalation (third minor variance from Waco in 30 days)\n"
           "Please provide explanation or corrective action.\n\nInventory Operations Analyst, Prairie Star Creamery")
S3 = ("Variance detected. Manifest 2026-04-02-001 received with flags. Temp: -9°F (P4). Variance: -1 cases. "
      "Email sent to the Production Planner and DC Manager.")
GOOD_ROW = {6: -9.5, 7: -10.5, 8: -13.0, 9: -9.5, 10: "Tier 2", 11: 399, 12: -1, 13: "-0.25%",
            14: "Class 1 – One case label torn (SC-001 pallet 3). No breach.", 15: "Accept with Note",
            16: "P3 – Open – Pending Variance Resolution (third minor variance from Waco in 30 days)",
            17: "Accepted – Warm side of acceptable range; Minor variance; Class 1 damage"}
INV_ROWS = [
    ["SC-001", "Sweet Cream Prairie", "A-20260327-01", "H-A", 160, "D(2026,4,2)", "D(2026,3,27)", "D(2027,9,27)",
     "Active", "D(2026,4,2)", "H-A-06-01", None],
    ["SC-003", "Midnight Chocolate Range", "A-20260327-02", "H-A", 119, "D(2026,4,2)", "D(2026,3,27)",
     "D(2027,9,27)", "Active", "D(2026,4,2)", "H-A-06-02", None],
    ["SC-007", "Golden Caramel Prairie Fire", "A-20260328-01", "H-A", 120, "D(2026,4,2)", "D(2026,3,28)",
     "D(2027,9,28)", "Active", "D(2026,4,2)", "H-A-06-03", None],
]
EXP_ROWS = [
    ["SC-001", "A-20260327-01", "H-A", 160, "D(2026,3,27)", "D(2027,9,27)", 543, "Green", None, None, None],
    ["SC-003", "A-20260327-02", "H-A", 119, "D(2026,3,27)", "D(2027,9,27)", 543, "Green", None, None, None],
    ["SC-007", "A-20260328-01", "H-A", 120, "D(2026,3,28)", "D(2027,9,28)", 544, "Green", None, None, None],
]


def _py(rows) -> str:
    return "[" + ",".join("[" + ",".join(v if isinstance(v, str) and v.startswith("D(") else repr(v) for v in r) + "]"
                          for r in rows) + "]"


class A9(TaskCase):
    TASK = "logistics_prairie_star_creamery_a9dc52cb"

    # helpers
    def fill_row(self, **over):
        vals = dict(GOOD_ROW)
        vals.update({int(k[1:]): v for k, v in over.items()})
        self.edit(LOG, "".join(f"ws.cell({ROW},{c}).value={v!r}\n" for c, v in vals.items()))

    def send_e2(self, **kw):
        args = {"to": PLANNER, "cc": DC_MGR, "subject": SUBJECT, "body": E2_BODY}
        args.update(kw)
        self.did("google_mail__send_email", args)

    def post_s3(self, text=S3):
        self.did("slack__reply_to_thread", {"channel_id": "C001", "thread_ts": "1775137500.000000", "text": text})

    def add_rows(self, fname, rows):
        self.edit(fname, "from datetime import datetime as D\nfor r in " + _py(rows) + ":\n    ws.append(r)\n")

    # initial state / golden path
    def test_initial_findings(self):
        self.assertEqual(set(self.done()), {"a9.comms.messages_sent", "a9.receiving_row"})

    def test_golden_path(self):
        self.fill_row()
        self.send_e2()
        self.post_s3()
        self.assertEqual(self.done(), {})

    def test_golden_path_with_inventory_and_expiry_rows(self):
        self.fill_row()
        self.send_e2()
        self.post_s3()
        self.add_rows(INV, INV_ROWS)
        self.add_rows(EXP, EXP_ROWS)
        self.assertEqual(self.done(), {})

    # receiving log row
    def test_rounded_warmest_accepted(self):
        self.fill_row(c9=-9)
        self.assertNotIn("a9.receiving_row", self.done())

    def test_wrong_tier(self):
        self.fill_row(c10="Tier 1")
        self.assertIn("Tier 2", self.done()["a9.receiving_row"])

    def test_temps_swapped(self):
        self.fill_row(c6=-13.0, c8=-9.5)
        self.assertIn("Temp 1 (front) = -9.5", self.done()["a9.receiving_row"])

    def test_per_sku_percentage(self):
        self.fill_row(c13="-0.83%")
        self.assertIn("-0.25%", self.done()["a9.receiving_row"])

    def test_fraction_percentage_ok(self):
        self.fill_row(c13=-0.0025)
        self.assertNotIn("a9.receiving_row", self.done())

    def test_disposition_must_be_acceptance_value(self):
        self.fill_row(c15="Accept with Note – Warm side of acceptable range")
        self.assertIn("Accept with Note", self.done()["a9.receiving_row"])

    def test_damage_not_as_reported(self):
        self.fill_row(c14="Class 1 – torn label")
        self.assertIn("exactly as reported", self.done()["a9.receiving_row"])

    def test_notes_missing_warm_note(self):
        self.fill_row(c17="Minor variance; Class 1 damage")
        self.assertIn("Warm side", self.done()["a9.receiving_row"])

    def test_notes_reference_prior_deliveries(self):
        self.fill_row(c17=GOOD_ROW[17] + ". Prior: 2026-03-25-001 (-3), 2026-03-31-001 (-1)")
        self.assertIn("prior deliveries", self.done()["a9.receiving_row"])

    def test_rounded_readings_ok(self):
        self.fill_row(c6=-9, c7=-10, c8=-13, c9=-9)
        self.assertNotIn("a9.receiving_row", self.done())

    def test_one_decimal_percentage_ok(self):
        self.fill_row(c13="-0.3%")
        self.assertNotIn("a9.receiving_row", self.done())

    def test_damage_paraphrase_ok(self):
        self.fill_row(c14="Class 1 – one case label torn (SC-001, pallet 3). No breach.")
        self.assertNotIn("a9.receiving_row", self.done())

    def test_closed_status_flagged(self):
        self.fill_row(c16="P3 – Closed – Accepted with variance note")
        self.assertIn("do not close", self.done()["a9.receiving_row"])

    def test_open_status_ok(self):
        self.fill_row(c16="P3 – Open – Pending Variance Resolution")
        self.assertNotIn("a9.receiving_row", self.done())

    def test_missing_p3_notation(self):
        self.fill_row(c16="Received – Pending Put-Away")
        self.assertIn("P3 notation", self.done()["a9.receiving_row"])

    def test_p3_in_notes_ok(self):
        self.fill_row(c16="Received – Pending Put-Away", c17=GOOD_ROW[17] + "; P3 – minor variance pattern")
        self.assertNotIn("a9.receiving_row", self.done())

    # receiving log invariants
    def test_earlier_row_edited(self):
        self.fill_row()
        self.edit(LOG, "ws.cell(16,17).value='changed'\n")
        self.assertIn("a9.receiving_log_append_only", self.done())

    def test_duplicate_row_added(self):
        self.fill_row()
        self.edit(LOG, "ws.append(['2026-04-02','2026-04-02-001','Waco Transfer',20,400])\n")
        self.assertIn("a9.receiving_log_append_only", self.done())

    # inventory / expiry rows (only checked when added)
    def test_inventory_wrong_zone(self):
        rows = [list(r) for r in INV_ROWS]
        rows[1][3] = "H-B"
        self.add_rows(INV, rows)
        self.assertIn("Zone H-A", self.done()["a9.inventory_rows"])

    def test_inventory_partial(self):
        self.add_rows(INV, INV_ROWS[:2])
        self.assertIn("missing: A-20260328-01", self.done()["a9.inventory_rows"])

    def test_inventory_existing_row_changed(self):
        self.edit(INV, "ws.cell(4,5).value=199\n")
        self.assertIn("a9.inventory_rows", self.done())

    def test_expiry_wrong_flag_and_qty(self):
        rows = [list(r) for r in EXP_ROWS]
        rows[1][3], rows[1][7] = 120, "Yellow"
        self.add_rows(EXP, rows)
        msg = self.done()["a9.expiry_rows"]
        self.assertIn("Qty 119", msg)
        self.assertIn("Status Flag Green", msg)

    def test_expiry_formula_days_ok(self):
        rows = [list(r) for r in EXP_ROWS]
        for r in rows:
            r[6] = "=F20-TODAY()"
        self.add_rows(EXP, rows)
        self.assertNotIn("a9.expiry_rows", self.done())

    # other invariants
    def test_temperature_log_append_only(self):
        self.edit(TEMP, "ws.cell(4,4).value=-5\n", sheet="April 2026")
        self.assertIn("a9.temperature_log_append_only", self.done())

    def test_temperature_log_append_ok(self):
        self.edit(TEMP, "from datetime import datetime as D, time as T\n"
                        "ws.append([D(2026,4,2),T(14,30),'H-A',-20,'Scheduled','Y',None,'AN'])\n", sheet="April 2026")
        self.assertNotIn("a9.temperature_log_append_only", self.done())

    def test_new_workbook(self):
        self.edit(LOG, "wb.save(path.replace('inbound_receiving_log','my_copy'))\n")
        self.assertIn("a9.no_new_workbooks", self.done())

    def test_manifest_readonly(self):
        self.assertIn("a9.manifests_readonly", self.pre("syntara__writeFile",
                                                        {"file_path": "/workdir/2026-04-02-001.pdf", "content": "x"}))
        self.assertNotIn("a9.manifests_readonly", self.pre(
            "syntara__executePython", {"code": "import openpyxl\nwb=openpyxl.load_workbook('/workdir/"
                                               "inbound_receiving_log.xlsx')\nwb.save('/workdir/inbound_receiving_log.xlsx')"}))

    # E2 email
    def test_e2_compliant(self):
        self.assertEqual(self.pre("google_mail__send_email",
                                  {"to": PLANNER, "cc": DC_MGR, "subject": SUBJECT, "body": E2_BODY}), set())

    def test_e2_long_subject_form_ok(self):
        self.assertEqual(self.pre("google_mail__send_email", {
            "to": PLANNER, "cc": DC_MGR, "body": E2_BODY,
            "subject": "P3 – Variance Notification – Inbound Waco Manifest 2026-04-02-001 – 2026-04-02"}), set())

    def test_e2_wrong_priority_and_missing_cc(self):
        self.assertIn("a9.comms.messages", self.pre("google_mail__send_email", {
            "to": PLANNER, "subject": SUBJECT.replace("P3", "P4"), "body": E2_BODY}))

    def test_e2_wrong_percentage(self):
        self.assertIn("a9.comms.messages", self.pre("google_mail__send_email", {
            "to": PLANNER, "cc": DC_MGR, "subject": SUBJECT, "body": E2_BODY.replace("-0.25%", "-0.83%")}))

    def test_e2_not_sent_is_outstanding(self):
        self.fill_row()
        self.post_s3()
        self.assertIn("E2", self.done()["a9.comms.messages_sent"])

    # S3 post
    def test_s3_threaded_compliant(self):
        self.assertEqual(self.pre("slack__reply_to_thread",
                                  {"channel_id": "C001", "thread_ts": "1775137500.000000", "text": S3}), set())

    def test_s3_top_level_blocked(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C001", "text": S3}), {"a9.s3_thread"})

    def test_s3_mentions_pattern_blocked(self):
        self.assertIn("a9.comms.messages", self.pre("slack__reply_to_thread", {
            "channel_id": "C001", "thread_ts": "1775137500.000000",
            "text": S3 + " Third minor variance in 30 days (2026-03-25-001, 2026-03-31-001)."}))

    def test_s3_unrounded_temp_blocked(self):
        self.assertIn("a9.comms.messages", self.pre("slack__reply_to_thread", {
            "channel_id": "C001", "thread_ts": "1775137500.000000", "text": S3.replace("-9°F", "-9.5°F")}))

    def test_putaway_question_in_thread_not_s3(self):
        self.post_s3()
        self.assertEqual(self.pre("slack__reply_to_thread", {
            "channel_id": "C001", "thread_ts": "1775137500.000000",
            "text": "@a.nguyen Please confirm put-away zones for manifest 2026-04-02-001."}), set())

    def test_s3_wrong_channel_outstanding(self):
        self.fill_row()
        self.send_e2()
        self.did("slack__post_message", {"channel_id": "C005", "text": S3})
        self.assertIn("S3", self.done()["a9.comms.messages_sent"])

    # forbidden messages
    def test_s1_repost_blocked(self):
        self.assertIn("a9.comms.messages", self.pre("slack__post_message", {
            "channel_id": "C001", "text": "Waco transfer 2026-04-02-001 expected at 09:00. Pallets: 20, Cases: 400. "
                                          "Dock crew standing by."}))

    def test_waco_coord_post_blocked(self):
        self.assertIn("a9.comms.messages", self.pre("slack__post_message", {
            "channel_id": "C004", "text": "Variance detected. Manifest 2026-04-02-001, SKU SC-003: -1 case."}))

    def test_waco_coord_unrelated_ok(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C004", "text": "Schedule question for 4/8."}),
                         set())

    def test_class1_credit_claim_blocked(self):
        self.assertIn("a9.comms.messages", self.pre("google_mail__send_email", {
            "to": PLANNER, "cc": DC_MGR, "subject": "P4 – Credit Claim – Damage Class 1 – Manifest 2026-04-02-001",
            "body": "Manifest 2026-04-02-001, Class 1, one case label torn."}))

    def test_at_channel_blocked(self):
        self.assertIn("a9.no_at_channel", self.pre("slack__post_message",
                                                   {"channel_id": "C005", "text": "@channel inventory update"}))

    def test_placeholder_blocked(self):
        self.assertIn("comms.no_placeholders", self.pre("google_mail__send_email", {
            "to": "carlos.mendoza@prairiestar.com", "subject": "Update", "body": "SKU affected: [SKU]"}))
