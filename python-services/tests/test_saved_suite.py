import asyncio
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from core.saved_plan import PlanPersistenceError, SavedPlanNotFound
from core.saved_suite import execute_selected_suite


ONE = "00000000-0000-0000-0000-000000000001"
TWO = "00000000-0000-0000-0000-000000000002"
THREE = "00000000-0000-0000-0000-000000000003"
TARGET = "http://127.0.0.1:5173/"


def selection(*ids):
    return [{"test_id": identifier, "revision": 1} for identifier in ids]


class SelectedSuiteTests(IsolatedAsyncioTestCase):
    async def test_only_selected_revisions_run_in_order(self):
        with patch("core.saved_suite.prepare_saved_plan", new_callable=AsyncMock, side_effect=["pinned-one", "pinned-two"]) as prepare, \
             patch("core.saved_suite.execute_prepared_plan", new_callable=AsyncMock, side_effect=[{"status": "passed", "saved_run_id": "run-one"}, {"status": "failed", "saved_run_id": "run-two"}]) as execute:
            report = await execute_selected_suite(selection(ONE, TWO), TARGET)
        self.assertEqual([call.args for call in prepare.call_args_list], [(ONE, 1), (TWO, 1)])
        self.assertEqual([call.args for call in execute.call_args_list], [("pinned-one", TARGET), ("pinned-two", TARGET)])
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["counts"], {"selected": 2, "completed": 2, "passed": 1, "failed": 1, "errors": 0, "not_run": 0})

    async def test_all_preflight_finishes_before_any_execution(self):
        with patch("core.saved_suite.prepare_saved_plan", new_callable=AsyncMock, side_effect=["valid", SavedPlanNotFound("Missing revision")]), \
             patch("core.saved_suite.execute_prepared_plan", new_callable=AsyncMock) as execute:
            with self.assertRaises(SavedPlanNotFound):
                await execute_selected_suite(selection(ONE, TWO), TARGET)
        execute.assert_not_awaited()

    async def test_assertion_failure_does_not_stop_next_selected_test(self):
        with patch("core.saved_suite.prepare_saved_plan", new_callable=AsyncMock, side_effect=["one", "two"]), \
             patch("core.saved_suite.execute_prepared_plan", new_callable=AsyncMock, side_effect=[{"status": "failed", "saved_run_id": "failed-run"}, {"status": "passed", "saved_run_id": "passed-run"}]) as execute:
            report = await execute_selected_suite(selection(ONE, TWO), TARGET)
        self.assertEqual(execute.await_count, 2)
        self.assertIsNone(report["stop_reason"])
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["counts"]["passed"], 1)
        self.assertEqual(report["counts"]["failed"], 1)

    async def test_empty_duplicate_or_oversized_selection_never_runs(self):
        for values in [[], selection(ONE, ONE), selection(*([ONE] * 11))]:
            with self.subTest(values=values), patch("core.saved_suite.prepare_saved_plan", new_callable=AsyncMock) as prepare:
                with self.assertRaises(ValueError):
                    await execute_selected_suite(values, TARGET)
                prepare.assert_not_awaited()

    async def test_persistence_error_returns_partial_results_without_retry(self):
        with patch("core.saved_suite.prepare_saved_plan", new_callable=AsyncMock, side_effect=["one", "two", "three"]), \
             patch("core.saved_suite.execute_prepared_plan", new_callable=AsyncMock, side_effect=[{"status": "passed", "saved_run_id": "run-one"}, PlanPersistenceError("DB unavailable")]) as execute:
            report = await execute_selected_suite(selection(ONE, TWO, THREE), TARGET)
        self.assertEqual(execute.await_count, 2)
        self.assertEqual([item["state"] for item in report["tests"]], ["completed", "completed_unsaved", "not_run"])
        self.assertEqual(report["counts"], {"selected": 3, "completed": 1, "passed": 1, "failed": 0, "errors": 1, "not_run": 1})
        self.assertEqual(report["stop_reason"], "persistence_failed")
        self.assertEqual(report["status"], "incomplete")

    async def test_unexpected_interruption_does_not_claim_assertion_failure(self):
        with patch("core.saved_suite.prepare_saved_plan", new_callable=AsyncMock, side_effect=["one", "two"]), \
             patch("core.saved_suite.execute_prepared_plan", new_callable=AsyncMock, side_effect=RuntimeError("private details")):
            report = await execute_selected_suite(selection(ONE, TWO), TARGET)
        self.assertEqual(report["tests"][0]["state"], "interrupted")
        self.assertEqual(report["counts"]["failed"], 0)
        self.assertNotIn("private details", str(report))

    async def test_cancellation_stops_future_executions(self):
        with patch("core.saved_suite.prepare_saved_plan", new_callable=AsyncMock, side_effect=["one", "two"]), \
             patch("core.saved_suite.execute_prepared_plan", new_callable=AsyncMock, side_effect=asyncio.CancelledError) as execute:
            with self.assertRaises(asyncio.CancelledError):
                await execute_selected_suite(selection(ONE, TWO), TARGET)
        self.assertEqual(execute.await_count, 1)
