from contextlib import ExitStack
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from api.main import app


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
