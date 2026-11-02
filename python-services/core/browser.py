import asyncio
from dataclasses import dataclass
from playwright.async_api import async_playwright, Browser, Page, Playwright, TimeoutError as PlaywrightTimeoutError

from utils.logger import log_info, log_success, log_error, log_warning
import os 
import subprocess


@dataclass
class BrowserSession:
    """
    Holds a live browser + page session.
    Always use the context manager so browser closes cleanly.
    """
    playwright: Playwright
    browser: Browser
    page: Page
    xvfb_process: subprocess.Popen | None = None

# Runs in every page before site scripts. Defuses common "devtools open" /
# automation detectors that warn, redirect, or block the page:
#   - navigator.webdriver: Playwright exposes it; many sites hard-block on it.
#   - console.clear spam: detectors wipe the console to hide their probes.
#   - getter/toString trap probes: detectors console.log an object whose
#     accessor fires when the console serializes it. Our console listener
#     keeps the CDP Runtime domain enabled, so serialization happens and the
#     site thinks DevTools is open. We drop such probe objects before logging.
_STEALTH_INIT_SCRIPT = """
(() => {
  try {
    Object.defineProperty(Navigator.prototype, "webdriver", {
      get: () => undefined,
      configurable: true,
    });
  } catch (e) {}

  try { console.clear = () => undefined; } catch (e) {}

  const isProbe = (arg) => {
    if (arg === null) return false;
    const type = typeof arg;
    if (type === "function") return Object.prototype.hasOwnProperty.call(arg, "toString");
    if (type !== "object") return false;
    if (arg instanceof RegExp || arg instanceof Date || arg instanceof Error) {
      return Object.prototype.hasOwnProperty.call(arg, "toString");
    }
    const descriptors = Object.getOwnPropertyDescriptors(arg);
    for (const key of Reflect.ownKeys(descriptors)) {
      if (typeof descriptors[key].get === "function") return true;
    }
    return Object.prototype.hasOwnProperty.call(arg, "toString");
  };

  for (const method of ["log", "debug", "info", "warn", "error", "table", "dir", "dirxml"]) {
    const original = console[method];
    if (typeof original !== "function") continue;
    console[method] = function (...args) {
      if (args.some(isProbe)) return undefined;
      return original.apply(this, args);
    };
  }
})();
"""


def start_xvfb(display: str = ":99") -> subprocess.Popen:
    """
    Start a virtual display using Xvfb.
    Required for headful mode inside Docker containers.
    """
    log_info(f"Starting Xvfb virtual display on {display}...")

    process = subprocess.Popen(
        ["Xvfb", display, "-screen", "0", "1280x720x24", "-ac"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # give Xvfb a moment to start
    import time
    time.sleep(1)

    os.environ["DISPLAY"] = display
    log_success(f"Xvfb started (pid={process.pid}), DISPLAY={display}")

    return process


def stop_xvfb(process: subprocess.Popen):
    """
    Stop the Xvfb virtual display process.
    """
    try:
        process.terminate()
        process.wait(timeout=5)
        log_info("Xvfb stopped.")
    except Exception as error:
        log_warning(f"Error stopping Xvfb: {error}")


async def launch_browser(headless: bool = True) -> BrowserSession:
    """
    Launch a Chromium browser and open a blank page.
    Returns a BrowserSession — caller is responsible for closing it.
    """
    xvfb_process = None

    if not headless:
        # check if a display is already available
        if not os.environ.get("DISPLAY"):
            xvfb_process = start_xvfb()
        else:
            log_info(f"Using existing DISPLAY={os.environ['DISPLAY']}")

    log_info(f"Launching Chromium ({'headful' if not headless else 'headless'})...")

    playwright = await async_playwright().start()

    browser = await playwright.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            # Stops Chromium from flagging itself as automated
            # (navigator.webdriver and related Blink signals).
            "--disable-blink-features=AutomationControlled",
        ],
    )

    page = await browser.new_page()
    await page.add_init_script(_STEALTH_INIT_SCRIPT)

    log_success("Browser launched successfully.")

    return BrowserSession(playwright=playwright, browser=browser, page=page, xvfb_process=xvfb_process,)


async def navigate_to(page: Page, url: str, timeout_ms: int = 30000) -> bool:
    """
    Navigate to a URL and wait for the document to become available.
    Returns True on success, False on failure.
    """
    log_info(f"Navigating to: {url}")

    try:
        await page.goto(url, wait_until="commit", timeout=timeout_ms)
        try:
            await page.wait_for_load_state(
                "domcontentloaded",
                timeout=min(timeout_ms, 10000),
            )
        except PlaywrightTimeoutError:
            log_warning("Document committed but DOMContentLoaded timed out; continuing.")

        await page.locator("body").wait_for(state="attached", timeout=5000)

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

    if session.xvfb_process:
        stop_xvfb(session.xvfb_process)


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