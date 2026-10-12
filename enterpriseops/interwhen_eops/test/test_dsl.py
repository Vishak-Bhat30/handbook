"""Three-valued rule evaluation."""

import unittest

from interwhen_eops.dsl import check, evaluate, referenced_fields

CATEGORIES = {"action_a": "action", "action_b": "action", "context_c": "context"}


def leaf(op: str, field: str, **extra) -> dict:
    """Field expression such as ``{"op": "is_true", "field": ...}``."""
    return {"op": op, "field": field, **extra}


class DslTest(unittest.TestCase):
    """Rule semantics, including abstention and action softening."""

    def test_rule_does_not_apply_passes(self):
        """A false ``when`` passes."""
        rule = {"when": leaf("is_true", "action_a"), "then": {"op": "const", "value": False}}
        self.assertTrue(check(rule, {"action_a": False}, CATEGORIES).passed)

    def test_prohibition_fails_when_applicable(self):
        """A prohibition fails once its scope applies."""
        rule = {"when": leaf("is_true", "action_a"), "then": {"op": "const", "value": False}}
        self.assertIs(check(rule, {"action_a": True}, CATEGORIES).passed, False)

    def test_unknown_when_field_abstains(self):
        """Any unknown ``when`` field abstains, even if the scope could be decided."""
        rule = {"when": {"op": "or", "args": [leaf("is_true", "action_a"), leaf("is_true", "context_c")]},
                "then": {"op": "const", "value": False}}
        outcome = check(rule, {"action_a": False}, CATEGORIES)
        self.assertIsNone(outcome.passed)
        self.assertEqual(outcome.missing, ["context_c"])

    def test_positive_action_obligation_abstains_but_context_is_enforced(self):
        """A missing action property abstains; a false context requirement fails."""
        when = leaf("is_true", "action_a")
        softened = check({"when": when, "then": leaf("is_true", "action_b")}, {"action_a": True, "action_b": False}, CATEGORIES)
        self.assertIsNone(softened.passed)
        enforced = check({"when": when, "then": leaf("is_true", "context_c")}, {"action_a": True, "context_c": False}, CATEGORIES)
        self.assertIs(enforced.passed, False)
        self.assertEqual(enforced.violating, ["context_c"])

    def test_and_or_with_constants(self):
        """Constants decide ``and``/``or`` despite unknown siblings."""
        self.assertIs(evaluate({"op": "and", "args": [{"op": "const", "value": False}, leaf("is_true", "x")]}, {}).value, False)
        self.assertIsNone(evaluate({"op": "and", "args": [{"op": "const", "value": True}, leaf("is_true", "x")]}, {}).value)
        self.assertIs(evaluate({"op": "or", "args": [leaf("is_true", "x"), {"op": "const", "value": True}]}, {}).value, True)
        self.assertIs(evaluate({"op": "or", "args": [{"op": "const", "value": False}, leaf("is_false", "x")]}, {"x": True}).value, False)

    def test_implies_and_comparisons(self):
        """``implies`` short-circuits; type-mismatched comparisons are unknown."""
        expr = {"op": "implies", "if": leaf("is_true", "x"), "then": leaf("ge", "n", value=3)}
        self.assertIs(evaluate(expr, {"x": False}).value, True)
        self.assertIs(evaluate(expr, {"x": True, "n": 2}).value, False)
        self.assertIs(evaluate(expr, {"n": 5}).value, True)
        self.assertIsNone(evaluate(expr, {"x": True, "n": "text"}).value)

    def test_referenced_fields_are_ordered_and_unique(self):
        """Fields are listed once, in first-use order."""
        expr = {"op": "and", "args": [leaf("is_true", "b"), {"op": "not", "arg": leaf("is_true", "a")}, leaf("is_false", "b")]}
        self.assertEqual(referenced_fields(expr), ["b", "a"])


if __name__ == "__main__":
    unittest.main()
