# core/runner.py

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from playwright.async_api import Page

from core.browser import launch_browser, navigate_to, close_browser, take_screenshot
from core.root_cause import RootCause
from extractors.accessibility import extract_accessibility_tree, AccessibilitySnapshot
from helpers.classify_reruns import classify_reruns, ClassifiedResult
from parser.llm_output_parser import parse_llm_output, ParseResult
from parser.models import ParsedStep, RunResult
from parser.step_runner import run_steps
from stores.run_store import save_run
from utils.logger import log_info, log_success, log_error, log_warning


@dataclass
class TestRunReport:
    """
    Full result of one test execution — single or multiple reruns..
    """
    url: str
    variant: str
    instruction: str | None

    # classification result (wraps all reruns)
    classified: ClassifiedResult

    # accessibility snapshots from last run
    accessibility_initial: AccessibilitySnapshot | None
    accessibility_final: AccessibilitySnapshot | None

    # screenshot on failure
    screenshot_path: str | None

    # db record id after saving
    saved_run_id: str | None = None


async def run_test(
    url: str,
    steps: list[ParsedStep],
    reruns: int = 1,
    variant: str = "original",
    instruction: str | None = None,
    headless: bool = True,
    save_to_db: bool = True,
) -> TestRunReport:
    """
    Main test execution pipeline.
    Launches browser, runs steps N times, classifies result,
    saves to DB and returns a TestRunReport.
    """
    reruns = min(max(1, reruns), 5)

    session = await launch_browser(headless=headless)

    all_results       = []
    accessibility_initial: AccessibilitySnapshot | None = None
    accessibility_final:   AccessibilitySnapshot | None = None
    screenshot_path:       str | None = None

    try:
        for i in range(reruns):
            if reruns > 1:
                log_info(f"Run {i + 1} of {reruns}...")

            # fresh navigation each run
            success = await navigate_to(session.page, url)
            if not success:
                log_error(f"Navigation failed on run {i + 1}.")
                break

            # initial snapshot on first run only
            if i == 0:
                accessibility_initial = await extract_accessibility_tree(session.page)

            # execute steps
            run_result, root_cause = await run_steps(session.page, steps)
            all_results.append((run_result, root_cause))

            # final snapshot from last run
            accessibility_final = await extract_accessibility_tree(session.page)

            # screenshot on failure
            if run_result.status == "failed" and screenshot_path is None:
                screenshot_path = await _capture_screenshot(session.page)

    finally:
        await close_browser(session)

    # classify across all reruns
    if not all_results:
        # navigation failed before any run completed
        from parser.models import RunResult
        from core.root_cause import RootCause

        empty_run = RunResult(
            status="failed",
            total_steps=0,
            passed_steps=0,
            failed_steps=0,
            duration_ms=0,
            steps=[],
        )
        empty_cause = RootCause(
            title="Test failed before execution",
            summary="Browser could not navigate to the target URL.",
            likely_cause="The target app may not be running or the URL is incorrect.",
            recommendation="Check the target URL and ensure the app is running.",
        )
        all_results = [(empty_run, empty_cause)]

    classified = classify_reruns(all_results)

    report = TestRunReport(
        url=url,
        variant=variant,
        instruction=instruction,
        classified=classified,
        accessibility_initial=accessibility_initial,
        accessibility_final=accessibility_final,
        screenshot_path=screenshot_path,
    )

    # save to DB
    if save_to_db:
        report.saved_run_id = await _save_report(report)

    return report


# ── private helpers ────────────────────────────────────────────────────────────

async def _capture_screenshot(page: Page) -> str | None:
    """
    Save a failure screenshot to output/failure_screenshots/.
    Returns the file path or None on failure.
    """
    try:
        os.makedirs("output/failure_screenshots", exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path      = f"output/failure_screenshots/failure_{timestamp}.png"
        await take_screenshot(page, path)
        return path
    except Exception as error:
        log_warning(f"Screenshot failed: {error}")
        return None


async def _save_report(report: TestRunReport) -> str | None:
    """
    Build the run dict shape and save via run_store.save_run().
    Returns the saved run id or None on failure.
    """
    try:
        classified  = report.classified
        last_run    = classified.runs[-1] if classified.runs else None
        root_cause  = classified.root_cause

        run_dict = {
            "status":               classified.status,
            "flaky":                classified.flaky,
            "durationMs":           classified.duration_ms,
            "runCount":             classified.total_runs,
            "healedCount":          _count_healed(classified),
            "wasHealed":            _was_healed(classified),
            "totalCostUsd":         0,
            "variant":              report.variant,
            "instruction":          report.instruction,
            "screenshotPath":       report.screenshot_path,
            "result": {
                "status":           classified.status,
                "startedAt":        datetime.now(timezone.utc).isoformat(),
                "finishedAt":       datetime.now(timezone.utc).isoformat(),
                "runNumber":        classified.total_runs,
                "rootCause": {
                    "title":          root_cause.title,
                    "summary":        root_cause.summary,
                    "likelyCause":    root_cause.likely_cause,
                    "recommendation": root_cause.recommendation,
                    "evidence":       root_cause.evidence,
                } if root_cause else None,
                "accessibilityAudit": {
                    "score":        None,
                    "issueCount":   len(report.accessibility_final.issues)
                                    if report.accessibility_final else 0,
                    "warningCount": 0,
                    "passedCount":  0,
                },
                "steps": [
                    {
                        "name":               f"{s.action} {s.target}",
                        "status":             s.status,
                        "durationMs":         s.duration_ms,
                        "selectorUsed":       s.selector_used,
                        "wasHealed":          s.was_healed,
                        "oldSelector":        s.old_selector,
                        "newSelector":        s.new_selector,
                        "resolutionStrategy": s.resolution_strategy,
                        "confidence":         s.confidence,
                        "estimatedCostUsd":   0,
                    }
                    for s in (last_run.steps if last_run else [])
                ],
                "accessibility": {
                    "initial": _serialize_snapshot(report.accessibility_initial),
                    "final":   _serialize_snapshot(report.accessibility_final),
                },
            },
        }

        saved = await save_run(run_dict)
        log_success(f"Run saved to DB → {saved['id']}")
        return saved["id"]

    except Exception as error:
        log_error(f"Failed to save run to DB: {error}")
        return None


def _count_healed(classified: ClassifiedResult) -> int:
    return sum(
        1
        for run in classified.runs
        for step in run.steps
        if step.was_healed
    )


def _was_healed(classified: ClassifiedResult) -> bool:
    return _count_healed(classified) > 0


def _serialize_snapshot(snapshot: AccessibilitySnapshot | None) -> list:
    if not snapshot:
        return []
    return [
        {
            "role":     node.role,
            "name":     node.name,
            "selector": node.selector,
            "id":       node.element_id,
            "tagName":  node.tag,
        }
        for node in snapshot.nodes
    ]