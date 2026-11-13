# Versioned test plans and definition history

Branch: `feature/versioned-test-plans`. Depends on the database-migrations PR.
This extends Fuse's existing `python-services/` service, not the prototype backend.

## Delivered

- Migration `0002_test_revisions.sql` adds nullable `tests.plan`, `tests.revision`,
  and `test_revisions` snapshots. Fresh-install SQL has the equivalent schema.
- Existing tests receive one snapshot of their current definition. Previous edits
  cannot be reconstructed; the migration does not invent historical versions.
- Database triggers increment revisions and record snapshots for definition changes,
  including SQL writes outside the Python store. A no-op edit creates no revision.
- Snapshots include name, instruction, variant, reruns, plan, revision and timestamps.
  The definition and its snapshot are saved in the same database transaction.
- Deleting a definition leaves both existing run history and definition snapshots.
  Snapshot `test_id` becomes null; `original_test_id` retains the original UUID.
- Snapshots have no application edit/delete API. Database administrators can still
  modify them; this is not tamper-proof auditing or a retention-policy implementation.

Run the reviewed [backup and migration procedure](database-migrations.md) before
deploying this store version. Existing volumes must apply migration 0002 explicitly;
initialization scripts do not upgrade them. No migration runs on API startup.

## Native API compatibility

Existing create/update fields are still accepted. Test responses gain `revision`
and `plan`. Existing instruction execution remains unchanged. The dashboard still
uses Express; this PR does not switch its proxy or expose a new plan editor.

### Optional structured plan

POST `/tests` or PUT `/tests/{id}` can include:

```json
{
  "name": "Project navigation",
  "instruction": "Click Projects. Check that Projects is visible.",
  "plan": {
    "schema_version": 1,
    "setup": [],
    "steps": [
      {"action": "click", "target": "Projects"},
      {"action": "check_visible", "target": "Projects"}
    ],
    "cleanup": []
  }
}
```

Plans use the current runner action vocabulary: `goto`, `type`, `click`,
`check_visible`, `check_contains`. `goto` retains the current heading-oriented
runner meaning, not arbitrary URL navigation. Unsupported actions/versions,
unknown plan or step fields, blank targets, empty test steps and missing required
values return 422. Setup and cleanup default to empty lists. Counts and text lengths
are bounded. Custom names are preserved; `fixture_name` is not required.

Plan storage is not execution. This PR neither submits the stored setup/test/cleanup
lists to Playwright nor verifies that a target exists on the website. The shared
execution/adapter PR must wire plan execution, permissions, assertions, cleanup
reporting and exact run-to-plan snapshots before advertising those behaviors.
Saved `instruction` remains the existing execution input in the meantime.

An instruction edit without a replacement plan clears the old plan. As a
conservative database rule, changing instruction text while leaving the exact same
plan also clears it. Rename-only edits preserve the plan. An explicit `"plan": null`
clears it. Changing the plan alone does not rewrite instruction text; clients must
keep both aligned until the execution cutover.

### Concurrent editing

Read the current test, then include its revision in PUT `/tests/{id}`:

```json
{"name": "Updated name", "expected_revision": 1}
```

Updates lock the test row while checking and saving. If it changed, the response is:

```json
{
  "detail": {
    "message": "The test changed; reload before saving again",
    "current_revision": 2
  }
}
```

HTTP status is 409. Reload, review and reconcile the edit instead of silently
retrying with the latest revision. Unknown IDs remain 404. Invalid revision values
return 422. Legacy clients may omit `expected_revision`; their updates still create
snapshots but retain last-write-wins semantics. Therefore lost-update protection
is opt-in until every editor supplies the revision.

### History

GET `/tests/{id}/revisions` returns snapshots newest first. The ID must be a UUID.
History remains readable by that original UUID after deletion. An unknown ID with
no definition or history returns 404. This endpoint currently returns all revisions;
pagination and retention policy are future work.

No credentials should be embedded in test instructions or plans. Snapshot history
retains previous values, including after a definition is deleted. Use approved
secret/session bindings when those are implemented; this PR adds no encryption,
ownership boundary, restore endpoint, or automatic redaction.

## Verification

Run the CI unit suite and opt-in PostgreSQL tests as described in
[Continuous integration](continuous-integration.md). The existing migration CI
job discovers this PR's additional database cases. Tests cover legacy backfill,
fresh initialization, plan validation/round-trip, no-op edits, retained history,
simultaneous stale edits, direct SQL changes and snapshot-write rollback.

The import writer remains separate. A dependent [saved-plan execution PR](saved-plan-execution.md)
adds opt-in phase execution and exact snapshots in run JSON; dashboard cutover and
relational run-to-revision linkage remain later work.
