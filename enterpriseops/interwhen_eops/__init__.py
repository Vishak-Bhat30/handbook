"""Interwhen for EnterpriseOps-Gym: reviewed policy guards around a ReAct agent.

Each task's system prompt is a source policy. Offline, a creator model drafts a
package per policy (Boolean facts, DSL rules quoting the policy, a clause
inventory and extractor/reviewer formats); every rule is reviewed against the
policy and repaired where needed (``generate``, ``review``, ``repair``). Online,
``guard`` wraps the gym's ReAct orchestrator: an extractor model fills the facts
for each candidate tool call, ``dsl`` evaluates the rules, failing calls are
blocked with the rule's remediation, and ``planner`` reminds the agent of
requested outcomes still outstanding at wrap-up.

``policies/`` holds the 75 reviewed packages and ``split.json`` the frozen
130/519 train/test split (training drawn from teams, csm and hr). Helpers live in
``utils/`` and tests in ``test/``. Run ``python -m interwhen_eops --help``.
"""
