"""Dashboard data and explicit saved-plan contracts; no proxy cutover."""

import logging
import os
import re
import uuid
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.routing import APIRoute
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.dashboard_dto import _result, approval_dto, metrics_dto, revision_dto, run_dto, suite_dto, test_dto
from api.routers.tests import RunSavedPlanRequest, RunSelectedSuiteRequest
from api.run_screenshots import read_screenshot, ScreenshotConfigurationError, ScreenshotUnavailable
from core.saved_suite import execute_selected_suite
from core.saved_plan import (
    PlanPersistenceError, SavedPlanNotFound, _origin,
    execute_prepared_plan, prepare_saved_plan,
)
from parser.test_plan import TestPlan
from stores.db import get_pool
from stores.approval_store import save_approval, list_approvals, delete_approval
from stores.run_store import get_execution_metrics, get_run_by_id, list_runs
from stores.test_store import (
    RevisionConflict, delete_test, get_test_by_id, list_test_revisions,
    list_tests, save_test, update_test,
)


logger = logging.getLogger(__name__)


class CompatibilityRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def dashboard_errors(request):
            try:
                return await handler(request)
            except RequestValidationError:
                return JSONResponse(status_code=422, content={"status": "failed", "errorMessage": "Invalid request. Check IDs, required fields, variant, reruns and optional plan."})
            except HTTPException as exc:
                return JSONResponse(status_code=exc.status_code, content={"status": "failed", "errorMessage": exc.detail})
            except Exception as exc:
                error_id = str(uuid.uuid4())
                logger.error("Compatibility data request %s failed: %s", error_id, type(exc).__name__)
                return JSONResponse(status_code=503, content={"status": "failed", "errorId": error_id,
                    "errorMessage": "Data request could not complete. For writes, verify the library before retrying."})
        return dashboard_errors


router = APIRouter(prefix="/compat", tags=["dashboard compatibility"], route_class=CompatibilityRoute)


class DashboardTestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=300)
    instruction: str = Field(min_length=1, max_length=100000)
    variant: Literal["original", "changed", "flaky"] = "original"
    reruns: int = Field(default=1, ge=1, le=5, strict=True)
    plan: TestPlan | None = None

    @field_validator("name", "instruction")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Value must not be blank")
        return value


class DashboardTestUpdateRequest(DashboardTestRequest):
    expectedRevision: int = Field(ge=1, strict=True)
    variant: Literal["original", "changed", "flaky"]
    reruns: int = Field(ge=1, le=5, strict=True)


class DashboardApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runId: UUID
    stepName: str = Field(min_length=1, max_length=1000)
    oldSelector: str = Field(min_length=1, max_length=10000)
    newSelector: str = Field(min_length=1, max_length=10000)
    oldTarget: str = Field(min_length=1, max_length=10000)
    newTarget: str = Field(min_length=1, max_length=10000)
    decision: Literal["approved", "rejected"]
    confidence: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    strategy: str | None = Field(default=None, max_length=1000)

    @field_validator("stepName", "oldSelector", "newSelector", "oldTarget", "newTarget")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Value must not be blank")
        return value


def selector_target(selector):
    # Match the dashboard's displayed target extraction, not a CSS parser.
    match = re.search(r'name="([^"]+)"', selector)
    return match[1] if match else selector


@router.get("/approvals")
async def get_approvals():
    return [approval_dto(row) for row in await list_approvals()]


@router.post("/approvals")
async def create_approval(body: DashboardApprovalRequest):
    run = await get_run_by_id(str(body.runId))
    if run is None:
        raise HTTPException(status_code=404, detail="Saved run not found")
    try:
        steps = _result(run["result_json"])["steps"]
    except (ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=409, detail="Saved run evidence cannot be reviewed for this decision") from exc
    matches = [step for step in steps if step.get("wasHealed") is True
               and step.get("name") == body.stepName
               and step.get("oldSelector") == body.oldSelector
               and step.get("newSelector") == body.newSelector]
    if (len(matches) != 1 or body.oldTarget != selector_target(body.oldSelector)
            or body.newTarget != selector_target(body.newSelector)):
        raise HTTPException(status_code=409, detail="Decision must match one recorded healed step and its selector targets")
    return approval_dto(await save_approval(body.model_dump(mode="json")))


@router.delete("/approvals/{approval_id}")
async def remove_approval(approval_id: UUID):
    if not await delete_approval(str(approval_id)):
        raise HTTPException(status_code=404, detail="Approval not found")
    return {"status": "passed", "deletedId": str(approval_id)}


async def database_ready():
    pool = await get_pool()
    async with pool.connection() as connection:
        cursor = await connection.execute("SELECT 1 FROM public.schema_migrations WHERE version = 2")
        return await cursor.fetchone() is not None


@router.get("/health")
async def health():
    if not await database_ready():
        raise HTTPException(status_code=503, detail="Database schema is not ready; apply the reviewed migrations")
    return {"ok": True, "service": "in-browser-qa-agent-fastapi", "scope": "data-only"}


@router.get("/tests")
async def get_tests():
    return [test_dto(row) for row in await list_tests()]


@router.get("/metrics")
async def get_metrics():
    return metrics_dto(await get_execution_metrics())


