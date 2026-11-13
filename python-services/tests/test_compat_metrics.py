from contextlib import ExitStack
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from api.main import app


class CompatibilityMetricsTests(TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch("api.main.get_pool", new_callable=AsyncMock))
        stack.enter_context(patch("api.main.close_pool", new_callable=AsyncMock))
        self.client = stack.enter_context(TestClient(app))

    def row(self, **overrides):
        return {"total_runs": 64, "passed_runs": 40, "failed_runs": 20, "flaky_runs": 4,
                "healed_runs": 21, "saved_tests": 2, "measured_at": datetime(2026, 1, 2, tzinfo=timezone.utc), **overrides}

    def test_all_time_counts_and_pass_percentage_have_explicit_scope(self):
        with patch("api.routers.compat.get_execution_metrics", new_callable=AsyncMock, create=True, return_value=self.row()):
            response = self.client.get("/compat/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"scope": "all_time", "unit": "saved_run_records", "totalRuns": 64,
            "passedRuns": 40, "failedRuns": 20, "flakyRuns": 4, "healedRuns": 21, "savedTests": 2,
            "passRate": 63, "measuredAt": "2026-01-02T00:00:00+00:00"})

    def test_empty_database_does_not_invent_a_pass_rate(self):
        with patch("api.routers.compat.get_execution_metrics", new_callable=AsyncMock, create=True,
                   return_value=self.row(total_runs=0, passed_runs=0, failed_runs=0, flaky_runs=0, healed_runs=0, saved_tests=0)):
            response = self.client.get("/compat/metrics")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["passRate"])
        self.assertEqual(response.json()["totalRuns"], 0)

    def test_unavailable_database_is_not_reported_as_zero_counts(self):
        with patch("api.routers.compat.get_execution_metrics", new_callable=AsyncMock, create=True,
                   side_effect=RuntimeError("private database credentials")):
            response = self.client.get("/compat/metrics")
        self.assertEqual(response.status_code, 503)
        self.assertIn("errorMessage", response.json())
        self.assertNotIn("totalRuns", response.json())
        self.assertNotIn("private database credentials", response.text)

    def test_inconsistent_aggregate_is_not_reported_as_valid_metrics(self):
        for row in [self.row(total_runs=1), self.row(healed_runs=65), self.row(saved_tests=-1), self.row(total_runs=True)]:
            with self.subTest(row=row), patch("api.routers.compat.get_execution_metrics", new_callable=AsyncMock, return_value=row):
                response = self.client.get("/compat/metrics")
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("passRate", response.json())
