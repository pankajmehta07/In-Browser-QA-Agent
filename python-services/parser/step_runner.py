import time
from playwright.async_api import Page, expect

from parser.models import ParsedStep, StepExecutionResult, RunResult
from utils.logger import log_info, log_success, log_error, log_warning

from core.root_cause import explain_failure, RootCause
from core.resolver import resolve_button, ResolutionResult


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
) -> tuple[RunResult, RootCause | None]:
    """
    Execute a list of ParsedStep objects against a loaded Playwright page.
    Returns (RunResult, RootCause | None).
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
        elif step.action == "scroll_to":
            extra = await _action_scroll_to(page, step.target)
        elif step.action == "scroll_down":
            extra = await _action_scroll_down(page, step.value or "300")
        elif step.action == "wait_for_element":
            extra = await _action_wait_for_element(page, step.target)
        elif step.action == "wait_seconds":
            extra = await _action_wait_seconds(page, step.value or "1")
        elif step.action == "hover":
            extra = await _action_hover(page, step.target)
        elif step.action == "press_key":
            extra = await _action_press_key(page, step.target, step.value or "Enter")
        elif step.action == "select_option":
            extra = await _action_select_option(page, step.target, step.value or "")
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
    Click a button using the full resolver pipeline.
    Tier 1 — exact match
    Tier 2 — approved memory
    Tier 3 — similarity
    Tier 4 — LLM stub
    """
    resolution = await resolve_button(page, target)

    if not resolution.resolved_name:
        raise _UnresolvedElementError(
            target=target,
            message=(
                f'Could not resolve button "{target}" '
                f'after {len(resolution.attempts)} tier(s). '
                f'Strategy: {resolution.resolution_strategy}.'
            ),
        )

    locator = page.get_by_role("button", name=resolution.resolved_name)
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


async def _action_scroll_to(page: Page, target: str) -> dict:
    """
    Scroll a specific element into view by its label, text or role.
    Tries label first, falls back to text match.
    """
    try:
        locator = page.get_by_label(target)
        await locator.scroll_into_view_if_needed(timeout=3000)
        return {"selector_used": f"label={target}"}
    except Exception:
        pass

    locator = page.get_by_text(target)
    await locator.first.scroll_into_view_if_needed(timeout=3000)
    return {"selector_used": f"text={target}"}


async def _action_scroll_down(page: Page, pixels: str) -> dict:
    """
    Scroll the page down by a fixed number of pixels.
    value field is the pixel amount as a string.
    """
    try:
        amount = int(pixels)
    except ValueError:
        amount = 300

    await page.evaluate(f"window.scrollBy(0, {amount})")
    return {"selector_used": f"window.scrollBy(0, {amount})"}


async def _action_wait_for_element(page: Page, target: str) -> dict:
    """
    Wait until an element matching target is visible.
    Tries role=button, then role=heading, then text.
    """
    try:
        locator = page.get_by_role("button", name=target)
        await locator.wait_for(state="visible", timeout=10000)
        return {"selector_used": f'role=button[name="{target}"]'}
    except Exception:
        pass

    try:
        locator = page.get_by_role("heading", name=target)
        await locator.wait_for(state="visible", timeout=10000)
        return {"selector_used": f'role=heading[name="{target}"]'}
    except Exception:
        pass

    locator = page.get_by_text(target)
    await locator.first.wait_for(state="visible", timeout=10000)
    return {"selector_used": f'text="{target}"'}


async def _action_wait_seconds(page: Page, seconds: str) -> dict:
    """
    Wait for a fixed number of seconds.
    value field is the number of seconds as a string.
    Capped at 10 seconds.
    """
    try:
        amount = float(seconds)
    except ValueError:
        amount = 1.0

    amount = min(amount, 10.0)
    await page.wait_for_timeout(amount * 1000)
    return {"selector_used": f"wait {amount}s"}


async def _action_hover(page: Page, target: str) -> dict:
    """
    Hover over a button, link or text element.
    Tries button role first, then link, then text.
    """
    try:
        locator = page.get_by_role("button", name=target)
        await locator.wait_for(state="visible", timeout=3000)
        await locator.hover()
        return {"selector_used": f'role=button[name="{target}"]'}
    except Exception:
        pass

    try:
        locator = page.get_by_role("link", name=target)
        await locator.wait_for(state="visible", timeout=3000)
        await locator.hover()
        return {"selector_used": f'role=link[name="{target}"]'}
    except Exception:
        pass

    locator = page.get_by_text(target)
    await locator.first.hover()
    return {"selector_used": f'text="{target}"'}


# supported keys map — normalizes common names to Playwright key strings
_KEY_MAP: dict[str, str] = {
    "enter":     "Enter",
    "tab":       "Tab",
    "escape":    "Escape",
    "esc":       "Escape",
    "backspace": "Backspace",
    "delete":    "Delete",
    "arrowup":   "ArrowUp",
    "arrowdown": "ArrowDown",
    "arrowleft": "ArrowLeft",
    "arrowright":"ArrowRight",
    "space":     "Space",
    "home":      "Home",
    "end":       "End",
    "pageup":    "PageUp",
    "pagedown":  "PageDown",
}


async def _action_press_key(page: Page, target: str, key: str) -> dict:
    """
    Press a keyboard key on a specific element or the page.
    target is the element label/name.
    value is the key name (Enter, Tab, Escape etc).

    If target is "page" press on the whole page.
    """
    normalized_key = _KEY_MAP.get(key.strip().lower(), key.strip())

    if target.strip().lower() == "page":
        await page.keyboard.press(normalized_key)
        return {"selector_used": f"keyboard.press({normalized_key})"}

    try:
        locator = page.get_by_label(target)
        await locator.wait_for(state="visible", timeout=3000)
        await locator.press(normalized_key)
        return {"selector_used": f"label={target}"}
    except Exception:
        pass

    locator = page.get_by_role("button", name=target)
    await locator.wait_for(state="visible", timeout=3000)
    await locator.press(normalized_key)
    return {"selector_used": f'role=button[name="{target}"]'}


async def _action_select_option(page: Page, target: str, value: str) -> dict:
    """
    Select an option from a dropdown by its label.
    target is the label of the select element.
    value is the option text or value to select.
    """
    locator = page.get_by_label(target)
    await locator.wait_for(state="visible", timeout=5000)

    # try by label text first, fall back to value attribute
    try:
        await locator.select_option(label=value)
        return {"selector_used": f"label={target} → option label={value}"}
    except Exception:
        pass

    await locator.select_option(value=value)
    return {"selector_used": f"label={target} → option value={value}"}