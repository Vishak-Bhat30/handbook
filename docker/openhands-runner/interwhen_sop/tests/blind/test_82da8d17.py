"""Blind unit tests for insurance_vanguard_shield_mutual_82da8d17 (SOP §7.2 multi-beneficiary life claims)."""

from __future__ import annotations

import json
import unittest

from interwhen_sop.tests.base import TaskCase

TASK = "insurance_vanguard_shield_mutual_82da8d17"
OK = '[Tool executed.]{"id": "81001"}'

ALLOC = {
    "CLM_LIFE-1": ("--- Beneficiary Allocation ---\nPolicy: LC-2019-08844 | Face Amount: $400,000.00\n"
                   "Beneficiary 1: Maria L. Martinez | Designation: Primary | Split: 60% | Amount: $240,000.00\n"
                   "Beneficiary 2: David R. Martinez | Designation: Primary | Split: 40% | Amount: $160,000.00\n"
                   "Analyst: TM | Date: 2026-04-10"),
    "CLM_LIFE-2": ("--- Beneficiary Allocation ---\nPolicy: LC-2021-15290 | Face Amount: $250,000.00\n"
                   "Beneficiary 1: Thomas P. Whitfield | Designation: Primary | Split: 50% | Amount: $125,000.00\n"
                   "Beneficiary 2: Emily J. Whitfield | Designation: Primary | Split: 50% | Amount: $125,000.00\n"
                   "Analyst: TM | Date: 2026-04-10"),
    "CLM_LIFE-3": ("--- Beneficiary Allocation ---\nPolicy: LC-2018-06231 | Face Amount: $600,000.00\n"
                   "Beneficiary 1: Mark H. Drummond (Son) | Designation: Primary | Split: 63.636% | Amount: $381,818.18\n"
                   "Beneficiary 2: Susan E. Drummond (Daughter) | Designation: Primary | Split: 36.36% | Amount: $218,181.82\n"
                   "Excluded: Linda M. Drummond (deceased 2026-02-12)\n"
                   "Analyst: TM | Date: 2026-04-10"),
}
OKAFOR_NOTE = ("CLM-920 Complex Beneficiary Hold applied. Potential conflict: attorney_letter_okafor_01.pdf "
               "(attorney letter dated April 4, 2026). Routed to CLM-Legal (nbriggs). No allocation calculated.")


def comment(key, text):
    return "jira__add_comment", {"issue_key": key, "comment": text}


def labels(key, labs, assignee=None):
    f = {"labels": labs}
    if assignee:
        f["assignee"] = assignee
    return "jira__update_issue", {"issue_key": key, "fields": json.dumps(f)}


class Base(TaskCase):
    TASK = TASK

    def do(self, call):
        self.did(call[0], call[1], OK)

    def golden(self, skip=()):
        for k, t in ALLOC.items():
            if ("alloc", k) not in skip:
                self.do(comment(k, t))
            if ("route", k) not in skip:
                self.do(labels(k, ["life-claim", "Route-to-AP-for-Payout"]))
        if "hold" not in skip:
            if "legal" in skip:
                self.do(labels("CLM_LIFE-4", ["life-claim", "CLM-920"]))
            else:
                self.do(labels("CLM_LIFE-4", ["life-claim", "CLM-920", "CLM-Legal"], "nbriggs"))
        if "note" not in skip:
            self.do(comment("CLM_LIFE-4", OKAFOR_NOTE))


class TestInitial(Base):
    def test_initial_obligations(self):
        rules = [r for r, _ in self.done_all()]
        self.assertEqual(rules.count("life.allocation_posted"), 3)
        self.assertEqual(rules.count("life.routed_to_ap"), 3)
        self.assertEqual(rules.count("life.okafor_hold"), 3)
        self.assertEqual(len(rules), 9)

    def test_golden_path(self):
        self.golden()
        self.assertEqual(self.done(), {})


class TestAllocationFormat(Base):
    def test_correct_comments_pass(self):
        for k, t in ALLOC.items():
            self.assertEqual(self.pre(*comment(k, t)), set(), k)

    def test_drummond_without_redistribution_blocked(self):
        bad = ("--- Beneficiary Allocation ---\nPolicy: LC-2018-06231 | Face Amount: $600,000.00\n"
               "Beneficiary 1: Linda M. Drummond | Designation: Primary | Split: 45% | Amount: $270,000.00\n"
               "Beneficiary 2: Mark H. Drummond | Designation: Primary | Split: 35% | Amount: $210,000.00\n"
               "Beneficiary 3: Susan E. Drummond | Designation: Primary | Split: 20% | Amount: $120,000.00\n"
               "Analyst: TM | Date: 2026-04-10")
        self.assertIn("life.allocation_format", self.pre(*comment("CLM_LIFE-3", bad)))

    def test_contingent_listed_blocked(self):
        bad = ALLOC["CLM_LIFE-1"].replace(
            "Analyst:", "Beneficiary 3: Elena Martinez | Designation: Contingent | Split: 0% | Amount: $0.00\nAnalyst:")
        self.assertIn("life.allocation_format", self.pre(*comment("CLM_LIFE-1", bad)))

    def test_analyst_placeholder_blocked(self):
        bad = ALLOC["CLM_LIFE-2"].replace("Analyst: TM", "Analyst: [Initials]")
        self.assertIn("life.allocation_format", self.pre(*comment("CLM_LIFE-2", bad)))

    def test_wrong_amount_blocked(self):
        bad = ALLOC["CLM_LIFE-2"].replace("$125,000.00\nBeneficiary 2", "$120,000.00\nBeneficiary 2")
        self.assertIn("life.allocation_format", self.pre(*comment("CLM_LIFE-2", bad)))

    def test_gives_up_after_two_denials(self):
        bad = ALLOC["CLM_LIFE-2"].replace("Analyst: TM", "Analyst: AI")
        self.records += [{"type": "rejection", "call_id": "x1", "text": "[alloc:CLM_LIFE-2] ..."},
                         {"type": "rejection", "call_id": "x2", "text": "[alloc:CLM_LIFE-2] ..."}]
        self.assertEqual(self.pre(*comment("CLM_LIFE-2", bad)), set())

    def test_completion_requires_valid_comment(self):
        self.golden(skip={("alloc", "CLM_LIFE-2"), ("route", "CLM_LIFE-2")})
        self.do(comment("CLM_LIFE-2", ALLOC["CLM_LIFE-2"].replace("Analyst: TM", "Analyst: AI Assistant")))
        self.do(labels("CLM_LIFE-2", ["Route-to-AP-for-Payout"]))
        self.assertEqual(set(self.done()), {"life.allocation_posted"})


