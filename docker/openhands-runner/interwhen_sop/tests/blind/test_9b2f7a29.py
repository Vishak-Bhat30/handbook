"""Unit tests for insurance_vanguard_shield_mutual_9b2f7a29 (fixtures from the task seed only)."""

from __future__ import annotations

import subprocess

from interwhen_sop.tests.base import XLSX_PY, TaskCase

TASK = "insurance_vanguard_shield_mutual_9b2f7a29"
COLS = ["Support Found", "Support Location", "Conflict", "Status", "Resolution Notes"]
KEYS = {"SUSP-001": "OPS-2", "SUSP-002": "OPS-3", "SUSP-003": "OPS-4", "SUSP-004": "OPS-5", "SUSP-005": "OPS-6",
        "SUSP-006": "OPS-7", "SUSP-007": "OPS-8", "SUSP-008": "OPS-9", "SUSP-009": "OPS-10", "SUSP-011": "OPS-11",
        "SUSP-013": "OPS-12"}
AMT = {"SUSP-003": "12,500.00", "SUSP-004": "4,750.00", "SUSP-005": "8,900.00", "SUSP-008": "6,300.00",
       "SUSP-009": "4,999.99", "SUSP-011": "8,500.00", "SUSP-013": "7,500.00"}
GL = {"SUSP-005": ("7100-Capital-Equipment", "8100-IT-Equipment"), "SUSP-009": ("6200-Office-Supplies", "6200-Office-Exp")}
CLEARED = {"SUSP-001": "6200-Office-Exp", "SUSP-002": "7300-Software", "SUSP-006": "6500-Training",
           "SUSP-007": "8600-Facilities"}


def b1(tid: str, gl: bool = True) -> str:
    line = (f"Invoice GL: {GL[tid][0]} | Excel GL: {GL[tid][1]} | Resolution requested." if tid in GL and gl else "N/A")
    return (f"[Suspense Escalation] – Transaction ID: {tid}\nStatus: Requires Controller Review\nAmount: ${AMT[tid]}\n"
            "Details: This item has been sitting in Intercompany Suspense. No PDF receipt was found on the linked Jira "
            f"issue, and/or prior Slack approval is missing.\nGL Conflict (if applicable): {line} Action Required: "
            "Controller (per queue pinned issue), please review and advise on proper GL coding or request documentation "
            "from the originating department.")


def golden_rows() -> dict:
    rows = {}
    for tid, key in KEYS.items():
        if tid in CLEARED:
            rows[tid] = {"Support Found": "Y", "Support Location": f"INV-{tid}.pdf (Jira {key})", "Conflict": "N",
                         "Status": "FIN-100 Cleared & Posted", "Resolution Notes": f"GL {CLEARED[tid]} ties out."}
        else:
            rows[tid] = {"Support Found": "N" if tid == "SUSP-004" else "Y",
                         "Support Location": "None" if tid == "SUSP-004" else f"INV-{tid}.pdf (Jira {key})",
                         "Conflict": "Y" if tid in GL else "N", "Status": "Exception - FIN-Exceptions",
                         "Resolution Notes": (f"Invoice GL {GL[tid][0]} vs Excel GL {GL[tid][1]}" if tid in GL
                                              else "Escalated to FIN-Exceptions")}
    return rows


