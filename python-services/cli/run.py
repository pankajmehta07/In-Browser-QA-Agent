import asyncio
import argparse
import sys
import os
import re
from dataclasses import asdict
from urllib.parse import urlsplit

# make sure imports work from project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.browser import launch_browser, navigate_to, close_browser, take_screenshot
from core.auditor import run_full_audit
from core.page_monitor import PageMonitor, PageState, collect_invalid_fields, diff_page_states
from core.runner import run_test, TestRunReport

from extractors.page_content import extract_page_content
from extractors.accessibility import extract_accessibility_tree

from parser.llm_output_parser import parse_llm_output
from parser.llm_client import PROVIDERS, set_provider
from parser.natural_language import respond_to_instruction
from parser.step_runner import run_steps

from utils.logger import log_step, log_success, log_error, log_info, log_warning, console
from utils.printer import print_page_content, print_accessibility_snapshot, print_audit_report, print_parse_result, print_run_result, print_root_cause, print_classified_result
from utils.serializer import serialize_report
from utils.file_writer import generate_filename, save_report_to_file

from helpers.classify_reruns import classify_reruns


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


async def cmd_run_steps(
    url: str,
    raw: str | None,
    input_file: str | None,
    headless: bool,
    reruns: int,
):
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

    report = await run_test(
        url=url,
        steps=parse_result.steps,
        reruns=reruns,
        headless=headless,
        instruction=content,
    )

    # print results
    if report.classified.total_runs == 1:
        run_result = report.classified.runs[0]
        root_cause = report.classified.root_cause
        print_run_result(run_result)
        if root_cause:
            print_root_cause(root_cause)
    else:
        print_classified_result(report.classified)

    if report.saved_run_id:
        log_success(f"Saved to DB → {report.saved_run_id}")


