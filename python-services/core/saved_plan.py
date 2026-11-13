"""Explicit saved-plan execution, isolated from the legacy instruction pipeline."""

import re
import time
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from core.browser import close_browser, launch_browser, navigate_to
from parser.models import ParsedStep
from parser.step_runner import run_steps
from parser.test_plan import TestPlan
from stores.run_store import save_run
from stores.test_store import get_test_by_id, list_test_revisions


class SavedPlanNotFound(LookupError):
    pass


class PlanPersistenceError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedPlan:
    test_id: str
    revision: int
    snapshot: dict
    plan: TestPlan


def _origin(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("The configured target must be an HTTP(S) URL without credentials")
    return parsed.scheme, parsed.hostname.lower(), parsed.port or (443 if parsed.scheme == "https" else 80)


async def execute_plan(page, plan: TestPlan, *, expected_origin=None):
    started = time.perf_counter()
    steps, phases = [], {}
    root_cause = None
    setup_failed = False
    for phase, configured in (("setup", plan.setup), ("test", plan.steps), ("cleanup", plan.cleanup)):
        info = {"status": "passed" if configured else "not_configured", "configured_steps": len(configured), "executed_steps": 0}
        phases[phase] = info
        if phase == "test" and setup_failed:
            info["status"] = "skipped"
            continue
        for number, step in enumerate(configured, 1):
            entry = {"phase": phase, "phase_step": number, "action": step.action,
                     "target": step.target, "status": "failed", "duration_ms": 0}
            try:
                if expected_origin is not None and _origin(page.url) != expected_origin:
                    raise ValueError("The page left the configured origin; no further action was performed")
                result, cause = await run_steps(page, [ParsedStep(step.action, step.target, step.value)])
                if not result.steps:
                    raise RuntimeError("The step runner returned no result")
                entry.update(asdict(result.steps[0]))
                if result.status == "failed" and root_cause is None and cause:
                    root_cause = {"title": cause.title, "summary": cause.summary,
                                  "likelyCause": cause.likely_cause, "recommendation": cause.recommendation,
                                  "evidence": cause.evidence}
                if expected_origin is not None and _origin(page.url) != expected_origin:
                    entry.update(status="failed", error="The page left the configured origin")
            except Exception:
                entry.update(status="failed", error="Step could not complete within the configured page scope")
            entry["step_number"] = len(steps) + 1
            steps.append(entry)
            info["executed_steps"] += 1
            if entry["status"] != "passed":
                info["status"] = "failed"
                break
        if phase == "setup":
            setup_failed = info["status"] == "failed"
    return {"status": "failed" if any(info["status"] == "failed" for info in phases.values()) else "passed",
            "steps": steps, "phases": phases, "rootCause": root_cause,
            "duration_ms": int((time.perf_counter() - started) * 1000)}


async def prepare_saved_plan(test_id, revision):
    """Load and validate a pinned definition without performing browser actions."""
    if type(revision) is not int or revision < 1:
        raise ValueError("Choose a positive saved revision")
    if not await get_test_by_id(test_id):
        raise SavedPlanNotFound("Saved test not found")
    history = await list_test_revisions(test_id)
    selected = next((item for item in history if item["revision"] == revision), None)
    if selected is None:
        raise SavedPlanNotFound("Saved test revision not found")
    snapshot = deepcopy(selected["snapshot"])
    if not snapshot.get("plan"):
        raise ValueError("This revision has no structured plan; save a reviewed plan first")
    if snapshot.get("variant", "original") != "original" or snapshot.get("reruns", 1) != 1:
        raise ValueError("Saved-plan execution currently requires original variant and one run")
    plan = TestPlan.model_validate(snapshot["plan"])
    for step in [*plan.setup, *plan.steps, *plan.cleanup]:
        if any(re.search(r"\{\{.*?\}\}", value) for value in (step.target, step.value) if isinstance(value, str)):
            raise ValueError("Resolve test-data placeholders before executing this plan")
    return PreparedPlan(test_id, revision, snapshot, plan)


async def execute_saved_plan(test_id, revision, url):
    """Caller must authorize execution and supply an operator-approved target."""
    _origin(url)
    prepared = await prepare_saved_plan(test_id, revision)
    return await execute_prepared_plan(prepared, url)


async def execute_prepared_plan(prepared: PreparedPlan, url):
    """Execute a previously validated snapshot; internal callers must authorize it."""
    origin = _origin(url)
    test_id, revision, snapshot, plan = prepared.test_id, prepared.revision, prepared.snapshot, prepared.plan
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    session = await launch_browser(headless=True)
    try:
        if await navigate_to(session.page, url) and _origin(session.page.url) == origin:
            result = await execute_plan(session.page, plan, expected_origin=origin)
        else:
            result = {"status": "failed", "steps": [], "phases": {}, "duration_ms": 0,
                      "error_message": "Target navigation failed or left the configured origin"}
    finally:
        await close_browser(session)
    result.update(test_id=test_id, test_revision=revision, definition_snapshot=snapshot,
                  target_url=url, startedAt=started_at, finishedAt=datetime.now(timezone.utc).isoformat(),
                  duration_ms=int((time.perf_counter() - started) * 1000))
    healed = sum(bool(step.get("was_healed")) for step in result["steps"])
    payload = {"status": result["status"], "durationMs": result["duration_ms"], "runCount": 1,
               "instruction": snapshot["instruction"], "variant": snapshot.get("variant", "original"),
               "healedCount": healed, "wasHealed": healed > 0, "result": result}
    try:
        saved = await save_run(payload)
    except Exception as exc:
        raise PlanPersistenceError("Browser execution finished but its result could not be saved. Do not automatically rerun it.") from exc
    return {**result, "saved_run_id": str(saved["id"])}
