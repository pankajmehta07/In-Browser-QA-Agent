from fastapi import APIRouter, HTTPException
from uuid import UUID

from pydantic import BaseModel, Field

from parser.test_plan import TestPlan

from stores.test_store import (
    save_test,
    list_tests,
    get_test_by_id,
    update_test,
    delete_test,
    list_test_revisions,
    RevisionConflict,
)

router = APIRouter(prefix="/tests", tags=["tests"])


class CreateTestRequest(BaseModel):
    name: str
    instruction: str
    variant: str = "original"
    reruns: int = 1
    plan: TestPlan | None = None


class UpdateTestRequest(BaseModel):
    name: str | None = None
    instruction: str | None = None
    variant: str | None = None
    reruns: int | None = None
    plan: TestPlan | None = None
    expected_revision: int | None = Field(default=None, ge=1, strict=True)


@router.get("")
async def get_tests():
    """
    List all saved test definitions.
    """
    tests = await list_tests()
    return tests


@router.get("/{test_id}")
async def get_test(test_id: str):
    """
    Get a single test by id.
    """
    test = await get_test_by_id(test_id)

    if not test:
        raise HTTPException(status_code=404, detail="Test not found")

    return test


@router.post("", status_code=201)
async def create_test(body: CreateTestRequest):
    """
    Save a new test definition.
    """
    fields = {
        "name":        body.name,
        "instruction": body.instruction,
        "variant":     body.variant,
        "reruns":      body.reruns,
    }
    if "plan" in body.model_fields_set:
        fields["plan"] = body.plan.model_dump() if body.plan is not None else None
    saved = await save_test(fields)
    return saved


@router.put("/{test_id}")
async def update_test_by_id(test_id: str, body: UpdateTestRequest):
    """
    Update an existing test definition.
    """
    fields = body.model_dump(exclude_unset=True)
    fields = {key: value for key, value in fields.items() if value is not None or key == "plan"}
    try:
        updated = await update_test(test_id, fields)
    except RevisionConflict as exc:
        raise HTTPException(status_code=409, detail={
            "message": str(exc), "current_revision": exc.current_revision,
        }) from exc

    if not updated:
        raise HTTPException(status_code=404, detail="Test not found")

    return updated


@router.get("/{test_id}/revisions")
async def get_test_revisions(test_id: UUID):
    history = await list_test_revisions(str(test_id))
    if not history and not await get_test_by_id(str(test_id)):
        raise HTTPException(status_code=404, detail="Test not found")
    return history


@router.delete("/{test_id}")
async def delete_test_by_id(test_id: str):
    """
    Delete a saved test by id.
    """
    deleted = await delete_test(test_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Test not found")

    return {
        "ok":        True,
        "deleted_id": test_id,
    }