async def process_natural_language_instruction(
    session,
    instruction: str,
    dry_run: bool,
    conversation_history: list[dict[str, str]] | None = None,
    session_state: dict | None = None,
):
    """Observe, act, and replan toward a question or QA goal on an open session."""
    max_actions = 8
    session_state = session_state if session_state is not None else {}
    evidence: dict[str, dict] = session_state.setdefault("evidence", {})
    session_actions: list[dict] = session_state.setdefault("actions", [])
    action_history: list[dict] = []
    attempted_actions: set[tuple] = set()
    known_urls = set(evidence) | {session.page.url}
    explicit_url = extract_instruction_url(instruction)
    if explicit_url:
        known_urls.add(explicit_url)
    feedback = None
    # research_only = False
    monitor = session_state.get("monitor")
    if monitor is None or monitor.page is not session.page:
        monitor = session_state["monitor"] = PageMonitor(session.page)

    for _ in range(max_actions + 1):
        snapshot = await extract_accessibility_tree(session.page)
        if not snapshot:
            log_error("Could not extract page context for the LLM.")
            return

        try:
            page_title = await session.page.title()
            page_text = await session.page.locator("body").inner_text(timeout=5000)
        except Exception as error:
            log_warning(f"Could not read page text; asking the LLM to replan with the browser error: {error}")
            page_title, page_text = "", ""
            feedback = " ".join(filter(None, [
                feedback,
                f"Reading the current page failed with this browser error: {_clean_browser_error(error)}. "
                "Page text is unavailable for this step; rely on the interactive elements, wait_for_change, "
                "or finish honestly.",
            ]))

        try:
            evidence[session.page.url] = {
                "url": session.page.url,
                "title": page_title,
                "text": page_text[:8000],
            }
            known_urls.add(session.page.url)
            known_urls.update(
                node.href for node in snapshot.nodes
                if node.href and node.href.startswith(("http://", "https://"))
            )
            agent_context = {
                "remaining_actions": max_actions - len(action_history),
                "visited_urls": list(evidence),
                "previous_pages": [
                    page for url, page in evidence.items() if url != session.page.url
                ][-5:],
                "actions": session_actions[-8:],
                "browser_events_since_last_action": monitor.drain(),
                "feedback": feedback,
            }
            response, _ = await respond_to_instruction(
                instruction, snapshot, page_title, page_text,
                (conversation_history or [])[-12:], agent_context,
            )
        except Exception as error:
            log_error(f"Could not interpret the instruction: {error}")
            return

        if response.kind in ("answer", "done"):
            if any(url not in evidence for url in response.sources):
                feedback = "The proposed answer cited an unvisited page. Use only observed supporting evidence."
                continue
            if response.kind == "answer" and len(evidence) > 1 and not response.sources:
                feedback = "Include the visited supporting page URLs in sources for this multi-page answer."
                continue
            if conversation_history is not None and response.history_content:
                conversation_history.extend([
                    {"role": "user", "content": instruction},
                    {"role": "assistant", "content": response.history_content},
                ])
            console.print("[bold]Answer[/bold]" if response.kind == "answer" else "[bold]Outcome[/bold]")
            console.print(response.answer or "", markup=False)
            if response.kind == "answer":
                for url in dict.fromkeys(response.sources or [session.page.url]):
                    console.print(f"Source: {url}", markup=False)
            return

        if response.kind == "browse":
            # research_only = True
            log_info("Agent is navigating to the next page...")
        # if research_only and response.kind == "test":
        #     feedback = "This is a read-only research task. Choose an observed link URL or provide a final factual answer."
        #     continue

        parse_result = parse_llm_output(response.steps_json or "[]")
        if not parse_result.success or not parse_result.steps or parse_result.error:
            feedback = "No complete valid action plan was generated. Choose supported actions or finish honestly."
            continue
        if len(parse_result.steps) > max_actions - len(action_history):
            feedback = "The action plan exceeds the remaining action budget. Return a shorter page-local plan."
            continue
        if response.kind == "browse" and (
            len(parse_result.steps) != 1 or parse_result.steps[0].action != "goto"
        ):
            feedback = "Read-only research permits exactly one navigation action at a time."
            continue

        if dry_run:
            print_parse_result(parse_result)
            log_success("Dry run complete. No browser actions were executed.")
            return

        page_changed = False
        plan_failed = False
        events_seen = False
        navigated = False
        state_before = PageState(session.page.url, page_title, page_text, snapshot)
        for step in parse_result.steps:
            target_url = urlsplit(step.target)
            if step.action == "goto" and target_url.scheme:
                if target_url.scheme not in ("http", "https") or step.target not in known_urls:
                    feedback = "Navigation rejected: use an exact observed HTTP(S) link URL or a user-provided URL."
                    plan_failed = True
                    break
            if response.kind == "browse" and (
                step.target not in known_urls or target_url.scheme not in ("http", "https")
            ):
                feedback = "Research permits only read-only navigation to an observed HTTP(S) URL."
                plan_failed = True
                break

            url_before = session.page.url
            fingerprint = (url_before, step.action, step.target, step.value)
            if fingerprint in attempted_actions and step.action != "wait_for_change":
                feedback = "That action was already attempted on this page. Choose another observed route or finish honestly."
                plan_failed = True
                break
            attempted_actions.add(fingerprint)

            log_info(f"Agent action {len(action_history) + 1}/{max_actions}: {step.action} {step.target}")
            run_result, root_cause = await run_steps(
                session.page, [step], allow_llm_fallback=False,
            )
            await monitor.settle()
            print_run_result(run_result)

            observation: dict = {"browser_events": monitor.drain()}
            if session.page.url == url_before:
                state_after = await _capture_page_state(session.page)
                if state_after is not None:
                    observation["page_changes"] = diff_page_states(state_before, state_after)
                    state_before = state_after
                    evidence[session.page.url] = {
                        "url": state_after.url,
                        "title": state_after.title,
                        "text": state_after.text[:8000],
                    }
                # Native validation bubbles are not in the DOM, so report field validity after clicks.
                if step.action == "click":
                    observation["invalid_fields"] = await collect_invalid_fields(session.page)
            observation = {key: value for key, value in observation.items() if value}
            if observation:
                _log_observation(observation)

            action_record = {
                "url_before": url_before,
                "url_after": session.page.url,
                "result": asdict(run_result.steps[0]),
            }
            if action_record["result"].get("error"):
                action_record["result"]["error"] = _clean_browser_error(action_record["result"]["error"])
            if observation:
                action_record["observation"] = observation
            action_history.append(action_record)
            session_actions.append(action_record)
            del session_actions[:-8]

            if root_cause:
                print_root_cause(root_cause)
            if run_result.status != "passed":
                failed = run_result.steps[0]
                log_info("Sending the browser error to the LLM to replan.")
                feedback = (
                    f"The last action ({failed.action} {failed.target!r}) failed with this browser error: "
                    f"{_clean_browser_error(failed.error or 'unknown error')}. Replan from the fresh page evidence "
                    "and do not repeat the identical action. If the error lists several matching elements "
                    "(strict mode violation), retarget the intended one by its exact, distinguishing accessible "
                    "name (for example the field 'Your password' rather than the shared word 'Password'). If "
                    "the element is missing, hidden, or disabled, choose another observed control, wait_for_change, "
                    "or finish with done explaining the failure."
                )
                plan_failed = True
                break

            if session.page.url != url_before:
                feedback = "Navigation completed. Inspect the destination page before planning further actions."
                page_changed = True
                navigated = True
                break

            if observation.get("page_changes") or observation.get("invalid_fields"):
                page_changed = True
            if observation.get("browser_events"):
                events_seen = True

        ended_with_assertion = bool(action_history) and action_history[-1]["result"]["action"] in (
            "check_visible", "check_contains",
        )
        needs_verification = (
            response.kind == "test" and not (plan_failed or navigated)
            and (page_changed or events_seen or not ended_with_assertion)
        )
        if needs_verification:
            if page_changed or events_seen:
                feedback = (
                    "The executed actions changed the page, flagged invalid fields, or produced browser events; "
                    "see actions[].observation. Verify the outcome against that evidence. If a result is still "
                    "pending (for example a 'Sending...' or loading state), use wait_for_change; otherwise finish "
                    "with done and report the success message, validation errors, alerts, or console/network "
                    "errors observed."
                )
            else:
                feedback = (
                    "The actions completed without any observable page change, invalid fields, or browser events, "
                    "and the plan did not assert an outcome. If a response is expected, use wait_for_change or "
                    "check_visible to verify it; otherwise finish with done stating that no visible response "
                    "was observed."
                )
        if page_changed or plan_failed or events_seen or needs_verification:
            continue
        if response.kind == "browse":
            log_warning("Navigation did not change the page; stopping to avoid repeating the same request.")
            return

        completed_actions = "; ".join(
            f"{item['result']['action']} {item['result']['target']}"
            for item in action_history
        )
        outcome = f"Page-local action plan completed: {completed_actions}."
        console.print("[bold]Outcome[/bold]")
        console.print(outcome, markup=False)
        if conversation_history is not None and response.history_content:
            conversation_history.extend([
                {"role": "user", "content": instruction},
                {"role": "assistant", "content": response.history_content},
            ])
        return

    log_warning("Agent stopped at its planning limit without a final answer or outcome. The task may be incomplete.")
    console.print(f"Last page: {session.page.url}", markup=False)


