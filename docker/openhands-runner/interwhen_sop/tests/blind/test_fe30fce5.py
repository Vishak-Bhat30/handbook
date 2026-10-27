"""Blind unit tests for insurance_vanguard_shield_mutual_fe30fce5 (Q1 2026 wire dual-authorization audit, SOP §3.3)."""

from __future__ import annotations

import json
import unittest

from interwhen_sop.tests.base import TaskCase

TASK = "insurance_vanguard_shield_mutual_fe30fce5"
WB = "Wire_Population_Q1_2026.xlsx"
TITLE = "Exception Report: International Wire Control Exception – {}"
PRIO = json.dumps({"priority": {"id": "2", "name": "High"}})


def b3(wid: str, issue: str, ts: str, a2: str) -> str:
    return (f"Wire ID: {wid}\nOPS-TRE-WIRE issue: OPS-TRE-WIRE-{wid}\n"
            "Population source: International wires population workbook from OPS-TRE-WIRES-Q1-2026 "
            "(Wire_Population_Q1_2026.xlsx)\n"
            f"Slack evidence: #treasury-wires | Thread timestamp: {ts}\n"
            "Approver 1: Karen Stills | VP, Treasury Operations | \"Approved.\"\n"
            f"Approver 2: {a2}\n"
            "Exception code applied on wire issue: TRE-900 High-Risk Exception\n"
            "Action requested: Chief Compliance Officer (per Compliance-Alerts board pinned issue) to determine "
            "corrective action and whether wire may proceed.")


B3_0151 = b3("INTL-2026-0151", "OPS-3", "2026-03-11, 11:00 AM EDT", "Missing")
B3_0158 = b3("INTL-2026-0158", "OPS-4", "2026-03-19, 11:00 AM EDT",
             "Brett Connors | Senior Manager, Treasury Operations | \"Approved.\" | title does not meet threshold")

ROWS = {
    4: ["2026-03-04, 10:00 AM EST", "Karen Stills", "VP, Treasury Operations", "Approved.", "Michael Drury",
        "SVP, Finance & Risk", "Approved.", "Y", None],
    5: ["2026-03-11, 11:00 AM EDT", "Karen Stills", "VP, Treasury Operations", "Approved.", None, None, None, "N",
        "TRE-900 High-Risk Exception"],
    6: ["2026-03-19, 11:00 AM EDT", "Karen Stills", "VP, Treasury Operations", "Approved.", "Brett Connors",
        "Senior Manager, Treasury Operations", "Approved.", "N", "TRE-900 High-Risk Exception"],
    7: ["2026-03-27, 11:00 AM EDT", "Karen Stills", "VP, Treasury Operations", "Approved.", "Priya Mehta",
        "AVP, Enterprise Risk", "Approved.", "Y", None],
}


