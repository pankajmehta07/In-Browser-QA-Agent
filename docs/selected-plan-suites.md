# Selected saved-plan suites

Branch: `feature/selected-plan-suites`, dependent on the saved-plan-execution PR.
This extends native FastAPI execution. It does not connect the dashboard's existing
Express suite button or change the dashboard proxy.

## Behavior

- POST `/tests/run-selected-plans` accepts 1-10 explicit test UUIDs and revisions.
  Selecting the same test twice, even at different revisions, is rejected. There
  is no omitted-selection fallback that runs the whole library.
- The existing `ENABLE_SAVED_PLAN_RUNS` flag must be enabled and the request must
  explicitly confirm execution. The server's `TARGET_APP_URL` is the only target;
  request-level URL overrides and unknown fields are rejected.
- Every selected definition is loaded, copied and validated before any browser
  opens. Missing tests/revisions or unsupported plans reject the request without
  starting an earlier valid selection. The accepted snapshots are then pinned in
  memory; later definition edits do not silently replace their contents.
- Cases run sequentially in request order using the existing prepared-plan executor.
  Each gets a fresh headless browser/context. Setup, assertions and optional cleanup
  retain their single-plan semantics. Website database records are not automatically
  reset between cases: each plan must arrange its own independent test data.
- An ordinary failed assertion/cleanup is a saved failed result; the next selected
  case can run. A mixture of passed and failed cases is a failed suite, not flaky.
- An infrastructure interruption or persistence error stops future cases. The
  response retains completed results and labels the interrupted/unsaved case and
  remaining not-run selections. Actions are never automatically repeated.
- Each completed case creates one ordinary saved run. The returned suite summary
  is not inserted as another run, avoiding an extra aggregate execution count.

The shared single-plan service now separates snapshot preparation from execution,
so both endpoints use the same validation and browser/persistence path. The old
instruction API and persistent CLI remain unchanged.

## Request

Use a trusted local/staging deployment configured as described in
[Saved-plan execution](saved-plan-execution.md). Migration 0002 is still required;
this PR adds no new migration, feature flag or database table.

```json
{
  "tests": [
    {"test_id": "00000000-0000-0000-0000-000000000001", "revision": 1},
    {"test_id": "00000000-0000-0000-0000-000000000002", "revision": 2}
  ],
  "confirm_execution": true
}
```

Those IDs are examples, not seeded tests. Replace them with reviewed saved test
IDs and revisions. As with individual execution, only original DOM / one-run
definitions with supported version-1 plans and resolved placeholders are accepted.
Do not include real secrets in instructions or plans.

## Response and counts

The response includes `suite_id`, `type: selected_plan_suite`, `status`, timestamps,
wall duration, `stop_reason`, `safe_to_retry: false`, `counts` and ordered `tests`.
Completed items include their `saved_run_id` and full individual result, including
the exact selected definition snapshot.

| Item state | Meaning |
| --- | --- |
| `completed` | Browser result finished and was saved, with passed/failed status. |
| `completed_unsaved` | Execution finished but persistence failed; do not assume it is safe to repeat. |
| `interrupted` | Infrastructure failed; whether website changes completed may be unknown. |
| `not_run` | No browser execution was started for this selection. |

The last three states have `status: unknown`, not a fabricated assertion failure.
The report's `completed` count means **saved completed cases**. `passed + failed`
equals `completed`; `completed + errors + not_run` equals `selected`. `errors`
counts unsaved/interrupted cases. No suite aggregate is included in these counts.

HTTP 200 means all selected cases completed and saved; inspect suite/test statuses
for assertion failures. HTTP 503 returns the full partial suite report if execution
stopped. Do not discard its completed run IDs just because the HTTP status is not
2xx. HTTP 403 means disabled, 422 invalid/duplicate/unconfirmed selection, 404 a
missing test/revision, and 409 a preflight plan/configuration issue. An unexpected
preflight infrastructure failure may still return HTTP 500; no browser starts until
preflight completes.

## Limits and operator responsibilities

This is synchronous execution, not a durable queue. The suite ID/summary is transient;
only individual results are persisted. There is no suite-history endpoint, worker
lease, restart recovery, progress polling, user cancellation API, request idempotency
key or automatic retry. Individual runs are not yet tagged with a durable suite
foreign key. A lost HTTP response can make completion uncertain: inspect run history
and the target website before retrying, even when selected plans appear read-only.

Preflight is not a multi-test database transaction or a website reservation. Accepted
cases use their captured snapshots even if a definition is edited or deleted after
acceptance. Cancellation propagates and stops future cases, but cannot undo completed
changes or guarantee cleanup for an interrupted case.

The existing flag/confirmation and origin checks are not authentication, per-record
destructive approval or an egress/SSRF sandbox. All trusted-staging, secret-binding,
event-loop and Linux deployment limitations from the single-plan guide still apply.
Review each case's setup and cleanup. Fresh browser storage does not roll back shared
website state. Never enable this path for an unapproved production target.

## Verification

Unit tests cover selection boundaries, preflight-before-execution, request order,
continuation after assertions, partial persistence failures, sanitized interruption
messages and cancellation. API contracts cover gating, confirmation, URL rejection
and partial HTTP 503 reports.

The opt-in Chromium fixture verifies that localStorage written by one case is not
reused by the next. PostgreSQL tests verify only selected individual runs are saved,
with the requested historical snapshot; an excluded test is not run and no aggregate
row is added. Browser and database boundaries are tested separately on Windows;
full FastAPI + PostgreSQL + browser deployment acceptance remains a Linux/Docker
smoke-test gate. Existing CI discovery includes the new tests automatically.

Local verification: all 102 Python tests passed together, including 16 PostgreSQL
cases and 4 real Chromium fixture cases; 3 Node parser tests and whitespace checks
also passed. Tests used Windows / Python 3.11 / PostgreSQL 17 with the existing
non-failing Starlette httpx deprecation warning. Linux/PostgreSQL 18 and full Docker
deployment acceptance remain pending. Verification used only synthetic fixtures;
no project database or external website was changed.
