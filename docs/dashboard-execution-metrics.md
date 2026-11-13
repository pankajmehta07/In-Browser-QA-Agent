# All-time saved execution metrics

`GET /compat/metrics` adds aggregate data for a future dashboard integration.
It does not change the current dashboard's statistics, proxy or history list.

## Response and counting rules

```json
{
  "scope": "all_time",
  "unit": "saved_run_records",
  "totalRuns": 64,
  "passedRuns": 40,
  "failedRuns": 20,
  "flakyRuns": 4,
  "healedRuns": 21,
  "savedTests": 2,
  "passRate": 63,
  "measuredAt": "2026-01-02T00:00:00+00:00"
}
```

- `totalRuns` counts persisted rows in `runs`, without the recent-history limit.
- Passed/failed/flaky counts use each row's `status`; they are mutually exclusive
  and sum to the total. The separate boolean `flaky` flag does not reclassify a
  row's stored status.
- `passRate` is `passedRuns / totalRuns * 100`, rounded to an integer with half-up
  rounding. Flaky-status rows remain in the denominator, matching the dashboard's
  existing percentage formula. An empty history returns null, not an invented
  success/failure percentage. Future UI wiring should display an unavailable mark.
- `healedRuns` counts rows where `was_healed` is true. It does not sum healed steps,
  infer healing from JSON, or claim every recovery was correct.
- `savedTests` counts current saved definitions, including definitions without a
  runnable structured plan. It is NOT a count of ready-for-regression tests.
- `measuredAt` is the database statement timestamp, serialized to ISO format.

Counts are saved records, not unique business workflows, browser attempts or
individual nested reruns. `run_count` is not summed. If historical producers saved
grouped executions as one row, they remain one row. Suite summaries from the new
executor are transient; its individually saved results each count once.

Unsaved/in-flight executions and interrupted attempts that produced no run row are
not counted. Deleting a test reduces `savedTests` but does not remove its retained
run history. No historical backfill or existing data normalization is performed.

## Storage and failure behavior

One PostgreSQL aggregate statement calculates the run counts, saved-test count and
measurement timestamp in one statement snapshot. It does not load result JSON or
call the bounded run-list API. No records are written. Exact all-time counts can
require scanning the table; this PR adds no cache, materialized counters or promise
of constant-time performance on large installations.

A failed query or inconsistent aggregate returns a sanitized compatibility 503
error, not a zero-filled success response. The endpoint has no date, website,
status or team filter contract. Counts cover all records visible to the configured
database role; there is no new tenant/authorization boundary. Restrict this API to
trusted development/staging access.

## Integration boundary

The dashboard continues to use its existing recent-run calculations. A later UI
integration must fetch this endpoint, handle null/unavailable percentages, and
label totals as saved records. The recent-history list remains bounded. Consumers
must not relabel its length as an all-time total. No native API, proxy, schema,
feature flag, LLM call or browser action is changed here.

## Verification

ASGI tests cover response fields, percentage rounding, empty history, inconsistent
counts and sanitized database failures. PostgreSQL tests create 64 synthetic run
rows with deliberately different `run_count` values, verify that history returns
only 50 while metrics count all 64, check mixed statuses/healing, and confirm
history survives saved-test deletion. A separate database test verifies empty
history. No actual project records or external websites are modified.

Local verification passed all 150 Python tests, including 20 PostgreSQL and 4
Chromium tests, plus 3 Node parser tests and `git diff --check`. Environment:
Windows, Python 3.11 and PostgreSQL 17 in an isolated disposable cluster. The
existing Starlette/httpx deprecation warning remains. Linux CI, PostgreSQL 18 and
full Docker deployment acceptance remain unverified locally.
