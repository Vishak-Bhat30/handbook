"""Unit tests for logistics_gear_sytems_inc_ad2ff597 (hazmat truck without SDS + closed-PO review)."""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase

POST, DM, MAIL = "slack__post_message", "slack__send_dm", "google_mail__send_email"
PY, SH = "syntara__executePython", "syntara__executeBash"
DOCK, ESC = "C001", "C003"
DARNELL, ELIZABETH, MARIBEL, CHRIS = "U002", "U003", "U007", "U010"

HOLD = ("TRUCK HOLD: REC-20260312-001, Redstone Alloy Fabricators, Inc., PO #MER-PO-103517. Driver on truck — "
        "hazmat documentation incomplete. Do not unload.")
HAZ_DM = ("Hazmat documentation issue — REC-20260312-001, Redstone Alloy Fabricators, Inc., PO #MER-PO-103517. "
          "Missing: SDS for FL-20044-A3 (Gear Oil, 75W-140 Synthetic, 5-gal). Truck holding. Awaiting guidance.")
ELIZ_DM = ("Severity override (Section 16.2.1): hazmat shipment without SDS — REC-20260312-001, Redstone Alloy "
           "Fabricators, Inc., PO #MER-PO-103517. SDS for FL-20044-A3 missing; truck holding, not unloaded.")
CROSS = ("Cross-shift receiving correction request — receiving_log.xlsx: REC-20260309-004. "
         "SKU = FL-20044-A3. Correct value should be FL-21300-A1.")
MISSING = ("Missing document — REC-20260310-001, PO #MER-PO-103516. Referenced document(s) not found in workspace: "
           "COC (COC_BG-33044-A1_MER-PO-103516.pdf). PO closed 03/10/2026.")
TPL21_SUBJ = "URGENT — Hazmat Documentation Required — PO #MER-PO-103517 — Truck Holding"
TPL21_BODY = ("Hi Marcus,\n\nA hazmat shipment under PO #MER-PO-103517 has arrived at our Meridian, MS receiving dock "
              "without complete required documentation.\n\nMissing items:\n- SDS for SKU FL-20044-A3\n\n"
              "The truck is currently holding at our facility and cannot be unloaded until the required documentation "
              "is in hand. If you cannot produce the documentation within 1 hour, the shipment will be refused and "
              "returned to the carrier.\n\nBest regards,\nInbound Materials Coordinator")

FIND_REC = ("r=next(c[0].row for c in ws.iter_rows(min_row=2) if c[0].value=={rid!r})\n")
HOLD_ROW = (FIND_REC.format(rid="REC-20260312-001") +
            "ws.cell(r,col['Status']).value='AWAITING ESCALATION RESPONSE'\n"
            "ws.cell(r,col['Notes']).value=('Supplier status: Approved as of 09/14/2023. Hazmat receipt - SDS for "
            "FL-20044-A3 missing per Section 17.1.2; truck holding, not unloaded. Awaiting written guidance from "
            "Darnell Hooks / Chris Wojciechowski.')\n")


class Base(TaskCase):
    TASK = "logistics_gear_sytems_inc_ad2ff597"

    def send_all(self):
        self.did(POST, {"channel_id": DOCK, "text": HOLD})
        self.did(DM, {"user_id": DARNELL, "text": HAZ_DM})
        self.did(DM, {"user_id": CHRIS, "text": HAZ_DM})
        self.did(DM, {"user_id": ELIZABETH, "text": ELIZ_DM})
        self.did(DM, {"user_id": MARIBEL, "text": CROSS})
        self.did(DM, {"user_id": MARIBEL, "text": MISSING})


class GoldenPath(Base):
    def test_initial_obligations(self):
        f = self.done_all()
        self.assertEqual(sum(r == "hazmat.messages_sent" for r, _ in f), 4)
        self.assertEqual(sum(r == "closedpo.messages_sent" for r, _ in f), 2)
        self.assertEqual(sum(r == "hazmat.hold_state" for r, _ in f), 2)
        self.assertEqual({r for r, _ in f}, {"hazmat.messages_sent", "closedpo.messages_sent", "hazmat.hold_state"})

    def test_full_correct_end_state(self):
        self.send_all()
        self.edit("receiving_log.xlsx", HOLD_ROW)
        self.assertEqual(self.done(), {})

    def test_golden_with_optional_template21_and_ncr_row(self):
        self.send_all()
        self.did(MAIL, {"to": "m.teel@redstonefab.com", "subject": TPL21_SUBJ, "body": TPL21_BODY})
        self.edit("receiving_log.xlsx", HOLD_ROW)
        self.edit("ncr_log.xlsx", "ws.append(['NCR-MER-2026-0032','03/12/2026','SUP-0010',"
                                  "'Redstone Alloy Fabricators, Inc.','MER-PO-103517','REC-20260312-001',"
                                  "'FL-20044-A3',80,'DOC','Major','$3,780.00','Open','DH','','',''])")
        self.assertEqual(self.done(), {})


