# Saved-plan execution

Branch: `feature/saved-plan-execution`, stacked on `feature/import-preview` and its
versioned-plan/migration dependencies. This is an opt-in native FastAPI feature,
not the dashboard compatibility adapter or API cutover.

## Delivered behavior

- POST `/tests/{uuid}/run-plan` requires an explicit saved revision and confirmation.
- Only the server-configured `TARGET_APP_URL` is used. Request URL overrides and
  unrecognized request fields are rejected.
- The selected snapshot's version-1 plan is validated before opening a browser.
  Missing plans are not regenerated or silently replaced with parsed instructions.
- Setup runs first, then test steps, then optional cleanup. Each phase stops on
  its first failure. Failed setup skips the test phase; configured cleanup is still
  attempted after ordinary setup/test failures. Cleanup failure makes the overall
  result failed, while the main phase's result remains separately visible.
- Empty setup/cleanup is `not_configured`, not a validation error. Cleanup is not
  mandatory and cannot undo actions that already occurred.
- Each execution gets a fresh headless browser session and closes it afterward.
  Browser launch/close failure cleanup also stops the Playwright driver.
- Results include per-phase statuses, executed/configured counts, step details,
  timestamps, duration, test ID/revision and the exact definition snapshot.
- Results use the existing run store. Revision and snapshot are retained inside
  `runs.result_json`, not a new foreign key. Later edits/deletion do not rewrite
  the result. The existing nullable `runs.test_id` column is not populated by this
  path; use the saved JSON metadata until relational run linkage is designed.
- A result-save error returns 503 and explicitly warns against automatically
  rerunning: website changes may already have completed.

The existing flat instruction API and persistent CLI keep their execution behavior.
The shared low-level action runner/resolver is reused one step at a time; it is
not replaced. No LLM is needed to parse a stored plan. The existing button resolver
may still use its normal fallback tiers, including its configured provider.

## Enable only for an approved local/staging target

Default: `ENABLE_SAVED_PLAN_RUNS=false`. This is an operator feature flag, not
authentication or per-record authorization. Do not expose this service publicly
or use it for a production target. The current native API has no new access-control
boundary supplied by this PR. Confirmation is a user-intent check, not proof of
ownership or permission to change a website.

Review the target and plan, follow the [backup/migration procedure](database-migrations.md)
through migration 0002, then opt in. For Compose, set the process environment before
recreating the Python container:

```powershell
$env:ENABLE_SAVED_PLAN_RUNS = 'true'
docker compose up -d --build target-app python-services
```

Compose passes this flag to Python and already sets its target to
`http://target-app:5173`. Existing root `.env` database configuration is still
required. This command does not apply migrations. It does not switch the dashboard
from Express, and it does not remove Node API services or frontend tooling.

For combined PostgreSQL + Playwright execution, use the Linux Compose service.
On Windows, psycopg async connections and Playwright subprocesses require different
event-loop support; this PR does not solve the existing host-runtime integration
problem. Local Windows database and browser tests validate the boundaries separately,
not an end-to-end host deployment.

## Request and response

Use an existing reviewed test ID and revision that has a supported stored plan:

```powershell
$testId = 'REPLACE_WITH_SAVED_TEST_UUID'
$body = @{ revision = 1; confirm_execution = $true } | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/tests/$testId/run-plan" -ContentType 'application/json' -Body $body
```

The request rejects URL overrides. It currently requires the saved definition's
`variant` to be `original` and `reruns` to be 1; other values return 409 rather than
silently ignoring the configuration. The test must still exist when execution is
accepted, even when replaying a historical revision. Deletion is not cancellation
of an already accepted browser operation.

Successful HTTP execution returns the actual `status` (`passed` or `failed`),
`saved_run_id`, `test_id`, `test_revision`, `definition_snapshot`, `steps`, `phases`,
`duration_ms`, `target_url`, `startedAt` and `finishedAt`. A browser assertion failure
is a completed failed test result, not necessarily an HTTP transport failure.
Navigation failure records a failed result without running plan phases.

Errors: 403 when disabled; 422 for invalid UUID/body/confirmation; 404 for missing
test/revision; 409 for an unsupported or incomplete saved plan/configuration; 503
when execution finished but persistence failed. Never blindly retry an execution
request after a timeout or 503. There is no durable job/idempotency key yet.

## Scope and limitations

- Only version-1 actions are supported: `goto`, `type`, `click`, `check_visible`,
  `check_contains`. `goto` checks a heading; it is not URL navigation.
- Resolve `{{...}}` placeholders before execution; secret/session bindings and
  generated fixture variables are not implemented here. Do not store real passwords
  in plans: snapshots and existing diagnostics can retain literal test values.
- Cleanup acts exactly as configured. Review its targets; this path does not yet
  enforce disposable-record ownership or request per-record destructive approvals.
- Origin checks before/after steps prevent subsequent planned actions on an
  observed off-origin page. They are NOT a network/SSRF sandbox: a page can initiate
  subrequests, redirects, popups or writes during an action. Run only trusted,
  operator-approved staging pages, with deployment-level egress controls as needed.
- A cancellation propagates and closes the browser; it does not guarantee cleanup
  or undo completed website changes. There is no cancellation/job UI in this PR.
- Persistence failures do not auto-repeat actions. Unexpected browser startup or
  infrastructure exceptions may still be HTTP 500; inspect service diagnostics.
- A dependent [selected-suite PR](selected-plan-suites.md) adds an explicit native
  suite endpoint. Retries, schedules, visual baselines, screenshot/trace capture,
  the full dashboard DTO adapter and compatibility proxy cutover remain separate.
- Passing configured steps is not proof that all business requirements are covered.

The import preview stays read-only. An import writer still needs a reviewed schema,
ownership/secrets mapping and idempotent ledger; this feature does not enable it.

## Verification

The normal Python suite covers phase ordering, skip/failure behavior, optional
cleanup, origin checks, snapshot selection, persistence errors and API gating.
PostgreSQL tests exercise real result persistence after edits and deletion, with
the browser boundary mocked. An opt-in Chromium fixture exercises actual controls
on an ephemeral loopback HTTP server, without provider calls or external writes:

```powershell
$env:PYTHONPATH = 'python-services'
python -m playwright install chromium
$env:RUN_PLAN_BROWSER_TESTS = '1'
python -X utf8 -m unittest discover -s python-services/tests -p test_saved_plan_browser.py -v
```

CI installs Chromium and runs these fixture tests separately from unit contracts.
Keep a full FastAPI + PostgreSQL + demo browser smoke test as an acceptance gate
before enabling this path in a shared deployment or connecting the dashboard.

Local verification: all 89 Python tests passed together, including 15 PostgreSQL
cases and 3 real Chromium fixture cases; 3 Node parser tests also passed. YAML
parsing and whitespace checks passed. Tests used Windows / Python 3.11 / PostgreSQL
17, with the existing non-failing Starlette httpx deprecation warning. PostgreSQL
18/Linux and Docker runtime acceptance await CI and the deployment smoke test.
No live project database or external website was changed by verification.
