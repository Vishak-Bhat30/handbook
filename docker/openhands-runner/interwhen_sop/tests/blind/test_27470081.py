"""Blind unit tests for logistics_prairie_star_creamery_27470081 (fixtures from the task's environment seed only)."""

import io
import zipfile

from interwhen_sop.tests.base import TaskCase

M1, M2, M3 = "2026-04-15-001", "2026-04-15-002", "2026-04-15-003"
DIR, DCM, PP, DPM = ("daniel.reyes@prairiestar.com", "carlos.mendoza@prairiestar.com",
                     "jacob.patel@prairiestar.com", "emily.carter@prairiestar.com")
E2 = f"P2 – Variance Notification – Inbound Waco Manifest {M2} – 2026-04-15"

RECV_ROWS = {
    12: dict(E=26, G=492, H=-18, I=-16, J=-20, K=-18, L="Tier 1", M=0, N=0, O="None", P="Accept – put-away after lunch",
             Q="Received – Pending Put-Away", R="P3 – Short-dated SW-008 lot C-20260201-01 (16 days, Orange)"),
    13: dict(E=26, G=522, H=-18, I=-16, J=-20, K=-18, L="Tier 1", M=2, N=0, O="None", P="Hold – Director review",
             Q="P2 – Major Variance – Open – Pending Major Variance Investigation", R="SC-006 -6; SC-008 +8"),
    14: dict(E=26, G=516, H=-5, I=-4.5, J=-4, K=-4.5, L="Tier 3", M=-4, N=-1, O="None", P="Hold – Director review",
             Q="P2 – Tier 3 temp + Moderate variance – Open – Pending Variance Resolution", R="SC-003 -4"),
}
TEMPS = [(M1, (-18, -16, -20)), (M2, (-18, -16, -20)), (M3, (-5, -4.5, -4))]


def docx_bytes(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", "<w:document><w:body>" + "".join(
            f"<w:p><w:r><w:t>{line}</w:t></w:r></w:p>" for line in text.splitlines()) + "</w:body></w:document>")
    return buf.getvalue()


def email(to, subject, body, cc=""):
    return "google_mail__send_email", {"to": to, "cc": cc, "subject": subject, "body": body}


def post(channel, text):
    return "slack__post_message", {"channel_id": channel, "text": text}


MSGS = {
    "e002": email(DIR, E2, f"Manifest {M2}: SC-006 manifest 200 / actual 194 (-6, -3%, Moderate); SC-008 manifest 160 / "
                           "actual 168 (+8, +5%, Major). Classification: Major (P2). Request immediate investigation. "
                           "Incident report IR-001-2026-04-15-Variance filed.", cc=f"{DCM}, {PP}"),
    "e003": email(DIR, f"P2 – Temperature and Variance Escalation – Inbound Waco Manifest {M3} – 2026-04-15",
                  f"Manifest {M3}: readings -5, -4.5, -4 °F, Tier 3 conditional acceptance, product flagged for enhanced "
                  "expiry monitoring. SC-003 manifest 160 / actual 156 (-4 cases, -2.5%, Moderate). Compound P2. "
                  "Incident report IR-002-2026-04-15-Variance filed.", cc=f"{DCM}, {PP}"),
    "esd_pp": email(PP, f"P3 – Inbound Short-Dated Product – Waco Manifest {M1} – 2026-04-15",
                    "Inbound short-dated product – SW-008, C-20260201-01, 16 days to expiry. Please prioritize in "
                    "outbound.", cc=DPM),
    "esd_dir": email(DIR, "P3 – Inbound Short-Dated Product – SW-008 C-20260201-01 – 2026-04-15",
                     "Inbound short-dated product – SW-008, lot C-20260201-01, 16 days to expiry (Orange). Please "
                     "provide an immediate demand plan."),
    "p001": post("C001", f"Manifest {M1} received with flags. Pallets: 26, Cases: 492, Temp: -18°F (avg), Variance: 0. "
                         "SW-008 short-dated (16 days). Pending put-away."),
    "pwaco": post("C004", f"Variance detected. Manifest {M2}, SKU SC-006, SC-008: SC-006 -6 cases (-3%), SC-008 +8 cases "
                          "(+5%). Variance tier: Major. Email sent. Status: Open – Pending response."),
    "pdc2": post("C003", f"P2 escalation. Major variance. Manifest/Reference {M2}. Detail: SC-008 +8 (+5%), SC-006 -6. "
                         "Escalated to @d.reyes. Incident report: open."),
    "pdc3": post("C003", f"P2 escalation. Tier 3 temperature + Moderate variance. Manifest/Reference {M3}. Detail: temps "
                         "-5/-4.5/-4, SC-003 -4. Escalated to @d.reyes. Incident report: open."),
}


