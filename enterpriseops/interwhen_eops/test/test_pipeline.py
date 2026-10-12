"""Review, repair, generation patches, gym adapters and arm comparison."""

import json
import tempfile
import unittest
from pathlib import Path

from interwhen_eops import evaluate
from interwhen_eops.generate import apply_patch
from interwhen_eops.repair import apply_patch_reply, keyed_package, validate_repair
from interwhen_eops.review import apply_reviews, held_rules
from interwhen_eops.test.fixtures import POLICY, RULE, package
from interwhen_eops.utils import gym


class ReviewTest(unittest.TestCase):
    """Applying reviewer findings."""

    def finding(self, **changes) -> dict:
        """An approving finding for ``RULE`` with ``changes`` applied."""
        return {"rule_id": "admin_delete", "status": "approved", "quote": RULE["quote"], "reason": "Faithful.",
                "replacement_rule": None, **changes}

    def test_same_id_replacement_is_applied(self):
        """An approved same-ID replacement replaces the rule."""
        replacement = {**RULE, "remediation": "Look up the requester's role first."}
        candidate, records = apply_reviews(package(), POLICY, ["admin_delete"],
                                           {"reviews": [self.finding(replacement_rule=replacement)]})
        self.assertEqual(candidate["rules"][0]["remediation"], replacement["remediation"])
        self.assertEqual(records[0]["status"], "approved")

    def test_invalid_findings_are_rejected(self):
        """Missing, uncited or unresolved-with-replacement findings are rejected."""
        for reply in ({"reviews": []}, {"reviews": [self.finding(quote="invented")]},
                      {"reviews": [self.finding(status="unresolved", replacement_rule=RULE)]}):
            with self.subTest(reply=reply), self.assertRaises(ValueError):
                apply_reviews(package(), POLICY, ["admin_delete"], reply)

    def test_held_rules_prefer_unresolved(self):
        """Repair targets unresolved rules first, else the whole batch."""
        feedback = {"reply": {"reviews": [{"rule_id": "a", "status": "approved", "replacement_rule": {}},
                                          {"rule_id": "b", "status": "unresolved"}]}}
        self.assertEqual(held_rules(feedback, ["a", "b", "c"]), ["b"])
        self.assertEqual(held_rules({"reply": None}, ["a", "c"]), ["a", "c"])


class RepairTest(unittest.TestCase):
    """Stable-ID patches and repair validation."""

    def test_keyed_round_trip(self):
        """An unchanged keyed package materializes back to the original."""
        self.assertEqual(validate_repair(package(), keyed_package(package()), POLICY, [], set()), package())

    def test_patches_use_stable_ids_and_retirements_are_required(self):
        """Whole collections cannot be patched; removals need selection and a retirement."""
        keyed = keyed_package(package())
        with self.assertRaises(ValueError):
            apply_patch_reply(keyed, {"patch": [{"op": "replace", "path": "/rules", "value": {}}],
                                      "retirements": [], "done": True}, POLICY)
        removal = {"patch": [{"op": "remove", "path": "/rules/admin_delete"},
                             {"op": "replace", "path": "/inventory/c1/status", "value": "ambiguous"},
                             {"op": "replace", "path": "/inventory/c1/rule_ids", "value": []},
                             {"op": "remove", "path": "/variables/action_deletes_ticket"},
                             {"op": "remove", "path": "/variables/context_requester_is_admin"}],
                   "retirements": [], "done": True}
        updated = apply_patch_reply(keyed, removal, POLICY)
        with self.assertRaises(ValueError):
            validate_repair(package(), updated, POLICY, [], {"admin_delete"})
        retirement = [{"rule_id": "admin_delete", "quote": RULE["quote"], "reason": "Unsupported."}]
        self.assertEqual(validate_repair(package(), updated, POLICY, retirement, {"admin_delete"})["rules"], [])
        with self.assertRaises(ValueError):
            validate_repair(package(), updated, POLICY, retirement, set())


