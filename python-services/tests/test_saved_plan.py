from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from core.saved_plan import execute_plan, execute_saved_plan, PlanPersistenceError
from parser.models import RunResult, StepExecutionResult
from parser.test_plan import TestPlan


def result(status="passed"):
    step = StepExecutionResult(1, "click", "Save", None, status, 2, error="Failed" if status == "failed" else None)
    return RunResult(status, 1, int(status == "passed"), int(status == "failed"), 2, [step]), None


def plan():
    return TestPlan.model_validate({"schema_version": 1,
        "setup": [{"action": "click", "target": "Open"}],
        "steps": [{"action": "click", "target": "Save"}, {"action": "check_visible", "target": "Saved"}],
        "cleanup": [{"action": "click", "target": "Remove"}],
    })


class PhaseExecutionTests(IsolatedAsyncioTestCase):
    async def test_phases_run_in_order_and_keep_phase_labels(self):
        with patch("core.saved_plan.run_steps", new_callable=AsyncMock, side_effect=[result()] * 4) as run:
            report = await execute_plan(object(), plan())
        self.assertEqual([call.args[1][0].target for call in run.call_args_list], ["Open", "Save", "Saved", "Remove"])
        self.assertEqual([step["phase"] for step in report["steps"]], ["setup", "test", "test", "cleanup"])
        self.assertEqual(report["status"], "passed")

    async def test_setup_failure_skips_test_but_attempts_cleanup(self):
        with patch("core.saved_plan.run_steps", new_callable=AsyncMock, side_effect=[result("failed"), result()]) as run:
            report = await execute_plan(object(), plan())
        self.assertEqual([call.args[1][0].target for call in run.call_args_list], ["Open", "Remove"])
        self.assertEqual(report["phases"]["test"]["status"], "skipped")
        self.assertEqual(report["status"], "failed")

    async def test_test_failure_stops_remaining_test_steps_and_keeps_cleanup_failure(self):
        with patch("core.saved_plan.run_steps", new_callable=AsyncMock, side_effect=[result(), result("failed"), result("failed")]) as run:
            report = await execute_plan(object(), plan())
        self.assertEqual(run.await_count, 3)
        self.assertEqual(report["phases"]["test"]["status"], "failed")
        self.assertEqual(report["phases"]["cleanup"]["status"], "failed")
        self.assertEqual(report["status"], "failed")

    async def test_empty_cleanup_is_not_a_failure(self):
        candidate = TestPlan.model_validate({"schema_version": 1, "steps": [{"action": "check_visible", "target": "Login"}]})
        with patch("core.saved_plan.run_steps", new_callable=AsyncMock, return_value=result()):
            report = await execute_plan(object(), candidate)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["phases"]["cleanup"]["status"], "not_configured")

    async def test_unexpected_step_error_still_attempts_cleanup(self):
        with patch("core.saved_plan.run_steps", new_callable=AsyncMock, side_effect=[RuntimeError("Disconnected"), result()]) as run:
            report = await execute_plan(object(), plan())
        self.assertEqual(run.await_count, 2)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["phases"]["cleanup"]["status"], "passed")

    async def test_off_origin_page_performs_no_actions(self):
        with patch("core.saved_plan.run_steps", new_callable=AsyncMock) as run:
            report = await execute_plan(SimpleNamespace(url="https://elsewhere.example/"), plan(), expected_origin=("http", "127.0.0.1", 5173))
        self.assertEqual(report["status"], "failed")
        run.assert_not_awaited()


class SavedPlanServiceTests(IsolatedAsyncioTestCase):
    def setUp(self):
        self.snapshot = {"id": "one", "name": "Pinned", "instruction": "Saved instruction", "variant": "original", "reruns": 1, "revision": 1, "plan": plan().model_dump()}
        self.session = SimpleNamespace(page=SimpleNamespace(url="http://127.0.0.1:5173/"))

    async def test_missing_plan_never_launches_browser(self):
        self.snapshot["plan"] = None
        with patch("core.saved_plan.get_test_by_id", new_callable=AsyncMock, return_value=self.snapshot), \
             patch("core.saved_plan.list_test_revisions", new_callable=AsyncMock, return_value=[{"revision": 1, "snapshot": self.snapshot}]), \
             patch("core.saved_plan.launch_browser", new_callable=AsyncMock) as launch:
            with self.assertRaises(ValueError):
                await execute_saved_plan("one", 1, "http://127.0.0.1:5173/")
        launch.assert_not_awaited()

    async def test_execution_uses_pinned_snapshot_and_persists_it(self):
        latest = {**self.snapshot, "name": "Changed", "revision": 2}
        execution = {"status": "passed", "steps": [], "phases": {}, "duration_ms": 3}
        with patch("core.saved_plan.get_test_by_id", new_callable=AsyncMock, return_value=latest), \
             patch("core.saved_plan.list_test_revisions", new_callable=AsyncMock, return_value=[{"revision": 1, "snapshot": self.snapshot}]), \
             patch("core.saved_plan.launch_browser", new_callable=AsyncMock, return_value=self.session), \
             patch("core.saved_plan.navigate_to", new_callable=AsyncMock, return_value=True), \
             patch("core.saved_plan.close_browser", new_callable=AsyncMock) as close, \
             patch("core.saved_plan.execute_plan", new_callable=AsyncMock, return_value=execution), \
             patch("core.saved_plan.save_run", new_callable=AsyncMock, return_value={"id": "run-one"}) as save:
            report = await execute_saved_plan("one", 1, "http://127.0.0.1:5173/")
        self.assertEqual(report["saved_run_id"], "run-one")
        self.assertEqual(save.call_args.args[0]["result"]["definition_snapshot"]["name"], "Pinned")
        self.assertEqual(save.call_args.args[0]["result"]["test_revision"], 1)
        close.assert_awaited_once_with(self.session)

    async def test_persistence_error_does_not_repeat_browser_execution(self):
        with patch("core.saved_plan.get_test_by_id", new_callable=AsyncMock, return_value=self.snapshot), \
             patch("core.saved_plan.list_test_revisions", new_callable=AsyncMock, return_value=[{"revision": 1, "snapshot": self.snapshot}]), \
             patch("core.saved_plan.launch_browser", new_callable=AsyncMock, return_value=self.session), \
             patch("core.saved_plan.navigate_to", new_callable=AsyncMock, return_value=True), \
             patch("core.saved_plan.close_browser", new_callable=AsyncMock) as close, \
             patch("core.saved_plan.execute_plan", new_callable=AsyncMock, return_value={"status": "passed", "steps": [], "phases": {}}) as execute, \
             patch("core.saved_plan.save_run", new_callable=AsyncMock, side_effect=RuntimeError("DB unavailable")):
            with self.assertRaises(PlanPersistenceError):
                await execute_saved_plan("one", 1, "http://127.0.0.1:5173/")
        execute.assert_awaited_once()
        close.assert_awaited_once()
