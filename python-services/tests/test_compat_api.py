from contextlib import ExitStack
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi.testclient import TestClient
from api.main import app


ID = "00000000-0000-0000-0000-000000000001"


class CompatibilityApiTests(TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch("api.main.get_pool", new_callable=AsyncMock))
        self.stack.enter_context(patch("api.main.close_pool", new_callable=AsyncMock))
        self.client = self.stack.enter_context(TestClient(app))

    def row(self):
        return {"id": UUID(ID), "name": "Login", "instruction": "Click Login", "variant": "original", "reruns": 1,
                "created_at": datetime(2026, 1, 2, tzinfo=timezone.utc), "updated_at": datetime(2026, 1, 2, tzinfo=timezone.utc), "revision": 1, "plan": None}

    def test_list_tests_is_an_array_with_dashboard_dates(self):
        with patch("api.routers.compat.list_tests", new_callable=AsyncMock, return_value=[self.row()]):
            response = self.client.get("/compat/tests")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["createdAt"], "2026-01-02T00:00:00+00:00")

    def test_create_saves_once_and_never_executes_a_test(self):
        payload = {"name": "Login", "instruction": "Click Login", "variant": "original", "reruns": 1}
        with patch("api.routers.compat.save_test", new_callable=AsyncMock, return_value=self.row()) as save, \
             patch("api.routers.tests.execute_saved_plan", new_callable=AsyncMock) as execute:
            response = self.client.post("/compat/tests", json=payload)
        self.assertEqual(response.status_code, 200)
        save.assert_awaited_once_with(payload)
        execute.assert_not_awaited()

    def test_delete_uses_the_store_and_returns_dashboard_shape(self):
        with patch("api.routers.compat.delete_test", new_callable=AsyncMock, return_value=True) as delete, \
             patch("api.routers.tests.execute_saved_plan", new_callable=AsyncMock) as execute:
            response = self.client.delete(f"/compat/tests/{ID}")
        self.assertEqual(response.json(), {"status": "passed", "deletedId": ID})
        delete.assert_awaited_once_with(ID)
        execute.assert_not_awaited()

    def test_validation_and_missing_ids_have_dashboard_errors(self):
        response = self.client.post("/compat/tests", json={"name": " ", "instruction": "x"})
        self.assertEqual(response.status_code, 422)
        self.assertIn("errorMessage", response.json())
        with patch("api.routers.compat.get_run_by_id", new_callable=AsyncMock, return_value=None):
            response = self.client.get(f"/compat/runs/{ID}")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["errorMessage"], "Run not found")

    def test_backend_error_is_sanitized(self):
        with patch("api.routers.compat.list_tests", new_callable=AsyncMock, side_effect=RuntimeError("password=private-value")):
            response = self.client.get("/compat/tests")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private-value", response.text)
        self.assertIn("errorMessage", response.json())

    def test_native_error_contract_remains_unchanged(self):
        with patch("api.routers.tests.get_test_by_id", new_callable=AsyncMock, return_value=None):
            response = self.client.get(f"/tests/{ID}")
        self.assertEqual(response.json(), {"detail": "Test not found"})

    def test_health_requires_database_readiness(self):
        with patch("api.routers.compat.database_ready", new_callable=AsyncMock, return_value=True):
            response = self.client.get("/compat/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["scope"], "data-only")
        with patch("api.routers.compat.database_ready", new_callable=AsyncMock, return_value=False):
            response = self.client.get("/compat/health")
        self.assertEqual(response.status_code, 503)
        self.assertIn("errorMessage", response.json())

    def test_invalid_ids_limits_and_reruns_are_rejected_before_stores(self):
        with patch("api.routers.compat.list_runs", new_callable=AsyncMock) as runs, \
             patch("api.routers.compat.save_test", new_callable=AsyncMock) as save:
            for path in ["/compat/tests/not-a-uuid", "/compat/runs?limit=0", "/compat/runs?limit=201"]:
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 422)
                    self.assertIn("errorMessage", response.json())
            response = self.client.post("/compat/tests", json={"name": "Login", "instruction": "Click Login", "reruns": True})
        self.assertEqual(response.status_code, 422)
        runs.assert_not_awaited()
        save.assert_not_awaited()
