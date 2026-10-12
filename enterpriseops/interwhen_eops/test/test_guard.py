"""Pre-tool guard behaviour on a fake ReAct base class."""

import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest import mock

from interwhen_eops.guard import make_orchestrator, tool_result_failed
from interwhen_eops.test.fixtures import POLICY, package
from interwhen_eops.utils import llm
from interwhen_eops.utils.data import policy_id


class FakeReact:
    """Stand-in for the gym's ReactOrchestrator that proposes one ``delete_ticket`` call."""

    def __init__(self):
        """Mimic the orchestrator attributes the guard reads."""
        self.config = SimpleNamespace(system_prompt=POLICY, user_prompt="Delete ticket 7.")
        self.available_tools = [{"name": "delete_ticket", "inputSchema": {"type": "object"}}]
        self.tool_to_server_mapping = {"delete_ticket": "itsm"}
        self.max_iterations = 50
        self.executed = []

    async def _execute_tool_call(self, name, args):
        """Record and succeed."""
        self.executed.append(name)
        return {"result": {"success": True, "result": {"deleted": args["id"]}}, "gym_server": "itsm"}

    async def execute(self):
        """Make the single call and finish."""
        result = {"conversation_flow": [], "messages": [], "final_response": ""}
        result["tool_results"] = [await self._execute_tool_call("delete_ticket", {"id": 7})]
        return result


def extractor_reply(facts: dict) -> dict:
    """Completion carrying ``facts`` in the fixture's extractor format."""
    evidence = {name: "" if value is None else "visible" for name, value in facts.items()}
    return {"model": "claude-sonnet-5",
            "choices": [{"message": {"content": json.dumps({"facts": facts, "evidence": evidence})}}]}


class GuardTest(unittest.TestCase):
    """Blocking, abstention, fail-open and audit behaviour."""

    def run_guard(self, reply):
        """Run the guarded fake with ``reply`` as the extractor's side effect.

        Returns:
            ``(orchestrator, result, audit step)``.
        """
        guarded = make_orchestrator(FakeReact, {policy_id(POLICY): package()})()
        with mock.patch.object(llm, "chat_async", mock.AsyncMock(side_effect=reply)):
            result = asyncio.run(guarded.execute())
        audit = [step for step in result["conversation_flow"] if step["type"] == "interwhen_audit"]
        self.assertEqual(len(audit), 1)
        return guarded, result, audit[0]

    def test_failing_rule_blocks_with_remediation_and_quote(self):
        """A failing rule blocks the call and explains why."""
        guarded, result, audit = self.run_guard(lambda *_: extractor_reply(
            {"action_deletes_ticket": True, "context_requester_is_admin": False}))
        blocked = result["tool_results"][0]["result"]
        self.assertEqual(blocked["error"], "policy_violation")
        self.assertIn("admin_delete", blocked["result"])
        self.assertIn("unless the requester is an administrator", blocked["result"])
        self.assertEqual(guarded.executed, [])
        self.assertEqual(audit["blocked_calls"], 1)
        self.assertIn("BLOCKED BY POLICY", guarded._trajectory_digest())

    def test_unknown_context_abstains_and_executes(self):
        """An unknown context requirement abstains and the call runs."""
        guarded, _, audit = self.run_guard(lambda *_: extractor_reply(
            {"action_deletes_ticket": True, "context_requester_is_admin": None}))
        self.assertEqual(guarded.executed, ["delete_ticket"])
        self.assertEqual(audit["checks"][0]["results"], [{"rule": "admin_delete", "status": "unknown"}])

    def test_extractor_failure_fails_open(self):
        """Extractor infrastructure errors never block."""
        guarded, _, audit = self.run_guard(ConnectionError("down"))
        self.assertEqual(guarded.executed, ["delete_ticket"])
        self.assertEqual(audit["extractor_errors"], 1)

    def test_model_identity_change_is_not_swallowed(self):
        """A substituted extractor model stops the run."""
        with self.assertRaises(llm.ModelIdentityError):
            self.run_guard(llm.ModelIdentityError("other model"))

    def test_nested_tool_failures_are_detected(self):
        """Errors inside a success envelope count as failures."""
        nested = {"success": True, "content": [{"type": "text", "text": json.dumps({"status": "error"})}]}
        self.assertTrue(tool_result_failed(nested))
        self.assertFalse(tool_result_failed({"success": True, "result": {"id": 1}}))


if __name__ == "__main__":
    unittest.main()
