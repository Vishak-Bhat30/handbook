"""A minimal valid policy package shared by the tests."""

from interwhen_eops.utils.contracts import format_schema

POLICY = ("Agents must not delete a ticket unless the requester is an administrator.\n"
          "Be polite with every requester.")

VARIABLES = [
    {"name": "action_deletes_ticket", "type": "bool", "category": "action",
     "description": "The candidate call deletes a ticket."},
    {"name": "context_requester_is_admin", "type": "bool", "category": "context",
     "description": "A prior lookup confirmed the requester is an administrator."},
]

RULE = {"id": "admin_delete", "title": "Only administrators may delete tickets",
        "rationale": "The policy restricts deletion.", "source": "policy", "reference": "1",
        "quote": "must not delete a ticket unless the requester is an administrator",
        "remediation": "Confirm the requester is an administrator first.",
        "when": {"op": "is_true", "field": "action_deletes_ticket"},
        "then": {"op": "is_true", "field": "context_requester_is_admin"}}


def package() -> dict:
    """Fresh copy of a valid package enforcing ``RULE`` over ``POLICY``."""
    reviewer = {"instructions": "Review rules against the policy.", "decision_key": "approved", "issues_key": "issues"}
    extractor = {"instructions": "Extract the requested facts.", "facts_key": "facts", "evidence_key": "evidence"}
    reviewer["response_schema"] = format_schema(reviewer, VARIABLES, "reviewer")
    extractor["response_schema"] = format_schema(extractor, VARIABLES, "extractor")
    return {"variables": [dict(item) for item in VARIABLES], "rules": [dict(RULE)],
            "inventory": [
                {"id": "c1", "quote": "Agents must not delete a ticket unless the requester is an administrator.",
                 "status": "enforced", "rule_ids": ["admin_delete"], "reason": "Observable before deletion."},
                {"id": "c2", "quote": "Be polite with every requester.", "status": "unobservable",
                 "rule_ids": [], "reason": "Tone is not visible in a tool call."}],
            "reviewer_format": reviewer, "extractor_format": extractor}
