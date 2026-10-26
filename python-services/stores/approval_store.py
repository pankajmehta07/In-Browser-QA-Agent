import uuid
from datetime import datetime, timezone

from psycopg.rows import dict_row

from stores.db import get_pool
from utils.logger import log_success


async def save_approval(approval: dict) -> dict:
    """
    Save a healing decision (approved or rejected).
    """
    pool     = await get_pool()
    saved_id = str(uuid.uuid4())
    saved_at = datetime.now(timezone.utc)

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                INSERT INTO healed_selectors (
                    id, saved_at, run_id, step_name,
                    old_selector, new_selector,
                    old_target, new_target,
                    decision, confidence, strategy
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    saved_id,
                    saved_at,
                    approval.get("runId"),
                    approval.get("stepName"),
                    approval.get("oldSelector"),
                    approval.get("newSelector"),
                    approval.get("oldTarget"),
                    approval.get("newTarget"),
                    approval.get("decision"),
                    approval.get("confidence"),
                    approval.get("strategy"),
                ),
            )
            row = await cur.fetchone()

    log_success(f"Approval saved → {saved_id}")
    return dict(row)


async def list_approvals() -> list[dict]:
    """
    Return all healing decisions, newest first.
    """
    pool = await get_pool()

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT * FROM healed_selectors
                ORDER BY saved_at DESC
                """
            )
            rows = await cur.fetchall()

    return [dict(row) for row in rows]


async def find_approved_mapping(old_target: str) -> dict | None:
    """
    Find an approved healing mapping by old_target.
    Used by resolver Tier 2.
    """
    pool       = await get_pool()
    normalized = old_target.strip().lower()

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT * FROM healed_selectors
                WHERE decision = 'approved'
                AND LOWER(TRIM(old_target)) = %s
                ORDER BY saved_at DESC
                LIMIT 1
                """,
                (normalized,),
            )
            row = await cur.fetchone()

    return dict(row) if row else None


async def delete_approval(approval_id: str) -> bool:
    """
    Delete an approval by id.
    Returns True if deleted, False if not found.
    """
    pool = await get_pool()

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM healed_selectors WHERE id = %s",
                (approval_id,),
            )
            deleted = cur.rowcount > 0

    return deleted