from contextlib import ExitStack
from datetime import datetime, timezone
from decimal import Decimal
from unittest import TestCase
from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi.testclient import TestClient
from api.main import app


ID = "00000000-0000-0000-0000-000000000001"
RUN = "00000000-0000-0000-0000-000000000002"


class CompatibilityApprovalTests(TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch("api.main.get_pool", new_callable=AsyncMock))
        stack.enter_context(patch("api.main.close_pool", new_callable=AsyncMock))
        self.client = stack.enter_context(TestClient(app))
        self.body = {"runId": RUN, "stepName": "Click Login", "oldSelector": 'role=button[name="Login"]',
                     "newSelector": 'role=button[name="Sign In"]', "oldTarget": "Login", "newTarget": "Sign In",
                     "decision": "approved", "confidence": 0.9, "strategy": "semantic"}
        self.row = {"id": UUID(ID), "saved_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
                    "run_id": UUID(RUN), "step_name": "Click Login", "old_selector": self.body["oldSelector"],
                    "new_selector": self.body["newSelector"], "old_target": "Login", "new_target": "Sign In",
                    "decision": "approved", "confidence": Decimal("0.900"), "strategy": "semantic"}
        self.step = {"name": "Click Login", "status": "passed", "wasHealed": True,
                     "oldSelector": self.body["oldSelector"], "newSelector": self.body["newSelector"]}

    def test_save_validated_decision_returns_dashboard_shape(self):
        with patch("api.routers.compat.get_run_by_id", new_callable=AsyncMock, return_value={"result_json": {"steps": [self.step]}}), \
             patch("api.routers.compat.save_approval", new_callable=AsyncMock, create=True, return_value=self.row) as save:
            response = self.client.post("/compat/approvals", json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["runId"], RUN)
        self.assertEqual(response.json()["stepName"], "Click Login")
        self.assertEqual(response.json()["confidence"], 0.9)
        self.assertEqual(response.json()["savedAt"], "2026-01-02T00:00:00+00:00")
        save.assert_awaited_once_with(self.body)

    def test_unobserved_mapping_or_target_cannot_enter_healing_memory(self):
        for override in [{"newSelector": "#unobserved"}, {"newTarget": "Delete Everything"}, {"stepName": "Other step"}]:
            with self.subTest(override=override), \
                 patch("api.routers.compat.get_run_by_id", new_callable=AsyncMock, return_value={"result_json": {"steps": [self.step]}}), \
                 patch("api.routers.compat.save_approval", new_callable=AsyncMock, create=True) as save:
                response = self.client.post("/compat/approvals", json={**self.body, **override})
                self.assertEqual(response.status_code, 409)
                save.assert_not_awaited()

    def test_missing_run_is_not_saved(self):
        with patch("api.routers.compat.get_run_by_id", new_callable=AsyncMock, return_value=None), \
             patch("api.routers.compat.save_approval", new_callable=AsyncMock, create=True) as save:
            response = self.client.post("/compat/approvals", json=self.body)
        self.assertEqual(response.status_code, 404)
        save.assert_not_awaited()

    def test_non_healed_or_ambiguous_step_is_not_saved(self):
        for steps in [[{**self.step, "wasHealed": False}], [self.step, self.step]]:
            with self.subTest(steps=steps), \
                 patch("api.routers.compat.get_run_by_id", new_callable=AsyncMock, return_value={"result_json": {"steps": steps}}), \
                 patch("api.routers.compat.save_approval", new_callable=AsyncMock, create=True) as save:
                response = self.client.post("/compat/approvals", json=self.body)
                self.assertEqual(response.status_code, 409)
                save.assert_not_awaited()

    def test_invalid_input_is_rejected_before_reading_or_writing(self):
        with patch("api.routers.compat.get_run_by_id", new_callable=AsyncMock) as read:
            for override in [{"runId": "bad"}, {"decision": "maybe"}, {"confidence": 2}, {"stepName": " "}, {"unexpected": True}]:
                with self.subTest(override=override):
                    response = self.client.post("/compat/approvals", json={**self.body, **override})
                    self.assertEqual(response.status_code, 422)
                    self.assertIn("errorMessage", response.json())
        read.assert_not_awaited()

    def test_list_and_delete_decisions_have_dashboard_contracts(self):
        with patch("api.routers.compat.list_approvals", new_callable=AsyncMock, create=True, return_value=[self.row]), \
             patch("api.routers.compat.delete_approval", new_callable=AsyncMock, create=True, return_value=True):
            response = self.client.get("/compat/approvals")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()[0]["oldTarget"], "Login")
            deleted = self.client.delete(f"/compat/approvals/{ID}")
            self.assertEqual(deleted.json(), {"status": "passed", "deletedId": ID})
        with patch("api.routers.compat.delete_approval", new_callable=AsyncMock, create=True, return_value=False):
            self.assertEqual(self.client.delete(f"/compat/approvals/{ID}").status_code, 404)

    def test_rejection_is_saved_as_rejection_and_store_errors_are_sanitized(self):
        with patch("api.routers.compat.get_run_by_id", new_callable=AsyncMock, return_value={"result_json": {"steps": [self.step]}}), \
             patch("api.routers.compat.save_approval", new_callable=AsyncMock, create=True, return_value={**self.row, "decision": "rejected"}) as save:
            response = self.client.post("/compat/approvals", json={**self.body, "decision": "rejected"})
        self.assertEqual(response.json()["decision"], "rejected")
        self.assertEqual(save.await_args.args[0]["decision"], "rejected")
        with patch("api.routers.compat.list_approvals", new_callable=AsyncMock, create=True, side_effect=RuntimeError("private database password")):
            response = self.client.get("/compat/approvals")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private database password", response.text)
