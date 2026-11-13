import uuid
from datetime import datetime, timezone

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from parser.test_plan import TestPlan
from stores.db import get_pool
from utils.logger import log_success


class RevisionConflict(Exception):
    def __init__(self, current_revision):
        self.current_revision = current_revision
        super().__init__("The test changed; reload before saving again")


def _plan_json(value):
    return Jsonb(TestPlan.model_validate(value).model_dump()) if value is not None else None


async def save_test(test: dict) -> dict:
    """
    Save a test definition.
    """
    pool     = await get_pool()
    saved_id = str(uuid.uuid4())
    now      = datetime.now(timezone.utc)
    plan = _plan_json(test.get("plan"))

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                INSERT INTO tests (
                    id, name, instruction, variant, reruns,
                    created_at, updated_at, plan
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
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
                    plan,
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
    Update a definition atomically; optional expected_revision prevents lost edits.
    """
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.transaction():
            async with conn.cursor(row_factory=dict_row) as cur:
                await cur.execute("SELECT * FROM tests WHERE id = %s FOR UPDATE", (test_id,))
                current = await cur.fetchone()
                if current is None:
                    return None
                expected = fields.get("expected_revision")
                if expected is not None:
                    if type(expected) is not int or expected < 1:
                        raise ValueError("expected_revision must be a positive integer")
                    if expected != current["revision"]:
                        raise RevisionConflict(current["revision"])
                values = dict(current)
                for key in ("name", "instruction", "variant", "reruns"):
                    if fields.get(key) is not None:
                        values[key] = fields[key]
                if "plan" in fields:
                    values["plan"] = fields["plan"]
                elif values["instruction"] != current["instruction"]:
                    values["plan"] = None
                await cur.execute(
                    """UPDATE tests SET name = %s, instruction = %s, variant = %s,
                       reruns = %s, plan = %s WHERE id = %s RETURNING *""",
                    (values["name"], values["instruction"], values["variant"], values["reruns"],
                     _plan_json(values["plan"]), test_id),
                )
                row = await cur.fetchone()
    return dict(row)


async def list_test_revisions(test_id: str) -> list[dict]:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM test_revisions WHERE original_test_id = %s ORDER BY revision DESC",
                (test_id,),
            )
            return [dict(row) for row in await cur.fetchall()]


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
