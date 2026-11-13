import unittest

from pydantic import ValidationError

from parser.test_plan import TestPlan


class PlanValidationTests(unittest.TestCase):
    def test_preserves_setup_steps_and_optional_cleanup(self):
        plan = TestPlan.model_validate({
            "schema_version": 1,
            "setup": [{"action": "click", "target": "Projects"}],
            "steps": [{"action": "type", "target": "Name", "value": "My chosen name"}],
        })
        self.assertEqual(plan.steps[0].value, "My chosen name")
        self.assertEqual(plan.setup[0].target, "Projects")
        self.assertEqual(plan.cleanup, [])

    def test_rejects_unsupported_version_action_and_extra_fields(self):
        for payload in [
            {"schema_version": 2, "steps": [{"action": "click", "target": "Save"}]},
            {"schema_version": True, "steps": [{"action": "click", "target": "Save"}]},
            {"schema_version": 1, "steps": [{"action": "execute_js", "target": "body"}]},
            {"schema_version": 1, "steps": [{"action": "click", "target": "Save", "script": "x"}]},
        ]:
            with self.subTest(payload=payload), self.assertRaises(ValidationError):
                TestPlan.model_validate(payload)

    def test_rejects_empty_steps_blank_targets_and_missing_values(self):
        for steps in [[], [{"action": "click", "target": " "}], [{"action": "type", "target": "Email"}]]:
            with self.subTest(steps=steps), self.assertRaises(ValidationError):
                TestPlan.model_validate({"schema_version": 1, "steps": steps})
