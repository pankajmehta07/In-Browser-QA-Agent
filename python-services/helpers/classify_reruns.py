from dataclasses import dataclass, field
from parser.models import RunResult
from core.root_cause import RootCause


@dataclass
class ClassifiedResult:
    status: str                        # passed | failed | flaky
    flaky: bool
    total_runs: int
    passed_runs: int
    failed_runs: int
    duration_ms: int                   # total across all runs
    runs: list[RunResult] = field(default_factory=list)
    root_cause: RootCause | None = None


def classify_reruns(
    run_results: list[tuple[RunResult, RootCause | None]]
) -> ClassifiedResult:
    """
    Analyze multiple runs of the same instruction and classify
    the overall result as passed, failed, or flaky.

    Accepts a list of (RunResult, RootCause | None) tuples
    — same shape that run_steps() returns.
    """
    if not run_results:
        return ClassifiedResult(
            status="failed",
            flaky=False,
            total_runs=0,
            passed_runs=0,
            failed_runs=0,
            duration_ms=0,
            root_cause=RootCause(
                title="No runs provided",
                summary="classify_reruns received an empty list.",
                likely_cause="The runner produced no results.",
                recommendation="Check that the step runner executed at least one run.",
            ),
        )

    just_results = [r for r, _ in run_results]
    statuses     = [r.status for r in just_results]
    unique       = set(statuses)
    total_ms     = sum(r.duration_ms for r in just_results)
    passed_runs  = statuses.count("passed")
    failed_runs  = statuses.count("failed")
    total_runs   = len(statuses)

    # single run — return as-is with its own root cause
    if total_runs == 1:
        run, root_cause = run_results[0]
        return ClassifiedResult(
            status=run.status,
            flaky=False,
            total_runs=1,
            passed_runs=passed_runs,
            failed_runs=failed_runs,
            duration_ms=total_ms,
            runs=just_results,
            root_cause=root_cause,
        )

    # all passed
    if unique == {"passed"}:
        return ClassifiedResult(
            status="passed",
            flaky=False,
            total_runs=total_runs,
            passed_runs=passed_runs,
            failed_runs=failed_runs,
            duration_ms=total_ms,
            runs=just_results,
            root_cause=None,
        )

    # all failed
    if unique == {"failed"}:
        # use root cause from first failed run
        first_failed_cause = next(
            (rc for _, rc in run_results if rc is not None),
            None,
        )
        return ClassifiedResult(
            status="failed",
            flaky=False,
            total_runs=total_runs,
            passed_runs=passed_runs,
            failed_runs=failed_runs,
            duration_ms=total_ms,
            runs=just_results,
            root_cause=first_failed_cause,
        )

    # mixed — flaky
    evidence = ", ".join(
        f"Run {i + 1}: {s}"
        for i, s in enumerate(statuses)
    )

    return ClassifiedResult(
        status="flaky",
        flaky=True,
        total_runs=total_runs,
        passed_runs=passed_runs,
        failed_runs=failed_runs,
        duration_ms=total_ms,
        runs=just_results,
        root_cause=RootCause(
            title="Flaky behaviour detected",
            summary="The same instruction produced mixed pass/fail results across reruns.",
            likely_cause="The test may depend on timing, async UI updates, animations, or nondeterministic app state.",
            recommendation="Stabilize the UI wait condition or add a more reliable assertion before treating this as a regression.",
            evidence=evidence,
        ),
    )