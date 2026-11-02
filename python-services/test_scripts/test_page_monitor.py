import unittest

from playwright.async_api import async_playwright

from core.page_monitor import PageMonitor, PageState, collect_invalid_fields, diff_page_states
from extractors.accessibility import extract_accessibility_tree
from parser.models import ParsedStep
from parser.step_runner import run_steps


FORM = """
<form id="contact">
  <label for="name">Full Name</label><input id="name">
  <button id="send" type="submit">Send</button>
</form>
<div id="result" role="status"></div>
<script>
document.getElementById("contact").addEventListener("submit", event => {
  event.preventDefault();
  const button = document.getElementById("send");
  button.textContent = "Sending...";
  button.disabled = true;
  setTimeout(() => {
    button.textContent = "Send";
    button.disabled = false;
    document.getElementById("result").textContent = "Message sent successfully";
    console.error("analytics endpoint unavailable");
    alert("Thanks!");
  }, 1500);
});
</script>
"""


class PageMonitorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch()
        self.page = await self.browser.new_page()
        self.monitor = PageMonitor(self.page)
        await self.page.set_content(FORM)

    async def asyncTearDown(self):
        await self.browser.close()
        await self.playwright.stop()

    async def _state(self):
        return PageState(
            self.page.url,
            await self.page.title(),
            await self.page.locator("body").inner_text(),
            await extract_accessibility_tree(self.page),
        )

    async def test_pending_submission_is_waited_for_and_reported(self):
        before = await self._state()
        result, _ = await run_steps(self.page, [ParsedStep("click", "Send")], allow_llm_fallback=False)
        self.assertEqual(result.status, "passed")
        pending = await self._state()
        changed = diff_page_states(before, pending)["elements_changed"][0]
        self.assertEqual(changed["name"], {"from": "Send", "to": "Sending..."})
        self.assertEqual(changed["disabled"], {"from": False, "to": True})

        result, _ = await run_steps(
            self.page, [ParsedStep("wait_for_change", "submission result", "5")], allow_llm_fallback=False,
        )
        self.assertEqual(result.status, "passed")
        changes = diff_page_states(pending, await self._state())
        self.assertIn("Message sent successfully", changes["text_added"])
        event_types = {event["type"] for event in self.monitor.drain()}
        self.assertTrue({"console_error", "dialog_alert"} <= event_types)

    async def test_wait_for_change_fails_when_nothing_happens(self):
        result, _ = await run_steps(
            self.page, [ParsedStep("wait_for_change", "anything", "1")], allow_llm_fallback=False,
        )
        self.assertEqual(result.status, "failed")
        self.assertIn("No page change", result.steps[0].error)

    async def test_native_validation_is_reported(self):
        await self.page.set_content(
            '<form><label for="email">Email Address</label><input id="email" type="email" required>'
            '<button type="submit">Send</button></form>'
        )
        await run_steps(self.page, [ParsedStep("type", "Email Address", "not-an-email")], allow_llm_fallback=False)
        await run_steps(self.page, [ParsedStep("click", "Send")], allow_llm_fallback=False)
        invalid = await collect_invalid_fields(self.page)
        self.assertEqual(invalid[0]["field"], "Email Address")
        self.assertTrue(invalid[0]["message"])


if __name__ == "__main__":
    unittest.main()
