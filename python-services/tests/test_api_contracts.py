from contextlib import ExitStack
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from api.main import app
from stores.test_store import RevisionConflict


class ApiContracts(TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch("api.main.get_pool", new_callable=AsyncMock))
        self.stack.enter_context(patch("api.main.close_pool", new_callable=AsyncMock))
        self.client = self.stack.enter_context(TestClient(app))

    def test_health_does_not_require_live_services(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["ok"])

    def test_save_calls_the_existing_store_once(self):
        payload = {"name": "Regression", "instruction": "[]", "variant": "original", "reruns": 1}
        with patch("api.routers.tests.save_test", new_callable=AsyncMock, return_value={"id": "one", **payload}) as save:
            response = self.client.post("/tests", json=payload)
        self.assertEqual(response.status_code, 201)
        save.assert_awaited_once_with(payload)

    def test_missing_save_fields_return_validation_error(self):
        with patch("api.routers.tests.save_test", new_callable=AsyncMock) as save:
            response = self.client.post("/tests", json={"name": "Missing instruction"})
        self.assertEqual(response.status_code, 422)
        save.assert_not_awaited()

    def test_delete_calls_only_the_test_store(self):
        with patch("api.routers.tests.delete_test", new_callable=AsyncMock, return_value=True) as delete, \
             patch("api.routers.instructions.run_test", new_callable=AsyncMock) as execute:
            response = self.client.delete("/tests/one")
        self.assertEqual(response.status_code, 200)
        delete.assert_awaited_once_with("one")
        execute.assert_not_awaited()

    def test_missing_test_returns_404(self):
        with patch("api.routers.tests.delete_test", new_callable=AsyncMock, return_value=False):
            response = self.client.delete("/tests/missing")
        self.assertEqual(response.status_code, 404)

    def test_invalid_steps_never_launch_execution(self):
        with patch("api.routers.instructions.run_test", new_callable=AsyncMock) as execute:
            response = self.client.post("/instructions/run", json={
                "instruction": '[{"action":"unsupported","target":"x"}]',
                "url": "http://127.0.0.1:5173/", "use_natural_language": False,
            })
        self.assertEqual(response.status_code, 400)
        execute.assert_not_awaited()

    def test_create_accepts_validated_plan_without_execution(self):
        plan = {"schema_version": 1, "setup": [], "steps": [{"action": "click", "target": "Login", "value": None}], "cleanup": []}
        with patch("api.routers.tests.save_test", new_callable=AsyncMock, return_value={"revision": 1}) as save:
            response = self.client.post("/tests", json={"name": "Plan", "instruction": "Click Login", "plan": plan})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(save.call_args.args[0]["plan"], plan)

    def test_create_rejects_unknown_plan_version_before_saving(self):
        with patch("api.routers.tests.save_test", new_callable=AsyncMock, return_value={}) as save:
            response = self.client.post("/tests", json={"name": "Plan", "instruction": "Click Login", "plan": {"schema_version": 9, "steps": []}})
        self.assertEqual(response.status_code, 422)
        save.assert_not_awaited()

    def test_expected_revision_is_positive_and_strict(self):
        for revision in [0, True, "1"]:
            with self.subTest(revision=revision), patch("api.routers.tests.update_test", new_callable=AsyncMock, return_value={"id": "one"}) as update:
                response = self.client.put("/tests/one", json={"name": "Edited", "expected_revision": revision})
                self.assertEqual(response.status_code, 422)
                update.assert_not_awaited()

    def test_revisions_endpoint_returns_history(self):
        test_id = "00000000-0000-0000-0000-000000000001"
        with patch("api.routers.tests.list_test_revisions", new_callable=AsyncMock, return_value=[{"revision": 1}]):
            response = self.client.get(f"/tests/{test_id}/revisions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [{"revision": 1}])

    def test_stale_edit_returns_conflict_with_current_revision(self):
        with patch("api.routers.tests.update_test", new_callable=AsyncMock, side_effect=RevisionConflict(3)) as update:
            response = self.client.put("/tests/one", json={"name": "Edited", "expected_revision": 2})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["detail"]["current_revision"], 3)
        update.assert_awaited_once_with("one", {"name": "Edited", "expected_revision": 2})

    def test_explicit_null_clears_plan(self):
        with patch("api.routers.tests.update_test", new_callable=AsyncMock, return_value={"plan": None}) as update:
            response = self.client.put("/tests/one", json={"plan": None, "expected_revision": 1})
        self.assertEqual(response.status_code, 200)
        update.assert_awaited_once_with("one", {"plan": None, "expected_revision": 1})

    def test_missing_revision_history_returns_404(self):
        with patch("api.routers.tests.list_test_revisions", new_callable=AsyncMock, return_value=[]), \
             patch("api.routers.tests.get_test_by_id", new_callable=AsyncMock, return_value=None):
            response = self.client.get("/tests/00000000-0000-0000-0000-000000000001/revisions")
        self.assertEqual(response.status_code, 404)

    def test_saved_plan_route_is_disabled_by_default(self):
        with patch.dict("os.environ", {"ENABLE_SAVED_PLAN_RUNS": "false"}):
            response = self.client.post("/tests/00000000-0000-0000-0000-000000000001/run-plan", json={"revision": 1, "confirm_execution": True})
        self.assertEqual(response.status_code, 403)

    def test_saved_plan_route_requires_confirmation_and_revision(self):
        for body in [{"revision": 1, "confirm_execution": False}, {"confirm_execution": True}]:
            with self.subTest(body=body), patch.dict("os.environ", {"ENABLE_SAVED_PLAN_RUNS": "true"}):
                response = self.client.post("/tests/00000000-0000-0000-0000-000000000001/run-plan", json=body)
                self.assertEqual(response.status_code, 422)

    def test_saved_plan_route_uses_only_configured_target(self):
        with patch.dict("os.environ", {"ENABLE_SAVED_PLAN_RUNS": "true", "TARGET_APP_URL": "http://target-app:5173/"}), \
             patch("api.routers.tests.execute_saved_plan", new_callable=AsyncMock, return_value={"status": "passed", "saved_run_id": "one"}) as execute:
            response = self.client.post("/tests/00000000-0000-0000-0000-000000000001/run-plan", json={"revision": 1, "confirm_execution": True})
        self.assertEqual(response.status_code, 200)
        execute.assert_awaited_once_with("00000000-0000-0000-0000-000000000001", 1, "http://target-app:5173/")

    def test_saved_plan_route_rejects_arbitrary_url_override(self):
        with patch.dict("os.environ", {"ENABLE_SAVED_PLAN_RUNS": "true"}):
            response = self.client.post("/tests/00000000-0000-0000-0000-000000000001/run-plan", json={"revision": 1, "confirm_execution": True, "url": "https://example.com"})
        self.assertEqual(response.status_code, 422)

    def test_selected_suite_is_disabled_by_default(self):
        with patch.dict("os.environ", {"ENABLE_SAVED_PLAN_RUNS": "false"}):
            response = self.client.post("/tests/run-selected-plans", json={"tests": [{"test_id": "00000000-0000-0000-0000-000000000001", "revision": 1}], "confirm_execution": True})
        self.assertEqual(response.status_code, 403)

    def test_selected_suite_rejects_empty_duplicates_and_unconfirmed_requests(self):
        item = {"test_id": "00000000-0000-0000-0000-000000000001", "revision": 1}
        bodies = [{"tests": [], "confirm_execution": True}, {"tests": [item, item], "confirm_execution": True},
                  {"tests": [item], "confirm_execution": False}, {"tests": [item], "confirm_execution": True, "url": "https://example.com"},
                  {"tests": [{**item, "revision": True}], "confirm_execution": True}, {"tests": [item] * 11, "confirm_execution": True}]
        for body in bodies:
            with self.subTest(body=body), patch.dict("os.environ", {"ENABLE_SAVED_PLAN_RUNS": "true"}):
                response = self.client.post("/tests/run-selected-plans", json=body)
                self.assertEqual(response.status_code, 422)

    def test_selected_suite_uses_configured_target(self):
        item = {"test_id": "00000000-0000-0000-0000-000000000001", "revision": 1}
        with patch.dict("os.environ", {"ENABLE_SAVED_PLAN_RUNS": "true", "TARGET_APP_URL": "http://target-app:5173/"}), \
             patch("api.routers.tests.execute_selected_suite", new_callable=AsyncMock, return_value={"status": "passed", "stop_reason": None}) as execute:
            response = self.client.post("/tests/run-selected-plans", json={"tests": [item], "confirm_execution": True})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(execute.call_args.args[1], "http://target-app:5173/")
        self.assertEqual(str(execute.call_args.args[0][0].test_id), item["test_id"])

    def test_interrupted_suite_preserves_partial_report_in_503_response(self):
        report = {"type": "selected_plan_suite", "status": "incomplete", "stop_reason": "persistence_failed",
                  "safe_to_retry": False, "counts": {"selected": 1, "completed": 0, "passed": 0, "failed": 0, "errors": 1, "not_run": 0},
                  "tests": [{"state": "completed_unsaved", "status": "unknown", "saved_run_id": None}]}
        with patch.dict("os.environ", {"ENABLE_SAVED_PLAN_RUNS": "true"}), \
             patch("api.routers.tests.execute_selected_suite", new_callable=AsyncMock, return_value=report):
            response = self.client.post("/tests/run-selected-plans", json={"tests": [{"test_id": "00000000-0000-0000-0000-000000000001", "revision": 1}], "confirm_execution": True})
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), report)
