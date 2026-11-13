import os
from contextlib import ExitStack
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from api.main import app
from core.saved_plan import PlanPersistenceError, SavedPlanNotFound


IDS = [f"00000000-0000-0000-0000-{number:012d}" for number in range(1, 4)]
RUNS = [f"10000000-0000-0000-0000-{number:012d}" for number in range(1, 4)]


class CompatibilitySuiteTests(TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch("api.main.get_pool", new_callable=AsyncMock))
        stack.enter_context(patch("api.main.close_pool", new_callable=AsyncMock))
        stack.enter_context(patch.dict(os.environ, {"ENABLE_SAVED_PLAN_RUNS": "true", "TARGET_APP_URL": "http://staging.example/"}))
        self.client = stack.enter_context(TestClient(app))
        # Keep suite orchestration real; isolate database and browser boundaries.
        self.prepare = stack.enter_context(patch("core.saved_suite.prepare_saved_plan", new_callable=AsyncMock, side_effect=IDS))
        self.execute = stack.enter_context(patch("core.saved_suite.execute_prepared_plan", new_callable=AsyncMock))
        self.path = "/compat/tests/run-selected-plans"
        self.body = {"tests": [{"test_id": value, "revision": 2} for value in IDS], "confirm_execution": True}

    def result(self, index, status="passed"):
        return {"status": status, "saved_run_id": RUNS[index], "test_id": IDS[index], "test_revision": 2,
                "duration_ms": 10, "steps": [{"action": "check_visible", "target": "Dashboard", "status": status,
                    "duration_ms": 4, **({"error": "Dashboard missing"} if status == "failed" else {})}]}

    def test_assertion_failure_preserves_all_results_and_continues_in_order(self):
        self.execute.side_effect = [self.result(0), self.result(1, "failed"), self.result(2)]
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 200)
        report = response.json()
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["counts"], {"selected": 3, "completed": 3, "passed": 2, "failed": 1, "errors": 0, "notRun": 0})
        self.assertEqual([item["testId"] for item in report["tests"]], IDS)
        self.assertEqual(report["tests"][1]["result"]["savedRunId"], RUNS[1])
        self.assertEqual(report["tests"][1]["result"]["errorMessage"], "Dashboard missing")
        self.assertFalse(report["safeToRetry"])
        self.assertIsNone(report["stopReason"])
        self.assertEqual([call.args for call in self.prepare.await_args_list], [(value, 2) for value in IDS])
        self.assertEqual([call.args for call in self.execute.await_args_list], [(value, "http://staging.example/") for value in IDS])

    def test_persistence_failure_returns_partial_report_and_never_runs_remaining_case(self):
        self.execute.side_effect = [self.result(0), PlanPersistenceError("private database detail")]
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 503)
        report = response.json()
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["stopReason"], "persistence_failed")
        self.assertEqual([item["state"] for item in report["tests"]], ["completed", "completed_unsaved", "not_run"])
        self.assertEqual([item["status"] for item in report["tests"]], ["passed", "unknown", "unknown"])
        self.assertEqual(report["counts"], {"selected": 3, "completed": 1, "passed": 1, "failed": 0, "errors": 1, "notRun": 1})
        self.assertEqual(report["tests"][0]["savedRunId"], RUNS[0])
        self.assertIn("errorMessage", report)
        self.assertNotIn("private database detail", response.text)
        self.assertEqual(self.execute.await_count, 2)

    def test_execution_interruption_is_not_misreported_as_an_assertion_failure(self):
        self.execute.side_effect = RuntimeError("private target details")
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 503)
        report = response.json()
        self.assertEqual(report["stopReason"], "execution_interrupted")
        self.assertEqual(report["tests"][0]["state"], "interrupted")
        self.assertEqual(report["counts"]["failed"], 0)
        self.assertEqual(report["counts"]["notRun"], 2)
        self.assertNotIn("private target details", response.text)
        self.execute.assert_awaited_once()

    def test_every_selected_revision_is_preflighted_before_any_execution(self):
        self.prepare.side_effect = [IDS[0], SavedPlanNotFound("missing revision")]
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["executionState"], "not_started")
        self.execute.assert_not_awaited()

    def test_disabled_flag_and_invalid_server_target_prevent_execution(self):
        for settings, status in [({"ENABLE_SAVED_PLAN_RUNS": "false"}, 403), ({"TARGET_APP_URL": "file:///private"}, 409)]:
            with self.subTest(settings=settings), patch.dict(os.environ, settings):
                response = self.client.post(self.path, json=self.body)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["executionState"], "not_started")
        self.prepare.assert_not_awaited()
        self.execute.assert_not_awaited()

    def test_invalid_selection_and_missing_confirmation_cannot_start_a_suite(self):
        bodies = [{"tests": []}, {**self.body, "confirm_execution": False},
                  {**self.body, "tests": [self.body["tests"][0]] * 2},
                  {**self.body, "target_url": "http://unapproved.example/"},
                  {**self.body, "tests": [{"test_id": IDS[0], "revision": True}]},
                  {**self.body, "tests": [{"test_id": f"00000000-0000-0000-0000-{i:012d}", "revision": 1} for i in range(11)]}]
        for body in bodies:
            with self.subTest(body=body):
                response = self.client.post(self.path, json=body)
                self.assertEqual(response.status_code, 422)
                self.assertIn("errorMessage", response.json())
        self.prepare.assert_not_awaited()
        self.execute.assert_not_awaited()

    def test_invalid_saved_plan_and_preflight_service_failure_are_sanitized(self):
        for error, status in [(ValueError("private plan values"), 409), (RuntimeError("private database"), 503)]:
            with self.subTest(status=status):
                self.prepare.side_effect = error
                response = self.client.post(self.path, json=self.body)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["executionState"], "not_started" if status == 409 else "unknown")
                self.assertNotIn("private", response.text)
        self.execute.assert_not_awaited()

    def test_passed_suite_has_no_failure_banner(self):
        self.execute.side_effect = [self.result(index) for index in range(3)]
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "passed")
        self.assertEqual(response.json()["counts"]["passed"], 3)
        self.assertNotIn("errorMessage", response.json())

    def test_malformed_saved_result_returns_unknown_without_reexecuting(self):
        malformed = {**self.result(0), "duration_ms": "not a number"}
        self.execute.side_effect = [malformed, self.result(1), self.result(2)]
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["executionState"], "unknown")
        self.assertFalse(response.json()["safeToRetry"])
        self.assertEqual(self.execute.await_count, 3)
