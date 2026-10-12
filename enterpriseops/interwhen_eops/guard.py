"""Pre-tool policy guard layered on the gym's ReAct orchestrator.

For each candidate tool call the task's reviewed package names the facts its rules
read. The extractor model fills them from what the agent can already see (request,
tool history, candidate call and its schema), never from the gym database or the
graders. ``dsl.check`` evaluates every rule; the first FAIL blocks the call and the
agent receives the rule's remediation and policy quote instead of a tool result.
Extraction failures abstain (fail open). When the loop is about to finish, the
planner may add bounded reminders. Every decision lands in one ``interwhen_audit``
step of the conversation flow.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy

import httpx

from . import planner
from .dsl import check, referenced_fields
from .prompts import EXTRACTION_GUARD
from .utils import config, llm
from .utils.contracts import digest, extraction_schema, parse_extraction, validate_package
from .utils.data import policy_id

logger = logging.getLogger(__name__)


def tool_result_failed(value) -> bool:
    """Whether a tool result reports failure anywhere, including nested JSON text content."""
    if not isinstance(value, dict):
        return False
    if (value.get("success") is False or value.get("isError") is True
            or value.get("error") or value.get("status") in ("error", "failed")):
        return True
    if any(tool_result_failed(value.get(key)) for key in ("result", "data", "detail", "structuredContent")):
        return True
    for item in value.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            try:
                body = json.loads(item.get("text", ""))
            except (ValueError, TypeError):
                continue
            if tool_result_failed(body):
                return True
    return False


def selected_schema(tools, tool_name: str):
    """Input schema of ``tool_name`` if exactly one visible tool has that name, else None."""
    matches = [function.get("parameters", function.get("inputSchema")) for function in
               (tool.get("function", tool) for tool in tools if isinstance(tool, dict))
               if isinstance(function, dict) and function.get("name") == tool_name]
    return matches[0] if len(matches) == 1 and isinstance(matches[0], dict) else None


def text_content(content) -> str:
    """Text of a model message whose content may be a list of blocks."""
    if isinstance(content, list):
        return next((block.get("text", "") for block in content
                     if isinstance(block, dict) and block.get("type") == "text"), "")
    return content or ""


def make_orchestrator(base_class, packages: dict[str, dict]):
    """Build the guarded orchestrator class.

    Args:
        base_class: The gym's ``ReactOrchestrator``.
        packages: Policy ID to reviewed package.

    Returns:
        Subclass of ``base_class`` with the pre-tool guard and planner reminders.
    """
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

    frozen = deepcopy(packages)
    extractor, planner_model = config.model("extractor"), config.model("planner")
    plan_nudges = config.plan_max_nudges() if config.plan_enabled() else 0

    class InterwhenOrchestrator(base_class):
        """ReAct orchestrator that checks every tool call against the task's reviewed package."""

        def __init__(self, *args, **kwargs):
            """Initialize the base orchestrator and bind the package for the task's policy.

            Raises:
                ValueError: If the policy has no package or the package is invalid for it.
            """
            super().__init__(*args, **kwargs)
            self._policy_id = policy_id(self.config.system_prompt)
            if self._policy_id not in frozen:
                raise ValueError(f"No reviewed package for policy {self._policy_id}")
            self._package = frozen[self._policy_id]
            validate_package(self._package, self.config.system_prompt)
            self._categories = {item["name"]: item["category"] for item in self._package["variables"]}
            self._history, self._interventions, self._nudges, self._audit, self._extractions = [], [], [], [], []
            self._extract_errors = self._extract_repairs = self._plan_errors = 0

        def _trajectory_digest(self) -> str:
            """Request and tool history as the extractor sees it; blocked calls are marked."""
            lines = [f"REQUEST:\n{self.config.user_prompt}\n\nTOOL HISTORY:"]
            for step in self._history:
                if step.get("blocked"):
                    lines.append(f"- {step['tool']}({json.dumps(step['args'])}) -> BLOCKED BY POLICY,"
                                 f" did not execute, returned no data")
                else:
                    lines.append(f"- {step['tool']}({json.dumps(step['args'])})"
                                 f" -> {step.get('status', 'ok')} {json.dumps(step.get('result'))}")
            if not self._history:
                lines.append("(no tool calls yet)")
            return "\n".join(lines)

        async def _extract_facts(self, tool_name, tool_args, names):
            """Extract facts for a candidate call.

            Args:
                tool_name: Candidate tool.
                tool_args: Candidate arguments.
                names: Facts the rules read.

            Returns:
                Known facts (unknown action facts as False); empty if extraction failed.
            """
            package = self._package
            specification = package["extractor_format"]
            schema = extraction_schema(package, names)
            context = {"policy": self.config.system_prompt,
                       "facts": [item for item in package["variables"] if item["name"] in names],
                       "visible_history": self._trajectory_digest(),
                       "candidate": {"tool": tool_name, "arguments": tool_args},
                       "selected_tool_schema": selected_schema(self.available_tools, tool_name),
                       "response_schema": schema}
            messages = [{"role": "system", "content": EXTRACTION_GUARD + "\nGENERATED EXTRACTION INSTRUCTIONS:\n"
                         + specification["instructions"]},
                        {"role": "user", "content": json.dumps(context, ensure_ascii=True)}]
            audit = {"tool": tool_name, "candidate_sha256": digest(tool_args), "format_sha256": digest(specification),
                     "response_schema": schema, "attempts": []}
            try:
                async with httpx.AsyncClient(timeout=180) as client:
                    for attempt in range(2):
                        reply = await llm.chat_async(client, extractor, deepcopy(messages))
                        audit["attempts"].append({"request_sha256": digest(messages), "response": reply})
                        body = reply["choices"][0]["message"].get("content")
                        try:
                            facts, evidence = parse_extraction(package, names, json.loads(body))
                            break
                        except (ValueError, TypeError) as error:
                            if attempt:
                                raise
                            self._extract_repairs += 1
                            messages += [{"role": "assistant", "content": body or ""},
                                         {"role": "user", "content": f"Format error: {error}. Return the supplied "
                                          "schema with null for unknown facts."}]
                audit.update(facts=facts, evidence=evidence)
            except llm.ModelIdentityError:
                raise
            except Exception as error:  # noqa: BLE001 - extraction failure abstains
                self._extract_errors += 1
                audit["error_type"] = type(error).__name__
                self._extractions.append(audit)
                logger.warning("interwhen: fact extraction failed (%s) - abstaining", error)
                return {}
            self._extractions.append(audit)
            # Closed world for action facts (the candidate is the full proposal); unknown context stays unknown.
            return {name: False if value is None else value for name, value in facts.items()
                    if value is not None or self._categories[name] == "action"}

        async def _evaluate(self, tool_name, tool_args):
            """Evaluate every rule for a candidate call and audit the result.

            Returns:
                The first failing rule, or None if the call may run.
            """
            rules = self._package["rules"]
            if not rules:
                self._audit.append({"tool": tool_name, "args": tool_args, "facts": {}, "results": [],
                                    "blocked_rule": None})
                return None
            names = sorted({name for rule in rules for side in ("when", "then") for name in referenced_fields(rule[side])})
            if not names:
                return None
            facts = await self._extract_facts(tool_name, tool_args, names)
            if not facts:
                self._audit.append({"tool": tool_name, "args": tool_args, "facts": {},
                                    "results": [{"rule": rule["id"], "status": "unknown"} for rule in rules],
                                    "blocked_rule": None})
                return None
            results, violation = [], None
            for rule in rules:
                outcome = check(rule, facts, self._categories)
                results.append({"rule": rule["id"], "status": "unknown" if outcome.passed is None
                                else "pass" if outcome.passed else "fail"})
                if outcome.passed is False and violation is None:
                    violation = rule
            self._audit.append({"tool": tool_name, "args": tool_args, "facts": facts, "results": results,
                                "blocked_rule": violation["id"] if violation else None})
            return violation

        async def _execute_tool_call(self, tool_name, tool_args):
            """Run the call unless a rule fails; a blocked call returns a ``policy_violation`` result."""
            rule = await self._evaluate(tool_name, tool_args)
            if rule:
                feedback = (f"Blocked by policy rule '{rule['id']}'. {rule['remediation']} "
                            f"Policy says: \"{rule['quote']}\"")
                self._interventions.append({"tool": tool_name, "args": tool_args, "rule": rule["id"],
                                            "policy": self._policy_id, "remediation": rule["remediation"]})
                self._history.append({"tool": tool_name, "args": tool_args, "blocked": True, "result": feedback})
                logger.info("interwhen: BLOCKED %s via %s", tool_name, rule["id"])
                return {"result": {"success": False, "result": feedback, "error": "policy_violation"},
                        "gym_server": self.tool_to_server_mapping.get(tool_name, "")}
            executed = await super()._execute_tool_call(tool_name, tool_args)
            payload = executed.get("result", {})
            succeeded = payload.get("success") is True and not tool_result_failed(payload)
            self._history.append({"tool": tool_name, "args": tool_args, "status": "ok" if succeeded else "error",
                                  "result": payload.get("result")})
            return executed

        async def execute(self):
            """Run the ReAct loop, add bounded planner reminders, then append the audit step."""
            result = await super().execute()
            messages = result.get("messages") or []
            checklist = None
            for _ in range(plan_nudges):
                turns = sum(step.get("type") == "ai_message" for step in result["conversation_flow"])
                if (turns >= self.max_iterations or not messages
                        or not isinstance(messages[-1], AIMessage) or messages[-1].tool_calls):
                    break
                try:
                    if checklist is None:
                        checklist = await planner.induce_checklist(self.config.user_prompt, planner_model)
                    missing = await planner.incomplete_items(
                        checklist, self._history, planner_model, request=self.config.user_prompt,
                        final_reply=result["final_response"], tools=self.available_tools,
                        policy=self.config.system_prompt)
                except Exception as error:  # noqa: BLE001 - the planner is advisory
                    self._plan_errors += 1
                    logger.warning("interwhen plan: check failed (%s)", error)
                    break
                reminded = {item.casefold() for nudge in self._nudges for item in nudge}
                missing = [item for item in missing if item.casefold() not in reminded]
                if not missing:
                    break
                self._nudges.append(missing)
                reminder = planner.format_reminder(missing)
                messages.append(HumanMessage(content=reminder))
                result["conversation_flow"].append({"type": "plan_reminder", "content": reminder})
                result = await self._continue_from(messages, result)
                messages = result["messages"]
            result["conversation_flow"].append({
                "type": "interwhen_audit", "policy_id": self._policy_id, "runtime_version": config.RUNTIME_VERSION,
                "package_sha256": digest(self._package), "extractor_model": extractor,
                "planner_model": planner_model, "planner_enabled": plan_nudges > 0, "nudges": self._nudges,
                "checks": self._audit, "extractions": self._extractions, "blocked_calls": len(self._interventions),
                "extractor_repairs": self._extract_repairs, "extractor_errors": self._extract_errors,
                "planner_errors": self._plan_errors})
            return result

        async def _continue_from(self, messages, result):
            """Resume the ReAct loop after a reminder within the original iteration budget."""
            flow = result.setdefault("conversation_flow", [])
            used = result.setdefault("tools_used", [])
            results = result.setdefault("tool_results", [])
            remaining = self.max_iterations - sum(step.get("type") == "ai_message" for step in flow)
            for _ in range(remaining):
                response = await self.llm_client.invoke_with_tools(messages, self.available_tools)
                messages.append(response)
                flow.append({"type": "ai_message", "content": text_content(response.content),
                             "usage_metadata": getattr(response, "usage_metadata", None),
                             "response_metadata": getattr(response, "response_metadata", None),
                             "tool_calls": [{"name": call["name"], "args": call["args"]}
                                            for call in (response.tool_calls or [])]})
                if not response.tool_calls:
                    break
                for call in response.tool_calls:
                    executed = await self._execute_tool_call(call["name"], call["args"])
                    payload = executed["result"]
                    if call["name"] not in used:
                        used.append(call["name"])
                    results.append({"tool_name": call["name"], "arguments": call["args"], "result": payload,
                                    "gym_server": executed["gym_server"]})
                    messages.append(ToolMessage(content=json.dumps(payload.get("result", {})),
                                                tool_call_id=call.get("id", "")))
                    flow.append({"type": "tool_result", "tool_name": call["name"], "result": payload,
                                 "gym_server": executed["gym_server"]})
            result["messages"] = messages
            result["final_response"] = text_content(messages[-1].content) if messages else ""
            return result

    return InterwhenOrchestrator
