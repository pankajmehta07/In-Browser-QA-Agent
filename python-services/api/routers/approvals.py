from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from stores.approval_store import (
    save_approval,
    list_approvals,
    find_approved_mapping,
    delete_approval,
)

router = APIRouter(prefix="/approvals", tags=["approvals"])


class CreateApprovalRequest(BaseModel):
    run_id: str | None = None
    step_name: str
    old_selector: str | None = None
    new_selector: str | None = None
    old_target: str
    new_target: str
    decision: str              # approved | rejected
    confidence: float | None = None
    strategy: str | None = None


@router.get("")
async def get_approvals():
    """
    List all healing decisions.
    """
    approvals = await list_approvals()
    return approvals


@router.post("", status_code=201)
async def create_approval(body: CreateApprovalRequest):
    """
    Save a healing decision.
    """
    if body.decision not in ("approved", "rejected"):
        raise HTTPException(
            status_code=400,
            detail="decision must be 'approved' or 'rejected'",
        )

    saved = await save_approval({
        "runId":       body.run_id,
        "stepName":    body.step_name,
        "oldSelector": body.old_selector,
        "newSelector": body.new_selector,
        "oldTarget":   body.old_target,
        "newTarget":   body.new_target,
        "decision":    body.decision,
        "confidence":  body.confidence,
        "strategy":    body.strategy,
    })
    return saved


@router.get("/mapping/{old_target}")
async def get_approved_mapping(old_target: str):
    """
    Find an approved healing mapping by old target name.
    Used by resolver Tier 2.
    """
    mapping = await find_approved_mapping(old_target)

    if not mapping:
        raise HTTPException(
            status_code=404,
            detail=f"No approved mapping found for '{old_target}'",
        )

    return mapping


@router.delete("/{approval_id}")
async def delete_approval_by_id(approval_id: str):
    """
    Delete a healing decision by id.
    """
    deleted = await delete_approval(approval_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Approval not found")

    return {
        "ok":         True,
        "deleted_id": approval_id,
    }