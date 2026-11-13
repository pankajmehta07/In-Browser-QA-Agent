# Dashboard test editing and revision history

This PR adds compatibility routes for revision-aware saved-test editing and
history inspection. It builds on the metrics branch without wiring the dashboard
to FastAPI or changing native endpoints.

## Update a saved definition

`PUT /compat/tests/{test_id}`

```json
{
  "name": "Login success",
  "instruction": "Check Login",
  "variant": "original",
  "reruns": 1,
  "expectedRevision": 2
}
```

This route requires a complete name/instruction/variant/reruns definition, plus
the positive integer revision read by the editor. It is not a partial PATCH.
Boolean revisions, blank names/instructions, unsupported variants, invalid rerun
counts, malformed structured plans and unknown fields are rejected with 422.
Missing records return 404; updates do not create a replacement test.

Plan handling delegates to the existing versioned store:

- Omitted `plan`: preserve it for metadata-only edits; invalidate it if the
  instruction changes so execution cannot silently use an outdated plan.
- `plan: null`: explicitly clear it.
- Supplied `plan`: validate the existing supported TestPlan schema and store it
  together with the definition edit.

The database transaction locks the current row, checks `expectedRevision` and
atomically updates the definition and its revision snapshot. A stale edit returns
409 with `errorMessage` and `currentRevision`. The adapter never retries it or
silently replaces the submitted revision with the latest one. Reload and review
the new definition before submitting another explicit save.

An actual definition change advances the revision. A no-op does not create a
duplicate revision. Success returns the existing dashboard test DTO including
`revision`, `createdAt`, `updatedAt` and `plan`. Unexpected storage failures return
a sanitized compatibility 503; inspect the saved definition before retrying an
uncertain write.

## Inspect history

`GET /compat/tests/{test_id}/revisions`

Returns newest-first revision entries with `id`, nullable `testId`,
`originalTestId`, `revision`, `createdAt` and `snapshot`. Snapshot contents retain
their existing stored schema and are not rewritten into a new plan format.
Deleting a saved test leaves these historical entries accessible through its
original ID; `testId` then becomes null. An unknown ID with no history returns 404.
An existing test with no history returns an empty array, not fabricated snapshots.

History is read-only. There is no automatic restore endpoint; intentionally
restoring an older definition requires a new reviewed update against the current
revision. Deleted tests cannot be edited or executed just because history exists.
The history list is currently unpaginated, like the native history API.

## Integration and access boundaries

The dashboard's current save flow does not call this endpoint or send
`expectedRevision`. A later editor integration must load the revision, submit the
full definition, surface conflicts and avoid automatic resubmission. No UI, proxy,
native update behavior, schema migration, feature flag, browser action or LLM call
is changed here. Native clients retain their existing optional revision check.

Snapshots may contain test data; this endpoint is not a general secret redaction
system. No authentication, per-team ownership or production access boundary is
added. Restrict the API to trusted development/staging until those gates are met.

## Verification

ASGI tests cover full update mapping, omitted/cleared plans, stale edits, invalid
definitions, missing records, retained history and sanitized errors. A PostgreSQL
round-trip test verifies no-op revision stability, instruction-change plan
invalidation, stale-write rejection, explicit replacement plan, and history after
deletion. Existing concurrent-writer store tests remain in the suite. No actual
project data or external website is modified.

Local verification passed all 159 Python tests (including 21 PostgreSQL and 4
Chromium tests), 3 Node parser tests and `git diff --check`. Environment: Windows,
Python 3.11 and PostgreSQL 17 in an isolated disposable cluster. The existing
Starlette/httpx deprecation warning remains. Linux CI, PostgreSQL 18 and combined
Docker deployment acceptance remain unverified locally.
