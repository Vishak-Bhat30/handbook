"""Blind unit tests for insurance_vanguard_shield_mutual_177fce83 (T&E review -> expense_reports.xlsx + B-2 flag).

    INTERWHEN_XLSX_PYTHON=/home/t-bhatvishak/miniconda3/bin/python3 \
        python3 -m unittest interwhen_sop.tests.blind.test_177fce83 -v
"""

from __future__ import annotations

import copy
import json
import subprocess

from interwhen_sop.tests.base import XLSX_PY, TaskCase

TASK = "insurance_vanguard_shield_mutual_177fce83"
HEADER = ["Jira Key", "Date of Purchase", "Merchant", "Amount", "Expense Category", "Approved Amount",
          "Denied Amount", "Denial Reason"]
MBJ = "Missing business justification. Please submit personal reimbursement."
S, C = "Staff Expense", "Client Relations Expense"

# key: (date, merchant, amount, category, approved, denied, reason)
GOLD = {
    "Amina Hassan": ("OPS-18", [
        ("OPS-1", "4/23/2026", "Shopify (promotional)", 43.89, C, 43.89, 0, ""),
        ("OPS-2", "5/5/2026", "Uber", 63.18, S, 63.18, 0, ""),
        ("OPS-3", "5/6/2026", "Blackstone Chophouse", 46.86, S, 46.86, 0, ""),
        ("OPS-4", "5/5/2026", "Delta", 389.75, S, 389.75, 0, ""),
        ("OPS-5", "5/6/2026", "Helios Coffee Shop", 24.75, S, 24.75, 0, ""),
        ("OPS-6", "5/6/2026", "Gold Coast Eatery", 27.01, S, 27.01, 0, ""),
        ("OPS-7", "5/6/2026", "Asgard Restaurant", 541.33, C, 541.33, 0, ""),
        ("OPS-8", "5/7/2026", "Helios Coffee Shop", 24.75, S, 24.75, 0, ""),
        ("OPS-9", "5/7/2026", "Pilsen Table", 18.74, S, 18.74, 0, ""),
        ("OPS-10", "5/7/2026", "The Greektown Table", 45.75, S, 45.75, 0, ""),
        ("OPS-11", "5/8/2026", "Helios Coffee Shop", 24.48, S, 24.48, 0, ""),
        ("OPS-12", "5/8/2026", "Wicker Park Kitchen", 28.67, S, 28.67, 0, ""),
        ("OPS-13", "5/7/2026", "Melody Bistro", 747.49, C, 747.49, 0, ""),
        ("OPS-14", "5/9/2026", "Uber", 59.80, S, 59.80, 0, ""),
        ("OPS-15", "5/9/2026", "Helios Coffee Shop", 22.55, S, 22.55, 0, ""),
        ("OPS-16", "5/9/2026", "Bucktown Bites", 33.02, S, 33.02, 0, ""),
        ("OPS-17", "5/5/2026 - 5/8/2026", "Hyatt Regency Chicago", 2098.94, S, 2098.94, 0, "")]),
    "Priya Natarajan": ("OPS-39", [
        ("OPS-33", "5/5/2026", "Riverfront Deli", 16.59, S, 0, 16.59, "No business event in Fort Wayne, IN"),
        ("OPS-34", "5/5/2026", "Self drove (mileage)", "200 miles", S, 0, 145.00, "No business event"),
        ("OPS-35", "5/6/2026", "The Creamery Cafe", 21.40, S, 0, 21.40, "No business event in Fort Wayne, IN"),
        ("OPS-36", "5/7/2026", "Canal Street Kitchen", 16.05, S, 0, 16.05, "No business event in Fort Wayne, IN"),
        ("OPS-37", "5/8/2026", "The Landing Spot", 20.33, S, 0, 20.33, "No business event in Fort Wayne, IN"),
        ("OPS-38", "5/5/2026 - 5/9/2026", "Serenity Hotel and Spa", 1471.96, S, 0, 1471.96,
         "No business event in Fort Wayne, IN")]),
    "Leila Rahimi": ("OPS-57", [
        ("OPS-40", "4/21/2026", "Shopify (client gifts)", 119.54, C, 119.54, 0, ""),
        ("OPS-41", "5/5/2026", "The Greektown Table", 47.96, S, 47.96, 0, ""),
        ("OPS-42", "5/5/2026", "Delta", 384.40, S, 384.40, 0, ""),
        ("OPS-43", "5/6/2026", "Helios Coffee Shop", 10.69, S, 10.69, 0, ""),
        ("OPS-44", "5/6/2026", "The Riverwalk Grille", 21.72, S, 21.72, 0, ""),
        ("OPS-45", "5/7/2026", "Helios Coffee Shop", 12.40, S, 12.40, 0, ""),
        ("OPS-46", "5/7/2026", "Gold Coast Eatery", 28.94, S, 28.94, 0, ""),
        ("OPS-47", "5/7/2026", "Sable & Oak Kitchen", 37.76, S, 37.76, 0, ""),
        ("OPS-48", "5/8/2026", "Helios Coffee Shop", 12.35, S, 12.35, 0, ""),
        ("OPS-49", "5/8/2026", "Pilsen Table", 24.81, S, 24.81, 0, ""),
        ("OPS-50", "5/8/2026", "Lock & Lantern Escape Room", 308.61, C, 192.88, 115.73,
         "Units beyond listed attendees exceed client entertainment limit"),
        ("OPS-51", "5/9/2026", "Helios Coffee Shop", 12.13, S, 12.13, 0, ""),
        ("OPS-52", "5/9/2026", "Wicker Park Kitchen", 26.13, S, 26.13, 0, ""),
        ("OPS-53", "5/9/2026", "Cosa Nostra Cucina", 49.06, S, 49.06, 0, ""),
        ("OPS-54", "5/5/2026 - 5/9/2026", "Hyatt Regency Chicago", 1916.99, S, 1916.99, 0, ""),
        ("OPS-55", "5/10/2026", "Uber", 57.00, S, 57.00, 0, ""),
        ("OPS-56", "5/10/2026", "Helios Coffee Shop", 11.85, S, 11.85, 0, "")]),
    "Hiroshi Tanaka": ("OPS-74", [
        ("OPS-58", "5/5/2026", "Sable & Oak Kitchen", 38.59, S, 38.59, 0, ""),
        ("OPS-59", "5/5/2026", "Self drove (mileage)", "357 miles", S, 258.83, 0, ""),
        ("OPS-60", "5/6/2026", "Gloriana Bakery", 9.10, S, 9.10, 0, ""),
        ("OPS-61", "5/6/2026", "Wicker Park Kitchen", 21.22, S, 21.22, 0, ""),
        ("OPS-62", "5/6/2026", "Harbor Light Bistro", 45.20, S, 45.20, 0, ""),
        ("OPS-63", "5/7/2026", "Gloriana Bakery", 10.47, S, 10.47, 0, ""),
        ("OPS-64", "5/7/2026", "Bucktown Bites", 26.40, S, 26.40, 0, ""),
        ("OPS-65", "5/7/2026", "Mariscos Del Lago", 33.07, S, 33.07, 0, ""),
        ("OPS-66", "5/8/2026", "Gloriana Bakery", 11.02, S, 11.02, 0, ""),
        ("OPS-67", "5/8/2026", "Lincoln Square Cafe", 26.13, S, 26.13, 0, ""),
        ("OPS-68", "5/9/2026", "Gloriana Bakery", 11.85, S, 11.85, 0, ""),
        ("OPS-69", "5/9/2026", "Loop Street Deli", 25.63, S, 25.63, 0, ""),
        ("OPS-70", "5/9/2026", "Koto Ramen & Izakaya", 39.69, S, 39.69, 0, ""),
        ("OPS-71", "5/5/2026 - 5/9/2026", "Hyatt Regency Chicago", 1916.99, S, 1916.99, 0, ""),
        ("OPS-72", "5/10/2026", "Gloriana Bakery", 11.30, S, 11.30, 0, ""),
        ("OPS-73", "5/10/2026", "Self drove (mileage)", "360 miles", S, 261.00, 0, "")]),
    "Carlos Mendez": ("OPS-32", [
        ("OPS-19", "5/5/2026", "Delta", 384.40, S, 384.40, 0, ""),
        ("OPS-20", "5/5/2026", "Cosa Nostra Cucina", 46.86, S, 46.86, 0, ""),
        ("OPS-21", "5/6/2026", "Bucktown Bites", 28.11, S, 28.11, 0, ""),
        ("OPS-22", "5/6/2026", "Sable & Oak Kitchen", 48.23, S, 48.23, 0, ""),
        ("OPS-23", "5/6/2026", "Art Institute of Chicago", 32.00, S, 0, 32.00, MBJ),
        ("OPS-24", "5/7/2026", "Lincoln Square Cafe", 24.25, S, 24.25, 0, ""),
        ("OPS-25", "5/7/2026", "Blackstone Chophouse", 46.86, S, 46.86, 0, ""),
        ("OPS-26", "5/8/2026", "Loop Street Deli", 21.22, S, 21.22, 0, ""),
        ("OPS-27", "5/8/2026", "Cosa Nostra Cucina", 43.55, S, 43.55, 0, ""),
        ("OPS-28", "5/9/2026", "Gloriana Bakery", 13.73, S, 13.73, 0, ""),
        ("OPS-29", "5/9/2026", "The Riverwalk Grille", 36.93, S, 36.93, 0, ""),
        ("OPS-30", "5/9/2026", "Harbor Light Bistro", 43.55, S, 43.55, 0, ""),
        ("OPS-31", "5/5/2026 - 5/9/2026", "Hyatt Regency Chicago", 1916.99, S, 1916.99, 0, "")]),
}

