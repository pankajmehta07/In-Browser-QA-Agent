# Prototype import preview

Branch: `feature/import-preview`. Depends on the versioned-test-plans PR.

This is a read-only preflight, not a data-import command. It does not modify a
source export, initialize a database, write destination rows, copy evidence, or
execute tests/jobs. There is deliberately no `--apply` option. A transactional,
idempotent writer and its source-to-destination ledger require a separate PR.

## 1. Export one authorized prototype team

The prototype has team-scoped `records` and `test_revisions` tables. The shared
Fuse schema is different. Do not restore the prototype dump over the shared DB.

Use a PostgreSQL client connected to the prototype SOURCE with read-only access.
Configure its `PGHOST`, `PGPORT`, `PGDATABASE`, and `PGUSER` appropriately, with a
protected password file or interactive password prompt. Do not put passwords in
commands or commit exports. This operation is manual and never runs at startup.

From the integration repository root, with `psql` on PATH:

```powershell
$export = Join-Path $env:TEMP 'browserqa-prototype-export.json'
psql -X -qAt -v ON_ERROR_STOP=1 -v team=local -f db/export-prototype.sql -o $export
```

Check the exit code and do not use a partial output after an error. Choose a new
filename to avoid overwriting an earlier export. The SQL is one SELECT statement,
giving the exported records and revisions a consistent snapshot. It exports only
tests, runs, approvals and definition revisions from that team. Secret/session,
member, cache, usage, queued-job, scan and agent-session records are excluded.

Exports can still contain sensitive instructions or historical results. Store them
outside the repository, restrict filesystem access, and review/redact them using an
approved process. Read-only preview does not sanitize or delete the source file.
Preview accepts at most 20 MiB / 10,000 rows, counting definitions and revisions;
oversized exports fail explicitly rather than silently truncating records.

## 2. Run an offline preview

With the existing Python dependencies installed, run from `python-services/`:

```powershell
python -m stores.import_preview "$env:TEMP/browserqa-prototype-export.json" --team local
```

No database connection occurs by default. The JSON report has `mode: preview`,
`writes_performed: false`, `destination_checked: false`, counts and per-row items.
Each item identifies its zero-based index/section, recognized kind, proposed
destination table/UUID, issues and verified evidence hashes. It does not echo
instructions, passwords, result payloads, filenames or unsupported non-UUID IDs.

Outcomes:

- `candidate`: supported shape and references under the checks performed.
- `rejected`: malformed, conflicting, incomplete or unsupported mapping.
- `skipped`: a different team or an unsupported/sensitive record kind.

Exit 0 means preview completed without rejected rows (skips may still exist), exit
2 means the report contains rejected rows, and exit 1 means preview could not
complete. No exit code authorizes an import. Offline candidates have not been
checked for collisions in a destination. Review every skipped/rejected record.

## 3. Check the shared destination and evidence

Configure the existing `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
for an isolated rehearsal copy of the shared DESTINATION, migrated through 0002.
Do not reuse the source client variables assuming they configure the Python store.
Host access to Compose PostgreSQL requires an explicitly reachable address; the
current Compose file does not publish a host database port.

```powershell
python -m stores.import_preview "$env:TEMP/browserqa-prototype-export.json" --team local --against-database --artifact-root D:/ML_Projects/In_Browser_QA_Agent/server/data
```

`--against-database` reads IDs in a repeatable-read, read-only transaction. It checks
definitions, runs, selector decisions and `(original_test_id, revision)` history
keys, including IDs reserved by deleted definitions. It does not migrate schemas,
merge rows or auto-renumber conflicting UUIDs. Use a read-only database role when
available. No connection string or source payload is printed on failure.

`--artifact-root` is the existing SOURCE evidence directory, not a copy destination.
Only local `screenshots/<file>` and `traces/<file>` references are recognized.
Remote URLs, traversal and resolved paths escaping the root are rejected. Missing
files or files above 20 MiB are reported. Existing files are read and SHA-256 hashed,
not moved or copied. Without an evidence root, referenced artifacts produce
`evidence_not_checked`, not a claim that they exist. Hashes record the observed file
bytes; they do not verify image content or prevent later filesystem changes.

## Supported mapping boundaries

| Source | Proposed destination | Boundary |
| --- | --- | --- |
| `test` | `tests` | UUID, nonblank name/instruction, known DOM variant, 1-5 reruns, timestamps and supported plan |
| `run` | `runs` | Completed individual result, valid status, test reference, numeric summary and evidence checks |
| approved `approval` | `healed_selectors` | Required selector-decision fields, confidence and optional run reference |
| revision row | `test_revisions` | Parent test, positive revision, contiguous complete history and matching latest definition |

Valid UUIDs are preserved in the proposed mapping. Duplicate source IDs reject
both rows. Existing destination IDs require review even if the content might be
identical; this PR has no applied-import ledger to prove equivalence/idempotence.
Definitions at revision 1 may omit history; later versions require every revision.
No unavailable history is invented. Orphan history is rejected rather than being
attached to an unrelated definition. A rejected parent blocks dependent records.

Simple prototype plan fields `setupSteps`, `steps`, `cleanupSteps` can be validated
against shared version-1 `setup`, `steps`, `cleanup`. Unknown plan metadata or
unsupported actions are rejected, never silently dropped. Custom names and empty
cleanup remain valid. No LLM is called to guess mappings or business outcomes.

Unmapped test properties such as `targetUrl`, `useSavedSession`, `credentialRef`,
visual settings or Page Agent provenance reject the definition with
`unmapped_test_fields`: those require reviewed destination storage, secret/ownership
migration and execution support. This tool intentionally cannot certify all current
prototype tests as compatible. Unsupported grouped/suite runs are rejected to avoid
silently double-counting execution history. Original run payloads and metric
semantics must be preserved/reconciled by the later writer; candidate is not a
complete insert payload or permission to discard unmapped information.

## Common issues

- `destination_id_conflict`: review the existing row; do not overwrite it.
- `duplicate_source_id`: resolve duplicated entries in a reviewed export copy.
- `unsupported_plan`: port the action/metadata contract before importing.
- `incomplete_revision_history` / `latest_revision_mismatch`: re-export consistent,
  complete definitions and histories; do not synthesize missing revisions.
- `missing_test_reference` / `missing_run_reference`: include a valid parent or
  confirm it exists in the checked destination without a conflicting source row.
- `unsafe_evidence_reference` / `evidence_missing`: resolve the correct local
  artifact mapping; do not substitute evidence from another execution.

An operator must still review team-to-destination authorization, secrets, scope,
timestamps, evidence, historical plan semantics and application readbacks. The
shared schema currently has no team ownership column; selecting a source team
does not add multi-tenancy to the destination. Nothing is imported by this PR.

## Verification

The existing Python unit job discovers preview tests automatically. The PostgreSQL
migration job also verifies conflict detection without modifying destination test
definitions or revision history. All fixtures are synthetic; tests do not read
real project records or call external providers/websites.

Local verification for this PR: 70 Python tests (including 14 PostgreSQL cases)
passed on Windows / Python 3.11 / PostgreSQL 17. PostgreSQL 18/Linux execution
awaits GitHub CI. The existing non-failing Starlette httpx deprecation warning
remains unchanged. The export SELECT was exercised against synthetic prototype
tables; no real prototype export was created or inspected during development.
