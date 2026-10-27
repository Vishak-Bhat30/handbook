import unittest

from interwhen_sop.tests.base import TaskCase

T = "medical_pathfinder_billing_and_coding_073e602b"

CLAIMS = [
    ("HIC-19887899", "2025-12-01", 80, 70), ("HIC-19887900", "2025-12-01", 80, 70),
    ("HIC-19887901", "2025-12-03", 80, 70), ("HIC-25124778", "2025-12-10", 80, 70),
    ("HIC-25124779", "2025-12-12", 80, 70), ("HIC-25124780", "2025-12-15", 80, 70),
    ("HIC-26877757", "2025-12-29", 80, 70), ("HIC-26877758", "2026-01-02", 75, 65),
    ("HIC-26877795", "2026-01-05", 75, 65),
]
IDS = [c[0] for c in CLAIMS]
HELD = ["HIC-26877757", "HIC-26877758", "HIC-26877795"]

DISPUTE_SUBJ = "Contractual Rate Dispute \u2014 Hull Insurance / A4789P / CPT 11241"
DISPUTE_BODY = (
    "Dear Ursula James,\n\nI am writing on behalf of Pathfinder Billing and Coding to formally dispute the payment "
    "amounts received for CPT 11241 under Payer ID A4789P. The following claim(s) were paid below the contracted "
    "rate with no adjustment reason code provided:\n\n"
    + "\n".join(f"{c} | {d} | Contracted: ${r} | Paid: ${p} | Variance: ${r - p}" for c, d, r, p in CLAIMS)
    + "\n\nTotal outstanding variance: $90\n\nWe request review and remittance of the outstanding balance within [X] "
      "Business Days. Please confirm receipt of this dispute and provide a reference number for tracking.\n\n"
      "Joe Malfroy | Pathfinder Billing and Coding | rcm@pathfinder.com")
PATTERN_SUBJ = "Pattern Recurrence \u2014 Hull Insurance / A4789P / CPT 11241"
PATTERN_BODY = (
    "Joe, I am escalating a pattern recurrence for Hull Insurance (A4789P) affecting 9 claims for CPT 11241. All "
    "instances share the same discrepancy:\n\n"
    + "\n".join(f"{c} | Contracted: ${r} | Paid: ${p}" for c, _, r, p in CLAIMS)
    + "\n\nTotal variance: $90.\n\nPathfinder Billing and Coding | rcm@pathfinder.com")

DRAFT = ("google_mail__save_draft", {"to": "ursula.james@hull.com", "subject": DISPUTE_SUBJ, "body": DISPUTE_BODY})
REPORT = ("google_mail__send_email", {"to": "joem@pathfinder.com", "subject": PATTERN_SUBJ, "body": PATTERN_BODY})
CAL = ("google_calendar__create_event", {
    "summary": "Escalation - Pattern Recurrence - Hull Insurance (A4789P) CPT 11241",
    "start": {"dateTime": "2026-02-17T10:30:00-06:00"}, "end": {"dateTime": "2026-02-17T11:00:00-06:00"},
    "description": "Escalated to RCM Manager"})


class Base(TaskCase):
    TASK = T

    def hold(self, ids=HELD, value="Held - Contractual Variance"):
        self.edit("PBC_Claim_Register.xlsx",
                  f"for r in range(2, ws.max_row+1):\n"
                  f"    if ws.cell(r, col['Claim_ID']).value in {list(ids)!r}:\n"
                  f"        ws.cell(r, col['Payment_Post_Status']).value = {value!r}")

    def ra(self, ids=IDS, trig="CO-45", staff="Joe Malfroy", status="Open"):
        self.edit("PBC_RA_Queue.xlsx", "\n".join(
            f"ws.append([{c!r}, {trig!r}, '02/17/2026', {staff!r}, {status!r}])" for c in ids))

    def worklist(self, ids=IDS, action="Appeal - Contractual Rate Dispute", status="Escalated"):
        self.edit("PBC_Denial_Worklist.xlsx", "\n".join(
            f"ws.append(['Contractual/Payer Error', {c!r}, 'CO-45', {action!r}, '02/17/2026', {status!r}])" for c in ids))

    def esc(self, ids=IDS, cat="Operational", reason="Pattern Recurrence", times=1):
        self.edit("PBC_Escalation_Log.xlsx", "\n".join(
            [f"ws.append([{', '.join(ids)!r}, 'A4789P', {cat!r}, {reason!r}, 'RCM Manager on 02/17/2026'])"] * times))

    def golden(self, skip=()):
        if "hold" not in skip:
            self.hold()
        if "ra" not in skip:
            self.ra()
        if "wl" not in skip:
            self.worklist()
        if "esc" not in skip:
            self.esc()
        if "cal" not in skip:
            self.did(*CAL)
        if "draft" not in skip:
            self.did(*DRAFT)
        if "report" not in skip:
            self.did(*REPORT)


