# FastAPI Integration Contracts

Status: proposed for team review; not implemented by this PR.

Baseline inspected: Fuse `develop` at `b829e099aca6bb92fd9b7e680c00e18f8d073810`, on 2026-11-12.

## 1. Decision and boundaries

Extend the existing `python-services/` FastAPI application. Port useful behavior from the local Python prototype into the existing service boundaries, with tests, rather than adding a second backend or replacing teammates' modules wholesale.

- Preserve the current Python API, CLI session/context behavior, approved selector memory, rerun classification, and audit comparison.
- Keep React/Vite for the dashboard and demo app. Node remains a frontend build/development requirement after the API migration.
- Keep the Express dashboard API operational until the replacement contract is verified against real PostgreSQL and browser execution.
- Do not merge the local `backend/` tree, dependency files, startup scripts, or schema wholesale into `develop`.
- This document proposes integration boundaries. It does not approve deployment changes, assert that another contributor's branch has been merged, or claim that the local prototype is production-ready.

Review the existing FastAPI update branches with their owners before porting overlapping changes. Each feature PR must name its dependencies and identify which behavior it reuses instead of duplicating.

## 2. Current implementation, not the target state

| Surface | Current shared-repository behavior |
| --- | --- |
| Dashboard | Browser requests use `/api` by default; its Vite proxy targets `http://server:4000` and removes `/api`. |
| Express | Port 4000; routes include `/health`, `/tests`, `/runs`, `/approvals`, `/run-instruction`, and `/run-test-suite`. Screenshots are exposed under `/screenshots`. |
| FastAPI | Separate service on port 8000; routes include `/health`, `/tests`, `/runs`, `/approvals`, `/instructions/run`, `/audit`, and `/audit/compare`. |
| Python instruction input | `/instructions/run` requires `instruction` and `url`. By default, instruction is structured JSON; natural-language handling is explicitly selected. |
| Python instruction output | The response exposes snake_case summary fields such as `saved_run_id`, `duration_ms`, and `root_cause`; it is not the dashboard's full result DTO. |
| Python storage | PostgreSQL relational tables `tests`, `runs`, and `healed_selectors`. Stores return database rows; some stored result payloads already contain camelCase fields. |
| Local prototype | A separate FastAPI implementation under `backend/`, with team-scoped JSONB records and additional features. It is reference code for porting, not the shared service's current runtime. |
| Docker | The shared Compose file runs both APIs, both frontends, and PostgreSQL 18. PostgreSQL is on the Compose network; the current file does not publish its port to the host. |

The local prototype's PostgreSQL 17 container, host port 55432, credentials, and volume are not interchangeable with the shared Compose deployment. Do not point a different PostgreSQL major version at an existing physical data directory.

## 3. Dashboard compatibility boundary

### Routing

Add a version-tested compatibility layer inside FastAPI, mounted under `/compat`. Keep the existing native Python routes unchanged. After cutover, configure the dashboard's `/api` proxy to target FastAPI and rewrite `/api/<path>` to `/compat/<path>`.

This explicit prefix prevents duplicate `/tests` or `/runs` routes from returning incompatible shapes to different callers. Do not rely on router registration order or blanket recursive key renaming.

| Browser request | Proposed FastAPI compatibility route | Required behavior |
| --- | --- | --- |
| `GET /api/health` | `GET /compat/health` | Return a successful health response; readiness must reflect required dependencies. |
| `GET /api/tests` | `GET /compat/tests` | Return a JSON array of dashboard test DTOs. |
| `POST /api/tests` | `POST /compat/tests` | Accept `name`, `instruction`, `variant`, and `reruns`; save exactly one definition. |
| `DELETE /api/tests/{id}` | `DELETE /compat/tests/{id}` | Delete only that definition; return 404 if absent; preserve saved run history. Never execute a test. |
| `GET /api/runs` | `GET /compat/runs` | Return dashboard run summaries, newest first. Preserve the existing list contract until pagination is explicitly introduced. |
| `GET /api/runs/{id}` | `GET /compat/runs/{id}` | Return the saved summary and its original complete result, not a reconstructed latest revision. |
| `POST /api/run-instruction` | `POST /compat/run-instruction` | Validate the request, execute through shared Python services, persist the run, and return the full dashboard result. |
| `POST /api/run-test-suite` | `POST /compat/run-test-suite` | Run only selected test IDs when supplied; otherwise run the permitted saved suite. Validate IDs and prerequisites. |
| `POST /api/approvals` | `POST /compat/approvals` | Accept the dashboard's camelCase approval fields and use the existing approval store/resolver path. |
| `GET /api/screenshots/{artifact}` | `GET /compat/screenshots/{artifact}` | Serve only validated evidence references owned by the relevant run/session. Add trace downloads under the same controlled evidence boundary when implemented. |

