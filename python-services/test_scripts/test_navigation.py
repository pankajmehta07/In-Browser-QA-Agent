import unittest
from unittest.mock import patch

from playwright.async_api import async_playwright

from parser.models import ParsedStep
from parser.step_runner import run_steps


class NavigationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.addCleanup(patch.stopall)
        patch("core.resolver.find_approved_mapping", return_value=None).start()
        patch("core.resolver.resolve_button_with_llm", return_value=None).start()
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch()
        self.page = await self.browser.new_page()
        await self.page.set_content(
            '<a href="#work">Projects</a><section id="work">Portfolio</section>'
            '<button onclick="document.body.dataset.clicked = true">Settings</button>'
        )

    async def asyncTearDown(self):
        await self.browser.close()
        await self.playwright.stop()

    async def test_click_and_goto_follow_links(self):
        for action in ("click", "goto"):
            with self.subTest(action=action):
                result, _ = await run_steps(self.page, [ParsedStep(action, "Projects")])
                self.assertEqual(result.status, "passed")
                self.assertTrue(self.page.url.endswith("#work"))
                self.assertEqual(result.steps[0].selector_used, 'role=link[name="Projects"]')
                self.assertFalse(result.steps[0].was_healed)

    async def test_buttons_still_work(self):
        result, _ = await run_steps(self.page, [ParsedStep("click", "Settings")])
        self.assertEqual(result.status, "passed")
        self.assertEqual(await self.page.locator("body").get_attribute("data-clicked"), "true")

    async def test_similarity_retains_link_role(self):
        with patch("core.resolver.find_approved_mapping", return_value=None):
            result, _ = await run_steps(self.page, [ParsedStep("click", "Project")])
        self.assertEqual(result.status, "passed")
        self.assertEqual(result.steps[0].selector_used, 'role=link[name="Projects"]')
        self.assertTrue(result.steps[0].was_healed)

    async def test_duplicate_links_to_same_destination(self):
        await self.page.set_content(
            '<a href="#work">Projects</a><a href="about:blank#work">Projects</a>'
            '<a href="#other" style="display:none">Projects</a>'
        )
        result, _ = await run_steps(self.page, [ParsedStep("goto", "Projects")])
        self.assertEqual(result.status, "passed")
        self.assertTrue(self.page.url.endswith("#work"))

    async def test_different_link_destinations_remain_ambiguous(self):
        await self.page.set_content('<a href="#one">Projects</a><a href="#two">Projects</a>')
        result, _ = await run_steps(self.page, [ParsedStep("goto", "Projects")])
        self.assertEqual(result.status, "failed")
        self.assertEqual(self.page.url, "about:blank")


if __name__ == "__main__":
    unittest.main()