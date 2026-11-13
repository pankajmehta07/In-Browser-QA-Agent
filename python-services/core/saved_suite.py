"""Selected, preflighted saved-plan suites; individual executions persist once."""

import time
import uuid
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator
from uuid import UUID

from core.saved_plan import _origin, execute_prepared_plan, prepare_saved_plan, PlanPersistenceError


class SuiteSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    test_id: UUID
    revision: int = Field(ge=1, strict=True)


class SelectedSuite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tests: list[SuiteSelection] = Field(min_length=1, max_length=10)

    @field_validator("tests")
    @classmethod
    def unique_tests(cls, values):
        if len({value.test_id for value in values}) != len(values):
            raise ValueError("Select each test only once")
        return values


async def execute_selected_suite(tests, url):
    selected = SelectedSuite(tests=tests).tests
    _origin(url)
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.perf_counter()
    # Do not open a browser until every selection has passed preflight.
    prepared = [await prepare_saved_plan(str(item.test_id), item.revision) for item in selected]
    outcomes = []
    stop_reason = None
    for item, definition in zip(selected, prepared):
        entry = {"test_id": str(item.test_id), "test_revision": item.revision, "saved_run_id": None}
        if stop_reason:
            outcomes.append({**entry, "state": "not_run", "status": "unknown"})
            continue
        try:
            result = await execute_prepared_plan(definition, url)
            if result.get("status") not in {"passed", "failed"} or not result.get("saved_run_id"):
                raise RuntimeError("Execution did not return a saved result")
        except PlanPersistenceError:
            stop_reason = "persistence_failed"
            outcomes.append({**entry, "state": "completed_unsaved", "status": "unknown",
                             "error_message": "Execution finished but its result could not be saved. Do not automatically rerun."})
        except Exception:
            stop_reason = "execution_interrupted"
            outcomes.append({**entry, "state": "interrupted", "status": "unknown",
                             "error_message": "Execution was interrupted; website changes may have occurred. Review before retrying."})
        else:
            outcomes.append({**entry, "state": "completed", "status": result["status"],
                             "saved_run_id": result["saved_run_id"], "result": result})
    completed = [entry for entry in outcomes if entry["state"] == "completed"]
    failed = sum(entry["status"] == "failed" for entry in completed)
    return {"type": "selected_plan_suite", "suite_id": str(uuid.uuid4()),
            "status": "incomplete" if stop_reason else "failed" if failed else "passed",
            "stop_reason": stop_reason, "safe_to_retry": False,
            "started_at": started_at, "finished_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": int((time.perf_counter() - started) * 1000),
            "counts": {"selected": len(selected), "completed": len(completed),
                       "passed": len(completed) - failed, "failed": failed,
                       "errors": sum(entry["state"] in {"completed_unsaved", "interrupted"} for entry in outcomes),
                       "not_run": sum(entry["state"] == "not_run" for entry in outcomes)},
            "tests": outcomes}
