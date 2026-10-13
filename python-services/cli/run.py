import asyncio
import argparse
import sys
import os

# make sure imports work from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.browser import launch_browser, navigate_to, close_browser, take_screenshot
from utils.logger import log_step, log_success, log_error, console


async def cmd_check_browser(url: str, screenshot: bool, headless: bool):
    """
    Step 1: Verify Playwright works.
    - Launches browser
    - Navigates to URL
    - Optionally takes a screenshot
    - Reports result
    """
    console.rule("[step]Step 1 — Browser Check[/step]")

    session = await launch_browser(headless=headless)

    try:
        log_step(1, "Launching browser")
        log_step(2, f"Navigating to {url}")

        success = await navigate_to(session.page, url)

        if not success:
            log_error("Navigation failed. Exiting.")
            return

        if screenshot:
            log_step(3, "Taking screenshot")
            os.makedirs("output", exist_ok=True)
            await take_screenshot(session.page, "output/screenshot.png")

        console.rule("[success]Browser check passed[/success]")

    finally:
        await close_browser(session)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qa-cli",
        description="QA Automation Python CLI",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- check-browser command ---
    browser_parser = subparsers.add_parser(
        "check-browser",
        help="Step 1: Verify Playwright can launch and navigate",
    )
    browser_parser.add_argument(
        "--url",
        type=str,
        default="https://example.com",
        help="URL to navigate to (default: https://example.com)",
    )
    browser_parser.add_argument(
        "--screenshot",
        action="store_true",
        help="Save a screenshot to output/screenshot.png",
    )
    browser_parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser in headful mode (visible window)",
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "check-browser":
        asyncio.run(cmd_check_browser(
            url=args.url,
            screenshot=args.screenshot,
            headless=not args.headful,
        ))


if __name__ == "__main__":
    main()