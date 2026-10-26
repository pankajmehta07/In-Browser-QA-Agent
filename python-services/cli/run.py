import asyncio
import argparse
import sys
import os
import re
from urllib.parse import urlsplit

# make sure imports work from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.browser import launch_browser, navigate_to, close_browser, take_screenshot
from core.auditor import run_full_audit

from extractors.page_content import extract_page_content
from extractors.accessibility import extract_accessibility_tree

from parser.llm_output_parser import parse_llm_output
from parser.natural_language import respond_to_instruction
from parser.step_runner import run_steps

from utils.logger import log_step, log_success, log_error, console
from utils.printer import print_page_content, print_accessibility_snapshot, print_audit_report, print_parse_result, print_run_result, print_root_cause
from utils.serializer import serialize_report
from utils.file_writer import generate_filename, save_report_to_file


def extract_instruction_url(instruction: str) -> str | None:
    match = re.search(r"https?://[^\s<>\"]+", instruction, re.IGNORECASE)
    if not match:
        return None

    candidate = match.group(0).rstrip(".,;:!?)]}'\"`")
    parsed = urlsplit(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None

    return candidate


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
            await take_screenshot(session.page, "output/screenshots/screenshot.png")

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


async def cmd_audit(url: str, screenshot: bool, headless: bool, save:bool):
    """
    Full audit — runs Steps 1, 2, 3 sequentially
    and prints step-wise + combined report.
    Optionally saves JSON report with --save.
    """
    report = await run_full_audit(url=url, screenshot = screenshot, headless=headless)
    print_audit_report(report)

    if save:
        filepath = generate_filename(url)
        data     = serialize_report(report)
        save_report_to_file(data, filepath)

async def cmd_parse_llm(input_file: str | None, raw: str | None):
    """
    Parse LLM output from a file or raw string.
    Useful for testing the parser before wiring it to Playwright.
    """
    if input_file:
        try:
            with open(input_file, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            log_error(f"File not found: {input_file}")
            return
    elif raw:
        content = raw
    else:
        log_error("Provide either --file or --raw")
        return

    result = parse_llm_output(content)
    print_parse_result(result)


async def cmd_run_steps(url: str, raw: str | None, input_file: str | None, headless: bool):
    """
    Parse LLM output then execute the steps against a live page.
    """
    # get raw input
    if input_file:
        try:
            with open(input_file, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            log_error(f"File not found: {input_file}")
            return
    elif raw:
        content = raw
    else:
        log_error("Provide either --file or --raw")
        return

    # parse
    parse_result = parse_llm_output(content)
    print_parse_result(parse_result)

    if not parse_result.success or not parse_result.steps:
        log_error("No valid steps to run.")
        return

    # launch browser and navigate
    session = await launch_browser(headless=headless)

    try:
        success = await navigate_to(session.page, url)

        if not success:
            log_error("Navigation failed. Exiting.")
            return

        # run steps
        run_result, root_cause = await run_steps(session.page, parse_result.steps)
        print_run_result(run_result)

        if root_cause:
            print_root_cause(root_cause)

    finally:
        await close_browser(session)


async def process_natural_language_instruction(
    session,
    instruction: str,
    dry_run: bool,
    conversation_history: list[dict[str, str]] | None = None,
):
    """Answer a page question or execute generated QA steps on an open session."""
    snapshot = await extract_accessibility_tree(session.page)
    if not snapshot:
        log_error("Could not extract page context for Groq.")
        return

    try:
        page_title = await session.page.title()
        page_text = await session.page.locator("body").inner_text(timeout=5000)
        response = await respond_to_instruction(
            instruction,
            snapshot,
            page_title,
            page_text,
            conversation_history,
        )
    except Exception as error:
        log_error(f"Groq request failed: {error}")
        return

    if conversation_history is not None and response.history_content:
        conversation_history.extend([
            {"role": "user", "content": instruction},
            {"role": "assistant", "content": response.history_content},
        ])

    if response.kind == "answer":
        console.print("[bold]Answer[/bold]")
        console.print(response.answer or "", markup=False)
        return

    parse_result = parse_llm_output(response.steps_json or "[]")
    print_parse_result(parse_result)

    if not parse_result.success or not parse_result.steps or parse_result.error:
        log_error("No complete, valid QA plan was generated. Nothing was run.")
        return

    if dry_run:
        log_success("Dry run complete. No browser actions were executed.")
        return

    run_result, root_cause = await run_steps(session.page, parse_result.steps)
    print_run_result(run_result)

    if root_cause:
        print_root_cause(root_cause)


async def cmd_run_natural_language(
    url: str,
    instruction: str,
    headless: bool,
    dry_run: bool,
):
    """Run one natural-language instruction in its own browser session."""
    if not os.getenv("GROQ_API_KEY"):
        log_error("GROQ_API_KEY is not set. Add it to .env and recreate the service.")
        return

    session = await launch_browser(headless=headless)
    try:
        if not await navigate_to(session.page, url):
            log_error("Navigation failed. Exiting.")
            return
        await process_natural_language_instruction(session, instruction, dry_run)
    finally:
        await close_browser(session)


async def _run_interactive(url: str):
    """Read instructions against one persistent browser and conversation."""
    if not os.getenv("GROQ_API_KEY"):
        log_error("GROQ_API_KEY is not set. Add it to .env and recreate the service.")
        return

    session = None
    current_url = None
    conversation_history: list[dict[str, str]] = []

    try:
        while True:
            try:
                instruction = input(">>> ").strip()
            except EOFError:
                console.print("\n[dim]End of input. Exiting.[/dim]")
                return

            if not instruction:
                continue

            instruction_url = extract_instruction_url(instruction)
            target_url = instruction_url or current_url or url

            if session is None:
                session = await launch_browser(headless=True)

            should_navigate = current_url is None or (
                instruction_url is not None
                and instruction_url.rstrip("/") != current_url.rstrip("/")
            )
            if should_navigate:
                console.print(f"Navigating to: {target_url}")
                if not await navigate_to(session.page, target_url):
                    log_error("Navigation failed. Enter another instruction or URL to retry.")
                    continue
                current_url = target_url
            else:
                console.print(f"Using current page: {session.page.url}")

            try:
                await process_natural_language_instruction(
                    session,
                    instruction,
                    dry_run=False,
                    conversation_history=conversation_history,
                )
            except Exception as error:
                log_error(f"Instruction failed: {error}")
    finally:
        if session is not None:
            await close_browser(session)


def run_interactive(url: str):
    """Keep one browser session open until the user exits the REPL."""
    console.rule("[step]Natural-Language QA CLI[/step]")
    console.print(f"Default target URL: {url}")
    console.print("Enter a QA instruction. Press Ctrl-C or Ctrl-D to quit.")

    try:
        asyncio.run(_run_interactive(url))
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted. Exiting.[/dim]")


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
        help="Save a screenshot to output/screenshots/screenshot.png",
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
        help="Save a screenshot to output/screenshots/audit_screenshot.png",
    )
    audit_parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser in headful mode",
    )
    audit_parser.add_argument(
        "--save",
        action="store_true",
        help="Save audit report to output/auditFiles/audit_<slug>_<timestamp>.json",
    )

    # --- parse-llm command ---
    parse_parser = subparsers.add_parser(
        "parse-llm",
        help="Parse LLM JSON output into structured steps",
    )
    parse_group = parse_parser.add_mutually_exclusive_group(required=True)
    parse_group.add_argument(
        "--file",
        type=str,
        help="Path to file containing LLM output",
    )
    parse_group.add_argument(
        "--raw",
        type=str,
        help="Raw LLM output string passed directly",
    )

    # --- run-steps command ---
    run_parser = subparsers.add_parser(
        "run-steps",
        help="Parse LLM output and execute steps against a live page",
    )
    run_parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="URL to run steps against",
    )
    run_input = run_parser.add_mutually_exclusive_group(required=True)
    run_input.add_argument(
        "--raw",
        type=str,
        help="Raw LLM output string",
    )
    run_input.add_argument(
        "--file",
        type=str,
        help="Path to file containing LLM output",
    )
    run_parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser in headful mode",
    )

    # --- run-natural-language command ---
    natural_parser = subparsers.add_parser(
        "run-natural-language",
        help="Use Groq to plan and run QA steps from a natural-language instruction",
    )
    natural_parser.add_argument(
        "--url",
        type=str,
        required=True,
        help="URL to inspect and run steps against",
    )
    natural_parser.add_argument(
        "--instruction",
        type=str,
        required=True,
        help="Natural-language QA instruction",
    )
    natural_parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser in headful mode",
    )
    natural_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated plan without executing browser actions",
    )

    return parser


def main():
    parser = build_parser()
    if len(sys.argv) == 1:
        run_interactive(os.getenv("TARGET_APP_URL", "http://127.0.0.1:5173"))
        return

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
            save=args.save,
        ))

    if args.command == "parse-llm":
        asyncio.run(cmd_parse_llm(
            input_file=getattr(args, "file", None),
            raw=getattr(args, "raw", None),
        ))

    if args.command == "run-steps":
        asyncio.run(cmd_run_steps(
            url=args.url,
            raw=getattr(args, "raw", None),
            input_file=getattr(args, "file", None),
            headless=not args.headful,
        ))

    if args.command == "run-natural-language":
        asyncio.run(cmd_run_natural_language(
            url=args.url,
            instruction=args.instruction,
            headless=not args.headful,
            dry_run=args.dry_run,
        ))

if __name__ == "__main__":
    main()