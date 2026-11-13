import base64
import os
import tempfile
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from core.saved_plan import PreparedPlan, execute_prepared_plan
from parser.test_plan import TestPlan


PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jL1sAAAAASUVORK5CYII=")
ID = "00000000-0000-0000-0000-000000000001"


class FailureCaptureTests(IsolatedAsyncioTestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        self.root = Path(stack.enter_context(tempfile.TemporaryDirectory()))
        stack.enter_context(patch.dict(os.environ, {"ENABLE_RUN_SCREENSHOT_CAPTURE": "true", "RUN_SCREENSHOT_ROOT": str(self.root)}))
        self.page = SimpleNamespace(url="http://staging.example/", screenshot=AsyncMock(return_value=PNG))
        self.session = SimpleNamespace(page=self.page)
        stack.enter_context(patch("core.saved_plan.launch_browser", new_callable=AsyncMock, return_value=self.session))
        stack.enter_context(patch("core.saved_plan.navigate_to", new_callable=AsyncMock, return_value=True))
        self.close = stack.enter_context(patch("core.saved_plan.close_browser", new_callable=AsyncMock))
        self.execute = stack.enter_context(patch("core.saved_plan.execute_plan", new_callable=AsyncMock,
            return_value={"status": "failed", "steps": [], "phases": {}, "error_message": "Original assertion failure"}))
        self.save = stack.enter_context(patch("core.saved_plan.save_run", new_callable=AsyncMock, return_value={"id": ID}))
        plan = TestPlan(schema_version=1, steps=[{"action": "check_visible", "target": "Missing heading"}])
        self.prepared = PreparedPlan(ID, 1, {"instruction": "Check heading", "plan": plan.model_dump()}, plan)

    async def test_failed_run_captures_png_and_persists_reference_before_close(self):
        result = await execute_prepared_plan(self.prepared, self.page.url)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["screenshotCapture"]["status"], "captured")
        saved = self.save.await_args.args[0]
        path = Path(saved["screenshotPath"])
        self.assertTrue(path.is_relative_to(self.root.resolve()))
        self.assertEqual(path.read_bytes(), PNG)
        self.assertEqual(result["screenshot_path"], str(path))
        self.page.screenshot.assert_awaited_once_with(type="png", full_page=False, timeout=5000)
        self.close.assert_awaited_once_with(self.session)
        self.save.assert_awaited_once()

    async def test_capture_is_disabled_by_default(self):
        with patch.dict(os.environ):
            os.environ.pop("ENABLE_RUN_SCREENSHOT_CAPTURE", None)
            result = await execute_prepared_plan(self.prepared, self.page.url)
        self.assertNotIn("screenshotCapture", result)
        self.assertNotIn("screenshotPath", self.save.await_args.args[0])
        self.page.screenshot.assert_not_awaited()
        self.assertEqual(list(self.root.iterdir()), [])

    async def test_passing_run_never_captures(self):
        self.execute.return_value = {"status": "passed", "steps": [], "phases": {}}
        result = await execute_prepared_plan(self.prepared, self.page.url)
        self.assertEqual(result["status"], "passed")
        self.page.screenshot.assert_not_awaited()
        self.assertEqual(list(self.root.iterdir()), [])

    async def test_capture_error_preserves_original_failure_and_still_saves_once(self):
        self.page.screenshot.side_effect = RuntimeError("private page secret")
        result = await execute_prepared_plan(self.prepared, self.page.url)
        self.assertEqual(result["error_message"], "Original assertion failure")
        self.assertEqual(result["screenshotCapture"]["status"], "unavailable")
        self.assertNotIn("private page secret", str(result))
        self.assertNotIn("screenshotPath", self.save.await_args.args[0])
        self.close.assert_awaited_once()
        self.save.assert_awaited_once()

    async def test_missing_root_does_not_fall_back_to_an_unapproved_directory(self):
        with patch.dict(os.environ):
            os.environ.pop("RUN_SCREENSHOT_ROOT", None)
            result = await execute_prepared_plan(self.prepared, self.page.url)
        self.assertEqual(result["screenshotCapture"]["status"], "unavailable")
        self.page.screenshot.assert_not_awaited()
        self.save.assert_awaited_once()

    async def test_out_of_origin_page_is_not_captured(self):
        self.page.url = "http://other.example/"
        result = await execute_prepared_plan(self.prepared, "http://staging.example/")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["screenshotCapture"]["status"], "skipped")
        self.page.screenshot.assert_not_awaited()

    async def test_invalid_or_oversized_png_is_not_persisted_as_evidence(self):
        for content in [b"not a png", PNG + b"x" * (5 * 1024 * 1024)]:
            with self.subTest(size=len(content)):
                self.page.screenshot.return_value = content
                result = await execute_prepared_plan(self.prepared, self.page.url)
                self.assertEqual(result["screenshotCapture"]["status"], "unavailable")
                self.assertNotIn("screenshotPath", self.save.await_args.args[0])
                self.assertEqual(list(self.root.iterdir()), [])
