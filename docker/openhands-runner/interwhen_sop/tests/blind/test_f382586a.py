"""Blind unit tests for logistics_prairie_star_creamery_f382586a (fixtures from the task environment only)."""

from __future__ import annotations

from interwhen_sop.tests.base import TaskCase

M = "2026-04-14-001"
DIRECTOR, DCM, JACOB = "daniel.reyes@prairiestar.com", "carlos.mendoza@prairiestar.com", "jacob.patel@prairiestar.com"
SEND, POST, DM = "google_mail__send_email", "slack__post_message", "slack__send_dm"

DIRECTOR_EMAIL = {
    "to": DIRECTOR, "cc": f"{DCM}, {JACOB}", "subject": f"P2 – Inbound Waco Manifest {M} – 2026-04-14",
    "body": f"Daniel,\n\nManifest {M} received with two P3 events (Tier 3 temp -4.5/-5/-8°F, avg -6°F; third minor "
            "variance -2 cases SC-001 in 30 days), treated as P2. Please advise whether to proceed with put-away or "
            "hold. Product is on hold.\n\nRegards"}
JACOB_EMAIL = {
    "to": JACOB, "cc": DCM, "subject": f"P3 – Inbound Waco Manifest {M} – 2026-04-14",
    "body": f"Jacob,\n\nManifest {M}: temperature readings -4.5°F, -5°F, -8°F (average -6°F). Tier 3 - product is "
            "flagged for enhanced expiry monitoring.\nVariance: SC-001 received 218 vs 220, -2 cases. This is the "
            "third minor variance in 30 days (repeated pattern). Please provide an explanation or credit.\n\nRegards"}
P2_POST = {"channel_id": "C002", "text": f"P2 escalation. Manifest {M}. Tier 3 temp + 3rd minor variance. Email sent."}
BRANDON_DM = {"user_id": "U007", "text": f"Heads up: manifest {M} (SC-001, SC-006) is on hold pending Director "
                                         "assessment, not available for picking yet. Existing H-A stock unaffected."}

RLOG_FILL = (
    "ws=wb.active\n"
    "assert ws.cell(13,2).value=='2026-04-14-001'\n"
    "vals={7:22,8:438,9:-4.5,10:-5,11:-8,13:'Tier 3',16:'None',"
    "17:'A-20260411-01 (SC-001, 218 cases), A-20260411-02 (SC-006, 220 cases)',18:'Hold',19:'P2',"
    "20:'Open — Pending P2 Assessment',21:'Compound P2. Third Repeated Minor Variance Pattern - P3'}\n"
    "for c,v in vals.items(): ws.cell(13,c).value=v\n")
TLOG_FILL = (
    "ws=wb['April 2026']\n"
    "vals=iter([-4.5,-5,-8])\n"
    "for row in ws.iter_rows(min_row=2):\n"
    "    if row[6].value=='2026-04-14-001':\n"
    "        row[2].value=next(vals); row[4].value='Y'\n")


class Base(TaskCase):
    TASK = "logistics_prairie_star_creamery_f382586a"

    def finish(self, skip=()):
        if "rlog" not in skip:
            self.edit("inbound_receiving_log.xlsx", RLOG_FILL)
        if "tlog" not in skip:
            self.edit("temperature_log.xlsx", TLOG_FILL)
        for key, tool, args in (("director", SEND, DIRECTOR_EMAIL), ("jacob", SEND, JACOB_EMAIL),
                                ("post", POST, P2_POST), ("brandon", DM, BRANDON_DM)):
            if key not in skip:
                self.did(tool, args)