class Base(TaskCase):
    TASK = "logistics_prairie_star_creamery_27470081"

    def fill_recv(self, rows=None):
        code = "".join(f"ws['{c}{r}']={v!r}\n" for r, d in (rows or RECV_ROWS).items() for c, v in d.items())
        self.edit("inbound_receiving_log.xlsx", code)

    def fill_temps(self, temps=TEMPS, initials="A.Nguyen"):
        lines = []
        for m, vals in temps:
            for v, pos in zip(vals, ("Front", "Middle", "Rear")):
                lines.append(f"ws.append(['2026-04-15','09:15','Inbound – Manifest {m}',{v!r},'Inbound – {pos}','Y',"
                             f"None,{initials!r}])")
        self.edit("temperature_log.xlsx", "\n".join(lines))

    def irs(self):
        self.write("incident_reports/IR-001-2026-04-15-Variance.docx", docx_bytes(f"Manifest {M2}\nPriority P2"))
        self.write("incident_reports/IR-002-2026-04-15-Variance.docx", docx_bytes(f"Manifest {M3}\nPriority P2"))

    def golden(self, skip=()):
        self.fill_recv()
        self.fill_temps()
        self.irs()
        for k, (tool, args) in MSGS.items():
            if k not in skip:
                self.did(tool, args)


class InitialState(Base):
    def test_initial_obligations(self):
        got = set(self.done())
        self.assertEqual(got, {"recv_log.fill", "recv_log.status", "temp_log.inbound", "msg.required", "ir.p2"})


class Golden(Base):
    def test_golden_path_clean(self):
        self.golden()
        self.assertEqual(self.done_all(), [])

    def test_golden_messages_pass_pre(self):
        for tool, args in MSGS.values():
            self.assertEqual(self.pre(tool, args), set(), args)


class PreRules(Base):
    def test_subject_format(self):
        self.assertIn("email.subject_format", self.pre(*email(PP, "Short dated product on 001", f"Manifest {M1} SW-008")))
        self.assertNotIn("email.subject_format", self.pre(*MSGS["esd_pp"]))
        self.assertNotIn("email.subject_format", self.pre(*email(PP, "Lunch", "unrelated")))
        self.assertNotIn("email.subject_format", self.pre(*email(DCM, "P4 – End-of-Shift Handoff – 2026-04-15 – Houston",
                                                               f"Receipts {M1}, {M2}, {M3}.")))

    def test_e2_subject(self):
        bad = email(DIR, f"P2 – Major Variance – Manifest {M2} – 2026-04-15", "x", cc=DCM)
        self.assertIn("email.e2_subject", self.pre(*bad))
        self.assertNotIn("email.e2_subject", self.pre(*MSGS["e002"]))
        ir = email(DCM, f"P2 – Incident Report IR-001 – Variance – Manifest {M2} – 2026-04-15", "IR attached")
        self.assertEqual(self.pre(*ir), set())

    def test_variance002_priority(self):
        self.assertIn("variance002.priority", self.pre(*email(PP, f"P3 – Variance Notification – {M2} – 2026-04-15", "x")))
        self.assertIn("variance002.priority", self.pre(*post("C001", f"Manifest {M2}: SC-008 +8 (Moderate, P3)")))
        self.assertNotIn("variance002.priority", self.pre(*MSGS["pwaco"]))
        self.assertNotIn("variance002.priority", self.pre(*post("C001", f"Manifest {M3}: Moderate variance")))

    def test_no_channel_mentions(self):
        self.assertIn("slack.no_channel_mentions", self.pre(*post("C001", "@here manifests received")))
        self.assertNotIn("slack.no_channel_mentions", self.pre(*MSGS["p001"]))

    def test_placeholders(self):
        self.assertIn("comms.sop_placeholders", self.pre(*post("C003", f"P2 escalation. Manifest {M2}. Detail: [brief "
                                                                        "description]. Incident report: [pending/open/closed].")))
        self.assertIn("comms.no_placeholders", self.pre(*post("C003", f"P2 escalation. Manifest {M2}. Escalated to "
                                                                      "[Recipient Name].")))
        self.assertEqual(self.pre(*MSGS["pdc2"]), set())


class ReceivingLog(Base):
    def test_fill_wrong_values(self):
        self.golden()
        self.edit("inbound_receiving_log.xlsx", "ws['G13']=520\nws['L14']='Tier 2'")
        probs = [p for r, p in self.done_all() if r == "recv_log.fill"]
        self.assertEqual(len(probs), 2)
        self.assertIn("522", probs[0])

    def test_rounded_readings_accepted(self):
        self.golden()
        self.edit("inbound_receiving_log.xlsx", "ws['I14']=-4\nws['K14']=-4\nws['M14']=4")
        self.assertNotIn("recv_log.fill", self.done())

    def test_damage_notes_blank(self):
        self.golden()
        self.edit("inbound_receiving_log.xlsx", "ws['O13']=None")
        self.assertIn("Damage Notes", self.done().get("recv_log.fill", ""))

    def test_status_put_away_complete(self):
        self.golden()
        self.edit("inbound_receiving_log.xlsx", "ws['Q12']='Put-Away Complete'")
        self.assertIn("recv_log.status", self.done())

    def test_status_missing_p2(self):
        self.golden()
        self.edit("inbound_receiving_log.xlsx", "ws['Q13']='Open – Pending Variance Resolution'\nws['R13']='SC-008 +8'")
        self.assertIn("2026-04-15-002", self.done().get("recv_log.status", ""))

    def test_one_row(self):
        self.golden()
        self.edit("inbound_receiving_log.xlsx", "ws.append(['2026-04-15','2026-04-15-002','Waco Transfer',26,26,520,522])")
        self.assertIn("recv_log.one_row", self.done())

    def test_append_only(self):
        self.golden()
        self.edit("inbound_receiving_log.xlsx", "ws['G5']=401")
        self.assertIn("logs.append_only", self.done())

    def test_prefill_identity_kept(self):
        self.golden()
        self.edit("inbound_receiving_log.xlsx", "ws['F13']=522")
        self.assertIn("logs.append_only", self.done())