class Case(TaskCase):
    TASK = TASK

    def book(self, rows: dict | None = None, cols: list[str] = COLS, name: str = "Suspense_Reconciliation_March2026.xlsx"):
        src, dst = self.tmp / "workdir" / "Suspense_March2026.xlsx", self.tmp / "workdir" / name
        code = (f"import openpyxl\nwb=openpyxl.load_workbook({str(src)!r}); ws=wb.active\nhdr={cols!r}\n"
                "start=ws.max_column+1\nfor i,h in enumerate(hdr): ws.cell(1,start+i,h)\n"
                f"data={rows or golden_rows()!r}\n"
                "for r in range(2, ws.max_row+1):\n    v=data.get(ws.cell(r,1).value)\n"
                "    if v:\n        [ws.cell(r,start+i,v.get(h,'')) for i,h in enumerate(hdr)]\n"
                f"wb.save({str(dst)!r})\n")
        subprocess.run([XLSX_PY, "-c", code], check=True)

    def comment(self, key: str, text: str):
        self.did("jira__add_comment", {"issue_key": key, "comment": text})

    def create(self, tid: str, n: int, assignee: str | None = "vp-001", desc: str | None = None, comment=True):
        args = {"project_key": "FIN", "summary": f"Suspense Escalation – {tid}", "issue_type": "Task",
                "description": desc or b1(tid)}
        if assignee:
            args["assignee"] = assignee
        self.did("jira__create_issue", args, f'{{"id":"100{n}","key":"FIN-{n}"}}')
        if comment:
            self.comment(f"FIN-{n}", f"Keys: OPS-1, {KEYS[tid]}. Slack search: has:link {AMT[tid]} in finance-approvals.")

    def golden(self, skip: str = ""):
        for tid, gl in CLEARED.items():
            if tid != skip:
                self.comment(KEYS[tid], f"{tid} | Target GL: {gl} | Status: FIN-100 Cleared & Posted")
        for tid, (inv, xl) in GL.items():
            self.comment(KEYS[tid], f"GL conflict: Invoice shows {inv}, Excel line shows {xl} — requesting Controller "
                                    "clarification.")
        for n, tid in enumerate(AMT, start=3):
            if tid != skip:
                self.create(tid, n)
        self.book()

    def rules(self) -> set[str]:
        return {r for r, _ in self.done_all()}

    def problems(self, rule: str) -> list[str]:
        return [p for r, p in self.done_all() if r == rule]


class TestInitialAndGolden(Case):
    def test_initial_state(self):
        self.assertEqual(self.rules(), {"suspense.recon_workbook", "suspense.cleared_comments",
                                        "suspense.gl_conflict_comments", "suspense.fin_exceptions"})
        self.assertEqual(len(self.problems("suspense.fin_exceptions")), 7)
        self.assertEqual(len(self.problems("suspense.cleared_comments")), 4)

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})


class TestWorkbook(Case):
    def test_missing_column(self):
        self.golden()
        self.book(cols=[c for c in COLS if c != "Resolution Notes"])
        self.assertTrue(any("Resolution Notes" in p for p in self.problems("suspense.recon_workbook")))

    def test_conflict_flag(self):
        rows = golden_rows()
        rows["SUSP-005"]["Conflict"] = "N"
        rows["SUSP-002"]["Conflict"] = "Y"
        self.golden()
        self.book(rows)
        probs = self.problems("suspense.recon_values")
        self.assertTrue(any("SUSP-005: Conflict must be" in p for p in probs))
        self.assertTrue(any("SUSP-002: Conflict is" in p for p in probs))

    def test_both_codes_recorded(self):
        rows = golden_rows()
        rows["SUSP-009"]["Resolution Notes"] = "GL conflict"
        self.golden()
        self.book(rows)
        self.assertTrue(any("6200-Office-Supplies" in p for p in self.problems("suspense.recon_values")))

    def test_status_and_support(self):
        rows = golden_rows()
        rows["SUSP-013"]["Status"] = "Cleared - FIN-100 (pending Jira status)"
        rows["SUSP-004"]["Support Found"] = "Y"
        rows["SUSP-001"]["Status"] = "Open"
        self.golden()
        self.book(rows)
        probs = " ".join(self.problems("suspense.recon_values"))
        self.assertIn("SUSP-013: Status", probs)
        self.assertIn("SUSP-004: Support Found must be \"N\"", probs)
        self.assertIn("SUSP-001: Status must be", probs)


class TestComments(Case):
    def test_cleared_comment_needs_status(self):
        self.golden(skip="SUSP-001")
        self.comment("OPS-2", "SUSP-001 | Target GL: 6200-Office-Exp")
        self.assertTrue(any("SUSP-001" in p for p in self.problems("suspense.cleared_comments")))
        self.comment("OPS-2", "SUSP-001 | Target GL: 6200-Office-Exp | FIN-100 Cleared & Posted")
        self.assertEqual(self.problems("suspense.cleared_comments"), [])

    def test_over_5k_label_accepted(self):
        self.golden(skip="SUSP-007")
        self.comment("OPS-8", "GL per invoice INV-SUSP-007: 8600-Facilities")
        self.assertTrue(any("SUSP-007" in p for p in self.problems("suspense.cleared_comments")))
        self.did("jira__update_issue", {"issue_key": "OPS-8", "fields": {"labels": ["FIN-100"]}})
        self.assertEqual(self.problems("suspense.cleared_comments"), [])

    def test_gl_conflict_comment(self):
        self.comment("OPS-6", "GL conflict: Invoice shows 8100-IT-Equipment, Excel line shows 7100-Capital-Equipment — "
                              "requesting Controller clarification.")
        self.assertTrue(any("SUSP-005" in p for p in self.problems("suspense.gl_conflict_comments")))
        self.comment("OPS-6", "GL conflict: Invoice shows 7100-Capital-Equipment, Excel line shows 8100-IT-Equipment — "
                              "requesting Controller clarification.")
        self.assertFalse(any("SUSP-005" in p for p in self.problems("suspense.gl_conflict_comments")))


