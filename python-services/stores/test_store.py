import uuid
from datetime import datetime, timezone

from psycopg.rows import dict_row

from stores.db import get_pool
from utils.logger import log_success


async def save_test(test: dict) -> dict:
    """
    Save a test definition.
    """
    pool     = await get_pool()
    saved_id = str(uuid.uuid4())
    now      = datetime.now(timezone.utc)

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                INSERT INTO tests (
                    id, name, instruction, variant, reruns,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    saved_id,
                    test.get("name"),
                    test.get("instruction"),
                    test.get("variant", "original"),
                    test.get("reruns", 1),
                    now,
                    now,
                ),
            )
            row = await cur.fetchone()

    log_success(f"Test saved → {saved_id}")
    return dict(row)


async def list_tests() -> list[dict]:
    """
    Return all saved tests, newest first.
    """
    pool = await get_pool()

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM tests ORDER BY created_at DESC"
            )
            rows = await cur.fetchall()

    return [dict(row) for row in rows]


async def get_test_by_id(test_id: str) -> dict | None:
    pool = await get_pool()

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM tests WHERE id = %s",
                (test_id,),
            )
            row = await cur.fetchone()

    return dict(row) if row else None


async def update_test(test_id: str, fields: dict) -> dict | None:
    """
    Update name, instruction, variant or reruns of a saved test.
    """
    pool = await get_pool()
    now  = datetime.now(timezone.utc)

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                UPDATE tests
                SET
                    name        = COALESCE(%s, name),
                    instruction = COALESCE(%s, instruction),
                    variant     = COALESCE(%s, variant),
                    reruns      = COALESCE(%s, reruns),
                    updated_at  = %s
                WHERE id = %s
                RETURNING *
                """,
                (
                    fields.get("name"),
                    fields.get("instruction"),
                    fields.get("variant"),
                    fields.get("reruns"),
                    now,
                    test_id,
                ),
            )
            row = await cur.fetchone()

    return dict(row) if row else None


async def delete_test(test_id: str) -> bool:
    """
    Delete a test by id. Returns True if deleted, False if not found.
    """
    pool = await get_pool()

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM tests WHERE id = %s",
                (test_id,),
            )
            deleted = cur.rowcount > 0

    return deleted