B2_OK = ("@Layla Zahra\nT&E Review Flag - Priya Natarajan\nExpense Date(s): 5/5/2026 - 5/9/2026\n"
         "Total Amount Approved: $0.00\nTotal Amount Denied: $1,691.33\n"
         "Merchant(s): Riverfront Deli, The Creamery Cafe, Canal Street Kitchen, The Landing Spot, "
         "Serenity Hotel and Spa, mileage reimbursement\n"
         "Details: Expense(s) submitted without business justification.\n"
         "Action Taken: Expenses report OPS-39 denied. Please review with your direct report.")

WRITE = r"""
import json, sys, openpyxl
spec = json.loads(sys.argv[2])
wb = openpyxl.Workbook()
wb.remove(wb.active)
for name, rows in spec.items():
    ws = wb.create_sheet(name)
    for r in rows:
        ws.append([None if v == "" else v for v in r])
wb.save(sys.argv[1])
"""


def summary(rows_):
    ap = round(sum(r[5] for r in rows_), 2)
    de = round(sum(r[6] for r in rows_), 2)
    if de == 0:
        st, cm = "Approved", "T&E review complete. All expenses approved."
    elif de < 200:
        st, cm = "Partially Approved", "T&E review complete. Expenses approved except where noted."
    else:
        st, cm = "Denied", f"T&E review complete. Denied expenses: ${de:,.2f}."
    return ap, de, st, cm


