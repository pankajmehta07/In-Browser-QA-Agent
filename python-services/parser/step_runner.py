import time
from playwright.async_api import Page, expect

from parser.models import ParsedStep, StepExecutionResult, RunResult
from utils.logger import log_info, log_success, log_error, log_warning


# known URL targets for goto action
# extend this dict as more pages are added
GOTO_TARGETS: dict[str, str] = {
    "login":     "Login",
    "dashboard": "Dashboard",
    "settings":  "Settings",
}


async def run_steps(
    page: Page,
    steps: list[ParsedStep],
) -> RunResult:
    """
    Execute a list of ParsedStep objects against a loaded Playwright page.
    Continues on failure — collects all results before returning.
    """
    log_info(f"Running {len(steps)} steps...")

    results: list[StepExecutionResult] = []
    overall_start = time.time()

    for index, step in enumerate(steps, start=1):
        log_info(f"  [{index}/{len(steps)}] {step.action} → {step.target}")
        result = await _execute_step(page, step, index)
        results.append(result)

        if result.status == "passed":
            log_success(f"  Step {index} passed ({result.duration_ms}ms)")
        else:
            log_error(f"  Step {index} failed — {result.error}")

    total_ms = int((time.time() - overall_start) * 1000)
    passed  = [r for r in results if r.status == "passed"]
    failed  = [r for r in results if r.status == "failed"]

    overall_status = "passed" if not failed else "failed"

    if overall_status == "passed":
        log_success(f"All {len(steps)} steps passed ({total_ms}ms)")
    else:
        log_error(f"{len(failed)} of {len(steps)} steps failed ({total_ms}ms)")

    return RunResult(
        status=overall_status,
        total_steps=len(steps),
        passed_steps=len(passed),
        failed_steps=len(failed),
        duration_ms=total_ms,
        steps=results,
    )


# ── private: route each action ─────────────────────────────────────────────────

async def _execute_step(
    page: Page,
    step: ParsedStep,
    step_number: int,
) -> StepExecutionResult:
    """
    Route a single ParsedStep to its handler.
    Always returns a StepExecutionResult — never throws.
    """
    start = time.time()

    try:
        if step.action == "goto":
            extra = await _action_goto(page, step.target)
        elif step.action == "type":
            extra = await _action_type(page, step.target, step.value or "")
        elif step.action == "click":
            extra = await _action_click(page, step.target)
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

async def _action_goto(page: Page, target: str) -> dict:
    """
    Verify the expected page is currently loaded by checking
    for a heading matching the target name.
    Does not navigate — navigation is done by browser.py before steps run.
    """
    normalized = target.strip().lower()
    heading_text = GOTO_TARGETS.get(normalized, target)

    await expect(
        page.get_by_role("heading", name=heading_text)
    ).to_be_visible(timeout=5000)

    return {}


async def _action_type(page: Page, target: str, value: str) -> dict:
    """
    Find a field by its label and fill it with value.
    """
    field = page.get_by_label(target)
    await field.wait_for(state="visible", timeout=5000)
    await field.fill(value)

    selector = f"label={target}"
    return {"selector_used": selector}


async def _action_click(page: Page, target: str) -> dict:
    """
    Click a button by name.
    """
    # tier 1 — exact match
    locator = page.get_by_role("button", name=target)

    try:
        await locator.wait_for(state="visible", timeout=3000)
        await locator.click()

        selector = f'role=button[name="{target}"]'
        return {
            "selector_used":        selector,
            "was_healed":           False,
            "old_selector":         None,
            "new_selector":         selector,
            "resolution_strategy":  "exact_role_match",
            "confidence":           1.0,
        }

    except Exception:
        pass

    # tier 2 — try link role (covers <a> elements)
    link_locator = page.get_by_role("link", name=target)

    try:
        await link_locator.wait_for(state="visible", timeout=3000)
        await link_locator.click()

        selector = f'role=link[name="{target}"]'
        return {
            "selector_used":        selector,
            "was_healed":           False,
            "old_selector":         None,
            "new_selector":         selector,
            "resolution_strategy":  "exact_role_match",
            "confidence":           1.0,
        }

    except Exception:
        pass

    # unresolved
    raise Exception(
        f'Could not find button or link with name "{target}". '
    )


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