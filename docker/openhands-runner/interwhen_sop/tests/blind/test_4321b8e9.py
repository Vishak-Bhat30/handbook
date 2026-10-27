"""Blind unit tests for insurance_vanguard_shield_mutual_4321b8e9 (fixtures from the task environment only)."""

from __future__ import annotations

from interwhen_sop.tests.base import TaskCase

W14, W19, W23 = "INTL-2026-0214", "INTL-2026-0219", "INTL-2026-0223"
BOOK = "Wire_Population_Q1_2026.xlsx"
DESC = ("[Wire Control Exception] Wire ID: INTL-2026-0223\nOPS-TRE-WIRE issue: OPS-TRE-WIRE-INTL-2026-0223\n"
        "Population source: International wires population workbook from OPS-TRE-WIRES-Q1-2026\n"
        "Slack evidence: Channel #treasury-wires | Queries attempted: (1) has:link INTL-2026-0223 "
        "(2) in:#treasury-wires INTL-2026-0223 (3) in:#treasury-wires \"INTL-2026-0223\" | Result: query (1) "
        "has:link worked\n"
        "Approvers found: Claire Overton / VP, Treasury Operations / Approved. for Approver 1; Missing dual approval\n"
        "Exception code applied on wire issue: TRE-900 High-Risk Exception\n"
        "Action requested: Chief Compliance Officer (per Compliance-Alerts board pinned issue) to determine "
        "corrective action and whether wire may proceed.")
TITLE = "Exception Report: International Wire Control Exception \u2013 INTL-2026-0223"
B4 = ("[Compliance] International wire control exception filed \u2014 Jira: COMP-1 | Wire ID: INTL-2026-0223 | "
      "OPS-TRE-WIRE-INTL-2026-0223 | Analyst: Jordan Analyst")
GOOD_ROWS = {
    4: ["has:link INTL-2026-0214", "Claire Overton", "VP, Treasury Operations", "Approved.", "Rachel Kim",
        "Chief Financial Officer", "Approved.", "Y", "", "verified"],
    5: ["in:#treasury-wires INTL-2026-0219", "Peter Walsh", "EVP, Corporate Finance", "Approved.", "Nadine Cole",
        "AVP, Enterprise Risk", "Approved.", "Y", "", "verified"],
    6: ["has:link INTL-2026-0223", "Claire Overton", "VP, Treasury Operations", "Approved.", "Steven Ford",
        "Chief Operating Officer", "LGTM", "N", "TRE-900 High-Risk Exception", "missing dual approval; COMP-1"],
}


def comp(desc=DESC, title=TITLE, assignee="diana.walsh"):
    return {"project_key": "COMP", "summary": title, "issue_type": "Task", "assignee": assignee, "description": desc}


class Base(TaskCase):
    TASK = "insurance_vanguard_shield_mutual_4321b8e9"

    def fill(self, rows=None):
        rows = rows or GOOD_ROWS
        code = f"rows={rows!r}\nfor r, vals in rows.items():\n    for i, v in enumerate(vals):\n" \
               "        ws.cell(row=r, column=8 + i, value=v or None)\n"
        self.edit(BOOK, code)

    def comment(self, key, text):
        self.did("jira__add_comment", {"issue_key": key, "comment": text}, '{"id":"2"}')

    def create_comp(self, **kw):
        self.did("jira__create_issue", comp(**kw), '{"id":"10008","key":"COMP-1"}')

    def golden(self):
        self.fill()
        self.comment("OPS-1", "status=verified - Claire Overton / Rachel Kim Approved.")
        self.comment("OPS-2", "status=verified - Peter Walsh / Nadine Cole Approved.")
        self.comment("OPS-3", "Exception code TRE-900 High-Risk Exception applied - missing dual approval.")
        self.create_comp()
        self.did("slack__post_message", {"channel_id": "C002", "text": B4}, '{"ok": true}')


class TestInitialAndGolden(Base):
    def test_initial_obligations(self):
        self.assertEqual(set(self.done()), {"vanguard.wire_log", "vanguard.jira_outcomes", "vanguard.b4.messages_sent"})

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})


class TestWireLog(Base):
    def test_compliant(self):
        self.fill()
        self.assertNotIn("vanguard.wire_log", self.done())

    def test_wrong_approver_and_query(self):
        rows = {k: list(v) for k, v in GOOD_ROWS.items()}
        rows[4][4] = "Peter Walsh"
        rows[6][0] = "in:#treasury-wires INTL-2026-0223"
        self.fill(rows)
        probs = [p for r, p in self.done_all() if r == "vanguard.wire_log"]
        self.assertEqual(len(probs), 2)
        self.assertTrue(any("Rachel Kim" in p for p in probs))
        self.assertTrue(any("has:link INTL-2026-0223" in p for p in probs))

    def test_lgtm_dual_y_is_wrong(self):
        rows = {k: list(v) for k, v in GOOD_ROWS.items()}
        rows[6][7], rows[6][8] = "Y", ""
        self.fill(rows)
        self.assertIn('Dual Auth Confirmed (Y/N) = "N"', self.done()["vanguard.wire_log"])


class TestSourceData(Base):
    def test_unchanged(self):
        self.fill()
        self.assertNotIn("vanguard.source_data", self.done())

    def test_amount_changed(self):
        self.edit(BOOK, "ws.cell(row=5, column=2, value=999)")
        self.assertIn("vanguard.source_data", self.done())