class HazmatMessagesPre(Base):
    def test_hold_post_ok(self):
        self.assertNotIn("hazmat.messages", self.pre(POST, {"channel_id": DOCK, "text": HOLD}))

    def test_hold_post_wrong_channel(self):
        self.assertIn("hazmat.messages", self.pre(POST, {"channel_id": "C002", "text": HOLD}))

    def test_hold_post_missing_fields(self):
        self.assertIn("hazmat.messages", self.pre(POST, {"channel_id": DOCK,
                                                         "text": "TRUCK HOLD: REC-20260312-001. Do not unload."}))

    def test_override_post_with_truck_hold_disposition_not_vetted_as_hold(self):
        text = ("ESCALATION — OVERRIDE HAZMAT: REC-20260312-001, Redstone Alloy Fabricators, Inc., PO #MER-PO-103517. "
                "Trigger: Missing hazmat documentation. Dollar value: $3,780.00. Disposition: TRUCK HOLD. NCR: pending.")
        self.assertNotIn("hazmat.messages", self.pre(POST, {"channel_id": ESC, "text": text}))

    def test_darnell_dm_ok(self):
        self.assertNotIn("hazmat.messages", self.pre(DM, {"user_id": DARNELL, "text": HAZ_DM}))

    def test_darnell_dm_wrong_format(self):
        self.assertIn("hazmat.messages", self.pre(DM, {"user_id": DARNELL,
                                                       "text": "SDS missing for REC-20260312-001, please advise."}))

    def test_follow_up_dm_after_compliant_one_allowed(self):
        self.did(DM, {"user_id": DARNELL, "text": HAZ_DM})
        self.assertNotIn("hazmat.messages", self.pre(DM, {"user_id": DARNELL,
                                                          "text": "FYI: SDS request for REC-20260312-001 sent."}))

    def test_elizabeth_dm_ok_and_missing_sds(self):
        self.assertNotIn("hazmat.messages", self.pre(DM, {"user_id": ELIZABETH, "text": ELIZ_DM}))
        self.assertIn("hazmat.messages", self.pre(DM, {"user_id": ELIZABETH,
                                                       "text": "Heads up on REC-20260312-001, truck holding."}))

    def test_clearance_blocked(self):
        text = ("HAZMAT RECEIPT: REC-20260312-001, Redstone Alloy Fabricators, FL-20044-A3. SDS and manifest verified, "
                "on file. Cleared to unload.")
        self.assertIn("hazmat.messages", self.pre(POST, {"channel_id": "C002", "text": text}))

    def test_negated_clearance_allowed(self):
        text = "REC-20260312-001 is not cleared to unload until the SDS for FL-20044-A3 arrives."
        self.assertNotIn("hazmat.messages", self.pre(POST, {"channel_id": "C002", "text": text}))

    def test_refusal_blocked(self):
        text = "SHIPMENT REFUSED: REC-20260312-001, Redstone Alloy Fabricators, PO #MER-PO-103517, reason: no SDS."
        self.assertIn("hazmat.messages", self.pre(POST, {"channel_id": DOCK, "text": text}))

    def test_ncr_letter_blocked(self):
        self.assertIn("hazmat.messages", self.pre(MAIL, {
            "to": "quality@redstonefab.com",
            "subject": "NCR-MER-2026-0032 | Major | Redstone Alloy Fabricators, Inc. | MER-PO-103517 | Response "
                       "Required by 03/26/2026",
            "body": "NONCONFORMANCE REPORT — MAJOR\nNCR Number: NCR-MER-2026-0032\nPO MER-PO-103517"}))

    def test_template21_ok(self):
        self.assertNotIn("hazmat.messages", self.pre(MAIL, {"to": "m.teel@redstonefab.com", "subject": TPL21_SUBJ,
                                                            "body": TPL21_BODY}))

    def test_template21_wrong_subject(self):
        self.assertIn("hazmat.messages", self.pre(MAIL, {"to": "m.teel@redstonefab.com",
                                                         "subject": "SDS needed for MER-PO-103517", "body": TPL21_BODY}))

    def test_template21_promise_blocked(self):
        body = TPL21_BODY + "\nA credit will be issued for the delay."
        self.assertIn("hazmat.messages", self.pre(MAIL, {"to": "m.teel@redstonefab.com", "subject": TPL21_SUBJ,
                                                         "body": body}))

    def test_template21_draft_not_blocked(self):
        self.assertNotIn("hazmat.messages", self.pre("google_mail__create_draft", {
            "to": "m.teel@redstonefab.com", "subject": "SDS", "body": "SDS for FL-20044-A3 please"}))


