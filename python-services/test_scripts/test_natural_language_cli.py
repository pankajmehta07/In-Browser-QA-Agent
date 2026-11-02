import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cli.run import process_natural_language_instruction
from parser.models import RunResult, StepExecutionResult
from parser.natural_language import InstructionResponse


class _FakeLocator:
    def __init__(self, page):
        self.page = page

    async def inner_text(self, timeout=None):
        return self.page.text


class _FakePage:
    def __init__(self, url, text="Page content"):
        self.url = url
        self.text = text

    async def title(self):
        return "Test page"

    def locator(self, selector):
        return _FakeLocator(self)


class NaturalLanguageCliTests(unittest.IsolatedAsyncioTestCase):
    def _passed_result(self, step):
        return RunResult(
            status="passed",
            total_steps=1,
            passed_steps=1,
            failed_steps=0,
            duration_ms=1,
            steps=[
                StepExecutionResult(
                    step_number=1,
                    action=step.action,
                    target=step.target,
                    value=step.value,
                    status="passed",
                    duration_ms=1,
                )
            ],
        ), None

    async def test_same_page_plan_uses_one_model_request(self):
        page = _FakePage("https://example.com/")
        session = SimpleNamespace(page=page)
        instruction = "Enter a value and verify the result"
        response = InstructionResponse(
            kind="test",
            steps_json=json.dumps([
                {"action": "type", "target": "Name", "value": "Ada"},
                {"action": "check_contains", "target": "Name", "value": "Ada"},
            ]),
            history_content='{"kind":"test"}',
        )
        model_call = AsyncMock(return_value=(response, {}))
        run_action = AsyncMock(
            side_effect=lambda current_page, steps, **kwargs: self._passed_result(steps[0]),
        )
        snapshot = AsyncMock(side_effect=lambda current_page: SimpleNamespace(url=current_page.url, nodes=[]))

        with patch("cli.run.respond_to_instruction", model_call), \
             patch("cli.run.run_steps", run_action), \
             patch("cli.run.extract_accessibility_tree", snapshot):
            await process_natural_language_instruction(
                session, instruction, dry_run=False,
                conversation_history=[], session_state={"evidence": {}, "actions": []},
            )

        self.assertEqual(model_call.await_count, 1)
        self.assertEqual(run_action.await_count, 2)
        self.assertTrue(all(
            call.kwargs["allow_llm_fallback"] is False
            for call in run_action.await_args_list
        ))

    async def test_navigation_triggers_a_fresh_model_request(self):
        page = _FakePage("https://example.com/")
        session = SimpleNamespace(page=page)
        destination = "https://example.com/next"
        instruction = f"Visit {destination}"
        plan = InstructionResponse(
            kind="test",
            steps_json=json.dumps([{"action": "goto", "target": destination}]),
            history_content='{"kind":"test"}',
        )
        answer = InstructionResponse(
            kind="answer",
            answer="Destination reached",
            sources=[destination],
            history_content='{"kind":"answer","answer":"Destination reached"}',
        )
        model_call = AsyncMock(side_effect=[(plan, {}), (answer, {})])
        snapshot = AsyncMock(side_effect=lambda current_page: SimpleNamespace(url=current_page.url, nodes=[]))

        async def navigate(current_page, steps, **kwargs):
            current_page.url = steps[0].target
            return self._passed_result(steps[0])

        run_action = AsyncMock(side_effect=navigate)
        with patch("cli.run.respond_to_instruction", model_call), \
             patch("cli.run.run_steps", run_action), \
             patch("cli.run.extract_accessibility_tree", snapshot):
            await process_natural_language_instruction(
                session, instruction, dry_run=False,
                conversation_history=[], session_state={"evidence": {}, "actions": []},
            )

        self.assertEqual(model_call.await_count, 2)
        self.assertEqual(page.url, destination)


if __name__ == "__main__":
    unittest.main()