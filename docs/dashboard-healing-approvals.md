# Dashboard healing-decision adapter

This PR adds dashboard-style healing decision routes on FastAPI. It builds on the
suite compatibility branch without changing the dashboard proxy or native API.

## Routes

| Method | Route | Result |
| --- | --- | --- |
| GET | /compat/approvals | Array of saved decisions, newest first |
| POST | /compat/approvals | Save a reviewed decision; HTTP 200 |
| DELETE | /compat/approvals/{uuid} | Remove one decision; passed/deletedId response |

POST uses camelCase fields matching the dashboard:

```json
{
  "runId": "00000000-0000-0000-0000-000000000001",
  "stepName": "Click Login",
  "oldSelector": "role=button[name=\"Login\"]",
  "newSelector": "role=button[name=\"Sign In\"]",
  "oldTarget": "Login",
  "newTarget": "Sign In",
  "decision": "approved",
  "confidence": 0.9,
  "strategy": "semantic"
}
```

Replace the example run ID with a real saved run. Decision must be `approved` or
`rejected`. Required strings must be nonblank, run IDs must be UUIDs and optional
confidence must be finite and between zero and one. Unknown fields are rejected.
Confidence and strategy are optional submitted metadata, not independently
verified proof that healing is correct.

Before saving, the adapter reads that run's stored evidence and requires exactly
one healed step matching the submitted step name and old/new selectors. Target
names must match the dashboard's existing selector display extraction (`name="..."`
when present, otherwise the selector itself). Missing runs return 404; absent,
ambiguous, mismatched or unsupported evidence returns 409 without saving.

Responses explicitly map known database fields to `savedAt`, `runId`, `stepName`,
`oldSelector`, `newSelector`, `oldTarget`, `newTarget`, `decision`, `confidence` and
`strategy`. UUIDs and timestamps are serialized, Decimal confidence is numeric,
and nullable run references remain null. Store failures use sanitized compatibility
errors; verify the decision list before retrying an uncertain write.

## Resolver semantics and limits

Decisions use the existing `healed_selectors` table and approval store. Approved
mappings are available to the existing resolver's approved-memory lookup. Rejected
rows are not themselves reusable mappings. Rejection is NOT revocation of an older
approval: the existing lookup still chooses the latest approved row. Deleting an
approval can reveal an earlier approved mapping for that target. Review the full
decision history before treating rejection/deletion as a revocation mechanism.

No browser action, test run or automatic replay occurs when saving or deleting a
decision. Deleting a decision leaves the originating run intact. POST is not
idempotent; repeated submissions can create multiple decision rows. Nested rerun
results without an unambiguous top-level healed step require separate integration;
the adapter does not guess which execution was approved.

The current memory lookup is global by normalized old target, NOT scoped to origin,
team or test revision. Evidence matching does not fix that limitation or prove
business intent. This PR adds no authentication, authorization or multi-tenant
isolation. Restrict this API and resolver memory to trusted development/staging;
origin-scoped memory and access control remain gates before multi-site production
use. The native approval API remains unchanged and does not gain these checks.

## Remaining integration

The dashboard is still connected to Express. These routes alone do not enable a
proxy cutover. Instruction execution, authorized artifacts, metrics, access
control and combined deployment acceptance remain separate work. No new migration,
feature flag or model call is introduced.

## Verification

ASGI tests exercise mapping, validation, evidence matching, ambiguous and unhealed
steps, approve/reject handling, deletion and sanitized failures. External store
boundaries are mocked in these tests. An isolated PostgreSQL round-trip test uses
the real stores to verify rejection exclusion, approved resolver lookup, removal,
and retention of saved execution evidence. No external website writes are needed.

Local verification passed all 144 Python tests (including 18 PostgreSQL and 4
Chromium tests), plus 3 Node parser tests and `git diff --check`. Environment:
Windows, Python 3.11 and PostgreSQL 17 in an isolated disposable cluster. The
existing Starlette/httpx deprecation warning remains. Linux CI, PostgreSQL 18 and
full Docker deployment acceptance remain unverified locally.
