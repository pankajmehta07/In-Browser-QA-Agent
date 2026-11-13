import unittest

from core.root_cause import explain_failure
from helpers.classify_reruns import classify_reruns
from parser.llm_output_parser import parse_llm_output
from parser.models import RunResult, StepExecutionResult


def run(status, duration=100):
    return RunResult(status=status, total_steps=1, passed_steps=int(status == "passed"),
                     failed_steps=int(status == "failed"), duration_ms=duration)


class ParserContracts(unittest.TestCase):
    def test_json_steps_preserve_targets_and_values(self):
        result = parse_llm_output('[{"action":"type","target":"Email","value":"qa@example.com"}]')
        self.assertTrue(result.success)
        self.assertEqual(result.steps[0].target, "Email")
        self.assertEqual(result.steps[0].value, "qa@example.com")

    def test_markdown_fences_are_recovered(self):
        result = parse_llm_output('```json\n[{"action":"click","target":"Login"}]\n```')
        self.assertTrue(result.success)
        self.assertEqual(result.recovery, "markdown_stripped")

    def test_single_step_is_wrapped(self):
        result = parse_llm_output('{"action":"click","target":"Login"}')
        self.assertTrue(result.success)
        self.assertEqual(len(result.steps), 1)
        self.assertEqual(result.recovery, "wrapped_in_array")

    def test_unsupported_action_is_rejected(self):
        result = parse_llm_output('[{"action":"execute_script","target":"body"}]')
        self.assertFalse(result.success)
        self.assertEqual(result.steps, [])

    def test_required_value_is_checked(self):
        self.assertFalse(parse_llm_output('[{"action":"type","target":"Email"}]').success)

    def test_malformed_json_is_reported(self):
        result = parse_llm_output('[{"action":')
        self.assertFalse(result.success)
        self.assertIn("JSON", result.error)


class ResultContracts(unittest.TestCase):
    def test_all_passed(self):
        result = classify_reruns([(run("passed", 100), None), (run("passed", 200), None)])
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.duration_ms, 300)
        self.assertFalse(result.flaky)

    def test_all_failed_keeps_first_cause(self):
        cause = explain_failure(run("failed"))
        result = classify_reruns([(run("failed"), cause), (run("failed"), None)])
        self.assertEqual(result.status, "failed")
        self.assertIs(result.root_cause, cause)

    def test_mixed_runs_are_flaky(self):
        result = classify_reruns([(run("passed"), None), (run("failed"), None)])
        self.assertEqual(result.status, "flaky")
        self.assertTrue(result.flaky)
        self.assertEqual((result.passed_runs, result.failed_runs), (1, 1))

    def test_empty_runs_do_not_pass(self):
        result = classify_reruns([])
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.total_runs, 0)

    def test_success_has_no_failure_explanation(self):
        self.assertIsNone(explain_failure(run("passed")))

    def test_failed_assertion_keeps_evidence(self):
        result = run("failed")
        result.steps = [StepExecutionResult(step_number=1, action="check_visible", target="Dashboard",
                                           value=None, status="failed", duration_ms=100, error="Text absent")]
        cause = explain_failure(result)
        self.assertEqual(cause.title, "Assertion failed")
        self.assertEqual(cause.evidence, "Text absent")