def gold_book() -> dict:
    out = {}
    for emp, (key, rows_) in GOLD.items():
        ap, de, st, cm = summary(rows_)
        grid = [HEADER] + [list(r) for r in rows_] + [[""]]
        grid += [["Report Summary"], ["Jira Key", key], ["Total Approved", ap], ["Total Denied", de],
                 ["Final Status", st], ["Manager Notified", "Y" if st == "Denied" else "N"], ["Comments", cm]]
        out[emp] = grid
    return out


def row_of(book, emp, key):
    return next(r for r in book[emp] if r and r[0] == key)


def label(book, emp, name):
    return next(r for r in book[emp] if len(r) == 2 and r[0] == name)


class Base(TaskCase):
    TASK = TASK

    def save(self, book: dict, name: str = "expense_reports.xlsx"):
        subprocess.run([XLSX_PY, "-c", WRITE, str(self.tmp / "workdir" / name), json.dumps(book)], check=True)

    def post(self, text, channel="C001"):
        return {"channel_id": channel, "text": text}

    def gold(self):
        return copy.deepcopy(gold_book())


class TestInitialAndGolden(Base):
    def test_initial_state_lists_only_outstanding_obligations(self):
        self.assertEqual(set(self.done()), {"report.file", "slack.b2.messages_sent"})

    def test_golden_path(self):
        self.save(self.gold())
        self.assertEqual(self.pre("slack__post_message", self.post(B2_OK)), set())
        self.did("slack__post_message", self.post(B2_OK))
        self.assertEqual(self.done_all(), [])