class TestVerified(Base):
    def test_verified_on_dual_ok(self):
        self.assertNotIn("vanguard.no_verified_without_dual",
                         self.pre("jira__add_comment", {"issue_key": "OPS-1", "comment": "status=verified"}))

    def test_verified_on_0223_blocked(self):
        self.assertIn("vanguard.no_verified_without_dual",
                      self.pre("jira__add_comment", {"issue_key": "OPS-3", "comment": "status=verified"}))

    def test_verified_on_0228_blocked(self):
        self.assertIn("vanguard.no_verified_without_dual",
                      self.pre("jira__add_comment", {"issue_key": "OPS-4", "comment": "status=verified"}))


class TestTre900(Base):
    def test_tre900_on_0223_ok(self):
        self.assertNotIn("vanguard.no_tre900_on_verified",
                         self.pre("jira__add_comment", {"issue_key": "OPS-3", "comment": "TRE-900 High-Risk Exception"}))

    def test_tre900_on_verified_blocked(self):
        self.assertIn("vanguard.no_tre900_on_verified",
                      self.pre("jira__add_comment", {"issue_key": "OPS-1", "comment": "TRE-900 High-Risk Exception"}))

    def test_negated_mention_ok(self):
        self.assertNotIn("vanguard.no_tre900_on_verified",
                         self.pre("jira__add_comment", {"issue_key": "OPS-1",
                                                        "comment": "status=verified; TRE-900 not applied"}))

    def test_completion_missing_tre900(self):
        self.golden()
        self.records = [r for r in self.records if "OPS-3" not in str(r.get("args"))]
        self.assertIn("TRE-900", self.done().get("vanguard.jira_outcomes", ""))


class TestCompTicket(Base):
    def test_good_create(self):
        self.assertNotIn("vanguard.comp_ticket", self.pre("jira__create_issue", comp()))

    def test_verified_wire_ticket_blocked(self):
        self.assertIn("vanguard.comp_ticket", self.pre("jira__create_issue", comp(
            title="Exception Report: International Wire Control Exception \u2013 INTL-2026-0219",
            desc=DESC.replace(W23, W19))))

    def test_wrong_assignee_blocked(self):
        self.assertIn("vanguard.comp_ticket", self.pre("jira__create_issue", comp(assignee="rachel.kim")))

    def test_wrong_result_line_blocked(self):
        self.assertIn("vanguard.comp_ticket", self.pre("jira__create_issue", comp(
            desc=DESC.replace("Result: query (1) has:link worked", "Result: Query (2) worked"))))

    def test_missing_b3_fields_blocked(self):
        self.assertIn("vanguard.comp_ticket", self.pre("jira__create_issue", comp(desc="Wire 0223 lacks approval")))

    def test_duplicate_blocked(self):
        self.create_comp()
        self.assertIn("vanguard.comp_ticket", self.pre("jira__create_issue", comp()))

    def test_0228_not_enforced_beyond_assignee(self):
        self.assertNotIn("vanguard.comp_ticket", self.pre("jira__create_issue", comp(
            title="Exception Report: International Wire Control Exception \u2013 INTL-2026-0228",
            desc="[Wire Control Exception] Wire ID: INTL-2026-0228")))

    def test_completion_fixed_by_update(self):
        self.golden()
        self.records = [r for r in self.records if r.get("tool") != "jira__create_issue"]
        self.create_comp(desc=DESC.replace("Missing dual approval", "one approver"))
        self.assertIn("Missing dual approval", self.done().get("vanguard.jira_outcomes", ""))
        self.did("jira__update_issue", {"issue_key": "COMP-1", "fields": '{"description": %s}' % __import__("json").dumps(DESC)},
                 '{"id":"10008","key":"COMP-1"}')
        self.assertNotIn("vanguard.jira_outcomes", self.done())


class TestB4(Base):
    def test_before_comp_blocked(self):
        self.assertIn("vanguard.b4.messages", self.pre("slack__post_message", {"channel_id": "C002", "text": B4}))

    def test_after_comp_ok(self):
        self.create_comp()
        self.assertEqual(self.pre("slack__post_message", {"channel_id": "C002", "text": B4}), set())

    def test_wrong_channel_blocked(self):
        self.create_comp()
        self.assertIn("vanguard.b4.messages", self.pre("slack__post_message", {"channel_id": "C001", "text": B4}))

    def test_wrong_key_blocked(self):
        self.create_comp()
        self.assertIn("vanguard.b4.messages", self.pre("slack__post_message",
                                                       {"channel_id": "C002", "text": B4.replace("COMP-1", "COMP-9")}))

    def test_amounts_blocked(self):
        self.create_comp()
        self.assertIn("vanguard.urgent_no_amounts", self.pre("slack__post_message", {
            "channel_id": "C002", "text": B4 + " Amount $623,000.00 ING Bank"}))

    def test_placeholder_blocked(self):
        self.create_comp()
        self.assertIn("comms.no_placeholders", self.pre("slack__post_message", {
            "channel_id": "C002", "text": B4.replace("Jordan Analyst", "[Your name]")}))

    def test_completion(self):
        self.create_comp()
        self.assertIn("vanguard.b4.messages_sent", self.done())
        self.did("slack__post_message", {"channel_id": "C002", "text": B4})
        self.assertNotIn("vanguard.b4.messages_sent", self.done())


class TestFileNames(Base):
    def test_spaces_blocked(self):
        self.assertIn("vanguard.file_names", self.pre("syntara__writeFile",
                                                      {"file_path": "/workdir/Wire Log Q1.csv", "content": "x"}))

    def test_underscores_ok(self):
        self.assertNotIn("vanguard.file_names", self.pre("syntara__writeFile",
                                                         {"file_path": "/workdir/Wire_Log_Q1.csv", "content": "x"}))
