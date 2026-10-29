from fastapi import APIRouter, HTTPException

from stores.run_store import list_runs, get_run_by_id

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("")
async def get_runs(limit: int = 50):
    """
    List saved runs, newest first.
    """
    runs = await list_runs(limit=limit)
    return runs


@router.get("/{run_id}")
async def get_run(run_id: str):
    """
    Get a single run by id.
    """
    run = await get_run_by_id(run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return run