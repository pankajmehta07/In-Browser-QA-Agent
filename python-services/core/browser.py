import asyncio
from dataclasses import dataclass
from playwright.async_api import async_playwright, Browser, Page, Playwright

from utils.logger import log_info, log_success, log_error, log_warning


@dataclass
class BrowserSession:
    """
    Holds a live browser + page session.
    Always use the context manager so browser closes cleanly.
    """
    playwright: Playwright
    browser: Browser
    page: Page


async def launch_browser(headless: bool = True) -> BrowserSession:
    """
    Launch a Chromium browser and open a blank page.
    Returns a BrowserSession — caller is responsible for closing it.
    """
    log_info("Launching Chromium browser...")

    playwright = await async_playwright().start()

    browser = await playwright.chromium.launch(
        headless=headless,
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )

    page = await browser.new_page()

    log_success("Browser launched successfully.")

    return BrowserSession(playwright=playwright, browser=browser, page=page)


async def navigate_to(page: Page, url: str, timeout_ms: int = 30000) -> bool:
    """
    Navigate to a URL and wait for the page to fully load.
    Returns True on success, False on failure.
    """
    log_info(f"Navigating to: {url}")

    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)

        current_url = page.url
        title = await page.title()

        log_success(f"Page loaded — Title: '{title}'")
        log_success(f"Final URL: {current_url}")

        return True

    except Exception as error:
        log_error(f"Navigation failed: {error}")
        return False


async def close_browser(session: BrowserSession):
    """
    Cleanly close browser and stop Playwright.
    """
    try:
        await session.browser.close()
        await session.playwright.stop()
        log_info("Browser closed.")
    except Exception as error:
        log_warning(f"Error while closing browser: {error}")


async def take_screenshot(page: Page, output_path: str) -> bool:
    """
    Take a full page screenshot and save it to output_path.
    Returns True on success, False on failure.
    """
    try:
        await page.screenshot(path=output_path, full_page=True)
        log_success(f"Screenshot saved: {output_path}")
        return True
    except Exception as error:
        log_error(f"Screenshot failed: {error}")
        return False