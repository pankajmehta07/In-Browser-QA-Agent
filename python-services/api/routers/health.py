from fastapi import APIRouter
from stores.db import get_pool

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """
    Basic liveness check — confirms the API is running.
    """
    return {
        "ok": True,
        "service": "server",
    }


@router.get("/health/db")
async def health_db():
    """
    DB connectivity check — confirms Postgres is reachable.
    """
    try:
        pool = await get_pool()
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT 1")
                await cur.fetchone()

        return {
            "ok":      True,
            "service": "server",
            "db":      "connected",
        }

    except Exception as error:
        return {
            "ok":      False,
            "service": "server",
            "db":      "unreachable",
            "error":   str(error),
        }