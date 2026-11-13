import os
from contextlib import ExitStack
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from api.main import app
from core.saved_plan import PlanPersistenceError, SavedPlanNotFound


ID = "00000000-0000-0000-0000-000000000001"
RUN = "00000000-0000-0000-0000-000000000002"


class CompatibilityExecutionTests(TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch("api.main.get_pool", new_callable=AsyncMock))
        stack.enter_context(patch("api.main.close_pool", new_callable=AsyncMock))
        stack.enter_context(patch.dict(os.environ, {"ENABLE_SAVED_PLAN_RUNS": "true", "TARGET_APP_URL": "http://staging.example/"}))
        self.client = stack.enter_context(TestClient(app))
        # Browser execution and persistence are external boundaries; exercise the
        # real route validation and response mapping around their returned result.
        self.prepare = stack.enter_context(patch("api.routers.compat.prepare_saved_plan", new_callable=AsyncMock, return_value="prepared-snapshot"))
        self.execute = stack.enter_context(patch("api.routers.compat.execute_prepared_plan", new_callable=AsyncMock))
        self.path = f"/compat/tests/{ID}/run-plan"
        self.body = {"revision": 2, "confirm_execution": True}

    def test_completed_execution_has_dashboard_diagnostics_and_pinned_revision(self):
        self.execute.return_value = {"status": "failed", "duration_ms": 12, "saved_run_id": RUN,
            "test_id": ID, "test_revision": 2, "target_url": "http://staging.example/",
            "steps": [{"action": "click", "target": "Save", "status": "failed", "duration_ms": 4, "error": "Save is disabled"}],
            "phases": {"test": {"status": "failed"}}, "rootCause": None}
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["savedRunId"], RUN)
        self.assertEqual(result["testRevision"], 2)
        self.assertEqual(result["durationMs"], 12)
        self.assertEqual(result["errorMessage"], "Save is disabled")
        self.assertEqual(result["steps"][0]["name"], "click Save")
        self.assertFalse(result["safeToRetry"])
        self.prepare.assert_awaited_once_with(ID, 2)
        self.execute.assert_awaited_once_with("prepared-snapshot", "http://staging.example/")

    def test_execution_is_disabled_by_default(self):
        with patch.dict(os.environ):
            os.environ.pop("ENABLE_SAVED_PLAN_RUNS", None)
            response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["executionState"], "not_started")
        self.execute.assert_not_awaited()

    def test_invalid_server_target_is_rejected_before_preparing_or_executing(self):
        with patch.dict(os.environ, {"TARGET_APP_URL": "file:///private"}):
            response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["executionState"], "not_started")
        self.prepare.assert_not_awaited()
        self.execute.assert_not_awaited()

    def test_preflight_database_failure_does_not_launch_browser(self):
        self.prepare.side_effect = RuntimeError("private database details")
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["executionState"], "not_started")
        self.assertNotIn("private database details", response.text)
        self.execute.assert_not_awaited()

    def test_confirmation_revision_and_target_override_are_validated(self):
        for body in [{"revision": 2}, {"revision": 2, "confirm_execution": False},
                     {"revision": True, "confirm_execution": True},
                     {**self.body, "target_url": "http://unapproved.example/"}]:
            with self.subTest(body=body):
                response = self.client.post(self.path, json=body)
                self.assertEqual(response.status_code, 422)
                self.assertIn("errorMessage", response.json())
        self.execute.assert_not_awaited()

    def test_missing_or_unreviewed_plan_returns_preflight_error(self):
        for error, status in [(SavedPlanNotFound("Missing revision"), 404), (ValueError("private saved value"), 409)]:
            with self.subTest(status=status):
                self.prepare.side_effect = error
                response = self.client.post(self.path, json=self.body)
                self.assertEqual(response.status_code, status)
                self.assertEqual(response.json()["executionState"], "not_started")
                self.assertNotIn("private saved value", response.text)
        self.execute.assert_not_awaited()

    def test_persistence_failure_does_not_claim_execution_never_started(self):
        self.execute.side_effect = PlanPersistenceError("private database details")
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["executionState"], "completed_unsaved")
        self.assertFalse(response.json()["safeToRetry"])
        self.assertNotIn("private database details", response.text)
        self.execute.assert_awaited_once()

    def test_unexpected_execution_error_is_sanitized_and_not_retried(self):
        self.execute.side_effect = RuntimeError("password=secret")
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["executionState"], "unknown")
        self.assertFalse(response.json()["safeToRetry"])
        self.assertNotIn("password=secret", response.text)
        self.execute.assert_awaited_once()

    def test_malformed_completed_result_is_not_reported_as_success(self):
        self.execute.return_value = {"status": "passed", "duration_ms": "bad", "saved_run_id": RUN}
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["executionState"], "unknown")
        self.assertFalse(response.json()["safeToRetry"])

    def test_value_error_after_execution_starts_is_not_a_preflight_rejection(self):
        self.execute.side_effect = ValueError("failure after a website change")
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["executionState"], "unknown")
        self.assertNotIn("failure after a website change", response.text)
