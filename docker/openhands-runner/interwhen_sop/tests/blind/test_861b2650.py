"""Blind unit tests for logistics_prairie_star_creamery_861b2650 (fixtures from the task seed only)."""

from __future__ import annotations

import unittest

from interwhen_sop.tests.base import TaskCase

DIRECTOR = "daniel.reyes@prairiestar.com"
DCM = "carlos.mendoza@prairiestar.com"
PROC = "marcus.liu@prairiestar.com"
VENDOR = "t.downes@texpal.com"
DM_URGENT = "URGENT: Pest Contamination – TexPal Logistics shipment received 2026-04-01"
POST_URGENT = "URGENT: issue with TexPal Logistics for shipment received on 2026-04-01"
OOS_DM = "OUT OF SCOPE: Delivery Waiting!!!!!!! -- please advise"
IR = "IR-2026-04-01-Contamination.pdf"
E7 = {"to": VENDOR, "cc": f"{DIRECTOR}, {PROC}",
      "subject": "PRIORITY – Shipment Rejection – Manifest TP56734 – 2026-04-01",
      "body": "Ty,\n\nManifest TP56734 rejected on 2026-04-01.\nReason: Class 4 Contamination\n"
              "Action required: Provide return transportation or Credit\nPlease respond ASAP.\n\n"
              "Regards,\nPrairie Star Creamery"}
REVIEW = {"to": DCM, "subject": f"{IR} for review", "body": "", "attachments": [f"/workdir/{IR}"]}


def pdf(lines: list[str]) -> bytes:
    """Minimal one-page PDF with the given text lines."""
    content = "BT /F1 11 Tf 72 720 Td 14 TL " + " ".join(f"({x}) Tj T*" for x in lines) + " ET"
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
            "/Resources << /Font << /F1 5 0 R >> >> >>",
            f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
            "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    out, offs = "%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out.encode()))
        out += f"{i} 0 obj\n{o}\nendobj\n"
    x = len(out.encode())
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n" + "".join(f"{o:010d} 00000 n \n" for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n"
    return out.encode()


IR_PDF = pdf(["Prairie Star Creamery", "Incident Report", "Incident Date: 2026-04-01",
              "Incident Category: Contamination", "Priority Level: P1"])


class Base(TaskCase):
    TASK = "logistics_prairie_star_creamery_861b2650"

    def comms_ok(self):
        self.did("slack__send_dm", {"user_id": "U007", "text": DM_URGENT})
        self.did("google_mail__forward_email", {"email_id": "2", "to": f"{DIRECTOR}, {DCM}"})
        self.did("slack__post_message", {"channel_id": "C005", "text": POST_URGENT})
        self.did("slack__post_message", {"channel_id": "C002", "text": POST_URGENT})
        self.did("google_mail__send_email", E7)
        self.did("google_mail__send_email", REVIEW)
        self.did("slack__send_dm", {"user_id": "U007", "text": OOS_DM})
        self.did("google_mail__forward_email", {"email_id": "1", "to": DCM})

    def files_ok(self):
        self.edit("inbound_receiving_log.xlsx",
                  "ws['H2']='Class 4'\nws['I2']='Rejected – Class 4 Contamination'\n"
                  "ws['J2']='Rodent droppings on 4-5 pallets. P1.'")
        self.write(IR, IR_PDF)


class GoldenPath(Base):
    def test_initial_obligations(self):
        rules = {r for r, _ in self.done_all()}
        self.assertEqual(rules, {"comms.messages_sent", "receiving_log.texpal_rejection",
                                 "incident_report.contamination"})
        self.assertEqual(sum(r == "comms.messages_sent" for r, _ in self.done_all()), 8)

    def test_full_correct_end_state(self):
        self.comms_ok()
        self.files_ok()
        self.assertEqual(self.done(), {})


