import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from stores.db import get_pool, close_pool
from stores.test_store import save_test, list_tests, get_test_by_id, delete_test
from stores.run_store import save_run, list_runs, get_run_by_id
from stores.approval_store import save_approval, list_approvals, find_approved_mapping, delete_approval
from utils.logger import log_info, log_success, log_error, console


async def test_connection():
    console.rule("DB Connection")
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT version()")
            row = await cur.fetchone()
            log_success(f"Connected — {row[0]}")


async def test_test_store():
    console.rule("Test Store")

    # save
    log_info("Saving test...")
    saved = await save_test({
        "name":        "Login flow",
        "instruction": "click Login",
        "variant":     "original",
        "reruns":      1,
    })
    log_success(f"Saved — id={saved['id']}")

    # get by id
    log_info("Fetching by id...")
    fetched = await get_test_by_id(saved["id"])
    assert fetched["name"] == "Login flow", "name mismatch"
    log_success(f"Fetched — name={fetched['name']}")

    # list
    log_info("Listing tests...")
    tests = await list_tests()
    assert any(t["id"] == saved["id"] for t in tests), "not found in list"
    log_success(f"Listed — {len(tests)} test(s) found")

    # delete
    log_info("Deleting test...")
    deleted = await delete_test(saved["id"])
    assert deleted, "delete returned False"
    log_success("Deleted successfully")

    # confirm gone
    gone = await get_test_by_id(saved["id"])
    assert gone is None, "still exists after delete"
    log_success("Confirmed gone")


async def test_run_store():
    console.rule("Run Store")

    log_info("Saving run...")
    saved = await save_run({
        "status":               "passed",
        "flaky":                False,
        "durationMs":           1234,
        "runCount":             1,
        "healedCount":          0,
        "wasHealed":            False,
        "totalCostUsd":         0,
        "variant":              "original",
        "instruction":          "click Login",
        "result": {
            "status":           "passed",
            "startedAt":        "2026-10-01T10:00:00Z",
            "finishedAt":       "2026-10-01T10:00:01Z",
            "runNumber":        1,
            "rootCause":        None,
            "accessibilityAudit": {
                "score":        100,
                "issueCount":   0,
                "warningCount": 0,
                "passedCount":  3,
            },
            "steps":            [],
        },
    })
    log_success(f"Saved — id={saved['id']}")

    # get by id
    log_info("Fetching by id...")
    fetched = await get_run_by_id(saved["id"])
    assert fetched["status"] == "passed", "status mismatch"
    log_success(f"Fetched — status={fetched['status']}")

    # list
    log_info("Listing runs...")
    runs = await list_runs()
    assert any(r["id"] == saved["id"] for r in runs), "not found in list"
    log_success(f"Listed — {len(runs)} run(s) found")


async def test_approval_store():
    console.rule("Approval Store")

    log_info("Saving approval...")
    saved = await save_approval({
        "runId":       None,
        "stepName":    "Click Login",
        "oldSelector": 'role=button[name="Login"]',
        "newSelector": 'role=button[name="Sign In"]',
        "oldTarget":   "Login",
        "newTarget":   "Sign In",
        "decision":    "approved",
        "confidence":  0.91,
        "strategy":    "accessibility_text_similarity",
    })
    log_success(f"Saved — id={saved['id']}")

    # list
    log_info("Listing approvals...")
    approvals = await list_approvals()
    assert any(a["id"] == saved["id"] for a in approvals), "not found in list"
    log_success(f"Listed — {len(approvals)} approval(s) found")

    # find mapping
    log_info("Finding approved mapping for 'Login'...")
    mapping = await find_approved_mapping("Login")
    assert mapping is not None,            "mapping not found"
    assert mapping["new_target"] == "Sign In", "new_target mismatch"
    log_success(f"Mapping found — {mapping['old_target']} → {mapping['new_target']}")

    # delete
    log_info("Deleting approval...")
    deleted = await delete_approval(saved["id"])
    assert deleted, "delete returned False"
    log_success("Deleted successfully")


async def main():
    console.rule("[bold cyan]DB Store Tests[/bold cyan]")

    try:
        await test_connection()
        await test_test_store()
        await test_run_store()
        await test_approval_store()

        console.rule("[bold green]All tests passed[/bold green]")

    except AssertionError as error:
        log_error(f"Assertion failed: {error}")
        console.rule("[bold red]Tests failed[/bold red]")

    except Exception as error:
        log_error(f"Unexpected error: {error}")
        console.rule("[bold red]Tests failed[/bold red]")

    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())