Compatibility handlers call shared Python services and stores directly. They must not proxy execution through Node or make internal HTTP calls to the native FastAPI endpoints.

Retain native Python request/response shapes for existing clients. Map camelCase only at the compatibility boundary using explicit DTOs and field-level conversions. The native `/instructions/run` summary alone is insufficient to populate the dashboard inspector.

### Request and response semantics

- Existing dashboard save requests keep their current fields. Validate nonblank names/instructions, supported variants, and bounded rerun counts server-side as well as in the UI.
- Resolve the target from the explicit validated URL or saved test configuration. For legacy requests without a URL, use the configured authorized demo target; never infer an arbitrary external target.
- Preserve the dashboard result fields used by the inspector: `status`, `savedRunId`, `durationMs`, `steps`, optional `runs`, `rootCause`, `screenshot`, and `accessibilityAudit`. Suite responses also provide counts and per-test results. Match existing consumers in contract fixtures before cutover.
- Map step fields such as `name`, `durationMs`, `selectorUsed`, `wasHealed`, and resolution metadata explicitly. Serialize UUIDs, dates, and numeric database values consistently; never invent missing evidence or confidence values.
- Expose a safe artifact URL in `screenshot.urlPath`; do not leak an absolute disk path or accept arbitrary filesystem paths in a request.
- Compatibility errors use the proper non-2xx status and `{ "status": "failed", "errorMessage": "..." }`, with sanitized messages. Native FastAPI error contracts remain unchanged.
- A genuine assertion failure is a completed execution result with failed status. Validation errors, unauthorized targets, missing records, and service failures must not be presented as successful execution.
- Preserve immediate response behavior until a separate job-aware frontend contract is introduced. Do not return a job ID where existing consumers expect an execution result. Durable workers may be introduced behind the service boundary first.
- Metrics must define their population and count execution attempts without double-counting suite aggregates. Do not label the length of a limited recent-run list as an all-time total.

## 4. PostgreSQL and evidence migration

Keep the shared relational schema as the starting point. Introduce ordered, recorded, additive migrations before adding new plan, revision, job, scan, or agent storage. New stores must have explicit ownership and referential rules; do not replace all tables with the local generic records store.

The storage PR must include:

1. A backup/restore rehearsal in an isolated database and a migration ledger. Update fresh-install SQL as appropriate, but do not assume container initialization scripts migrate an existing volume.
2. Additive columns/tables for versioned plans and revisions while keeping existing tests/runs readable. Define optimistic revision checks before allowing concurrent edits.
3. A dry-run importer that reports source counts, accepted/skipped/rejected records, ID conflicts, unsupported kinds, and missing references without writing data.
4. Explicit mapping from local record kinds to destination stores. Map tests, run results, revisions, and approved selector records first; migrate scans/jobs/agent sessions only after their corresponding schemas exist.
5. Preserve valid source IDs where safe. Record source-to-destination mappings when conversion is required, and make repeated imports idempotent. Preserve historical plans and do not silently execute imported drafts or queued jobs.
6. Validate evidence references and copy approved artifacts with integrity checks. Keep source files intact. A missing screenshot should be reported rather than replaced with another run's image.
7. Keep unknown or sensitive records out of automatic import. Encrypted secrets require an explicit key/ownership migration procedure; never import ciphertext assuming a different deployment can decrypt it.
8. Verify counts, references, foreign keys, and sample readbacks before enabling migrated features.

Deleting a saved test must retain execution evidence and run history; the existing `runs.test_id` foreign key already uses `ON DELETE SET NULL`. Cancellation and cleanup must not be confused with deleting historical results.

Never run `docker compose down -v` as a migration step. That removes persisted volumes. Follow the reviewed additive migration and backup procedure instead, even though the current schema file's historical header suggests rebuilding the database.

## 5. Runtime configuration and cutover

Keep existing Compose service names, ports, and database settings unchanged during the preparation PRs. Reuse the Python service's `DB_HOST`, `DB_PORT`, `DB_NAME`, and `DB_USER`/`DB_PASSWORD` configuration; do not introduce a conflicting second database configuration source without explicit precedence and tests.

Secrets come from untracked deployment environment configuration, never committed examples with real values or frontend `VITE_` variables. Keep provider models configurable, distinguish app budgets from provider quotas, and pass credentials only through approved secret/session bindings.

