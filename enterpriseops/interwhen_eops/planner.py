"""Plan-completion reminders: the positive complement to blocking rules.

Rules stop wrong actions; they cannot notice an agent that stops after doing only
part of the request. When the ReAct loop is about to end, a checklist induced from
the request is compared with executed tool calls, and still-actionable items are
sent back as an advisory reminder. Never blocks; bounded by the nudge budget.
"""

from __future__ import annotations

import json

import httpx

from .prompts import CHECKLIST_PROMPT, GAP_PROMPT
from .utils import llm

TIMEOUT = 90


async def _chat_json(model: str, system: str, user: str) -> dict:
    """One planner call; returns the reply as a JSON object (an exact code fence is allowed)."""
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        reply = await llm.chat_async(client, model, [{"role": "system", "content": system},
                                                     {"role": "user", "content": user}])
    body = reply["choices"][0]["message"]["content"]
    if not isinstance(body, str):
        raise ValueError("Planner response content must be text")
    body = body.strip()
    if body.startswith("```"):
        lines = body.splitlines()
        if lines[0].strip() not in {"```", "```json"} or len(lines) < 3 or lines[-1].strip() != "```":
            raise ValueError("Planner JSON fence is incomplete or invalid")
        body = "\n".join(lines[1:-1])
    data = json.loads(body.strip())
    if not isinstance(data, dict):
        raise ValueError("Planner response must be an object")
    return data


async def induce_checklist(task_text: str, model: str) -> list[str]:
    """List the outcomes a request explicitly asks for.

    Args:
        task_text: The user request.
        model: Planner model.

    Returns:
        Unique, non-empty outcome strings.

    Raises:
        ValueError: If the reply is still malformed after one format repair.
    """
    key = "items"
    user = f"TASK:\n{task_text}"
    schema = {"type": "object", "properties": {key: {"type": "array", "items": {"type": "string"}}},
              "required": [key], "additionalProperties": False}
    instruction = f"\n\nReturn JSON matching this schema: {json.dumps(schema)}. Use strings, not objects."
    for attempt in range(2):
        try:
            data = await _chat_json(model, CHECKLIST_PROMPT, user + instruction)
        except (ValueError, TypeError):
            if attempt:
                raise
            user += "\n\nYour previous response was not a JSON object. Return only the requested JSON."
            continue
        items = data.get(key)
        if isinstance(items, list) and all(isinstance(item, str) for item in items):
            return list(dict.fromkeys(item.strip() for item in items if item.strip()))
        if attempt == 0:
            user += (f"\n\nYour previous output had the wrong format: {json.dumps(data)}. "
                     f"Reformat {key} as an array of strings; preserve the requested outcomes.")
    raise ValueError(f"Planner {key} must be a list of strings after format repair")


async def incomplete_items(checklist: list[str], history: list[dict], model: str, request: str = "",
                           final_reply: str = "", tools: list[dict] | None = None, policy: str = "") -> list[str]:
    """Checklist items not yet achieved that a permitted available tool can still advance.

    Args:
        checklist: Items from ``induce_checklist``.
        history: Guard tool history (executed and blocked calls).
        model: Planner model.
        request: The user request.
        final_reply: Agent's final message (not evidence of execution).
        tools: Visible tool schemas.
        policy: Source policy.

    Returns:
        Outstanding checklist items, in checklist wording.

    Raises:
        ValueError: If the reply is still malformed after one format repair.
    """
    if not checklist:
        return []
    available = {tool.get("function", tool).get("name") for tool in (tools or [])}
    available.discard(None)
    if not available:
        return []
    calls = json.dumps([step for step in history if not step.get("blocked")], ensure_ascii=True)
    blocked = json.dumps([step for step in history if step.get("blocked")], ensure_ascii=True)
    user = ("CHECKLIST:\n" + "\n".join(f"- {item}" for item in checklist)
            + f"\n\nEXECUTED TOOL CALLS AND RESULTS:\n{calls}"
            + f"\n\nBLOCKED ATTEMPTS (DID NOT EXECUTE):\n{blocked}"
            + f"\n\nAVAILABLE TOOLS:\n{json.dumps(tools)}\n\nPOLICY:\n{policy}"
            + f"\n\nREQUEST:\n{request}\n\nFINAL REPLY (NOT EXECUTION EVIDENCE):\n{final_reply}")
    wanted = {item.casefold(): item for item in checklist}
    schema = {"type": "object", "properties": {"incomplete": {"type": "array", "items": {
        "type": "object", "properties": {"item": {"enum": checklist},
        "next_tool": {"enum": sorted(available)}, "reason": {"type": "string"}},
        "required": ["item", "next_tool", "reason"], "additionalProperties": False}}},
        "required": ["incomplete"], "additionalProperties": False}
    for attempt in range(2):
        try:
            data = await _chat_json(model, GAP_PROMPT, user + f"\nReturn JSON matching: {json.dumps(schema)}")
            proposals = data.get("incomplete")
            if not isinstance(proposals, list):
                raise ValueError("incomplete must be a list")
            for proposal in proposals:
                if (not isinstance(proposal, dict) or set(proposal) != {"item", "next_tool", "reason"}
                        or any(not isinstance(value, str) for value in proposal.values())
                        or not proposal["reason"].strip()):
                    raise ValueError("Each incomplete item needs item, next_tool and reason strings")
            return list(dict.fromkeys(wanted[proposal["item"].strip().casefold()] for proposal in proposals
                if proposal["item"].strip().casefold() in wanted and proposal["next_tool"] in available))
        except (ValueError, TypeError) as error:
            if attempt:
                raise ValueError("Planner actionable items invalid after format repair") from error
            user += f"\nPrevious response invalid: {error}. Return only objects matching the schema."


def format_reminder(items: list[str]) -> str:
    """Advisory reminder message listing outstanding items."""
    listed = "\n".join(f"- {item}" for item in items)
    return ("[Process check: internal, not from the requester]\n"
            "Before finishing, these requested outcomes do not appear to have been "
            f"carried out yet:\n{listed}\n"
            "Complete them with the appropriate tool calls if they are still outstanding, "
            "then give your final answer. If an item is already done, cancelled, out of policy, "
            "or cannot be completed, explain that and finish without bypassing policy.")