class TestFile(Base):
    def test_missing_and_extra_sheets(self):
        book = self.gold()
        book["Sheet"] = [["x"]]
        book["Natarajan"] = book.pop("Priya Natarajan")
        self.save(book)
        probs = [p for r, p in self.done_all() if r == "report.file"]
        self.assertTrue(any("missing worksheet" in p and "Priya Natarajan" in p for p in probs))
        self.assertTrue(any("'Sheet'" in p for p in probs))

    def test_directory_must_stay_unchanged(self):
        self.save(self.gold())
        self.did("slack__post_message", self.post(B2_OK))
        self.edit("People Directory.xlsx", "ws.cell(row=2, column=1).value = 'X'")
        self.assertIn("files.directory_unchanged", self.done())


class Mut(Base):
    def run_mut(self, fn):
        book = self.gold()
        fn(book)
        self.save(book)
        self.did("slack__post_message", self.post(B2_OK))
        return self.done_all()


class TestLines(Mut):
    def test_split_must_add_up(self):
        def f(b):
            row_of(b, "Amina Hassan", "OPS-9")[5] = 10.0
        out = self.run_mut(f)
        self.assertTrue(any(r == "report.lines" and "OPS-9" in p and "must equal" in p for r, p in out))

    def test_other_field_zero_not_blank(self):
        def f(b):
            row_of(b, "Hiroshi Tanaka", "OPS-60")[6] = ""
        out = self.run_mut(f)
        self.assertTrue(any(r == "report.lines" and "OPS-60" in p and "never left blank" in p for r, p in out))

    def test_reason_blank_when_fully_approved(self):
        def f(b):
            row_of(b, "Hiroshi Tanaka", "OPS-60")[7] = "ok"
        out = self.run_mut(f)
        self.assertTrue(any(r == "report.lines" and "must be blank" in p for r, p in out))

    def test_standard_note_text_exact(self):
        def f(b):
            row_of(b, "Carlos Mendez", "OPS-23")[7] = "Missing business justification"
        out = self.run_mut(f)
        self.assertTrue(any(r == "report.lines" and "exactly" in p for r, p in out))

    def test_category_values(self):
        def f(b):
            row_of(b, "Leila Rahimi", "OPS-45")[4] = "Meals"
        out = self.run_mut(f)
        self.assertTrue(any(r == "report.lines" and "OPS-45" in p and "Expense Category" in p for r, p in out))

    def test_header_and_missing_line(self):
        def f(b):
            b["Carlos Mendez"][0][3] = "Total"
            b["Carlos Mendez"] = [r for r in b["Carlos Mendez"] if not (r and r[0] == "OPS-28")]
        out = self.run_mut(f)
        self.assertTrue(any(r == "report.lines" and "header" in p for r, p in out))
        self.assertTrue(any(r == "report.lines" and "OPS-28" in p for r, p in out))

    def test_mileage_amount_in_dollars(self):
        def f(b):
            row_of(b, "Priya Natarajan", "OPS-34")[6] = 200
        out = self.run_mut(f)
        self.assertTrue(any(r == "report.lines" and "OPS-34" in p and "145.00" in p for r, p in out))