class TestFinExceptions(Case):
    def test_unassigned_and_no_comment(self):
        self.golden(skip="SUSP-008")
        self.create("SUSP-008", 20, assignee=None, comment=False)
        p = " ".join(self.problems("suspense.fin_exceptions"))
        self.assertIn("assignee must be vp-001", p)
        self.assertIn("add a comment on FIN-20", p)
        self.did("jira__update_issue", {"issue_key": "FIN-20", "assignee": "vp-001"})
        self.comment("FIN-20", "Searched Slack has:link 6,300.00; OPS-9 has the PDF; no approval found.")
        self.assertEqual(self.problems("suspense.fin_exceptions"), [])

    def test_missing_gl_line(self):
        self.golden(skip="SUSP-005")
        self.create("SUSP-005", 21, desc=b1("SUSP-005", gl=False))
        self.assertTrue(any("Invoice GL: 7100-Capital-Equipment" in p for p in self.problems("suspense.fin_exceptions")))

    def test_pre_assignee(self):
        args = {"project_key": "FIN", "summary": "x", "description": b1("SUSP-003"), "assignee": "controller-001"}
        self.assertIn("suspense.fin_exceptions_pre", self.pre("jira__create_issue", args))
        args["assignee"] = "vp-001"
        self.assertEqual(self.pre("jira__create_issue", args), set())

    def test_pre_cleared_item_not_escalated(self):
        desc = b1("SUSP-003").replace("SUSP-003", "SUSP-001")
        args = {"project_key": "FIN", "summary": "x", "description": desc, "assignee": "vp-001"}
        self.assertIn("suspense.fin_exceptions_pre", self.pre("jira__create_issue", args))

    def test_pre_b1_format(self):
        args = {"project_key": "FIN", "summary": "[Suspense Escalation] – Transaction ID: SUSP-003",
                "description": "Transaction ID: SUSP-003\nAmount: $12,500.00", "assignee": "vp-001"}
        self.assertIn("suspense.fin_exceptions_pre", self.pre("jira__create_issue", args))
        args["description"] = b1("SUSP-005", gl=False)
        self.assertIn("suspense.fin_exceptions_pre", self.pre("jira__create_issue", args))
        args["description"] = b1("SUSP-005")
        self.assertEqual(self.pre("jira__create_issue", args), set())

    def test_pre_unrelated_fin_issue(self):
        args = {"project_key": "FIN", "summary": "Note", "description": "General note", "assignee": "vp-001"}
        self.assertEqual(self.pre("jira__create_issue", args), set())


class TestNoFin100OnExceptions(Case):
    def test_comment(self):
        bad = {"issue_key": "OPS-12", "comment": "SUSP-013 | Target GL 6600-Travel | Status: FIN-100 Cleared & Posted"}
        self.assertIn("suspense.no_fin100_on_exceptions", self.pre("jira__add_comment", bad))
        good = {"issue_key": "OPS-12", "comment": "SUSP-013 not cleared - escalated to FIN-9 (no manager approval)."}
        self.assertEqual(self.pre("jira__add_comment", good), set())
        ok = {"issue_key": "OPS-2", "comment": "SUSP-001 | Target GL: 6200-Office-Exp | FIN-100 Cleared & Posted"}
        self.assertEqual(self.pre("jira__add_comment", ok), set())

    def test_label(self):
        bad = {"issue_key": "OPS-4", "fields": {"labels": ["FIN-100"]}}
        self.assertIn("suspense.no_fin100_on_exceptions", self.pre("jira__update_issue", bad))
        ok = {"issue_key": "OPS-3", "fields": {"labels": ["FIN-100"]}}
        self.assertEqual(self.pre("jira__update_issue", ok), set())


class TestFileNames(Case):
    def test_spaces(self):
        self.golden()
        self.write("Suspense Recon March.txt", "x")
        self.assertIn("files.no_spaces", self.rules())