class TestInitialAndGolden(Base):
    def test_initial_obligations(self):
        got = {r for r, _ in self.done_all()}
        self.assertEqual(got, {"pbc.claim_register", "pbc.ra_queue", "pbc.denial_worklist", "pbc.escalation_log",
                               "pbc.escalation_calendar", "pbc.comms.messages_sent"})

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})


class TestClaimRegister(Base):
    def test_held_missing(self):
        self.golden(skip=("hold",))
        self.assertIn("pbc.claim_register", self.done())

    def test_reconciled_changed(self):
        self.golden()
        self.hold(["HIC-19887899"])
        self.assertIn("Reconciled", self.done()["pbc.claim_register"])

    def test_written_off(self):
        self.golden()
        self.edit("PBC_Claim_Register.xlsx",
                  "for r in range(2, ws.max_row+1):\n"
                  "    if ws.cell(r, col['Claim_ID']).value == 'HIC-25124778':\n"
                  "        ws.cell(r, col['Claim_Status']).value = 'Written Off'")
        self.assertIn("pbc.claim_register", self.done())

    def test_in_recovery_ok(self):
        self.golden()
        self.edit("PBC_Claim_Register.xlsx",
                  "for r in range(2, ws.max_row+1):\n"
                  f"    if ws.cell(r, col['Claim_ID']).value in {IDS!r}:\n"
                  "        ws.cell(r, col['Claim_Status']).value = 'In Recovery'")
        self.assertEqual(self.done(), {})


class TestQueues(Base):
    def test_ra_wrong_staff(self):
        self.golden(skip=("ra",))
        self.ra(staff="Russell Commy")
        self.assertIn("pbc.ra_queue", self.done())

    def test_ra_partial(self):
        self.golden(skip=("ra",))
        self.ra(ids=IDS[:6])
        self.assertIn("HIC-26877757", self.done()["pbc.ra_queue"])

    def test_worklist_wrong_status(self):
        self.golden(skip=("wl",))
        self.worklist(status="Pending Review")
        self.assertIn("pbc.denial_worklist", self.done())

    def test_worklist_wrong_action(self):
        self.golden(skip=("wl",))
        self.worklist(action="Write Off")
        self.assertIn("pbc.denial_worklist", self.done())


class TestEscalationLog(Base):
    def test_missing(self):
        self.golden(skip=("esc",))
        self.assertIn("pbc.escalation_log", self.done())

    def test_duplicate(self):
        self.golden(skip=("esc",))
        self.esc(times=2)
        self.assertIn("single", self.done()["pbc.escalation_log"])

    def test_wrong_category(self):
        self.golden(skip=("esc",))
        self.esc(cat="Critical")
        self.assertIn("Operational", self.done()["pbc.escalation_log"])

    def test_category_long_form_ok(self):
        self.golden(skip=("esc",))
        self.esc(cat="Operational (under $5,000)")
        self.assertEqual(self.done(), {})

    def test_missing_claims(self):
        self.golden(skip=("esc",))
        self.esc(ids=IDS[:5])
        self.assertIn("pbc.escalation_log", self.done())

    def test_existing_row_edited(self):
        self.golden()
        self.edit("PBC_Escalation_Log.xlsx", "ws.cell(2, 3).value = 'Operational'")
        self.assertIn("pbc.escalation_log_append_only", self.done())