class TestDecisions(Mut):
    def test_priya_lines_all_denied(self):
        def f(b):
            r = row_of(b, "Priya Natarajan", "OPS-33")
            r[5], r[6], r[7] = 16.59, 0, ""
        out = self.run_mut(f)
        self.assertTrue(any(r == "report.decisions" and "OPS-33" in p and "Fort Wayne" in p for r, p in out))

    def test_art_institute_denied(self):
        def f(b):
            r = row_of(b, "Carlos Mendez", "OPS-23")
            r[5], r[6], r[7] = 32.0, 0, ""
        out = self.run_mut(f)
        self.assertTrue(any(r == "report.decisions" and "OPS-23" in p for r, p in out))

    def test_escape_room_partial(self):
        def f(b):
            r = row_of(b, "Leila Rahimi", "OPS-50")
            r[5], r[6] = 0, 308.61
        out = self.run_mut(f)
        self.assertTrue(any(r == "report.decisions" and "OPS-50" in p and "192.88" in p for r, p in out))

    def test_receipt_date_correction(self):
        def f(b):
            row_of(b, "Amina Hassan", "OPS-13")[1] = "5/8/2026"
        out = self.run_mut(f)
        self.assertTrue(any(r == "report.decisions" and "OPS-13" in p and "5/7/2026" in p for r, p in out))

    def test_receipt_date_accepts_iso(self):
        def f(b):
            row_of(b, "Amina Hassan", "OPS-3")[1] = "2026-05-06"
        out = self.run_mut(f)
        self.assertEqual(out, [])

    def test_shopify_item_approved(self):
        def f(b):
            r = row_of(b, "Leila Rahimi", "OPS-40")
            r[5], r[6], r[7] = 0, 119.54, "No receipt"
        out = self.run_mut(f)
        self.assertTrue(any(r == "report.decisions" and "OPS-40" in p and "c1002" in p for r, p in out))

    def test_client_relations_category(self):
        def f(b):
            row_of(b, "Amina Hassan", "OPS-7")[4] = S
        out = self.run_mut(f)
        self.assertTrue(any(r == "report.decisions" and "OPS-7" in p and "Client Relations" in p for r, p in out))

    def test_carlos_not_denied(self):
        def f(b):
            r = row_of(b, "Carlos Mendez", "OPS-22")
            r[5], r[6], r[7] = 0, 48.23, "x"
            r = row_of(b, "Carlos Mendez", "OPS-19")
            r[5], r[6], r[7] = 0, 384.40, "x"
        out = self.run_mut(f)
        self.assertTrue(any(r == "report.decisions" and "cannot reach $200" in p for r, p in out))


class TestSummary(Mut):
    def test_totals_status_comment_manager(self):
        def f(b):
            label(b, "Leila Rahimi", "Total Approved")[1] = 2785.34
            label(b, "Leila Rahimi", "Final Status")[1] = "Approved"
            label(b, "Leila Rahimi", "Comments")[1] = "Done"
            label(b, "Leila Rahimi", "Manager Notified")[1] = "Y"
        out = [p for r, p in self.run_mut(f) if r == "report.summary"]
        self.assertTrue(any("Total Approved" in p for p in out))
        self.assertTrue(any("Partially Approved" in p and "Final Status" in p for p in out))
        self.assertTrue(any("except where noted" in p for p in out))
        self.assertTrue(any("Manager Notified must be N" in p for p in out))

    def test_denied_comment_amount(self):
        def f(b):
            label(b, "Priya Natarajan", "Comments")[1] = "T&E review complete. Denied expenses: $1,546.33."
        out = [p for r, p in self.run_mut(f) if r == "report.summary"]
        self.assertTrue(any("Denied expenses: $1,691.33" in p for p in out))

    def test_summary_placement_and_jira_key(self):
        def f(b):
            g = b["Hiroshi Tanaka"]
            g.remove([""])
            label(b, "Hiroshi Tanaka", "Jira Key")[1] = "OPS-73"
        out = [p for r, p in self.run_mut(f) if r == "report.summary"]
        self.assertTrue(any("one blank row" in p for p in out))
        self.assertTrue(any("OPS-74" in p for p in out))


