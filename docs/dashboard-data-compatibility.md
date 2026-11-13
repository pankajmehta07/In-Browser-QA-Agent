# Dashboard data compatibility

Branch: `feature/dashboard-data-compatibility`, stacked on selected-plan-suites.
This is the data-contract portion of the proposed `/compat` boundary. It is NOT
a dashboard cutover, a complete Express replacement or a new frontend feature.

## Routes delivered

| Route | Behavior |
| --- | --- |
| GET `/compat/health` | Checks database connectivity and migration-0002 ledger presence; returns `ok` and `scope: data-only`. |
| GET `/compat/tests` | Array of saved test DTOs, newest first. |
| GET `/compat/tests/{uuid}` | One saved test DTO or 404. |
| POST `/compat/tests` | Saves exactly one definition; returns HTTP 200 and its DTO, matching the dashboard's current save behavior. |
| DELETE `/compat/tests/{uuid}` | Deletes only that definition; returns `{status: passed, deletedId}`. |
| GET `/compat/runs` | Recent saved run DTOs, default 50; optional limit 1-200. |
| GET `/compat/runs/{uuid}` | A saved summary and mapped historical result, not a rerun or reconstruction from the current test definition. |

Handlers call shared Python stores directly. There is no Node proxy or internal
HTTP forwarding. Deletion uses existing foreign-key rules, retaining run history
and revision snapshots. Neither save nor delete invokes the runner.

The existing `/tests`, `/runs`, `/health`, instruction, audit and approval routes
retain their native contracts. Dashboard Vite configuration and API base URL remain
unchanged; Express remains the current dashboard backend. No Node code is removed.

## Request and DTO mapping

Create requests accept nonblank `name` and `instruction`, known DOM `variant`
(`original`, `changed`, `flaky`), integer `reruns` from 1-5, and optional validated
version-1 `plan`. Unknown fields are rejected. Names are limited to 300 characters,
instructions to 100,000; values are not silently rewritten or parsed by an LLM.

UUIDs become strings, database timestamps become ISO strings, and Decimal cost
summaries become finite JSON numbers. Test fields map `created_at`/`updated_at` to
`createdAt`/`updatedAt`, retaining revision and plan. Run summaries explicitly map
`savedAt`, `durationMs`, `runCount`, healing, cost and accessibility count fields.

Known historical result formats are adapted field by field:

- Legacy camelCase diagnostics, step results and reruns remain available.
- Native phased results gain dashboard aliases such as `durationMs`, `testId`,
  `testRevision`, `definitionSnapshot`, `selectorUsed` and `resolutionStrategy`.
- Step names are retained or derived from the stored action/target, not regenerated
  by AI. An existing failed-step error can populate the inspector's error banner.
- Phase statuses and historical definition snapshots are retained. Mapping does
  not mutate the stored JSON or substitute a newly edited test definition.
- Zero durations/confidence values remain zero. Missing audit status becomes
  `unknown`, never `passed` merely because issue counts are zero.
- Malformed results or contradictory summary/result statuses fail explicitly.
  Grouped suite payloads are not adapted yet and are rejected rather than displayed
  as empty successful executions.

This is an explicit view of known fields, not a recursive key-renaming or universal
data-export mechanism. Unrecognized result fields are not automatically exposed.
The native stored record remains unchanged and readable through the native API;
new result schemas need explicit DTO mappings and regression fixtures.

## Errors and artifacts

Registered compatibility routes return non-2xx errors with `status: failed` and
`errorMessage`, as expected by the dashboard request helper. Invalid UUIDs/bodies/
limits return 422; missing records return 404. Data-service/mapping errors return
503 with a diagnostic `errorId`. Logs record that ID and exception type without
printing the underlying exception message, SQL payload or connection string.
For writes, inspect the library before retrying after an ambiguous failure.

This error wrapper is scoped to the new routes; it does not globally replace native
FastAPI validation errors. Unknown/unimplemented paths retain normal FastAPI 404s.

Artifact serving is deliberately absent. Known screenshot/trace references and
filesystem path fields are not converted into working image/download links.
Available-but-unexposed artifacts are marked `artifactAvailability: not_exposed`.
The current UI does not display that marker yet. This mapping is not a general
secret/path redaction system for arbitrary diagnostic text or test values.

## Readiness and cutover gates

After applying the reviewed migrations, inspect the data-only endpoints at the
native Python port (8000 in Compose):

```powershell
Invoke-RestMethod http://127.0.0.1:8000/compat/health
Invoke-RestMethod http://127.0.0.1:8000/compat/tests
Invoke-RestMethod 'http://127.0.0.1:8000/compat/runs?limit=10'
```

Health checks connectivity and the migration ledger, not every column/constraint,
browser availability, LLM configuration or full execution parity. A green response
does not authorize switching the dashboard proxy. Keep the service restricted to
trusted development/staging access; this PR adds no authentication or team ownership.

Remaining gates include execution DTO adapters, approved selector-decision routes,
authorized artifact serving, all-time execution metrics, durable jobs where needed,
and real dashboard/FastAPI/PostgreSQL/browser acceptance before a dedicated proxy
cutover PR. Recent-run list length is not an all-time total and must not be used as
one. No existing dashboard statistics are rewired by this PR.

No new schema migration or runtime feature flag is introduced. Existing
`ENABLE_SAVED_PLAN_RUNS` behavior applies only to native execution, not these CRUD
routes; the new routes themselves never execute a test or a suite.

## Verification

DTO tests cover known result formats, UUID/date/Decimal conversion, preservation of
zero values, immutable historical snapshots, malformed payloads and unavailable
artifact links. API tests cover array/response shapes, one-save semantics, delete
without execution, sanitized errors, limits, readiness and unchanged native errors.
An ASGI/PostgreSQL test exercises real create/list/history/delete persistence and
history retention without opening a browser. Full deployment/browser cutover
acceptance remains a separate gate; no actual project records are used in tests.

Local verification: all 117 Python tests passed, including 17 PostgreSQL tests and
4 Chromium execution tests, on Windows with Python 3.11 and PostgreSQL 17. The
3 Node parser tests also passed. The disposable PostgreSQL cluster was stopped
after verification. Linux/Python 3.12/PostgreSQL 18 CI and the full Docker deployment
remain unverified locally; these results are not dashboard cutover acceptance.