class TestCalendar(Base):
    def test_missing(self):
        self.golden(skip=("cal",))
        self.assertIn("pbc.escalation_calendar", self.done())

    def test_wrong_day(self):
        self.golden(skip=("cal",))
        self.did("google_calendar__create_event", {**CAL[1], "start": {"dateTime": "2026-02-19T09:00:00-06:00"}})
        self.assertIn("pbc.escalation_calendar", self.done())


class TestIntegrity(Base):
    def test_fee_schedule_edit(self):
        self.golden()
        self.edit("PBC_Fee_Schedule.xlsx", "ws.cell(3, 3).value = 999", sheet="Updated for Jan 1, 2026")
        self.assertIn("pbc.sources_unchanged", self.done())

    def test_audit_log_edit(self):
        self.golden()
        self.edit("PBC_Audit_Log.xlsx", "ws.cell(3, 3).value = 'Fail - CPT Alignment'")
        self.assertIn("pbc.audit_log_append_only", self.done())

    def test_controlled_values(self):
        self.golden()
        self.hold(HELD, "On Hold - Variance")
        self.assertIn("pbc.controlled_values", self.done())


class TestComms(Base):
    def test_dispute_draft_ok(self):
        self.assertEqual(self.pre(*DRAFT), set())

    def test_dispute_sent_blocked(self):
        got = self.pre("google_mail__send_email", DRAFT[1])
        self.assertIn("pbc.comms.messages", got)
        self.assertIn("pbc.no_external_send", got)

    def test_dispute_wrong_total(self):
        bad = {**DRAFT[1], "body": DISPUTE_BODY.replace("variance: $90", "variance: $60")}
        self.assertIn("pbc.comms.messages", self.pre("google_mail__save_draft", bad))

    def test_dispute_missing_claim(self):
        bad = {**DRAFT[1], "body": DISPUTE_BODY.replace("HIC-26877795 | 2026-01-05", "")}
        self.assertIn("pbc.comms.messages", self.pre("google_mail__save_draft", bad))

    def test_dispute_wrong_subject(self):
        bad = {**DRAFT[1], "subject": "Contractual Rate Dispute - Hull"}
        self.assertIn("pbc.comms.messages", self.pre("google_mail__save_draft", bad))

    def test_dispute_placeholder_contact_ok(self):
        ok = {**DRAFT[1], "body": DISPUTE_BODY.replace("Dear Ursula James", "Dear [Payer Billing/Appeals Contact Name]")}
        self.assertEqual(self.pre("google_mail__save_draft", ok), set())

    def test_report_ok(self):
        self.assertEqual(self.pre(*REPORT), set())

    def test_report_draft_not_counted(self):
        self.golden(skip=("report",))
        self.did("google_mail__save_draft", REPORT[1])
        self.assertIn("pbc.comms.messages_sent", self.done())

    def test_report_wrong_count(self):
        bad = {**REPORT[1], "body": PATTERN_BODY.replace("affecting 9 claims", "affecting 6 claims")}
        self.assertIn("pbc.comms.messages", self.pre("google_mail__send_email", bad))

    def test_report_placeholder(self):
        bad = {**REPORT[1], "body": PATTERN_BODY.replace("Joe,", "[RCM Manager First Name],")}
        got = self.pre("google_mail__send_email", bad)
        self.assertIn("pbc.no_placeholders", got)

    def test_internal_note_not_captured(self):
        note = {"to": "joem@pathfinder.com", "subject": "Hull 11241 follow-up done",
                "body": "Contractual Rate Dispute draft saved for Hull; not sent."}
        self.assertEqual(self.pre("google_mail__send_email", note), set())

    def test_phi_wrong_recipient(self):
        bad = {**DRAFT[1], "to": "popler.wen@bulliongoldinsurance.com"}
        self.assertIn("pbc.phi_recipients", self.pre("google_mail__save_draft", bad))

    def test_external_unrelated_send(self):
        self.assertIn("pbc.no_external_send", self.pre("google_mail__send_email", {
            "to": "ursula.james@hull.com", "subject": "Question", "body": "Hello"}))


if __name__ == "__main__":
    unittest.main()