class TemperatureLog(Base):
    def test_initials(self):
        self.fill_recv()
        self.fill_temps(initials="AI")
        self.assertIn("A.Nguyen", self.done().get("temp_log.inbound", ""))

    def test_order(self):
        self.fill_recv()
        self.fill_temps(temps=[TEMPS[1], TEMPS[0], TEMPS[2]])
        self.assertIn("order", self.done().get("temp_log.inbound", ""))

    def test_missing_reading(self):
        self.fill_recv()
        self.fill_temps(temps=[TEMPS[0], TEMPS[1], (M3, (-5, -4))])
        self.assertIn(M3, self.done().get("temp_log.inbound", ""))

    def test_old_reading_edited(self):
        self.golden()
        self.edit("temperature_log.xlsx", "ws['D3']=-10")
        self.assertIn("logs.append_only", self.done())


class Invariants(Base):
    def test_inventory_putaway_premature(self):
        self.golden()
        self.edit("inventory_master.xlsx", "ws.append(['SW-008','Huckleberry Lemon Sorbet','C-20260201-01','2026-02-01',"
                                           "'2026-05-01',16,12,'H-C','H-C-12','Active','2026-04-15'])")
        self.assertIn("inventory.no_putaway", self.done())

    def test_inventory_note_only_ok(self):
        self.golden()
        self.edit("inventory_master.xlsx", "ws['N29']='SHORT-DATED – ACCELERATE OUTBOUND'")
        self.assertNotIn("inventory.no_putaway", self.done())

    def test_manifest_read_only(self):
        self.golden()
        self.edit("2026-04-15-002.xlsx", "ws['H13']=194")
        self.assertIn("files.read_only", self.done())

    def test_no_copies(self):
        self.golden()
        self.write("receiving_copy.xlsx", (self.tmp / "workdir" / "inbound_receiving_log.xlsx").read_bytes())
        self.assertIn("files.no_copies", self.done())


class Messages(Base):
    def test_missing_short_dated_director(self):
        self.golden(skip=("esd_dir",))
        self.assertIn("Director", self.done().get("msg.required", ""))

    def test_major_email_wrong_recipients(self):
        self.golden(skip=("e002",))
        self.did(*email(PP, E2, MSGS["e002"][1]["body"], cc=DCM))
        self.assertIn(f"To {DIR}", self.done().get("msg.required", ""))

    def test_waco_post_needs_major(self):
        self.golden(skip=("pwaco",))
        self.did(*post("C004", f"Variance detected. Manifest {M2}, SKU SC-006, SC-008: -6 / +8. Variance tier: Moderate "
                               "and P2."))
        self.assertIn("Major", self.done().get("msg.required", ""))

    def test_dc_escalations_needs_p2_prefix(self):
        self.golden(skip=("pdc3",))
        self.did(*post("C003", f"Escalation for manifest {M3}: P2. Incident report: open."))
        self.assertIn("P2", self.done().get("msg.required", ""))

    def test_pp_temperature_email(self):
        self.golden(skip=("e003",))
        self.did(*email(DIR, f"P2 – Escalation – Inbound Waco Manifest {M3} – 2026-04-15",
                        f"Manifest {M3} Tier 3. SC-003 160 vs 156. Incident report filed.", cc=DCM))
        out = self.done().get("msg.required", "")
        self.assertIn("Production Planner", out)

    def test_combined_003_email_ok(self):
        self.golden()
        self.assertNotIn("msg.required", self.done())


class IncidentReports(Base):
    def test_missing_ir(self):
        self.golden()
        (self.tmp / "workdir" / "incident_reports" / "IR-002-2026-04-15-Variance.docx").unlink()
        self.assertIn(M3, self.done().get("ir.p2", ""))

    def test_badly_named_ir(self):
        self.golden()
        (self.tmp / "workdir" / "incident_reports" / "IR-002-2026-04-15-Variance.docx").rename(
            self.tmp / "workdir" / "incident_reports" / "incident_003.docx")
        self.assertIn("incident_003.docx", self.done().get("ir.p2", ""))

    def test_route_to_dcm(self):
        self.fill_recv()
        self.fill_temps()
        self.irs()
        for k, (tool, args) in MSGS.items():
            args = dict(args)
            if tool.startswith("google_mail"):
                args["body"] = args["body"].replace("Incident report", "Report").replace("IR-00", "R-00")
            self.did(tool, args)
        self.assertIn("DC Manager", self.done().get("ir.p2", ""))