class GenerationPatchTest(unittest.TestCase):
    """Creator patch replies."""

    def test_patch_reply_contract(self):
        """Valid patches apply; invalid paths are rejected."""
        patched = apply_patch(package(), {"patch": [{"op": "replace", "path": "/rules/0/title", "value": "X"}],
                                          "reason": "Fix title."})
        self.assertEqual(patched["rules"][0]["title"], "X")
        with self.assertRaises(ValueError):
            apply_patch(package(), {"patch": [{"op": "remove", "path": "/missing"}], "reason": "x"})


class GymAdapterTest(unittest.TestCase):
    """Runtime adapters for an unmodified gym."""

    def test_numeric_sql_comparison(self):
        """Numbers compare numerically with numeric strings; other types are unchanged."""
        self.assertTrue(gym.compare_values(3, "3", "equals")["passed"])
        self.assertTrue(gym.compare_values(2.50, "2.5", "equals")["passed"])
        self.assertFalse(gym.compare_values("3", "3.0", "equals")["passed"])
        self.assertTrue(gym.compare_values(5, "4", "greater_than")["passed"])
        self.assertTrue(gym.compare_values("abc", "b", "contains")["passed"])

    def test_create_call_source_schema(self):
        """The call source schema gains ``identity.user``; an unexpected upstream schema is refused."""
        identity = {"properties": {"applicationInstance": {"type": "object"}}}
        tools = [{"name": "create_call", "inputSchema": {"properties": {"source": {
            "description": "old", "properties": {"identity": identity}}}}}, {"name": "other"}]
        source = gym.tool_catalog(tools)[0]["inputSchema"]["properties"]["source"]
        self.assertEqual(set(source["properties"]["identity"]["properties"]["user"]["properties"]),
                         {"id", "displayName", "tenantId"})
        self.assertEqual(tools[0]["inputSchema"]["properties"]["source"]["description"], "old")
        identity["properties"]["user"] = {"type": "object"}
        with self.assertRaises(ValueError):
            gym.tool_catalog(tools)

    def test_task_payload_normalization(self):
        """Payloads run once, with stripped context keys and unique verifier names."""
        task = {"task_id": "t1", "domain": "hr", "system_prompt": POLICY, "user_prompt": "Do it.",
                "gym_servers_config": json.dumps([{"context": {" user_id ": "u1"}}]),
                "verifiers": json.dumps([{"name": "check"}, {"name": "check"}, {}]), "number_of_runs": 3}
        payload = gym.task_payload(task)
        self.assertNotIn("task_id", payload)
        self.assertEqual(payload["gym_servers_config"][0]["context"], {"user_id": "u1"})
        self.assertEqual([item["name"] for item in payload["verifiers"]], ["01_check", "02_check", "03_verifier_3"])
        self.assertEqual((payload["number_of_runs"], payload["reset_database_between_runs"]), (1, True))


class CompareTest(unittest.TestCase):
    """Arm comparison and error archiving."""

    def write(self, folder: Path, task: str, success: bool, error=None) -> None:
        """Write a payload and a one-run result for ``task``."""
        (folder / "payloads").mkdir(parents=True, exist_ok=True)
        (folder / "payloads" / f"{task}.json").write_text(json.dumps({"system_prompt": POLICY}))
        (folder / f"results_{task}.json").write_text(json.dumps({"runs": [
            {"overall_success": success, "error": error, "conversation_flow": []}]}))

    def test_paired_comparison_and_error_archive(self):
        """Errored tasks are unpaired; train losses select policies; connection errors are archived."""
        with tempfile.TemporaryDirectory() as root:
            baseline, guarded = Path(root, "b"), Path(root, "i")
            for task, left, right in (("t1", True, False), ("t2", False, True), ("t3", True, True)):
                self.write(baseline, task, left)
                self.write(guarded, task, right)
            self.write(guarded, "t4", False, "Connection error.")
            self.write(baseline, "t4", True)
            result = evaluate.compare(baseline, guarded, train_ids=["t1"])
            self.assertEqual((result["paired"], result["gains"], result["losses"]), (3, ["t2"], ["t1"]))
            self.assertEqual(len(result["regression_policies"]), 1)
            self.assertEqual(evaluate.archive_errors(guarded), ["t4"])
            self.assertFalse((guarded / "results_t4.json").exists())
            self.assertTrue((guarded / "_superseded" / "results_t4.0.json").exists())


if __name__ == "__main__":
    unittest.main()