@router.get("/tests/{test_id}")
async def get_test(test_id: UUID):
    row = await get_test_by_id(str(test_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Test not found")
    return test_dto(row)


@router.put("/tests/{test_id}")
async def edit_test(test_id: UUID, body: DashboardTestUpdateRequest):
    fields = body.model_dump(exclude={"expectedRevision", "plan"})
    fields["expected_revision"] = body.expectedRevision
    if "plan" in body.model_fields_set:
        fields["plan"] = body.plan.model_dump() if body.plan is not None else None
    try:
        row = await update_test(str(test_id), fields)
    except RevisionConflict as exc:
        return JSONResponse(status_code=409, content={"status": "failed",
            "errorMessage": "The test changed; reload and review before saving again",
            "currentRevision": exc.current_revision})
    if row is None:
        raise HTTPException(status_code=404, detail="Test not found")
    return test_dto(row)


@router.get("/tests/{test_id}/revisions")
async def get_revisions(test_id: UUID):
    history = await list_test_revisions(str(test_id))
    if not history and not await get_test_by_id(str(test_id)):
        raise HTTPException(status_code=404, detail="Test not found")
    return [revision_dto(row) for row in history]


@router.post("/tests/run-selected-plans")
async def run_selected_plans(body: RunSelectedSuiteRequest):
    if os.getenv("ENABLE_SAVED_PLAN_RUNS", "false").lower() != "true":
        return execution_error(403, "Saved-plan execution is disabled", "not_started")
    target = os.getenv("TARGET_APP_URL", "http://127.0.0.1:5173/")
    try:
        report = await execute_selected_suite(body.tests, target)
    except SavedPlanNotFound:
        return execution_error(404, "A selected test or revision was not found; no browser was started", "not_started")
    except ValueError:
        return execution_error(409, "Review every selected plan, revision and the server target before execution", "not_started")
    except Exception as exc:
        error_id = str(uuid.uuid4())
        logger.error("Compatibility suite %s failed: %s", error_id, type(exc).__name__)
        return execution_error(503, f"Suite outcome could not be confirmed. Review history before retrying. Reference: {error_id}", "unknown")
    try:
        result = suite_dto(report)
    except Exception as exc:
        error_id = str(uuid.uuid4())
        logger.error("Compatibility suite mapping %s failed: %s", error_id, type(exc).__name__)
        return execution_error(503, f"Suite results could not be displayed. Inspect run history before retrying. Reference: {error_id}", "unknown")
    return JSONResponse(status_code=503 if result["status"] == "incomplete" else 200, content=result)


@router.post("/tests")
async def create_test(body: DashboardTestRequest):
    fields = body.model_dump(exclude={"plan"})
    if "plan" in body.model_fields_set:
        fields["plan"] = body.plan.model_dump() if body.plan else None
    return test_dto(await save_test(fields))


@router.delete("/tests/{test_id}")
async def remove_test(test_id: UUID):
    if not await delete_test(str(test_id)):
        raise HTTPException(status_code=404, detail="Test not found")
    return {"status": "passed", "deletedId": str(test_id)}


@router.get("/runs")
async def get_runs(limit: int = Query(default=50, ge=1, le=200)):
    return [run_dto(row) for row in await list_runs(limit=limit)]


@router.get("/runs/{run_id}")
async def get_run(run_id: UUID):
    row = await get_run_by_id(str(run_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_dto(row)


@router.get("/runs/{run_id}/screenshot")
async def get_run_screenshot(run_id: UUID):
    if os.getenv("ENABLE_RUN_SCREENSHOTS", "false").lower() != "true":
        raise HTTPException(status_code=403, detail="Run screenshot access is disabled")
    root = os.getenv("RUN_SCREENSHOT_ROOT", "").strip()
    if not root:
        raise HTTPException(status_code=503, detail="Run screenshot storage is not configured")
    row = await get_run_by_id(str(run_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Run screenshot is unavailable")
    try:
        content = await run_in_threadpool(read_screenshot, row.get("screenshot_path"), root)
    except ScreenshotConfigurationError as exc:
        raise HTTPException(status_code=503, detail="Run screenshot storage is not configured") from exc
    except ScreenshotUnavailable as exc:
        raise HTTPException(status_code=404, detail="Run screenshot is unavailable") from exc
    return Response(content=content, media_type="image/png", headers={
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
        "Content-Disposition": f'inline; filename="failure-{run_id}.png"',
        "Content-Security-Policy": "default-src 'none'; sandbox",
    })


def execution_error(status_code, message, state):
    return JSONResponse(status_code=status_code, content={
        "status": "failed", "errorMessage": message,
        "executionState": state, "safeToRetry": False,
    })


@router.post("/tests/{test_id}/run-plan")
async def run_plan(test_id: UUID, body: RunSavedPlanRequest):
    if os.getenv("ENABLE_SAVED_PLAN_RUNS", "false").lower() != "true":
        return execution_error(403, "Saved-plan execution is disabled", "not_started")
    target = os.getenv("TARGET_APP_URL", "http://127.0.0.1:5173/")
    try:
        _origin(target)
        prepared = await prepare_saved_plan(str(test_id), body.revision)
    except SavedPlanNotFound:
        return execution_error(404, "Saved test or revision not found", "not_started")
    except ValueError:
        return execution_error(409, "Review the saved plan, placeholders, variant, rerun count and server target before execution", "not_started")
    except Exception:
        return execution_error(503, "Execution preflight could not complete; no browser was started", "not_started")
    try:
        raw = await execute_prepared_plan(prepared, target)
        result = _result(raw)
        if result.get("status") not in ("passed", "failed"):
            raise ValueError("Invalid execution status")
        result.update(savedRunId=str(UUID(raw["saved_run_id"])),
                      executionState="completed", safeToRetry=False)
        return result
    except PlanPersistenceError:
        return execution_error(503, "Browser execution finished but its result could not be saved. Do not automatically rerun it.", "completed_unsaved")
    except Exception as exc:
        error_id = str(uuid.uuid4())
        logger.error("Compatibility execution %s failed: %s", error_id, type(exc).__name__)
        return execution_error(503, f"Execution could not be confirmed. Inspect run history and the website before retrying. Reference: {error_id}", "unknown")