class Wires(TaskCase):
    TASK = TASK

    # ---- helpers ----
    def comment(self, key, text):
        self.did("jira__add_comment", {"issue_key": key, "comment": text})

    def create(self, wid, desc, key, title=None, assignee="diana.walsh", prio=True):
        args = {"project_key": "OPS", "issue_type": "Task", "summary": title or TITLE.format(wid),
                "description": desc, "assignee": assignee}
        if prio:
            args["additional_fields"] = PRIO
        self.did("jira__create_issue", args, json.dumps({"id": "10008", "key": key}))

    def b4_args(self, key, wid, role="Junior Operations Analyst"):
        return {"channel_id": "C002", "text": f"Compliance International wire control exception filed — Jira: {key} | "
                                              f"Wire ID: {wid} | OPS-TRE-WIRE-{wid} | {role}"}

    def post(self, args):
        self.did("slack__post_message", args, json.dumps({"ok": True, "channel": "C002", "ts": "1792435846.1"}))

    def wire_0147(self):
        self.comment("OPS-2", "INTL-2026-0147 dual authorization confirmed. status=verified")

    def wire_0151(self):
        self.comment("OPS-3", "Exception code TRE-900 High-Risk Exception applied - dual approval missing.")
        self.create("INTL-2026-0151", B3_0151, "OPS-7")
        self.post(self.b4_args("OPS-7", "INTL-2026-0151"))

    def wire_0158(self):
        self.comment("OPS-4", "TRE-900 High-Risk Exception - second approver below VP threshold.")
        self.create("INTL-2026-0158", B3_0158, "OPS-8")
        self.post(self.b4_args("OPS-8", "INTL-2026-0158"))

    def wire_0163(self):
        self.comment("OPS-5", "INTL-2026-0163 dual authorization confirmed. status=verified")

    def fill(self, rows=ROWS):
        code = "".join(f"for i, v in enumerate({vals!r}):\n    ws.cell({r}, 8 + i).value = v\n"
                       for r, vals in rows.items())
        self.edit(WB, code)

    def golden(self):
        self.wire_0147()
        self.wire_0151()
        self.wire_0158()
        self.wire_0163()
        self.fill()

    # ---- initial / golden ----
    def test_initial_obligations(self):
        d = self.done()
        self.assertEqual(set(d), {"wire.jira_comments", "wire.exception_task", "wire.workbook",
                                  "wire.b4.messages_sent"})

    def test_golden_path_clean(self):
        self.golden()
        self.assertEqual(self.done(), {})

    # ---- wire.order ----
    def test_order_blocks_later_wire(self):
        self.wire_0147()
        self.assertIn("wire.order", self.pre("jira__add_comment",
                                             {"issue_key": "OPS-5", "comment": "status=verified"}))

    def test_order_allows_after_earlier_done(self):
        self.wire_0147()
        self.wire_0151()
        self.wire_0158()
        self.assertEqual(self.pre("jira__add_comment", {"issue_key": "OPS-5", "comment": "status=verified"}), set())

    def test_order_allows_first_wire(self):
        self.assertEqual(self.pre("jira__add_comment", {"issue_key": "OPS-2", "comment": "status=verified"}), set())

    # ---- wire.outcome ----
    def test_outcome_verified_on_exception_wire_blocked(self):
        self.wire_0147()
        self.assertIn("wire.outcome", self.pre("jira__add_comment",
                                               {"issue_key": "OPS-3", "comment": "status=verified"}))

    def test_outcome_tre900_on_verified_wire_blocked(self):
        self.assertIn("wire.outcome", self.pre("jira__add_comment",
                                               {"issue_key": "OPS-2", "comment": "TRE-900 High-Risk Exception"}))

    def test_outcome_exception_task_for_verified_wire_blocked(self):
        self.wire_0147()
        self.wire_0151()
        self.wire_0158()
        args = {"project_key": "OPS", "issue_type": "Task", "summary": TITLE.format("INTL-2026-0163"),
                "description": "Wire ID: INTL-2026-0163", "assignee": "diana.walsh"}
        self.assertIn("wire.outcome", self.pre("jira__create_issue", args))

    def test_outcome_correct_comment_ok(self):
        self.wire_0147()
        self.assertEqual(self.pre("jira__add_comment", {"issue_key": "OPS-3",
                                                        "comment": "TRE-900 High-Risk Exception applied."}), set())

    # ---- wire.exception_task_fields ----
    def _create_args(self, **kw):
        a = {"project_key": "OPS", "issue_type": "Task", "summary": TITLE.format("INTL-2026-0151"),
             "description": B3_0151, "assignee": "diana.walsh", "additional_fields": PRIO}
        a.update(kw)
        return a

    def test_task_fields_ok(self):
        self.wire_0147()
        self.comment("OPS-3", "TRE-900 High-Risk Exception")
        self.assertEqual(self.pre("jira__create_issue", self._create_args()), set())

    def test_task_wrong_title_blocked(self):
        self.wire_0147()
        r = self.pre("jira__create_issue", self._create_args(summary="Wire exception INTL-2026-0151"))
        self.assertIn("wire.exception_task_fields", r)

    def test_task_wrong_assignee_blocked(self):
        self.wire_0147()
        self.assertIn("wire.exception_task_fields", self.pre("jira__create_issue", self._create_args(assignee="sys-001")))

    def test_task_missing_b3_line_blocked(self):
        self.wire_0147()
        desc = B3_0151.replace("Approver 2: Missing\n", "")
        self.assertIn("wire.exception_task_fields", self.pre("jira__create_issue", self._create_args(description=desc)))

    def test_task_wrong_timezone_blocked(self):
        self.wire_0147()
        desc = B3_0151.replace("11:00 AM EDT", "11:00 AM EST")
        self.assertIn("wire.exception_task_fields", self.pre("jira__create_issue", self._create_args(description=desc)))

    def test_task_duplicate_blocked(self):
        self.wire_0147()
        self.wire_0151()
        self.assertIn("wire.exception_task_fields", self.pre("jira__create_issue", self._create_args()))

    def test_task_0158_requires_threshold_note(self):
        self.wire_0147()
        self.wire_0151()
        desc = B3_0158.replace(" | title does not meet threshold", "")
        args = self._create_args(summary=TITLE.format("INTL-2026-0158"), description=desc)
        self.assertIn("wire.exception_task_fields", self.pre("jira__create_issue", args))
        args = self._create_args(summary=TITLE.format("INTL-2026-0158"), description=B3_0158)
        self.assertEqual(self.pre("jira__create_issue", args), set())

    # ---- wire.exception_task (completion) ----
    def test_task_priority_missing_then_fixed(self):
        self.golden()
        self.records = []
        self.wire_0147()
        self.comment("OPS-3", "TRE-900 High-Risk Exception")
        self.create("INTL-2026-0151", B3_0151, "OPS-7", prio=False)
        self.post(self.b4_args("OPS-7", "INTL-2026-0151"))
        self.wire_0158()
        self.wire_0163()
        self.assertIn("priority must be High", self.done().get("wire.exception_task", ""))
        self.did("jira__update_issue", {"issue_key": "OPS-7", "fields": PRIO, "summary": "Set priority"})
        self.assertEqual(self.done(), {})

    # ---- wire.b4 ----
    def test_b4_before_task_blocked(self):
        self.wire_0147()
        self.comment("OPS-3", "TRE-900 High-Risk Exception")
        self.assertIn("wire.b4.messages", self.pre("slack__post_message", self.b4_args("OPS-7", "INTL-2026-0151")))

    def test_b4_ok_after_task(self):
        self.wire_0147()
        self.comment("OPS-3", "TRE-900 High-Risk Exception")
        self.create("INTL-2026-0151", B3_0151, "OPS-7")
        self.assertEqual(self.pre("slack__post_message", self.b4_args("OPS-7", "INTL-2026-0151")), set())

    def test_b4_with_amount_blocked(self):
        self.wire_0147()
        self.comment("OPS-3", "TRE-900 High-Risk Exception")
        self.create("INTL-2026-0151", B3_0151, "OPS-7")
        args = self.b4_args("OPS-7", "INTL-2026-0151")
        args["text"] += " | Amount $87,200.00"
        self.assertIn("wire.b4.messages", self.pre("slack__post_message", args))

    def test_b4_for_verified_wire_blocked(self):
        self.assertIn("wire.b4.messages", self.pre("slack__post_message", self.b4_args("OPS-7", "INTL-2026-0147")))

    def test_b4_placeholder_blocked(self):
        self.wire_0147()
        self.comment("OPS-3", "TRE-900 High-Risk Exception")
        self.create("INTL-2026-0151", B3_0151, "OPS-7")
        r = self.pre("slack__post_message", self.b4_args("OPS-7", "INTL-2026-0151", role="[Your role]"))
        self.assertIn("comms.no_placeholders", r)

    def test_b4_missing_at_completion(self):
        self.wire_0147()
        self.comment("OPS-3", "TRE-900 High-Risk Exception")
        self.create("INTL-2026-0151", B3_0151, "OPS-7")
        self.wire_0158()
        self.wire_0163()
        self.fill()
        self.assertEqual(set(self.done()), {"wire.b4.messages_sent"})

    # ---- wire.jira_comments ----
    def test_comments_missing(self):
        self.golden()
        self.records = [r for r in self.records if not (r.get("args") or {}).get("issue_key") == "OPS-5"]
        self.records = [r for r in self.records if r["type"] == "action" or
                        any(a["call_id"] == r["call_id"] for a in self.records if a["type"] == "action")]
        self.assertIn("OPS-5", self.done().get("wire.jira_comments", ""))

    # ---- wire.workbook ----
    def test_workbook_wrong_timezone(self):
        rows = dict(ROWS)
        rows[4] = ["2026-03-04, 11:00 AM EDT"] + ROWS[4][1:]
        self.wire_0147(); self.wire_0151(); self.wire_0158(); self.wire_0163()
        self.fill(rows)
        self.assertIn("INTL-2026-0147", self.done().get("wire.workbook", ""))

    def test_workbook_missing_text_in_empty_cells(self):
        rows = dict(ROWS)
        rows[5] = ROWS[5][:4] + ["Missing", None, None] + ROWS[5][7:]
        self.wire_0147(); self.wire_0151(); self.wire_0158(); self.wire_0163()
        self.fill(rows)
        self.assertIn("Approver 2 Name = empty", self.done().get("wire.workbook", ""))

    def test_workbook_dual_flag_wrong(self):
        rows = dict(ROWS)
        rows[6] = ROWS[6][:7] + ["Y", None]
        self.wire_0147(); self.wire_0151(); self.wire_0158(); self.wire_0163()
        self.fill(rows)
        self.assertIn("INTL-2026-0158", self.done().get("wire.workbook", ""))

    def test_workbook_source_column_changed(self):
        self.golden()
        self.edit(WB, "ws.cell(5, 2).value = 1")
        self.assertIn("pre-populated source columns", self.done().get("wire.workbook", ""))

    def test_workbook_suffix_optional(self):
        rows = {r: [v.replace(" EST", "").replace(" EDT", "") if i == 0 else v for i, v in enumerate(vals)]
                for r, vals in ROWS.items()}
        self.wire_0147(); self.wire_0151(); self.wire_0158(); self.wire_0163()
        self.fill(rows)
        self.assertEqual(self.done(), {})


if __name__ == "__main__":
    unittest.main()