class P1Messages(Base):
    def test_urgent_dm(self):
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U007", "text": DM_URGENT + ". Rodent droppings."}),
                         set())
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U007", "text": "URGENT: TexPal pests found"}),
                         {"comms.messages"})

    def test_forward_both(self):
        self.assertEqual(self.pre("google_mail__forward_email", {"email_id": "2", "to": f"{DIRECTOR}, {DCM}"}), set())
        self.assertEqual(self.pre("google_mail__forward_email", {"email_id": "2", "to": DIRECTOR, "cc": DCM}), set())
        self.assertEqual(self.pre("google_mail__forward_email", {"email_id": "2", "to": DIRECTOR}), {"comms.messages"})

    def test_channel_posts(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C005", "text": POST_URGENT}), set())
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C002", "text": POST_URGENT + " Manifest TP56734."}),
                         set())
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C002", "text":
                                  "P2 Escalation. Detail: pest droppings on TexPal pallets."}), {"comms.messages"})

    def test_e7(self):
        self.assertEqual(self.pre("google_mail__send_email", E7), set())
        self.assertEqual(self.pre("google_mail__send_email", {**E7, "subject": "PRIORITY – Shipment Rejection – TP56734 – 2026-04-01"}),
                         set())
        bad_reason = {**E7, "body": E7["body"].replace("Reason: Class 4 Contamination", "Reason: Pest contamination")}
        self.assertEqual(self.pre("google_mail__send_email", bad_reason), {"comms.messages"})
        self.assertEqual(self.pre("google_mail__send_email", {**E7, "cc": DIRECTOR}), {"comms.messages"})
        self.assertEqual(self.pre("google_mail__send_email", {**E7, "subject": "Rejection of TP56734"}),
                         {"comms.messages"})

    def test_ir_review(self):
        self.assertEqual(self.pre("google_mail__send_email", REVIEW), set())
        self.assertEqual(self.pre("google_mail__send_email", {**REVIEW, "body": "Please review."}), {"comms.messages"})
        self.assertEqual(self.pre("google_mail__send_email", {**REVIEW, "attachments": []}), {"comms.messages"})

    def test_duplicate_blocked(self):
        self.did("slack__send_dm", {"user_id": "U007", "text": DM_URGENT})
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U007", "text": DM_URGENT}), {"comms.messages"})

    def test_messages_sent_completion(self):
        self.comms_ok()
        self.assertNotIn("comms.messages_sent", self.done())


class OutOfScope(Base):
    def test_oos_dm(self):
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U007", "text": OOS_DM}), set())
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U007", "text": OOS_DM + ". Driver at gate 20 min."}),
                         {"comms.messages"})

    def test_oos_forward(self):
        self.assertEqual(self.pre("google_mail__forward_email", {"email_id": "1", "to": DCM,
                                                                 "body": "Driver waiting at the gate."}), set())
        self.assertEqual(self.pre("google_mail__forward_email", {"email_id": "1", "to": f"{DCM}, {DIRECTOR}"}),
                         {"comms.messages"})

    def test_gate_quiet(self):
        self.assertEqual(self.pre("google_mail__reply_to_email", {"email_id": "1", "body": "Sending someone now"}),
                         {"comms.messages"})
        self.assertEqual(self.pre("google_mail__send_email", {"to": VENDOR, "subject": "Gate", "body": "On it"}),
                         {"comms.messages"})
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C001", "text": "TexPal driver waiting at gate"}),
                         {"comms.messages"})
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U008", "text": "Can you let the driver in at the gate?"}),
                         {"comms.messages"})


class P4Quiet(Base):
    def test_freezer(self):
        self.assertEqual(self.pre("google_mail__reply_to_email", {"email_id": "4", "body": "-28C is -18.4F, fine."}),
                         {"comms.messages"})
        self.assertEqual(self.pre("google_mail__send_email", {"to": DCM, "subject": "Freezer Temp H-A",
                                                              "body": "H-A reading -28 C"}), {"comms.messages"})
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C005", "text": "Zone H-A freezer reading -28C"}),
                         {"comms.messages"})

    def test_hannah(self):
        self.assertEqual(self.pre("google_mail__reply_to_email", {"email_id": "3", "body": "Thanks Hannah"}),
                         {"comms.messages"})
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U004", "text": "Thanks for the heads up"}),
                         {"comms.messages"})

    def test_sarah_no_reply(self):
        self.assertEqual(self.pre("google_mail__reply_to_email", {"email_id": "2", "body": "Thanks, escalating"}),
                         {"comms.messages"})

    def test_unrelated_message_not_blocked(self):
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C007", "text": "Inventory counts look fine today"}),
                         set())


class Placeholders(Base):
    def test_placeholder(self):
        self.assertIn("comms.no_placeholders",
                      self.pre("slack__send_dm", {"user_id": "U007", "text": "URGENT: Pest Contamination – [Vendor Name] x"}))
        self.assertNotIn("comms.no_placeholders", self.pre("slack__send_dm", {"user_id": "U007", "text": DM_URGENT}))


