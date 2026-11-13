# Dashboard saved-plan execution adapter

This PR builds on dashboard data compatibility. It adds one opt-in route, not a
dashboard cutover or a general natural-language execution endpoint.

## Request

`POST /compat/tests/{test_id}/run-plan`

```json
{"revision": 2, "confirm_execution": true}
```

- The ID must be a UUID; revision must be a positive integer, not a boolean.
- Explicit boolean confirmation is required. Extra fields are rejected.
- `ENABLE_SAVED_PLAN_RUNS` must be `true`; it remains disabled by default.
- Only the operator-configured `TARGET_APP_URL` is used. Clients cannot override it.
- The existing preflight loads the exact revision and validates its structured
  plan, original variant, one-run setting and absence of unresolved placeholders.
- Preflight completes before browser execution. The same prepared snapshot is
  passed to the existing executor; it is not fetched again after validation.

The existing five-action TestPlan schema and heading-based `goto` semantics remain
unchanged. This route does not generate a plan, use the LLM, import browser sessions,
or expand the supported action set. Native execution routes remain unchanged.

## Responses and retry safety

A completed run returns HTTP 200 even when an assertion or cleanup failed. The
payload uses dashboard-compatible `durationMs`, `testId`, `testRevision`,
`targetUrl`, `savedRunId`, step diagnostics and root-cause fields. Existing phase
results are retained. No screenshot or trace link is invented.

| Outcome | HTTP | executionState |
| --- | --- | --- |
| Finished and saved, assertions passed or failed | 200 | completed |
| Feature disabled | 403 | not_started |
| Missing test or revision | 404 | not_started |
| Invalid reviewed plan or configured target | 409 | not_started |
| Preflight storage/service error | 503 | not_started |
| Browser finished but persistence failed | 503 | completed_unsaved |
| Execution interrupted, result invalid, or outcome uncertain | 503 | unknown |

Execution responses include `safeToRetry: false`; the adapter never retries a
browser action or write. Request validation errors use the existing compatibility
422 `errorMessage` response and occur before the handler starts execution.
Unexpected exception messages and stored private values are not returned.

An `unknown` outcome is not proof that no change occurred. Inspect the website and
run history before making a new explicit request. A lost client connection or
server restart is also not proof of cancellation. No durable job, idempotency key,
concurrency limit or cancellation API is introduced here. Operators must restrict
the server target to authorized staging and avoid simultaneous conflicting tests.

Existing origin checks before and after steps remain in force; they are not a
network sandbox and do not prevent every redirect or outgoing request. This PR
does not introduce authentication or per-team ownership.

## Integration boundary

The dashboard proxy and Express endpoints are untouched. The dashboard does not
call this new route yet. Its existing run request is not interchangeable with this
explicit revision/confirmation contract. Selected-suite response adaptation is
documented in `dashboard-suite-execution.md`. Instruction execution, approvals,
authorized artifacts, metrics and deployment
acceptance remain separate work before proxy cutover.

The existing executor persists each completed result once and closes its browser
in its normal finally path. Setup/test/optional cleanup behavior is unchanged.
Optional failure capture is documented in `saved-plan-failure-screenshots.md` and
is disabled by default. This adapter itself requires no schema migration.

## Verification

`test_compat_execution.py` exercises real route validation and result mapping,
mocking the external preflight/execution boundaries. Tests cover disabled-by-default
behavior, pinned revision and target forwarding, completed assertion failures,
invalid confirmation and target overrides, preflight failures, persistence errors,
sanitized unexpected errors, and malformed results. Existing native executor,
PostgreSQL and Chromium tests cover their respective boundaries separately.
These are not a combined dashboard-to-browser deployment acceptance test.

Local verification passed all 127 Python tests (including 17 PostgreSQL and 4
Chromium tests) and 3 Node parser tests on Windows, Python 3.11 and PostgreSQL 17.
An initial run was interrupted after the temporary database failed to bind its
default port; the full suite was rerun successfully using the dedicated loopback
test port. The existing Starlette/httpx deprecation warning remains. Linux CI and
full Docker deployment acceptance remain unverified locally.