class TestSlack(Base):
    def test_correct_flag_allowed_and_counts(self):
        self.assertEqual(self.pre("slack__post_message", self.post(B2_OK)), set())
        self.assertIn("slack.b2.messages_sent", self.done())
        self.did("slack__post_message", self.post(B2_OK))
        self.assertNotIn("slack.b2.messages_sent", self.done())

    def test_handle_mention_accepted(self):
        self.assertEqual(self.pre("slack__post_message", self.post(B2_OK.replace("@Layla Zahra", "@l_zahra"))), set())

    def test_wrong_amounts_blocked(self):
        bad = B2_OK.replace("Approved: $0.00", "Approved: $161.59").replace(", mileage reimbursement", "")
        self.assertIn("slack.b2.messages", self.pre("slack__post_message", self.post(bad)))

    def test_wrong_manager_blocked(self):
        bad = B2_OK.replace("@Layla Zahra", "@Rashid Al-Maktoum")
        self.assertIn("slack.b2.messages", self.pre("slack__post_message", self.post(bad)))

    def test_dm_and_wrong_channel_blocked(self):
        self.assertIn("slack.b2.messages", self.pre("slack__send_dm", {"user_id": "U072", "text": B2_OK}))
        self.assertIn("slack.b2.messages", self.pre("slack__post_message", self.post(B2_OK, "C006")))

    def test_second_flag_blocked(self):
        self.did("slack__post_message", self.post(B2_OK))
        self.assertIn("slack.b2.messages", self.pre("slack__post_message", self.post(B2_OK)))

    def test_flags_for_non_denied_reports_blocked(self):
        for emp, key, mgr in (("Amina Hassan", "OPS-18", "@Rashid Al-Maktoum"), ("Carlos Mendez", "OPS-32", "@Amina Hassan"),
                              ("Hiroshi Tanaka", "OPS-74", "@Thabo Nkosi")):
            txt = f"{mgr}\nT&E Review Flag - {emp}\nAction Taken: Expenses report {key} denied."
            self.assertIn("slack.b2.messages", self.pre("slack__post_message", self.post(txt)), emp)

    def test_leila_flag_not_enforced_and_unrelated_post_allowed(self):
        txt = "@Thabo Nkosi\nT&E Review Flag - Leila Rahimi\nAction Taken: Expenses report OPS-57 denied."
        self.assertEqual(self.pre("slack__post_message", self.post(txt)), set())
        self.assertEqual(self.pre("slack__post_message", self.post("Expense reviews are in progress.")), set())
        self.assertEqual(self.pre("slack__send_dm", {"user_id": "U110", "text": "Hi Priya, quick question on OPS-39"}),
                         set())

    def test_placeholders_blocked(self):
        bad = B2_OK.replace("OPS-39 denied", "[Report ID] denied")
        self.assertIn("comms.no_placeholders", self.pre("slack__post_message", self.post(bad)))


class TestPreWrites(Base):
    def test_jira_writes_blocked_reads_allowed(self):
        self.assertIn("jira.no_updates", self.pre("jira__transition_issue", {"issue_key": "OPS-39", "transition_id": "1"}))
        self.assertIn("jira.no_updates", self.pre("jira__add_comment", {"issue_key": "OPS-23", "comment": MBJ}))
        self.assertEqual(self.pre("jira__get_issue", {"issue_key": "OPS-39"}), set())

    def test_source_pdfs_read_only(self):
        self.assertIn("files.no_source_edits",
                      self.pre("syntara__writeFile", {"file_path": "/workdir/OPS-HR-TE-Hassan-2026-05-05-01.pdf",
                                                      "content": "x"}))
        code = ("import openpyxl\nd=openpyxl.load_workbook('/workdir/People Directory.xlsx')\n"
                "wb=openpyxl.Workbook()\nwb.save('/workdir/expense_reports.xlsx')")
        self.assertEqual(self.pre("syntara__executePython", {"code": code}), set())


if __name__ == "__main__":
    import unittest
    unittest.main()
