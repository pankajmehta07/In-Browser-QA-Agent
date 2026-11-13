"""Dashboard data contracts only; execution and artifact adapters are separate."""

import logging
import uuid
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, ConfigDict, Field, field_validator

from api.dashboard_dto import run_dto, test_dto
from parser.test_plan import TestPlan
from stores.db import get_pool
from stores.run_store import get_run_by_id, list_runs
from stores.test_store import delete_test, get_test_by_id, list_tests, save_test


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


@router.get("/tests/{test_id}")
async def get_test(test_id: UUID):
    row = await get_test_by_id(str(test_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Test not found")
    return test_dto(row)


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
