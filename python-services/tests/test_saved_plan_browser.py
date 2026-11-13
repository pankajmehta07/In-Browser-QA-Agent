"""Real Chromium against an ephemeral, loopback-only synthetic fixture."""

import os
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from core.browser import close_browser, launch_browser, navigate_to
from core.saved_plan import execute_plan, _origin
from parser.test_plan import TestPlan


HTML = b'''<!doctype html><html><body><h1>Plan fixture</h1>
<label for="name">Name</label><input id="name">
<button onclick="document.getElementById('record').textContent=document.getElementById('name').value">Save</button>
<button onclick="document.getElementById('record').textContent='Cleared'">Reset</button>
<h2 id="record">Empty</h2></body></html>'''


class FixtureHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HTML)

    def log_message(self, *args):
        pass


@unittest.skipUnless(os.getenv("RUN_PLAN_BROWSER_TESTS") == "1", "Opt-in local Chromium fixture")
class PlanBrowserTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    async def asyncSetUp(self):
        self.session = await launch_browser()
        self.addAsyncCleanup(close_browser, self.session)
        self.assertTrue(await navigate_to(self.session.page, self.url))

    async def test_setup_test_and_cleanup_execute_real_controls(self):
        plan = TestPlan.model_validate({"schema_version": 1,
            "setup": [{"action": "type", "target": "Name", "value": "Created record"}],
            "steps": [{"action": "click", "target": "Save"}, {"action": "check_visible", "target": "Created record"}],
            "cleanup": [{"action": "click", "target": "Reset"}, {"action": "check_visible", "target": "Cleared"}]})
        result = await execute_plan(self.session.page, plan, expected_origin=_origin(self.url))
        self.assertEqual(result["status"], "passed")
        self.assertEqual(len(result["steps"]), 5)
        self.assertEqual(await self.session.page.locator("#record").text_content(), "Cleared")

    async def test_failed_setup_does_not_submit_and_cleanup_still_runs(self):
        plan = TestPlan.model_validate({"schema_version": 1,
            "setup": [{"action": "type", "target": "Missing field", "value": "No write"}],
            "steps": [{"action": "click", "target": "Save"}],
            "cleanup": [{"action": "click", "target": "Reset"}]})
        result = await execute_plan(self.session.page, plan, expected_origin=_origin(self.url))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["phases"]["test"]["status"], "skipped")
        self.assertEqual(await self.session.page.locator("#record").text_content(), "Cleared")

    async def test_cleanup_failure_is_reported_after_main_assertion_passes(self):
        plan = TestPlan.model_validate({"schema_version": 1,
            "steps": [{"action": "check_visible", "target": "Plan fixture"}],
            "cleanup": [{"action": "goto", "target": "Missing heading"}]})
        result = await execute_plan(self.session.page, plan, expected_origin=_origin(self.url))
        self.assertEqual(result["phases"]["test"]["status"], "passed")
        self.assertEqual(result["phases"]["cleanup"]["status"], "failed")
        self.assertEqual(result["status"], "failed")
