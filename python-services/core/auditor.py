from dataclasses import dataclass, field
from playwright.async_api import Page

from core.browser import (
    launch_browser,
    navigate_to,
    take_screenshot,
    close_browser,
    BrowserSession,
)
from extractors.page_content import extract_page_content, PageContent
from extractors.accessibility import extract_accessibility_tree, AccessibilitySnapshot
from utils.logger import log_step, log_error, log_success, log_info


@dataclass
class StepResult:
    step: int
    name: str
    status: str           # passed | failed
    duration_ms: int
    error: str | None = None


@dataclass
class AuditReport:
    url: str
    screenshot_path: str | None

    # step results
    steps: list[StepResult] = field(default_factory=list)

    # extracted data
    content: PageContent | None = None
    accessibility: AccessibilitySnapshot | None = None

    # combined health score
    health_score: int = 0
    health_breakdown: dict = field(default_factory=dict)

    # combined issues across all steps
    all_issues: list[str] = field(default_factory=list)

    # overall status
    status: str = "passed"   # passed | failed | partial


async def run_full_audit(url: str, screenshot: bool = False, headless: bool = True) -> AuditReport:
    """
    Runs all three steps sequentially:
      Step 1 — Browser launch + navigation + screenshot
      Step 2 — Page content extraction
      Step 3 — Accessibility tree extraction
    Returns a full AuditReport with per-step and combined results.
    """
    import time

    report = AuditReport(url=url, screenshot_path=None)
    session: BrowserSession | None = None

    # ── Step 1: Browser + Navigation ─────────────────────────────────────

    step1_start = time.time()
    log_step(1, "Launching browser and navigating to page...")

    try:
        session = await launch_browser(headless=headless)

        success = await navigate_to(session.page, url)

        if not success:
            raise Exception(f"Failed to navigate to {url}")

        if screenshot:
            # take screenshot as part of step 1

            import os
            os.makedirs("output", exist_ok=True)
            screenshot_path = "output/screenshots/audit_screenshot.png"
            await take_screenshot(session.page, screenshot_path)
            report.screenshot_path = screenshot_path

        step1_ms = int((time.time() - step1_start) * 1000)
        report.steps.append(StepResult(
            step=1,
            name="Browser launch + navigation",
            status="passed",
            duration_ms=step1_ms,
        ))
        log_success(f"Step 1 complete ({step1_ms}ms)")

    except Exception as error:
        step1_ms = int((time.time() - step1_start) * 1000)
        report.steps.append(StepResult(
            step=1,
            name="Browser launch + navigation",
            status="failed",
            duration_ms=step1_ms,
            error=str(error),
        ))
        report.status = "failed"
        log_error(f"Step 1 failed: {error}")

        if session:
            await close_browser(session)
        return report

    # ── Step 2: Page Content ──────────────────────────────────────────────

    step2_start = time.time()
    log_step(2, "Extracting page content...")

    try:
        content = await extract_page_content(session.page)

        if not content:
            raise Exception("Content extraction returned None")

        report.content = content

        step2_ms = int((time.time() - step2_start) * 1000)
        report.steps.append(StepResult(
            step=2,
            name="Page content extraction",
            status="passed",
            duration_ms=step2_ms,
        ))
        log_success(f"Step 2 complete ({step2_ms}ms)")

    except Exception as error:
        step2_ms = int((time.time() - step2_start) * 1000)
        report.steps.append(StepResult(
            step=2,
            name="Page content extraction",
            status="failed",
            duration_ms=step2_ms,
            error=str(error),
        ))
        report.status = "partial"
        log_error(f"Step 2 failed: {error}")

    # ── Step 3: Accessibility Tree ────────────────────────────────────────

    step3_start = time.time()
    log_step(3, "Extracting accessibility tree...")

    try:
        accessibility = await extract_accessibility_tree(session.page)

        if not accessibility:
            raise Exception("Accessibility extraction returned None")

        report.accessibility = accessibility
        report.all_issues.extend(accessibility.issues)

        step3_ms = int((time.time() - step3_start) * 1000)
        report.steps.append(StepResult(
            step=3,
            name="Accessibility tree extraction",
            status="passed",
            duration_ms=step3_ms,
        ))
        log_success(f"Step 3 complete ({step3_ms}ms)")

    except Exception as error:
        step3_ms = int((time.time() - step3_start) * 1000)
        report.steps.append(StepResult(
            step=3,
            name="Accessibility tree extraction",
            status="failed",
            duration_ms=step3_ms,
            error=str(error),
        ))
        report.status = "partial"
        log_error(f"Step 3 failed: {error}")

    # ── Combined Health Score ─────────────────────────────────────────────

    report.health_score, report.health_breakdown = _calculate_health_score(report)

    # ── Final Status ──────────────────────────────────────────────────────

    if report.status != "failed" and report.status != "partial":
        failed_steps = [s for s in report.steps if s.status == "failed"]
        if failed_steps:
            report.status = "partial"

    await close_browser(session)
    return report


def _calculate_health_score(report: AuditReport) -> tuple[int, dict]:
    """
    Calculate an overall page health score out of 100.

    Breakdown:
      - Navigation success:        20 points
      - Content completeness:      30 points
      - Accessibility cleanliness: 50 points
    """
    score = 0
    breakdown = {}

    # navigation (20pts)
    nav_step = next((s for s in report.steps if s.step == 1), None)
    nav_score = 20 if nav_step and nav_step.status == "passed" else 0
    breakdown["navigation"] = nav_score
    score += nav_score

    # content completeness (30pts)
    content_score = 0
    if report.content:
        if report.content.title:
            content_score += 6
        if report.content.meta.description:
            content_score += 6
        if report.content.headings:
            content_score += 6
        if report.content.links:
            content_score += 6
        if report.content.buttons or report.content.forms:
            content_score += 6

    breakdown["content"] = content_score
    score += content_score

    # accessibility (50pts)
    a11y_score = 50
    if report.accessibility:
        issue_count = len(report.accessibility.issues)
        # each issue costs 10 points, minimum 0
        a11y_score = max(0, 50 - (issue_count * 10))
    elif not report.accessibility:
        a11y_score = 0

    breakdown["accessibility"] = a11y_score
    score += a11y_score

    return score, breakdown