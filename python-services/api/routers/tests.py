from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from stores.test_store import (
    save_test,
    list_tests,
    get_test_by_id,
    update_test,
    delete_test,
)

router = APIRouter(prefix="/tests", tags=["tests"])


class CreateTestRequest(BaseModel):
    name: str
    instruction: str
    variant: str = "original"
    reruns: int = 1


class UpdateTestRequest(BaseModel):
    name: str | None = None
    instruction: str | None = None
    variant: str | None = None
    reruns: int | None = None


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
    saved = await save_test({
        "name":        body.name,
        "instruction": body.instruction,
        "variant":     body.variant,
        "reruns":      body.reruns,
    })
    return saved


@router.put("/{test_id}")
async def update_test_by_id(test_id: str, body: UpdateTestRequest):
    """
    Update an existing test definition.
    """
    updated = await update_test(test_id, body.model_dump(exclude_none=True))

    if not updated:
        raise HTTPException(status_code=404, detail="Test not found")

    return updated


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