class Golden(Base):
    def test_initial_state_lists_obligations(self):
        d = self.done()
        for rid in ("f382586a.comms.messages_sent", "f382586a.rlog_row", "f382586a.templog", "f382586a.dispatcher"):
            self.assertIn(rid, d)
        for rid in ("f382586a.rlog_other", "f382586a.templog_other", "f382586a.no_putaway_records"):
            self.assertNotIn(rid, d)

    def test_golden_path(self):
        self.finish()
        self.assertEqual(self.done(), {})

    def test_golden_messages_pass_pre(self):
        for tool, args in ((SEND, DIRECTOR_EMAIL), (SEND, JACOB_EMAIL), (POST, P2_POST), (DM, BRANDON_DM)):
            self.assertEqual(self.pre(tool, args), set(), args)


class Comms(Base):
    def test_director_email_missing_cc_blocked(self):
        bad = dict(DIRECTOR_EMAIL, cc=DCM)
        self.assertIn("f382586a.comms.messages", self.pre(SEND, bad))

    def test_director_email_wrong_priority_blocked(self):
        bad = dict(DIRECTOR_EMAIL, subject=f"P3 – Inbound Waco Manifest {M} – 2026-04-14")
        self.assertIn("f382586a.comms.messages", self.pre(SEND, bad))

    def test_director_email_missing(self):
        self.finish(skip=("director",))
        self.assertIn("Director", self.done().get("f382586a.comms.messages_sent", ""))

    def test_tier3_email_missing_average_blocked(self):
        bad = dict(JACOB_EMAIL, body=JACOB_EMAIL["body"].replace(" (average -6°F)", ""))
        self.assertIn("f382586a.comms.messages", self.pre(SEND, bad))

    def test_variance_email_missing_pattern_blocked(self):
        bad = dict(JACOB_EMAIL, body=f"Jacob,\nManifest {M}: SC-001 short -2 cases. Please explain.\n")
        self.assertIn("f382586a.comms.messages", self.pre(SEND, bad))

    def test_jacob_only_cc_not_enough(self):
        self.finish(skip=("jacob",))
        d = self.done_all()
        self.assertTrue(any("Production Planner" in p for r, p in d if r == "f382586a.comms.messages_sent"))
        self.assertTrue(any("variance notice" in p for r, p in d if r == "f382586a.comms.messages_sent"))

    def test_p2_post_format(self):
        bad = {"channel_id": "C002", "text": f"Escalation for manifest {M}: tier 3 and variance."}
        self.assertIn("f382586a.comms.messages", self.pre(POST, bad))

    def test_p2_post_missing(self):
        self.finish(skip=("post",))
        self.assertIn("dc-escalations", self.done().get("f382586a.comms.messages_sent", ""))

    def test_unrelated_channel_post_not_blocked(self):
        ok = {"channel_id": "C001", "text": f"Manifest {M} received with flags. Receipt on hold pending Director."}
        self.assertEqual(self.pre(POST, ok), set())


