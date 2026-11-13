# Dashboard selected-suite execution adapter

This adapter builds on the data and single-plan compatibility PRs. It exposes
the existing selected-suite engine through a dashboard-oriented response contract.
It does not connect the current dashboard to FastAPI.

## Request

`POST /compat/tests/run-selected-plans`

```json
{
  "tests": [
    {"test_id": "00000000-0000-0000-0000-000000000001", "revision": 2},
    {"test_id": "00000000-0000-0000-0000-000000000002", "revision": 1}
  ],
  "confirm_execution": true
}
```

Use real saved-test IDs/revisions, not these example values. Request fields match
the native selected-suite contract. One to ten distinct tests, positive integer
revisions and explicit boolean confirmation are required. Extra fields, duplicate
tests, booleans as revisions and client target overrides are rejected.

`ENABLE_SAVED_PLAN_RUNS` remains false by default. Only `TARGET_APP_URL` supplies
the operator-approved target. The engine preflights every selected revision before
opening any browser, then executes the pinned snapshots sequentially in request
order with a fresh browser context per test. Existing plan/action restrictions,
origin checks, optional cleanup and persistence behavior remain unchanged.

## Response

The response includes `type: selected_plan_suite`, `suiteId`, `status`,
`stopReason`, `safeToRetry: false`, timestamps, `durationMs`, `counts` and `tests`.
Each entry includes `testId`, `testRevision`, `state`, `status` and nullable
`savedRunId`. Completed entries contain a dashboard-mapped `result` with phase,
step and root-cause diagnostics and a saved run ID. No artifact URL is invented.

Counts use `selected`, `completed`, `passed`, `failed`, `errors` and `notRun`.
They are derived from individual outcomes. Completed means finished AND saved;
an unsaved or interrupted run is not counted as an assertion failure or pass.

| State | Assertion status | Meaning |
| --- | --- | --- |
| completed | passed or failed | Execution finished and result was saved |
| completed_unsaved | unknown | Website execution finished but saving failed |
| interrupted | unknown | Website changes may have occurred; outcome uncertain |
| not_run | unknown | Stopped before this test started |

- All completed: HTTP 200, overall `passed` or `failed`. An ordinary failed
  assertion or cleanup does not stop later selected tests.
- Infrastructure/persistence stop: HTTP 503, overall `incomplete`, complete
  available partial report, safe `errorMessage`, and untouched later tests marked
  `not_run`.
- Disabled execution: 403; missing revision: 404; invalid reviewed plan/target:
  409. These return `executionState: not_started`.
- Invalid request: 422 with the compatibility validation error before execution.
- Unexpected engine or mapping failure: 503, `executionState: unknown` and a
  reference ID. Inspect history and website state; never automatically rerun.

Unexpected engine exceptions are conservatively reported as unknown, even if a
storage outage may have happened during preflight. When mapping itself fails,
the response cannot promise a partial report; independently saved runs remain
accessible through history. Private exception messages are not exposed.

## Remaining boundaries

The report and suite ID are transient, not stored as a durable suite/job. Only
individual completed runs are persisted by the existing engine. No automatic
retries, resume, cancellation, idempotency or concurrency control is added. A lost
HTTP connection is not evidence that execution stopped. Review website state
before manually repeating tests, and avoid conflicting concurrent executions.

The current dashboard's request builder and error helper are NOT wired to this
route. The shared client now retains error bodies as described in
`dashboard-api-error-context.md`; future views must still render the partial
report explicitly. This is an adapter, not full UI compatibility
acceptance or a proxy cutover. Native routes, Express, database schema and
environment settings are unchanged.

The server remains restricted to trusted development/authorized staging. This PR
adds no login, per-team ownership, sessions, network sandbox, instruction parser,
artifact serving or metrics. Origin checks are not a substitute for target
authorization. Supported plans still use the existing five-action schema.

## Verification

Route tests use the real suite engine, request validation and response mapper,
isolating only the database preflight and browser/persistence boundaries. They
exercise success, assertion-failure continuation, selection order, preflight of all
revisions, partial persistence failure, execution interruption, invalid requests,
disabled execution, invalid targets, sanitized failures and malformed results.
Existing PostgreSQL and Chromium tests verify their respective boundaries
separately; this is not a combined dashboard deployment acceptance test.

Local verification passed all 136 Python tests, including 17 PostgreSQL tests and
4 Chromium tests, plus 3 Node parser tests. Environment: Windows, Python 3.11,
PostgreSQL 17 and an isolated disposable database cluster. The existing
Starlette/httpx deprecation warning remains. Linux CI, PostgreSQL 18 and the full
Docker deployment were not verified locally. No external write probes were run.
