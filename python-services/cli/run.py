import asyncio
import argparse
import sys
import os

# make sure imports work from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.browser import launch_browser, navigate_to, close_browser, take_screenshot
from utils.logger import log_step, log_success, log_error, console

from extractors.page_content import extract_page_content
from extractors.accessibility import extract_accessibility_tree
from core.auditor import run_full_audit

from utils.printer import print_page_content, print_accessibility_snapshot, print_audit_report

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


async def cmd_extract_content(url: str, headless: bool):
    """
    Step 2: Extract and display full page content.
    """
    session = await launch_browser(headless=headless)

    try:
        success = await navigate_to(session.page, url)

        if not success:
            log_error("Navigation failed. Exiting.")
            return

        content = await extract_page_content(session.page)

        if not content:
            log_error("Content extraction failed.")
            return

        print_page_content(content)

    finally:
        await close_browser(session)


async def cmd_extract_accessibility(url: str, headless: bool):
    """
    Step 3: Extract and display accessibility tree.
    """
    session = await launch_browser(headless=headless)

    try:
        success = await navigate_to(session.page, url)

        if not success:
            log_error("Navigation failed. Exiting.")
            return

        snapshot = await extract_accessibility_tree(session.page)

        if not snapshot:
            log_error("Accessibility extraction failed.")
            return

        print_accessibility_snapshot(snapshot)

    finally:
        await close_browser(session)


async def cmd_audit(url: str, screenshot: bool, headless: bool):
    """
    Full audit — runs Steps 1, 2, 3 sequentially
    and prints step-wise + combined report.
    """
    report = await run_full_audit(url=url, screenshot = screenshot, headless=headless)
    print_audit_report(report)


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

    # --- extract-content command ---
    content_parser = subparsers.add_parser(
        "extract-content",
        help="Step 2: Extract full page content — title, meta, headings, links, buttons, images, forms",
    )
    content_parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="URL to extract content from",
    )
    content_parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser in headful mode",
    )

    # --- extract-accessibility command ---
    a11y_parser = subparsers.add_parser(
        "extract-accessibility",
        help="Step 3: Extract accessibility tree for all interactive elements",
    )
    a11y_parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="URL to extract accessibility tree from",
    )
    a11y_parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser in headful mode",
    )

    # --- audit command ---
    audit_parser = subparsers.add_parser(
        "audit",
        help="Full audit — runs Steps 1, 2, 3 and prints combined report",
    )
    audit_parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="URL to audit",
    )
    audit_parser.add_argument(
        "--screenshot",
        action="store_true",
        help="Save a screenshot to output/audit_screenshot.png",
    )
    audit_parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser in headful mode",
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

    if args.command == "extract-content":
        asyncio.run(cmd_extract_content(
            url=args.url,
            headless=not args.headful,
        ))

    if args.command == "extract-accessibility":
        asyncio.run(cmd_extract_accessibility(
            url=args.url,
            headless=not args.headful,
        ))

    if args.command == "audit":
        asyncio.run(cmd_audit(
            url=args.url,
            screenshot=args.screenshot,
            headless=not args.headful,
        ))

if __name__ == "__main__":
    main()