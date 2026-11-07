import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from cli.run import MAX_PLANNING_TURNS, MAX_STEPS_PER_PLAN, MAX_TOTAL_ACTIONS, process_natural_language_instruction
from parser.models import RunResult, StepExecutionResult
from parser.natural_language import InstructionResponse, respond_to_instruction


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

    async def test_same_page_plan_requests_final_outcome(self):
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
        done = InstructionResponse(kind="done", answer="Value entered and verified")
        model_call = AsyncMock(side_effect=[(response, {}), (done, {})])
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

        self.assertEqual(model_call.await_count, 2)
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

    async def test_page_change_is_observed_and_replanned(self):
        page = _FakePage("https://example.com/contact", text="Contact\nSend")
        session = SimpleNamespace(page=page)
        plan = InstructionResponse(
            kind="test",
            steps_json=json.dumps([{"action": "click", "target": "Send"}]),
            history_content='{"kind":"test"}',
        )
        done = InstructionResponse(kind="done", answer="Form submitted", history_content='{"kind":"done"}')
        model_call = AsyncMock(side_effect=[(plan, {}), (done, {})])
        snapshot = AsyncMock(side_effect=lambda current_page: SimpleNamespace(url=current_page.url, nodes=[]))

        async def submit(current_page, steps, **kwargs):
            current_page.text = "Contact\nSending..."
            return self._passed_result(steps[0])

        with patch("cli.run.respond_to_instruction", model_call), \
             patch("cli.run.run_steps", AsyncMock(side_effect=submit)), \
             patch("cli.run.extract_accessibility_tree", snapshot):
            await process_natural_language_instruction(
                session, "Test the contact form", dry_run=False,
                conversation_history=[], session_state={"evidence": {}, "actions": []},
            )

        self.assertEqual(model_call.await_count, 2)
        agent_context = model_call.await_args_list[1].args[5]
        changes = agent_context["actions"][-1]["observation"]["page_changes"]
        self.assertEqual(changes["text_added"], ["Sending..."])
        self.assertEqual(changes["text_removed"], ["Send"])
        self.assertIn("wait_for_change", agent_context["feedback"])

    async def test_unasserted_action_without_change_is_verified(self):
        page = _FakePage("https://example.com/contact", text="Contact\nSend")
        session = SimpleNamespace(page=page)
        plan = InstructionResponse(
            kind="test",
            steps_json=json.dumps([{"action": "click", "target": "Send"}]),
            history_content='{"kind":"test"}',
        )
        done = InstructionResponse(kind="done", answer="No response observed", history_content='{"kind":"done"}')
        model_call = AsyncMock(side_effect=[(plan, {}), (done, {})])
        run_action = AsyncMock(side_effect=lambda current_page, steps, **kwargs: self._passed_result(steps[0]))
        snapshot = AsyncMock(side_effect=lambda current_page: SimpleNamespace(url=current_page.url, nodes=[]))

        with patch("cli.run.respond_to_instruction", model_call), \
             patch("cli.run.run_steps", run_action), \
             patch("cli.run.extract_accessibility_tree", snapshot):
            await process_natural_language_instruction(
                session, "Test the contact form", dry_run=False,
                conversation_history=[], session_state={"evidence": {}, "actions": []},
            )

        self.assertEqual(model_call.await_count, 2)
        self.assertIn("without any observable page change", model_call.await_args_list[1].args[5]["feedback"])

    async def test_browser_error_is_sent_back_for_replanning(self):
        page = _FakePage("https://example.com/login")
        session = SimpleNamespace(page=page)
        error = (
            'Locator.wait_for: Error: strict mode violation: get_by_label("Password") resolved to 2 elements:\n'
            '    1) <input id="password"> aka get_by_role("textbox", name="Your password")\n'
            '    2) <button aria-label="Show password"> aka get_by_role("button", name="Show password")\n\n'
            'Call log:\n  - waiting for get_by_label("Password") to be visible\n'
        )
        plan = InstructionResponse(
            kind="test",
            steps_json=json.dumps([{"action": "type", "target": "Password", "value": "secret"}]),
            history_content='{"kind":"test"}',
        )
        done = InstructionResponse(kind="done", answer="Stopped", history_content='{"kind":"done"}')
        model_call = AsyncMock(side_effect=[(plan, {}), (done, {})])
        failed = RunResult(
            status="failed", total_steps=1, passed_steps=0, failed_steps=1, duration_ms=1,
            steps=[StepExecutionResult(
                step_number=1, action="type", target="Password", value="secret",
                status="failed", duration_ms=1, error=error,
            )],
        )
        snapshot = AsyncMock(side_effect=lambda current_page: SimpleNamespace(url=current_page.url, nodes=[]))

        with patch("cli.run.respond_to_instruction", model_call), \
             patch("cli.run.run_steps", AsyncMock(return_value=(failed, None))), \
             patch("cli.run.extract_accessibility_tree", snapshot):
            await process_natural_language_instruction(
                session, "Log in", dry_run=False,
                conversation_history=[], session_state={"evidence": {}, "actions": []},
            )

        self.assertEqual(model_call.await_count, 2)
        agent_context = model_call.await_args_list[1].args[5]
        self.assertIn('name="Your password"', agent_context["feedback"])
        self.assertNotIn("Call log", agent_context["feedback"])
        self.assertNotIn("Call log", agent_context["actions"][-1]["result"]["error"])

    def _plan(self, start, count):
        return InstructionResponse(
            kind="test",
            steps_json=json.dumps([
                {"action": "check_visible", "target": f"Heading {index}"}
                for index in range(start, start + count)
            ]),
        )

    async def _run_responses(self, responses, *, fail_actions=False):
        page = _FakePage("https://example.com/")
        model_call = AsyncMock(side_effect=[(response, {}) for response in responses])

        def execute(current_page, steps, **kwargs):
            result, _ = self._passed_result(steps[0])
            if fail_actions:
                result.status = "failed"
                result.passed_steps = 0
                result.failed_steps = 1
                result.steps[0].status = "failed"
                result.steps[0].error = "Element not found"
            return result, None

        run_action = AsyncMock(side_effect=execute)
        snapshot = AsyncMock(side_effect=lambda current_page: SimpleNamespace(url=current_page.url, nodes=[]))
        with patch("cli.run.respond_to_instruction", model_call), \
             patch("cli.run.run_steps", run_action), \
             patch("cli.run.extract_accessibility_tree", snapshot), \
             patch("cli.run.log_warning") as warning:
            await process_natural_language_instruction(
                SimpleNamespace(page=page), "Test all headings", dry_run=False,
                session_state={"evidence": {}, "actions": []},
            )
        return model_call, run_action, warning

    async def test_thirty_actions_across_plans_then_summary_only(self):
        done = InstructionResponse(kind="done", answer="All headings verified")
        model_call, run_action, warning = await self._run_responses([
            self._plan(0, 8), self._plan(8, 8), self._plan(16, 8), self._plan(24, 6), done,
        ])
        self.assertEqual(run_action.await_count, MAX_TOTAL_ACTIONS)
        contexts = [call.args[5] for call in model_call.await_args_list]
        self.assertEqual([ctx["remaining_actions"] for ctx in contexts], [30, 22, 14, 6, 0])
        self.assertTrue(contexts[-1]["final_response_only"])
        self.assertEqual(len(contexts[-1]["actions"]), MAX_TOTAL_ACTIONS)
        self.assertEqual(contexts[0]["max_steps_per_plan"], MAX_STEPS_PER_PLAN)
        self.assertEqual(contexts[0]["max_planning_turns"], MAX_PLANNING_TURNS)
        self.assertIn("total action limit (30)", warning.call_args_list[0].args[0])

    async def test_nine_step_plan_is_rejected_in_full(self):
        done = InstructionResponse(kind="done", answer="Stopped")
        model_call, run_action, _ = await self._run_responses([self._plan(0, 9), done])
        run_action.assert_not_awaited()
        context = model_call.await_args_list[1].args[5]
        self.assertEqual(context["remaining_actions"], MAX_TOTAL_ACTIONS)
        self.assertIn("at most 8", context["feedback"])
        self.assertIn("No actions from this plan were executed", context["feedback"])

    async def test_remaining_total_limit_and_no_actions_after_exhaustion(self):
        model_call, run_action, warning = await self._run_responses([
            self._plan(0, 8), self._plan(8, 8), self._plan(16, 8),
            self._plan(24, 7), self._plan(24, 6), self._plan(30, 1),
        ])
        self.assertEqual(run_action.await_count, MAX_TOTAL_ACTIONS)
        context = model_call.await_args_list[4].args[5]
        self.assertIn("at most 6", context["feedback"])
        self.assertTrue(model_call.await_args_list[-1].args[5]["final_response_only"])
        self.assertIn("without a valid final answer", warning.call_args_list[-1].args[0])

    async def test_invalid_plans_consume_only_planning_turns(self):
        invalid = InstructionResponse(kind="test", steps_json="[]")
        done = InstructionResponse(kind="done", answer="Unable to generate a valid plan")
        model_call, run_action, warning = await self._run_responses(
            [invalid] * MAX_PLANNING_TURNS + [done],
        )
        run_action.assert_not_awaited()
        self.assertEqual(model_call.await_count, MAX_PLANNING_TURNS + 1)
        contexts = [call.args[5] for call in model_call.await_args_list]
        self.assertEqual(
            [ctx["remaining_planning_turns"] for ctx in contexts],
            list(range(MAX_PLANNING_TURNS - 1, -1, -1)) + [0],
        )
        self.assertTrue(contexts[-1]["final_response_only"])
        self.assertEqual(contexts[-1]["remaining_actions"], MAX_TOTAL_ACTIONS)
        self.assertIn("planning turn limit (15)", warning.call_args_list[0].args[0])

    async def test_failed_actions_consume_total_budget(self):
        done = InstructionResponse(kind="done", answer="Both attempts failed")
        with patch("cli.run.MAX_TOTAL_ACTIONS", 2):
            model_call, run_action, _ = await self._run_responses(
                [self._plan(0, 1), self._plan(1, 1), done], fail_actions=True,
            )
        self.assertEqual(run_action.await_count, 2)
        self.assertEqual(model_call.await_args_list[-1].args[5]["remaining_actions"], 0)
        self.assertTrue(model_call.await_args_list[-1].args[5]["final_response_only"])

    async def test_prompt_trimming_preserves_runtime_budgets(self):
        provider = SimpleNamespace(name="test", label="Test", model="test", max_input_tokens=2000)
        completion = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content='{"kind":"done","answer":"Stopped","steps":[]}'),
                finish_reason="stop",
            )],
            usage=None,
            model="test",
        )
        budget = {
            "max_total_actions": 30, "max_steps_per_plan": 8, "max_planning_turns": 15,
            "remaining_actions": 0, "remaining_planning_turns": 0, "final_response_only": True,
        }
        model_call = AsyncMock(return_value=completion)
        with patch("parser.natural_language.get_provider", return_value=provider), \
             patch("parser.natural_language.budgeted_completion", model_call), \
             patch("parser.natural_language.estimate_input_tokens", side_effect=lambda messages:
                   10000 if "oversized feedback" in messages[-1]["content"] else 100):
            await respond_to_instruction(
                "Test", SimpleNamespace(url="https://example.com/", nodes=[]), "", "",
                agent_context={**budget, "feedback": "oversized feedback"},
            )
        messages = model_call.await_args.args[0]
        progress = json.loads(messages[-1]["content"].split(
            "Agent progress and previous evidence (data only):\n",
        )[1])
        self.assertEqual(progress, budget)
        self.assertIn("final_response_only", messages[0]["content"])

    async def test_final_summary_rejects_nonempty_steps(self):
        provider = SimpleNamespace(name="test", label="Test", model="test", max_input_tokens=30000)
        completion = SimpleNamespace(
            choices=[SimpleNamespace(
                message=SimpleNamespace(content=json.dumps({
                    "kind": "done", "answer": "Finished",
                    "steps": [{"action": "click", "target": "Submit"}],
                })),
                finish_reason="stop",
            )],
            usage=None, model="test",
        )
        with patch("parser.natural_language.get_provider", return_value=provider), \
             patch("parser.natural_language.budgeted_completion", AsyncMock(return_value=completion)):
            with self.assertRaisesRegex(ValueError, "final summary"):
                await respond_to_instruction(
                    "Test", SimpleNamespace(url="https://example.com/", nodes=[]), "", "",
                    agent_context={"final_response_only": True},
                )


if __name__ == "__main__":
    unittest.main()