Cut over in this order:

1. Land CI and additive storage support. Verify native API/CLI behavior is unchanged.
2. Implement and contract-test the compatibility layer, supported execution actions, suites, evidence, and errors. Keep Express as the current dashboard target.
3. Run a real smoke test with an isolated PostgreSQL instance and the authorized demo app: save, list, run, inspect history/evidence, approve a selector change, and delete a definition without executing anything.
4. Test both local development and Compose networking. `server`/`python-services` hostnames resolve inside Compose, not in an ordinary host process; target URLs used by a container must resolve from that container.
5. Switch only the dashboard API proxy/configuration in a dedicated cutover change. Keep `/api` stable for the browser. Specify any direct API-base override and evidence URL behavior in tests.
6. Observe health, contract errors, job status, evidence access, and persistence after restart. Keep provider access optional for deterministic tests.
7. Retire Node API startup references only after team review and end-to-end parity. Do not remove Node from the frontend build toolchain.

Rollback before retirement restores the previous proxy/application configuration and leaves additive schema changes in place. Test the previous application against the expanded schema and retain a recorded cutover boundary. Do not continue normal writes through both APIs after rollback; reconcile any newer records before re-enabling the new service. A destructive schema downgrade is not the default rollback strategy.

## 6. Feature-port sequence

Each feature includes backend support, necessary schema changes, UI wiring, and tests. Do not expose a button before its backend path is usable.

1. Dashboard request correctness, reviewed architecture contracts, and CI.
2. Versioned storage and validated data import.
3. Shared execution, durable jobs, compatibility adapters, and API cutover.
4. Reusable AI service controls and richer Test Library operations.
5. Encrypted saved sessions and access controls; authorized demo workflow expansion can proceed independently where compatible.
6. Scoped passive Site Analysis, persisted findings, exact-rule rechecks, and grounded summaries; preserve native audit comparison.
7. Separately authorized active/security checks with explicit inconclusive outcomes.
8. Page Agent discovery and persistent conversations, followed by grounded draft generation/review and publication to the shared runner.
9. Voice, visual baselines, schedules, and workbook import as separate reviewed features.
10. Updated operational documentation and approved legacy runtime retirement.

Keep observed facts separate from model suggestions. Generated tests remain drafts until reviewed; custom record names and optional cleanup remain supported. AI never determines assertion pass/fail. Preserve authorized-scope checks and never promote page text into instructions or executable code.

## 7. Acceptance gates and review checklist

- Contract fixtures cover dashboard requests, full execution/suite results, UUID/date/numeric conversions, errors, selected IDs, missing data, and evidence URLs.
- Regression tests prove one save produces one definition and deleting a definition never starts an instruction or suite.
- Native API, persistent CLI context, approved selector memory, rerun classification, and audit comparison continue to work.
- Migration tests cover empty and existing databases, repeated import, conflicts, invalid references, unsupported kinds, and missing evidence. Backup restoration is rehearsed outside the live database.
- Integration tests cover the dashboard against FastAPI and PostgreSQL, including restart behavior. Mocked UI tests alone are not cutover acceptance.
- Provider tests use mocks in CI. No external write/security probes or real account-lockout tests run in CI.
- No new feature is called production-ready solely because its schema validates or its mocked tests pass.
- Maintainers review ownership of overlapping backend changes, storage migration, deployment switch, and rollback. The person submitting the PR must not claim team approval in advance.

## Source references

These repository-relative links describe the inspected baseline. Future implementations must update this document when contracts change.

- [Dashboard request helper](../apps/dashboard/src/api.js) and [dashboard consumers](../apps/dashboard/src/main.jsx)
- [Vite proxy](../apps/dashboard/vite.config.js) and [shared Compose configuration](../docker-compose.yaml)
- [Express API](../server/src/index.js)
- [FastAPI application](../python-services/api/main.py)
- [Instruction API](../python-services/api/routers/instructions.py), [test API](../python-services/api/routers/tests.py), and [run API](../python-services/api/routers/runs.py)
- [Approval API](../python-services/api/routers/approvals.py) and [audit API](../python-services/api/routers/audit.py)
- [Python runner](../python-services/core/runner.py), [CLI](../python-services/cli/run.py), and [resolver](../python-services/core/resolver.py)
- [Database schema](../db/schema.sql), [connection configuration](../python-services/stores/db.py), [test store](../python-services/stores/test_store.py), and [run store](../python-services/stores/run_store.py)
