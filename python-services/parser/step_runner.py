import time
from urllib.parse import urlsplit
from playwright.async_api import Page, expect

from parser.models import ParsedStep, StepExecutionResult, RunResult
from utils.logger import log_info, log_success, log_error, log_warning

from core.root_cause import explain_failure, RootCause
from core.resolver import resolve_button, ResolutionResult, find_interactive_locator


# known URL targets for goto action
# extend this dict as more pages are added
GOTO_TARGETS: dict[str, str] = {
    "login":     "Login",
    "dashboard": "Dashboard",
    "settings":  "Settings",
}


class _UnresolvedElementError(Exception):
    """
    Raised when all resolution tiers fail to find an element.
    Carries the target name so _execute_step can mark
    resolution_strategy as 'unresolved' on the result.
    """
    def __init__(self, target: str, message: str):
        super().__init__(message)
        self.target = target


async def run_steps(
    page: Page,
    steps: list[ParsedStep],
    allow_llm_fallback: bool = True,
) -> tuple[RunResult, RootCause | None]:
    """
    Execute a list of ParsedStep objects against a loaded Playwright page.
    Stops execution at the first failed step.
    Returns (RunResult, RootCause | None).
    """
    log_info(f"Running {len(steps)} steps...")

    results: list[StepExecutionResult] = []
    overall_start = time.time()

    for index, step in enumerate(steps, start=1):
        log_info(f"  [{index}/{len(steps)}] {step.action} → {step.target}")
        result = await _execute_step(page, step, index, allow_llm_fallback)
        results.append(result)

        if result.status == "passed":
            log_success(f"  Step {index} passed ({result.duration_ms}ms)")
        else:
            log_error(f"  Step {index} failed — {result.error}")
            
            skipped = len(steps) - len(results)
            if skipped:
                log_warning(
                    f"Stopping execution. {skipped} remaining step(s) skipped."
                )

            break

    total_ms = int((time.time() - overall_start) * 1000)
    passed   = [r for r in results if r.status == "passed"]
    failed   = [r for r in results if r.status == "failed"]

    overall_status = "passed" if not failed else "failed"

    if overall_status == "passed":
        log_success(f"All {len(steps)} steps passed ({total_ms}ms)")
    else:
        log_error(f"{len(failed)} of {len(steps)} steps failed ({total_ms}ms)")

    run_result = RunResult(
        status=overall_status,
        total_steps=len(steps),
        passed_steps=len(passed),
        failed_steps=len(failed),
        duration_ms=total_ms,
        steps=results,
    )

    root_cause = explain_failure(run_result)

    return run_result, root_cause


# ── private: route each action ─────────────────────────────────────────────────

async def _execute_step(
    page: Page,
    step: ParsedStep,
    step_number: int,
    allow_llm_fallback: bool = True,
) -> StepExecutionResult:
    """
    Route a single ParsedStep to its handler.
    Always returns a StepExecutionResult — never throws.
    """
    start = time.time()

    try:
        if step.action == "goto":
            extra = await _action_goto(page, step.target, allow_llm_fallback)
        elif step.action == "type":
            extra = await _action_type(page, step.target, step.value or "")
        elif step.action == "click":
            extra = await _action_click(page, step.target, allow_llm_fallback)
        elif step.action == "check_visible":
            extra = await _action_check_visible(page, step.target)
        elif step.action == "check_contains":
            extra = await _action_check_contains(page, step.target, step.value or "")
        else:
            raise ValueError(f"Unsupported action: {step.action}")

        duration_ms = int((time.time() - start) * 1000)

        return StepExecutionResult(
            step_number=step_number,
            action=step.action,
            target=step.target,
            value=step.value,
            status="passed",
            duration_ms=duration_ms,
            **extra,
        )

    except _UnresolvedElementError as error:
        # element not found after all tiers 
        duration_ms = int((time.time() - start) * 1000)
        return StepExecutionResult(
            step_number=step_number,
            action=step.action,
            target=step.target,
            value=step.value,
            status="failed",
            duration_ms=duration_ms,
            error=str(error),
            resolution_strategy="unresolved",
            confidence=0.0,
            old_selector=f'role=button[name="{step.target}"]',
            new_selector=None,
        )

    except Exception as error:
        duration_ms = int((time.time() - start) * 1000)

        return StepExecutionResult(
            step_number=step_number,
            action=step.action,
            target=step.target,
            value=step.value,
            status="failed",
            duration_ms=duration_ms,
            error=str(error),
        )


# ── action handlers ────────────────────────────────────────────────────────────

async def _action_goto(
    page: Page,
    target: str,
    allow_llm_fallback: bool = True,
) -> dict:
    """Open a URL or activate a named navigation button or link."""
    url = urlsplit(target)
    if url.scheme in ("http", "https") and url.netloc:
        await page.goto(target, wait_until="domcontentloaded")
        return {"selector_used": target}

    normalized = target.strip().lower()
    heading_text = GOTO_TARGETS.get(normalized, target)

    heading = page.get_by_role("heading", name=heading_text, exact=True).first
    if await heading.is_visible():
        return {"selector_used": f'role=heading[name="{heading_text}"]'}
    return await _action_click(page, target, allow_llm_fallback)


async def _action_type(page: Page, target: str, value: str) -> dict:
    """
    Find a field by its label and fill it with value.
    """
    field = page.get_by_label(target)
    await field.wait_for(state="visible", timeout=5000)
    await field.fill(value)

    selector = f"label={target}"
    return {"selector_used": selector}


async def _action_click(
    page: Page,
    target: str,
    allow_llm_fallback: bool = True,
) -> dict:
    """
    Click a button or link using the full resolver pipeline.
    Tier 1 — exact match
    Tier 2 — approved memory
    Tier 3 — similarity
    Tier 4 — LLM stub
    """
    resolution = await resolve_button(page, target, allow_llm_fallback)

    if not resolution.resolved_name:
        raise _UnresolvedElementError(
            target=target,
            message=(
                f'Could not resolve button or link "{target}" '
                f'after {len(resolution.attempts)} tier(s). '
                f'Strategy: {resolution.resolution_strategy}.'
            ),
        )

    locator = await find_interactive_locator(
        page, resolution.resolved_role, resolution.resolved_name
    )
    await locator.click()

    return {
        "selector_used":       resolution.new_selector,
        "was_healed":          resolution.was_healed,
        "old_selector":        resolution.old_selector,
        "new_selector":        resolution.new_selector,
        "resolution_strategy": resolution.resolution_strategy,
        "confidence":          resolution.confidence,
    }


async def _action_check_visible(page: Page, target: str) -> dict:
    """
    Assert that text or a heading matching target is visible on the page.
    """
    # try heading first, fall back to any text
    try:
        await expect(
            page.get_by_role("heading", name=target)
        ).to_be_visible(timeout=5000)
        return {"selector_used": f'role=heading[name="{target}"]'}

    except Exception:
        pass

    await expect(
        page.get_by_text(target)
    ).to_be_visible(timeout=5000)

    return {"selector_used": f'text="{target}"'}


async def _action_check_contains(page: Page, target: str, value: str) -> dict:
    """
    Assert that a field identified by label contains the expected value.
    """
    field = page.get_by_label(target)
    await expect(field).to_have_value(value, timeout=5000)

    return {"selector_used": f"label={target}"}