class ReceivingLog(Base):
    def test_wrong_status(self):
        self.edit("inbound_receiving_log.xlsx", "ws['H2']='Class 4'\nws['I2']='Rejected – Pest Contamination'")
        self.assertIn("Status must be exactly", self.done()["receiving_log.texpal_rejection"])

    def test_wrong_damage(self):
        self.edit("inbound_receiving_log.xlsx", "ws['H2']='4'\nws['I2']='Rejected – Class 4 Contamination'")
        self.assertIn("Damage Class", self.done()["receiving_log.texpal_rejection"])

    def test_ok(self):
        self.edit("inbound_receiving_log.xlsx", "ws['H2']='Class 4'\nws['I2']='Rejected - Class 4 Contamination'")
        self.assertNotIn("receiving_log.texpal_rejection", self.done())

    def test_extra_row(self):
        self.edit("inbound_receiving_log.xlsx", "ws.append(['2026-04-01','TP56734-B','Ashdown, AR',5,0])")
        self.assertIn("logs.no_unrequested_rows", self.done())

    def test_no_extra_row(self):
        self.assertNotIn("logs.no_unrequested_rows", self.done())


class TemperatureLog(Base):
    def test_new_row_flagged(self):
        self.edit("temperature_log.xlsx", "ws.append(['2026-04-01','08:30','H-A',-18.4,'Spot-check','Y','N/A','IOA'])",
                  sheet="Apr 26")
        self.assertIn("logs.no_unrequested_rows", self.done())

    def test_existing_row_correction_not_flagged(self):
        self.edit("temperature_log.xlsx", "ws['D2']=-18.4\nws['F2']='Y'", sheet="Apr 26")
        found = self.done()
        self.assertNotIn("logs.no_unrequested_rows", found)
        self.assertNotIn("temperature_log.append_only", found)

    def test_march_edit_flagged(self):
        self.edit("temperature_log.xlsx", "ws['D2']=-25", sheet="Mar 26")
        self.assertIn("temperature_log.append_only", self.done())


class Inventory(Base):
    def test_changed(self):
        self.edit("inventory_master.xlsx", "ws['G2']='Hold'")
        self.assertIn("inventory_master.unchanged", self.done())

    def test_unchanged(self):
        self.assertNotIn("inventory_master.unchanged", self.done())


class IncidentReport(Base):
    def test_missing(self):
        self.assertIn("Create the incident report", self.done()["incident_report.contamination"])

    def test_missing_priority(self):
        self.write(IR, pdf(["Incident Date: 2026-04-01", "Incident Category: Contamination", "Priority Level: high"]))
        self.assertIn("Priority Level: P1", self.done()["incident_report.contamination"])

    def test_ok(self):
        self.write(IR, IR_PDF)
        self.assertNotIn("incident_report.contamination", self.done())

    def test_extra_report(self):
        self.write(IR, IR_PDF)
        self.write("IR-2026-04-01-Temperature.pdf", pdf(["Incident Category: Temperature"]))
        self.assertIn("incident_report.only_required", self.done())
        self.assertNotIn("incident_report.contamination", self.done())


class PersonalCopies(Base):
    def test_python_copy_blocked(self):
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/inventory_master.xlsx')\n"
                "wb.save('/workdir/inventory_master_backup.xlsx')")
        self.assertIn("files.no_personal_copies", self.pre("syntara__executePython", {"code": code}))

    def test_bash_copy_blocked(self):
        self.assertIn("files.no_personal_copies",
                      self.pre("syntara__executeBash", {"command": "cp /workdir/inventory_master.xlsx ~/my_copy.xlsx"}))

    def test_new_sheet_blocked(self):
        code = "import openpyxl\nwb=openpyxl.Workbook()\nwb.save('/workdir/tracker.xlsx')"
        self.assertIn("files.no_personal_copies", self.pre("syntara__executePython", {"code": code}))

    def test_official_write_allowed(self):
        code = ("import openpyxl\nwb=openpyxl.load_workbook('/workdir/inbound_receiving_log.xlsx')\n"
                "wb.active['I2']='Rejected – Class 4 Contamination'\nwb.save('/workdir/inbound_receiving_log.xlsx')")
        self.assertEqual(self.pre("syntara__executePython", {"code": code}), set())

    def test_copy_at_end(self):
        self.write("inventory_master_backup.xlsx", b"x")
        self.assertIn("files.no_personal_copies_end", self.done())

    def test_no_copy_at_end(self):
        self.write("make_ir.py", "print(1)")
        self.assertNotIn("files.no_personal_copies_end", self.done())


if __name__ == "__main__":
    unittest.main()