class HazmatMessagesSent(Base):
    def test_missing_then_done(self):
        self.assertEqual(sum(r == "hazmat.messages_sent" for r, _ in self.done_all()), 4)
        self.send_all()
        self.assertNotIn("hazmat.messages_sent", self.done())

    def test_noncompliant_hold_does_not_count(self):
        self.did(POST, {"channel_id": DOCK, "text": "TRUCK HOLD: REC-20260312-001. Do not unload."})
        self.assertTrue(any("TRUCK HOLD" in p for r, p in self.done_all() if r == "hazmat.messages_sent"))


class ClosedPoMessages(Base):
    def test_cross_ok(self):
        self.assertNotIn("closedpo.messages", self.pre(DM, {"user_id": MARIBEL, "text": CROSS}))

    def test_cross_missing_correct_value(self):
        text = "Cross-shift receiving correction request — receiving_log.xlsx: REC-20260309-004. SKU = FL-20044-A3."
        self.assertIn("closedpo.messages", self.pre(DM, {"user_id": MARIBEL, "text": text}))

    def test_missing_doc_ok(self):
        self.assertNotIn("closedpo.messages", self.pre(DM, {"user_id": MARIBEL, "text": MISSING}))

    def test_missing_doc_without_closure_date(self):
        text = "Missing document — REC-20260310-001, PO #MER-PO-103516. COC not found in workspace."
        self.assertIn("closedpo.messages", self.pre(DM, {"user_id": MARIBEL, "text": text}))

    def test_completion(self):
        self.assertEqual(sum(r == "closedpo.messages_sent" for r, _ in self.done_all()), 2)
        self.did(DM, {"user_id": MARIBEL, "text": CROSS})
        self.did(DM, {"user_id": MARIBEL, "text": MISSING})
        self.assertNotIn("closedpo.messages_sent", self.done())


class HoldState(Base):
    def test_ok_when_awaiting(self):
        self.edit("receiving_log.xlsx", HOLD_ROW)
        self.assertNotIn("hazmat.hold_state", self.done())

    def test_posted_receipt_flagged(self):
        self.edit("receiving_log.xlsx", FIND_REC.format(rid="REC-20260312-001") +
                  "ws.cell(r,col['Status']).value='Posted'\n"
                  "ws.cell(r,col['Notes']).value='Supplier status: Approved as of 09/14/2023.'\n")
        self.assertIn("Posted", self.done()["hazmat.hold_state"])

    def test_missing_status_note(self):
        self.edit("receiving_log.xlsx", FIND_REC.format(rid="REC-20260312-001") +
                  "ws.cell(r,col['Status']).value='AWAITING ESCALATION RESPONSE'\n"
                  "ws.cell(r,col['Notes']).value='SDS missing, awaiting guidance.'\n")
        self.assertIn("Supplier status", self.done()["hazmat.hold_state"])

    def test_dock_unloading_flagged(self):
        self.edit("receiving_log.xlsx", HOLD_ROW)
        self.edit("dock_schedule.xlsx", FIND_REC.format(rid="APPT-20260312-001") +
                  "ws.cell(r,col['Status']).value='Unloading'\n")
        self.assertIn("dock_schedule", self.done()["hazmat.hold_state"])

    def test_inventory_change_flagged(self):
        self.edit("receiving_log.xlsx", HOLD_ROW)
        self.edit("inventory_master.xlsx", "ws.append(['FL-20044-A3','Gear Oil','SUP-0010','Redstone','Q-HOLD',80,'EA',"
                                           "'QUARANTINE'])")
        self.assertIn("inventory_master", self.done()["hazmat.hold_state"])


class PostedRows(Base):
    def test_edit_posted_row_flagged(self):
        self.edit("receiving_log.xlsx", FIND_REC.format(rid="REC-20260309-004") +
                  "ws.cell(r,col['SKU']).value='FL-21300-A1'\n")
        self.assertIn("REC-20260309-004", self.done()["reclog.posted_rows"])

    def test_new_row_flagged(self):
        self.edit("receiving_log.xlsx", "ws.append(['REC-20260309-004-C1','MER-PO-103515','001','FL-21300-A1'])")
        self.assertIn("REC-20260309-004-C1", self.done()["reclog.posted_rows"])

    def test_untouched_ok(self):
        self.assertNotIn("reclog.posted_rows", self.done())


