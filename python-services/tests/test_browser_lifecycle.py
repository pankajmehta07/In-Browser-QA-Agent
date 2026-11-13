from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from core.browser import close_browser, launch_browser


class BrowserLifecycleTests(IsolatedAsyncioTestCase):
    async def test_failed_launch_stops_driver(self):
        engine = SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(side_effect=RuntimeError("Missing executable"))), stop=AsyncMock())
        starter = SimpleNamespace(start=AsyncMock(return_value=engine))
        with patch("core.browser.async_playwright", return_value=starter):
            with self.assertRaises(RuntimeError):
                await launch_browser()
        engine.stop.assert_awaited_once()

    async def test_browser_close_failure_does_not_skip_driver_stop(self):
        session = SimpleNamespace(browser=SimpleNamespace(close=AsyncMock(side_effect=RuntimeError("Already disconnected"))),
                                  playwright=SimpleNamespace(stop=AsyncMock()), xvfb_process=None)
        await close_browser(session)
        session.playwright.stop.assert_awaited_once()
