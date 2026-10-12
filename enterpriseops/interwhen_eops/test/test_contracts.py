"""Package contracts, and the shipped packages and split against the dataset."""

import os
import unittest
from copy import deepcopy

from interwhen_eops.test.fixtures import POLICY, package
from interwhen_eops.utils.contracts import extraction_schema, parse_extraction, validate_package
from interwhen_eops.utils.data import load_packages, load_split, policy_id, proportional_split


class ContractTest(unittest.TestCase):
    """Package validation and the extraction contract."""

    def test_fixture_is_valid(self):
        """The fixture package validates."""
        validate_package(package(), POLICY)

    def test_rejections(self):
        """Each contract violation is rejected."""
        cases = {
            "quote not in policy": lambda p: p["rules"][0].update(quote="delete anything"),
            "unmapped rule": lambda p: p["inventory"][0].update(rule_ids=[], status="ambiguous"),
            "fact in when and then": lambda p: p["rules"][0].update(then={"op": "is_false", "field": "action_deletes_ticket"}),
            "constant when": lambda p: p["rules"][0].update(when={"op": "const", "value": True}),
            "prefix mismatch": lambda p: p["variables"][1].update(category="action"),
            "schema drift": lambda p: p["extractor_format"]["response_schema"].update(additionalProperties=True),
        }
        for name, mutate in cases.items():
            with self.subTest(name):
                candidate = deepcopy(package())
                mutate(candidate)
                with self.assertRaises(ValueError):
                    validate_package(candidate, POLICY)

    def test_extraction_contract(self):
        """Extraction schema narrows to requested facts; known facts need evidence."""
        names = ["context_requester_is_admin"]
        self.assertEqual(extraction_schema(package(), names)["properties"]["facts"]["required"], names)
        facts, _ = parse_extraction(package(), names, {"facts": {names[0]: None}, "evidence": {names[0]: ""}})
        self.assertEqual(facts, {names[0]: None})
        with self.assertRaises(ValueError):
            parse_extraction(package(), names, {"facts": {names[0]: True}, "evidence": {names[0]: " "}})


class ShippedDataTest(unittest.TestCase):
    """Needs the dataset in the local Hugging Face cache; skipped otherwise."""

    @classmethod
    def setUpClass(cls):
        """Load all dataset tasks offline."""
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("HF_DATASETS_OFFLINE", "1")
        try:
            from interwhen_eops.utils.data import load_tasks
            cls.tasks = load_tasks()
        except Exception as error:  # noqa: BLE001
            raise unittest.SkipTest(f"dataset unavailable: {error}")

    def test_packages_cover_every_policy_and_validate(self):
        """All 75 reviewed packages (1,399 rules) validate against their exact policies."""
        policies = {policy_id(task["system_prompt"]): task["system_prompt"] for task in self.tasks}
        packages = load_packages()
        self.assertEqual(set(packages), set(policies))
        self.assertEqual((len(packages), sum(len(item["rules"]) for item in packages.values())), (75, 1399))
        for owner, item in packages.items():
            with self.subTest(owner):
                validate_package(item, policies[owner])

    def test_split_reproduces(self):
        """``split.json`` is exactly what ``proportional_split`` draws from the dataset."""
        split = load_split()
        fresh = proportional_split(self.tasks, split["seed"], split["forced_train_ids"],
                                   tuple(split["train_domains"]), split["train_size"])
        self.assertEqual((fresh["train"], fresh["test"]), (split["train"], split["test"]))


if __name__ == "__main__":
    unittest.main()
