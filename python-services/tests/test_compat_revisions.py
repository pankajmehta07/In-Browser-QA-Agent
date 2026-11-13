from contextlib import ExitStack
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import AsyncMock, patch
from uuid import UUID

from fastapi.testclient import TestClient
from api.main import app
from stores.test_store import RevisionConflict


ID = "00000000-0000-0000-0000-000000000001"
REVISION_ID = "00000000-0000-0000-0000-000000000002"


class CompatibilityRevisionTests(TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch("api.main.get_pool", new_callable=AsyncMock))
        stack.enter_context(patch("api.main.close_pool", new_callable=AsyncMock))
        self.client = stack.enter_context(TestClient(app))
        self.path = f"/compat/tests/{ID}"
        self.body = {"name": "Edited", "instruction": "Check Dashboard", "variant": "original", "reruns": 1, "expectedRevision": 1}
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)
        self.row = {"id": UUID(ID), "name": "Edited", "instruction": "Check Dashboard", "variant": "original",
                    "reruns": 1, "revision": 2, "created_at": now, "updated_at": now, "plan": None}

    def test_update_forwards_expected_revision_without_inventing_a_plan(self):
        with patch("api.routers.compat.update_test", new_callable=AsyncMock, create=True, return_value=self.row) as update:
            response = self.client.put(self.path, json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["revision"], 2)
        self.assertEqual(response.json()["name"], "Edited")
        update.assert_awaited_once_with(ID, {"name": "Edited", "instruction": "Check Dashboard", "variant": "original",
                                            "reruns": 1, "expected_revision": 1})

    def test_explicit_null_clears_the_plan(self):
        with patch("api.routers.compat.update_test", new_callable=AsyncMock, create=True, return_value=self.row) as update:
            response = self.client.put(self.path, json={**self.body, "plan": None})
        self.assertEqual(response.status_code, 200)
        self.assertIn("plan", update.await_args.args[1])
        self.assertIsNone(update.await_args.args[1]["plan"])

    def test_stale_edit_exposes_current_revision_without_retrying(self):
        with patch("api.routers.compat.update_test", new_callable=AsyncMock, create=True, side_effect=RevisionConflict(3)) as update:
            response = self.client.put(self.path, json=self.body)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["currentRevision"], 3)
        self.assertIn("errorMessage", response.json())
        update.assert_awaited_once()

    def test_invalid_or_missing_revision_and_missing_definition_are_rejected(self):
        payloads = [{key: value for key, value in self.body.items() if key != "expectedRevision"},
                    {**self.body, "expectedRevision": True}, {**self.body, "expectedRevision": 0},
                    {**self.body, "name": " "}, {**self.body, "plan": {"schema_version": 1, "steps": []}},
                    {key: value for key, value in self.body.items() if key != "variant"}]
        with patch("api.routers.compat.update_test", new_callable=AsyncMock, create=True) as update:
            for body in payloads:
                with self.subTest(body=body):
                    response = self.client.put(self.path, json=body)
                    self.assertEqual(response.status_code, 422)
                    self.assertIn("errorMessage", response.json())
        update.assert_not_awaited()

    def test_missing_test_is_not_created_by_update(self):
        with patch("api.routers.compat.update_test", new_callable=AsyncMock, create=True, return_value=None):
            response = self.client.put(self.path, json=self.body)
        self.assertEqual(response.status_code, 404)

    def test_deleted_test_history_keeps_original_id_and_snapshot_unchanged(self):
        snapshot = {"name": "Original", "plan": {"schema_version": 1, "steps": [{"action": "click", "target": "Login"}]}}
        row = {"id": UUID(REVISION_ID), "test_id": None, "original_test_id": UUID(ID), "revision": 1,
               "created_at": self.row["created_at"], "snapshot": snapshot}
        with patch("api.routers.compat.list_test_revisions", new_callable=AsyncMock, create=True, return_value=[row]), \
             patch("api.routers.compat.get_test_by_id", new_callable=AsyncMock) as current:
            response = self.client.get(self.path + "/revisions")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0], {"id": REVISION_ID, "testId": None, "originalTestId": ID,
            "revision": 1, "createdAt": "2026-01-02T00:00:00+00:00", "snapshot": snapshot})
        current.assert_not_awaited()

    def test_history_distinguishes_missing_test_from_empty_existing_history(self):
        with patch("api.routers.compat.list_test_revisions", new_callable=AsyncMock, create=True, return_value=[]), \
             patch("api.routers.compat.get_test_by_id", new_callable=AsyncMock, return_value=None):
            self.assertEqual(self.client.get(self.path + "/revisions").status_code, 404)
        with patch("api.routers.compat.list_test_revisions", new_callable=AsyncMock, create=True, return_value=[]), \
             patch("api.routers.compat.get_test_by_id", new_callable=AsyncMock, return_value=self.row):
            self.assertEqual(self.client.get(self.path + "/revisions").json(), [])

    def test_storage_error_does_not_leak_details_or_retry(self):
        with patch("api.routers.compat.update_test", new_callable=AsyncMock, create=True, side_effect=RuntimeError("private database password")) as update:
            response = self.client.put(self.path, json=self.body)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private database password", response.text)
        update.assert_awaited_once()