def _clean_browser_error(error) -> str:
    # Playwright appends a verbose call log; the message and matched-element list precede it.
    return str(error).split("Call log:", 1)[0].strip()[:1500]


async def _capture_page_state(page) -> PageState | None:
    try:
        snapshot = await extract_accessibility_tree(page)
        title = await page.title()
        text = await page.locator("body").inner_text(timeout=5000)
    except Exception as error:
        log_warning(f"Could not read page state after the action: {error}")
        return None
    return PageState(page.url, title, text, snapshot)


def _log_observation(observation: dict):
    changes = observation.get("page_changes", {})
    for item in changes.get("elements_changed", []):
        details = ", ".join(
            f"{field}: {item[field]['from']!r} -> {item[field]['to']!r}"
            for field in ("name", "disabled", "visible") if field in item
        )
        log_info(f"Observed {item['role']} '{item['name']}' change ({details})")
    for line in changes.get("text_added", []):
        log_info(f"Observed new text: {line}")
    for field in observation.get("invalid_fields", []):
        log_info(f"Observed invalid field '{field['field']}': {field['message']}")
    for event in observation.get("browser_events", []):
        detail = event.get("text") or f"{event.get('method')} {event.get('url')} {event.get('status') or event.get('error') or ''}"
        log_info(f"Observed {event['type']}: {detail}")


async def cmd_run_natural_language(
    url: str,
    instruction: str,
    headless: bool,
    dry_run: bool,
):
    """Run one natural-language instruction in its own browser session."""
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
    session = None
    current_url = None
    conversation_history: list[dict[str, str]] = []
    session_state: dict = {"evidence": {}, "actions": []}

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
                    session_state=session_state,
                )
                current_url = session.page.url
            except Exception as error:
                log_error(f"Instruction failed: {error}")
    finally:
        if session is not None:
            await close_browser(session)


def select_provider_or_exit(name: str):
    try:
        provider = set_provider(name)
    except RuntimeError as error:
        log_error(str(error))
        sys.exit(1)
    log_info(f"Using {provider.label} ({provider.model}).")


def prompt_for_provider() -> str:
    names = list(PROVIDERS)
    console.print("Choose an LLM provider:")
    for index, name in enumerate(names, start=1):
        console.print(f"  {index}. {PROVIDERS[name].label} [dim]({name})[/dim]")
    while True:
        try:
            choice = input("Provider: ").strip().lower()
        except EOFError:
            console.print("\n[dim]End of input. Exiting.[/dim]")
            sys.exit(0)
        if choice.isdigit() and 1 <= int(choice) <= len(names):
            return names[int(choice) - 1]
        if choice in PROVIDERS:
            return choice
        console.print(f"Enter 1-{len(names)} or one of: {', '.join(names)}.")


def run_interactive(url: str):
    """Keep one browser session open until the user exits the REPL."""
    console.rule("[step]Natural-Language QA CLI[/step]")
    try:
        select_provider_or_exit(prompt_for_provider())
    except KeyboardInterrupt:
        console.print("\n[dim]Interrupted. Exiting.[/dim]")
        return
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
    run_parser.add_argument(
        "--reruns",
        type=int,
        default=1,
        help="Number of times to run the steps (default: 1, max: 5)",
    )

    # --- run-natural-language command ---
    natural_parser = subparsers.add_parser(
        "run-natural-language",
        help="Use an LLM to plan and run QA steps from a natural-language instruction",
    )
    natural_parser.add_argument(
        "--provider",
        choices=list(PROVIDERS),
        default=os.getenv("LLM_PROVIDER", "groq"),
        help="LLM provider free tier to use (default: $LLM_PROVIDER or groq)",
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
            reruns=min(max(1, args.reruns), 5),
        ))

    if args.command == "run-natural-language":
        select_provider_or_exit(args.provider)
        asyncio.run(cmd_run_natural_language(
            url=args.url,
            instruction=args.instruction,
            headless=not args.headful,
            dry_run=args.dry_run,
        ))

if __name__ == "__main__":
    main()