import json
import uuid
from datetime import datetime, timezone

from psycopg.rows import dict_row

from stores.db import get_pool
from utils.logger import log_info, log_success, log_error


async def save_run(run: dict) -> dict:
    """
    Save a run result to the runs table.
    Returns the saved row with generated id and saved_at.
    """
    pool = await get_pool()

    saved_id  = str(uuid.uuid4())
    saved_at  = datetime.now(timezone.utc)

    result      = run.get("result", {})
    root_cause  = result.get("rootCause") or {}
    a11y_audit  = result.get("accessibilityAudit") or {}

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                INSERT INTO runs (
                    id,
                    saved_at,
                    status,
                    flaky,
                    duration_ms,
                    run_count,
                    healed_count,
                    was_healed,
                    total_cost_usd,
                    root_cause_title,
                    root_cause_summary,
                    root_cause_likely_cause,
                    root_cause_recommendation,
                    root_cause_evidence,
                    accessibility_score,
                    accessibility_issue_count,
                    accessibility_warning_count,
                    accessibility_passed_count,
                    started_at,
                    finished_at,
                    run_number,
                    instruction,
                    variant,
                    screenshot_path,
                    result_json
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s
                )
                RETURNING *
                """,
                (
                    saved_id,
                    saved_at,
                    run.get("status"),
                    run.get("flaky", False),
                    run.get("durationMs"),
                    run.get("runCount", 1),
                    run.get("healedCount", 0),
                    run.get("wasHealed", False),
                    run.get("totalCostUsd", 0),
                    root_cause.get("title"),
                    root_cause.get("summary"),
                    root_cause.get("likelyCause"),
                    root_cause.get("recommendation"),
                    root_cause.get("evidence"),
                    a11y_audit.get("score"),
                    a11y_audit.get("issueCount", 0),
                    a11y_audit.get("warningCount", 0),
                    a11y_audit.get("passedCount", 0),
                    result.get("startedAt"),
                    result.get("finishedAt"),
                    result.get("runNumber"),
                    run.get("instruction"),
                    run.get("variant", "original"),
                    run.get("screenshotPath"),
                    json.dumps(result),
                ),
            )
            row = await cur.fetchone()

    log_success(f"Run saved → {saved_id}")
    return dict(row)


async def list_runs(limit: int = 50) -> list[dict]:
    """
    Return the most recent runs, newest first.
    """
    pool = await get_pool()

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                """
                SELECT * FROM runs
                ORDER BY saved_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = await cur.fetchall()

    return [dict(row) for row in rows]


async def get_run_by_id(run_id: str) -> dict | None:
    """
    Return a single run by id.
    """
    pool = await get_pool()

    async with pool.connection() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT * FROM runs WHERE id = %s",
                (run_id,),
            )
            row = await cur.fetchone()

    return dict(row) if row else None