import json
import os
from contextlib import ExitStack
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from api.main import app
from extractors.accessibility import AccessibilitySnapshot
from parser.natural_language import InstructionResponse


class InstructionPreviewTests(TestCase):
    def setUp(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch("api.main.get_pool", new_callable=AsyncMock))
        stack.enter_context(patch("api.main.close_pool", new_callable=AsyncMock))
        stack.enter_context(patch.dict(os.environ, {"ENABLE_INSTRUCTION_PREVIEW": "true", "GROQ_API_KEY": "test-not-real",
                                                    "TARGET_APP_URL": "http://staging.example/login?private=value"}))
        self.page = MagicMock()
        self.page.url = "http://staging.example/login?private=value"
        self.page.title = AsyncMock(return_value="Login")
        self.page.get_by_role.return_value.all_text_contents = AsyncMock(return_value=["Login"])
        self.launch = stack.enter_context(patch("core.browser.launch_browser", new_callable=AsyncMock,
                                                return_value=SimpleNamespace(page=self.page)))
        self.close = stack.enter_context(patch("core.browser.close_browser", new_callable=AsyncMock))
        self.navigate = stack.enter_context(patch("core.browser.navigate_to", new_callable=AsyncMock, return_value=True))
        self.nodes = [SimpleNamespace(tag="input", role="textbox", name="Email", visible=True, disabled=False),
                      SimpleNamespace(tag="button", role="button", name="Login", visible=True, disabled=False)]
        self.extract = stack.enter_context(patch("extractors.accessibility.extract_accessibility_tree", new_callable=AsyncMock,
            return_value=AccessibilitySnapshot(url=self.page.url, total_count=2, nodes=self.nodes)))
        self.steps = [{"action": "type", "target": "Email", "value": "user@example.com"},
                      {"action": "click", "target": "Login"}]
        self.ai = stack.enter_context(patch("parser.natural_language.respond_to_instruction", new_callable=AsyncMock,
            return_value=InstructionResponse(kind="test", steps_json=json.dumps(self.steps))))
        self.save = stack.enter_context(patch("api.routers.compat.save_test", new_callable=AsyncMock))
        self.client = stack.enter_context(TestClient(app))
        self.path = "/compat/instructions/preview"
        self.body = {"instruction": "Enter user@example.com in Email and click Login", "confirmPageRead": True, "allowAI": True}

    def test_grounded_plan_is_returned_for_review_without_saving_or_execution(self):
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 200)
        result = response.json()
        self.assertEqual(result["status"], "draft")
        self.assertTrue(result["reviewRequired"])
        self.assertEqual(result["plan"]["steps"], [{**step, "value": step.get("value")} for step in self.steps])
        self.assertEqual(result["issues"], [])
        self.assertEqual(result["parser"]["source"], "llm")
        self.page.get_by_role.return_value.click.assert_not_called()
        self.save.assert_not_awaited()
        self.close.assert_awaited_once()

    def test_unobserved_future_state_is_needs_input_not_ready(self):
        self.ai.return_value = InstructionResponse(kind="test", steps_json=json.dumps([{"action": "click", "target": "Create Project"}]))
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "needs_input")
        self.assertEqual(response.json()["issues"][0]["target"], "Create Project")
        self.assertIn("observed", response.json()["issues"][0]["reason"])
        self.save.assert_not_awaited()

    def test_invalid_provider_steps_are_not_silently_dropped(self):
        self.ai.return_value = InstructionResponse(kind="test", steps_json=json.dumps([*self.steps, {"action": "delete", "target": "Project"}]))
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("plan", response.json())
        self.close.assert_awaited_once()

    def test_page_query_and_full_body_text_are_not_sent_to_provider(self):
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 200)
        context = self.ai.await_args.kwargs
        self.assertEqual(context["snapshot"].url, "http://staging.example/login")
        self.assertEqual(context["page_text"], "Login")
        self.page.locator.assert_not_called()
        self.assertNotIn("private=value", response.text)

    def test_flag_and_missing_provider_key_prevent_browser_start(self):
        for setting, status in [({"ENABLE_INSTRUCTION_PREVIEW": "false"}, 403), ({"GROQ_API_KEY": ""}, 503)]:
            with self.subTest(setting=setting), patch.dict(os.environ, setting):
                self.assertEqual(self.client.post(self.path, json=self.body).status_code, status)
        self.launch.assert_not_awaited()

    def test_consent_and_target_override_are_validated_before_browser_start(self):
        for override in [{"allowAI": False}, {"confirmPageRead": False}, {"url": "http://unapproved.example/"}, {"instruction": " "}]:
            with self.subTest(override=override):
                self.assertEqual(self.client.post(self.path, json={**self.body, **override}).status_code, 422)
        self.launch.assert_not_awaited()

    def test_redirect_outside_origin_is_rejected_before_provider_call(self):
        self.page.url = "http://unapproved.example/"
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 409)
        self.ai.assert_not_awaited()
        self.close.assert_awaited_once()

    def test_provider_failure_is_sanitized_and_browser_is_closed(self):
        self.ai.side_effect = RuntimeError("private provider API key")
        response = self.client.post(self.path, json=self.body)
        self.assertEqual(response.status_code, 502)
        self.assertNotIn("private provider API key", response.text)
        self.ai.assert_awaited_once()
        self.close.assert_awaited_once()

    def test_ambiguous_disabled_or_wrong_control_type_needs_input(self):
        for nodes in [[self.nodes[0], self.nodes[1], self.nodes[1]],
                      [self.nodes[0], SimpleNamespace(tag="button", role="button", name="Login", visible=True, disabled=True)],
                      [SimpleNamespace(tag="select", role="combobox", name="Email", visible=True, disabled=False), self.nodes[1]]]:
            with self.subTest(nodes=nodes):
                self.extract.return_value = AccessibilitySnapshot(url=self.page.url, total_count=len(nodes), nodes=nodes)
                response = self.client.post(self.path, json=self.body)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["status"], "needs_input")