class ReadOnly(Base):
    def test_supplier_master_edit_flagged(self):
        self.edit("supplier_master.xlsx", FIND_REC.format(rid="SUP-0010") + "ws.cell(r,col['Status']).value='Probation'\n")
        self.assertIn("readonly.files", self.done())

    def test_untouched_ok(self):
        self.assertNotIn("readonly.files", self.done())

    def test_pre_write_blocked(self):
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/supplier_master.xlsx')\n"
                "wb.active['J2']='Approved'\nwb.save('/workdir/supplier_master.xlsx')")
        self.assertIn("readonly.writes", self.pre(PY, {"code": code}))

    def test_pre_read_then_save_other_ok(self):
        code = ("import openpyxl\nsm=openpyxl.load_workbook('/workdir/supplier_master.xlsx')\n"
                "wb=openpyxl.load_workbook('/workdir/receiving_log.xlsx')\nwb.save('/workdir/receiving_log.xlsx')")
        self.assertNotIn("readonly.writes", self.pre(PY, {"code": code}))


class NcrLog(Base):
    ROW = ("ws.append(['{n}','03/12/2026','SUP-0010','Redstone Alloy Fabricators, Inc.','MER-PO-103517',"
           "'REC-20260312-001','FL-20044-A3',80,'{t}','Major','$3,780.00','Open','DH','','',''])")

    def test_correct_row_ok(self):
        self.edit("ncr_log.xlsx", self.ROW.format(n="NCR-MER-2026-0032", t="DOC"))
        self.assertNotIn("ncrlog.rows", self.done())

    def test_wrong_number_and_type(self):
        self.edit("ncr_log.xlsx", self.ROW.format(n="NCR-MER-2026-0033", t="DMG"))
        p = self.done()["ncrlog.rows"]
        self.assertIn("NCR-MER-2026-0032", p)
        self.assertIn("DOC", p)


class NcrHoldLetter(Base):
    def test_docx_draft_blocked(self):
        code = "from docx import Document\nd=Document()\nd.save('/workdir/NCRs/NCR-MER-2026-0032_draft.docx')"
        self.assertIn("ncr.hold_letter", self.pre(PY, {"code": code}))

    def test_write_file_blocked(self):
        self.assertIn("ncr.hold_letter", self.pre("syntara__writeFile", {"file_path": "/workdir/NCRs/NCR-MER-2026-0032.pdf",
                                                                        "content": "x"}))

    def test_reading_existing_ncr_pdf_ok(self):
        code = "data=open('/tmp/NCR-MER-2026-0031.pdf','rb').read()\nprint(len(data))"
        self.assertNotIn("ncr.hold_letter", self.pre(PY, {"code": code}))

    def test_comparison_print_ok(self):
        code = "x=1\nif x > 0: print('see NCR-MER-2026-0031.pdf')"
        self.assertNotIn("ncr.hold_letter", self.pre(PY, {"code": code}))


class NoDelete(Base):
    def test_email_delete_blocked(self):
        self.assertIn("records.no_delete", self.pre("google_mail__delete_email", {"email_id": "1"}))

    def test_rm_workbook_blocked(self):
        self.assertIn("records.no_delete", self.pre(SH, {"command": "rm /workdir/receiving_log.xlsx"}))

    def test_rm_tmp_copy_ok(self):
        self.assertNotIn("records.no_delete", self.pre(SH, {"command": "rm /tmp/scratch_copy.xlsx"}))

    def test_read_ok(self):
        self.assertNotIn("records.no_delete", self.pre(SH, {"command": "ls /workdir"}))


class Placeholders(Base):
    def test_placeholder_blocked(self):
        self.assertIn("comms.no_placeholders", self.pre(DM, {"user_id": DARNELL,
                                                             "text": "Hazmat documentation issue — [Supplier Name]."}))

    def test_underscore_placeholder_blocked(self):
        self.assertIn("comms.no_placeholders_fields", self.pre(POST, {
            "channel_id": DOCK, "text": "TRUCK HOLD: [Receipt_ID], [Supplier_Name]."}))

    def test_filled_ok(self):
        found = self.pre(POST, {"channel_id": DOCK, "text": HOLD})
        self.assertNotIn("comms.no_placeholders", found)
        self.assertNotIn("comms.no_placeholders_fields", found)


if __name__ == "__main__":
    unittest.main()