class Records(Base):
    def test_status_closed_flagged(self):
        self.finish()
        self.edit("inbound_receiving_log.xlsx", "wb.active.cell(13,20).value='Closed – Accepted'")
        self.assertIn("Status", self.done().get("f382586a.rlog_row", ""))

    def test_tier_wrong_flagged(self):
        self.finish()
        self.edit("inbound_receiving_log.xlsx", "wb.active.cell(13,13).value='Tier 2'")
        self.assertIn("Tier 3", self.done().get("f382586a.rlog_row", ""))

    def test_priority_and_note(self):
        self.finish()
        self.edit("inbound_receiving_log.xlsx", "wb.active.cell(13,19).value='P3'\nwb.active.cell(13,21).value='x'")
        probs = [p for r, p in self.done_all() if r == "f382586a.rlog_row"]
        self.assertTrue(any("P2" in p and "Priority" in p for p in probs))
        self.assertTrue(any("Third Repeated Minor Variance Pattern - P3" in p for p in probs))

    def test_other_rlog_row_edited(self):
        self.finish()
        self.edit("inbound_receiving_log.xlsx", "wb.active.cell(3,21).value='changed'")
        self.assertIn("f382586a.rlog_other", self.done())

    def test_templog_missing(self):
        self.finish(skip=("tlog",))
        self.assertIn("f382586a.templog", self.done())

    def test_templog_extra_row(self):
        self.finish()
        self.edit("temperature_log.xlsx", "wb['April 2026'].append(['2026-04-14','H-A',-19,'End-of-shift','Y','-22 to -18','—','AN'])")
        self.assertIn("f382586a.templog_other", self.done())

    def test_inventory_row_added_flagged(self):
        self.finish()
        self.edit("inventory_master.xlsx", "wb.active.append(['SC-001','Sweet Cream Prairie','A-20260411-01','2026-04-11',"
                                           "'2027-10-11',218,'H-A','','Active','2026-04-14','',''])")
        self.assertIn("f382586a.no_putaway_records", self.done())

    def test_expiry_row_added_flagged(self):
        self.finish()
        self.edit("expiry_tracker.xlsx", "wb['Expiry Tracker'].append(['SC-006','Salted Honey Drift','A-20260411-02','H-A'])")
        self.assertIn("f382586a.no_putaway_records", self.done())

    def test_personal_copy_flagged(self):
        self.finish()
        self.assertNotIn("f382586a.no_copies", self.done())
        import shutil
        shutil.copy(self.tmp / "workdir" / "inbound_receiving_log.xlsx", self.tmp / "workdir" / "my_copy.xlsx")
        self.assertIn("f382586a.no_copies", self.done())


class Pre(Base):
    def test_putaway_go_blocked(self):
        bad = {"channel_id": "C001", "text": f"Manifest {M} received with flags. Dock crew may proceed with put-away."}
        self.assertIn("f382586a.no_putaway_go", self.pre(POST, bad))

    def test_putaway_question_allowed(self):
        self.assertNotIn("f382586a.no_putaway_go", self.pre(SEND, DIRECTOR_EMAIL))
        ok = {"channel_id": "C001", "text": f"@a.nguyen Manifest {M}: do not proceed with put-away; hold as received."}
        self.assertNotIn("f382586a.no_putaway_go", self.pre(POST, ok))

    def test_mass_tag_blocked(self):
        self.assertIn("f382586a.no_mass_tag", self.pre(POST, {"channel_id": "C001", "text": "@here manifest update"}))
        self.assertNotIn("f382586a.no_mass_tag", self.pre(POST, {"channel_id": "C001", "text": "@c.mendoza update"}))

    def test_duplicate_subject_blocked(self):
        self.did(SEND, JACOB_EMAIL)
        again = dict(JACOB_EMAIL, body="Jacob, one more note about the manifest.")
        self.assertIn("f382586a.dup_subject", self.pre(SEND, again))
        other = dict(again, subject=f"P3 – Variance Notification – {M} – 2026-04-14")
        self.assertNotIn("f382586a.dup_subject", self.pre(SEND, other))

    def test_readonly_manifest(self):
        bad = {"file_path": "/workdir/transfer_manifests/2026-04-14-001.pdf", "content": "x"}
        self.assertIn("f382586a.readonly", self.pre("syntara__writeFile", bad))
        ok = {"file_path": "/workdir/notes_scratch.txt", "content": "x"}
        self.assertNotIn("f382586a.readonly", self.pre("syntara__writeFile", ok))

    def test_placeholders_blocked(self):
        bad = dict(DIRECTOR_EMAIL, body=DIRECTOR_EMAIL["body"] + "\nManifest [Manifest#]")
        self.assertIn("comms.no_placeholders", self.pre(SEND, bad))

    def test_dispatcher_missing(self):
        self.finish(skip=("brandon",))
        self.assertIn("f382586a.dispatcher", self.done())
        self.did(POST, {"channel_id": "C001", "text": f"@b.keller SC-006 from manifest {M} is on hold, not available yet."})
        self.assertNotIn("f382586a.dispatcher", self.done())