class TestOkaforStop(Base):
    def test_hold_note_and_legal_routing_allowed(self):
        self.assertEqual(self.pre(*comment("CLM_LIFE-4", OKAFOR_NOTE)), set())
        self.assertEqual(self.pre(*comment("CLM_LIFE-4", OKAFOR_NOTE + " Policy LC-2020-11467 | Face Amount: "
                                                                      "$350,000.00; primaries Emeka 70%, Chidi 30%.")),
                         set())
        self.assertEqual(self.pre(*labels("CLM_LIFE-4", ["CLM-920", "CLM-Legal"], "nbriggs")), set())

    def test_allocation_on_okafor_blocked(self):
        alloc = ("--- Beneficiary Allocation ---\nPolicy: LC-2020-11467 | Face Amount: $350,000.00\n"
                 "Beneficiary 1: Emeka A. Okafor | Designation: Primary | Split: 70% | Amount: $245,000.00\n"
                 "Beneficiary 2: Chidi E. Okafor | Designation: Primary | Split: 30% | Amount: $105,000.00\n"
                 "Analyst: TM | Date: 2026-04-10")
        self.assertIn("life.okafor_stop", self.pre(*comment("CLM_LIFE-4", alloc)))

    def test_route_okafor_to_ap_blocked(self):
        self.assertIn("life.okafor_stop", self.pre(*labels("CLM_LIFE-4", ["Route-to-AP-for-Payout"])))

    def test_external_email_about_okafor_blocked(self):
        args = {"to": "cadeyemi@acrlaw.com", "subject": "Okafor claim LC-2020-11467", "body": "Payout update"}
        self.assertIn("life.okafor_stop", self.pre("google_mail__send_email", args))
        args = {"to": "nathan.briggs@vanguardshield.com", "subject": "Okafor claim LC-2020-11467", "body": "On hold"}
        self.assertEqual(self.pre("google_mail__send_email", args), set())

    def test_completion_missing_note(self):
        self.golden(skip={"note"})
        self.do(comment("CLM_LIFE-4", "CLM-920 Complex Beneficiary Hold applied; routed to CLM-Legal."))
        self.assertIn("note comment", self.done()["life.okafor_hold"])

    def test_completion_missing_legal(self):
        self.golden(skip={"legal"})
        self.assertIn("CLM-Legal", self.done()["life.okafor_hold"])

    def test_completion_missing_hold(self):
        self.golden(skip={"hold", "note"})
        self.do(comment("CLM_LIFE-4", "Potential conflict noted: attorney_letter_okafor_01.pdf dated 2026-04-04. "
                                      "No CLM-920 hold set yet."))
        self.do(labels("CLM_LIFE-4", ["life-claim"], "nbriggs"))
        self.assertIn("set CLM-920", self.done()["life.okafor_hold"])


class TestNoHoldOnClearClaims(Base):
    def test_hold_label_on_martinez_blocked(self):
        self.assertIn("life.no_hold_on_clear_claims", self.pre(*labels("CLM_LIFE-1", ["life-claim", "CLM-920"])))
        self.assertIn("life.no_hold_on_clear_claims", self.pre(*labels("CLM_LIFE-3", ["CLM-910"])))

    def test_other_labels_allowed(self):
        self.assertEqual(self.pre(*labels("CLM_LIFE-2", ["life-claim", "allocation-complete"])), set())


class TestRouteAfterAllocation(Base):
    def test_route_before_allocation_blocked(self):
        self.assertIn("life.route_after_allocation",
                      self.pre(*labels("CLM_LIFE-1", ["life-claim", "Route-to-AP-for-Payout"])))

    def test_route_after_allocation_allowed(self):
        self.do(comment("CLM_LIFE-1", ALLOC["CLM_LIFE-1"]))
        self.assertEqual(self.pre(*labels("CLM_LIFE-1", ["life-claim", "Route-to-AP-for-Payout"])), set())

    def test_not_routed_completion(self):
        self.golden(skip={("route", "CLM_LIFE-3")})
        self.do(comment("CLM_LIFE-3", "Route to AP for Payout transition is not available; not routed."))
        self.assertEqual(set(self.done()), {"life.routed_to_ap"})
        self.assertIn("CLM_LIFE-3", self.done()["life.routed_to_ap"])

    def test_affirmative_comment_counts_as_routed(self):
        self.golden(skip={("route", "CLM_LIFE-3")})
        self.do(comment("CLM_LIFE-3", "Routed to AP for payout with the allocation comment in place."))
        self.assertEqual(self.done(), {})


if __name__ == "__main__":
    unittest.main()
