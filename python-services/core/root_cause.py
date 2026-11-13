from dataclasses import dataclass

from parser.models import StepExecutionResult, RunResult


@dataclass
class RootCause:
    title: str
    summary: str
    likely_cause: str
    recommendation: str
    evidence: str | None = None


def explain_failure(result: RunResult) -> RootCause | None:
    """
    Analyze a RunResult and return a human-readable RootCause
    explaining why it failed.
    Returns None if the run passed.
    """
    if result.status != "failed":
        return None

    # find first failed step
    failed_step = next(
        (step for step in result.steps if step.status == "failed"),
        None,
    )

    # case 1 — no steps were recorded at all
    if not failed_step:
        return RootCause(
            title="Test failed before step logging",
            summary="The test failed before the runner could record a specific failed step.",
            likely_cause="The browser failed to launch, the URL was unreachable, or an unhandled exception occurred before execution started.",
            recommendation="Check that the target URL is reachable and the browser launched correctly.",
            evidence=None,
        )

    # case 2 — button/element could not be resolved
    if failed_step.resolution_strategy == "unresolved":
        attempted = _format_resolution_attempts(failed_step)
        target    = _extract_target(failed_step)

        return RootCause(
            title="Element could not be resolved",
            summary=f'The runner could not find a reliable match for "{target}".',
            likely_cause="The expected UI element may have been renamed, removed, hidden, or changed too much for the available resolver tiers.",
            recommendation="Check the target page manually. If the UI change is intentional, update the instruction or approve a healed selector.",
            evidence=attempted,
        )

    # case 3 — assertion failed (check_visible or check_contains)
    if failed_step.action in ("check_visible", "check_contains"):
        return RootCause(
            title="Assertion failed",
            summary=f'The test reached the page but this check failed: "{failed_step.action} → {failed_step.target}".',
            likely_cause="The expected text or field value was not visible or did not match the instruction.",
            recommendation="Confirm whether the app behaviour changed or the test expectation is outdated.",
            evidence=failed_step.error,
        )

    # case 4 — generic step failure
    return RootCause(
        title="Step execution failed",
        summary=f'The test failed while running: "{failed_step.action} → {failed_step.target}".',
        likely_cause="The page did not match the expected state for this action.",
        recommendation="Review the failed step, selector details, and accessibility snapshot.",
        evidence=failed_step.error,
    )


# ── private helpers ────────────────────────────────────────────────────────────

def _extract_target(step: StepExecutionResult) -> str:
    return step.target or "unknown"


def _format_resolution_attempts(step: StepExecutionResult) -> str | None:
    """
    Format a human readable summary of what resolution
    strategies were attempted before giving up.
    """
    parts = []

    if step.resolution_strategy:
        parts.append(f"Last strategy attempted: {step.resolution_strategy}")

    if step.confidence is not None:
        parts.append(f"Best confidence score: {step.confidence:.2f}")

    if step.selector_used:
        parts.append(f"Selector tried: {step.selector_used}")

    if step.error:
        parts.append(f"Error: {step.error}")

    return " | ".join(parts) if parts else None