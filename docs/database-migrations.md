# Database migrations

The migration infrastructure depends on the project CI PR. It does not cut the
dashboard over to FastAPI or import the local prototype. Migration 0002 adds
[versioned test definitions](versioned-test-plans.md) in a dependent feature PR;
the dry-run importer and execution cutover remain separate work.

## How it works

- SQL lives in `python-services/migrations/`, so it is included in the existing
  Python Docker build context.
- `0001_initial.sql` establishes the current shared `tests`, `runs`, and
  `healed_selectors` schema. It can adopt an existing compatible installation.
- `0002_test_revisions.sql` adds plan storage and revision snapshots without
  replacing existing tests or runs. See the versioned-plan API documentation above.
- `public.schema_migrations` records each version, filename, SHA-256 checksum and
  application time. Checksums normalize CRLF/LF for Windows/Linux checkouts.
- Applied SQL files are immutable. Add a higher numbered migration for changes.
  Unknown ledger versions, changed checksums and out-of-order additions are refused.
- Each migration and its ledger entry commit together. A failing migration rolls
  back; earlier successfully committed migrations remain applied. Fix an unapplied
  file or create a forward repair, then retry; never rewrite applied SQL.
- A session-level PostgreSQL advisory lock serializes migration commands. Use a
  dedicated autocommit connection, not an API pool connection.
- `status` performs no writes. `apply` is explicit; API startup does not migrate.
  Stop application writers during upgrades and rehearse against a restored copy.

`CREATE TABLE IF NOT EXISTS` does not repair arbitrary schema drift. Review the
existing schema against `db/schema.sql` before adopting the baseline. The ledger
validates migration history, not every hand-edited column or constraint. Do not
use baseline adoption as proof that an unknown database matches this application.

## Docker: inspect, back up, rehearse, apply

Run from the repository root with Docker Desktop running and the repository's
untracked root `.env` configured. Never use `docker compose down -v` to upgrade.
Do not use the local prototype's port 55432 or its PostgreSQL 17 volume with this
repository's PostgreSQL 18 container.

1. Start PostgreSQL and inspect pending migrations. `run --rm --no-deps` creates
   a temporary Python service container, using its existing database environment;
   it does not start another API server.

   ```powershell
   docker compose up -d --wait postgres
   docker compose run --rm --no-deps python-services python -m stores.migrations status
   ```

2. Quiesce writers and create a backup. The dump remains in the container and is
   copied as a binary file, avoiding PowerShell binary redirection problems.
   Store backups outside Git, restrict access, and check every command succeeded.

   ```powershell
   docker compose stop server python-services
   $backup = "qa-agent-$(Get-Date -Format yyyyMMdd-HHmmss).dump"
   $backupPath = Join-Path $env:TEMP $backup
   docker compose exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/qa-agent-before-migration.dump'
   docker compose cp postgres:/tmp/qa-agent-before-migration.dump $backupPath
   ```

3. Restore into a NEW isolated rehearsal database, never over the live database.
   The database owner must have permission to create it. Keep the rehearsal name
   separate from `POSTGRES_DB` and retain it until readback checks are complete.

   ```powershell
   $rehearsal = "qa_restore_$(Get-Date -Format yyyyMMddHHmmss)"
   docker compose exec -T postgres sh -c 'createdb -U "$POSTGRES_USER" "$1"' sh $rehearsal
   docker compose exec -T postgres sh -c 'pg_restore -U "$POSTGRES_USER" --exit-on-error --no-owner -d "$1" /tmp/qa-agent-before-migration.dump' sh $rehearsal
   docker compose run --rm --no-deps -e "DB_NAME=$rehearsal" python-services python -m stores.migrations apply
   docker compose run --rm --no-deps -e "DB_NAME=$rehearsal" python-services python -m stores.migrations status
   docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$1" -c "SELECT COUNT(*) FROM tests; SELECT COUNT(*) FROM runs; SELECT COUNT(*) FROM healed_selectors; SELECT * FROM schema_migrations;"' sh $rehearsal
   ```

   Compare counts, sample IDs, saved results, foreign keys and approval records
   with the source. Run application readbacks against the rehearsal instance
   before approving a production upgrade. A successful dump alone is not a
   restore rehearsal. Evidence files require a separate protected backup; database
   dumps do not contain screenshots or traces stored on disk.

4. Only after review and successful rehearsal, apply to the configured database.
   If any command fails, stop and investigate before restarting writers.

   ```powershell
   docker compose run --rm --no-deps python-services python -m stores.migrations apply
   docker compose run --rm --no-deps python-services python -m stores.migrations status
   docker compose start server python-services
   ```

Rollback normally restores the prior application configuration and leaves additive
schema changes intact. This tool deliberately has no destructive `down` command.
Restoring an old backup over live data can lose newer writes and requires explicit
operator review and reconciliation; do not automate that as an error handler.

## Host development

Activate a Python 3.11+ environment with `python-services/requirements.txt` installed.
Set `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, and `DB_PASSWORD` in that process
to the intended database, then run from `python-services/`:

```powershell
python -m stores.migrations status
python -m stores.migrations apply
```

The CLI reuses the existing Python DB configuration. It does not automatically
load `server/.env` or publish a PostgreSQL host port. Inside Compose, `postgres`
resolves through Docker networking; host processes need an explicitly reachable
database address. Do not put credentials in command history or commit them.

## Adding migrations

Use `0002_descriptive_name.sql`, then increasing numeric prefixes. SQL must be
reviewed and transactional: no `BEGIN`/`COMMIT`, `VACUUM`, concurrent index creation,
or other commands that escape or cannot run in a transaction. Keep changes
additive and compatible with current native API and legacy consumers. Update
`db/schema.sql` and `db/init.sql` for equivalent fresh installs. Initialization
scripts run only for new volumes; they never replace migrations for old volumes.

## Verification

From the root with dependencies installed:

```powershell
$env:PYTHONPATH = 'python-services'
python -X utf8 -m unittest discover -s python-services/tests -v
```

Database integration tests are skipped unless `MIGRATION_TEST_ADMIN_DSN` points
to an explicitly isolated disposable PostgreSQL instance with CREATEDB permission.
They create/drop randomly named `qa_migration_test_*` databases. Never point this
variable at a shared or production cluster. CI supplies an ephemeral PostgreSQL 18
service. Tests cover fresh install, legacy adoption, read-only status, repeat
application, history retention, checksum refusal, failed-DDL rollback and concurrent
migrators. Provider calls and external website probes are not involved.

Local verification for this PR: 36 Python tests (including six real PostgreSQL
integration tests) and three Node parser tests passed on Windows, Python 3.11 and
PostgreSQL 17. A custom-format dump/restore rehearsal preserved sample test/run/
approval rows and the ledger, followed by a no-op migration rerun. The temporary
cluster was stopped afterward; no project database was modified. PostgreSQL 18
and Linux verification remain for GitHub CI. The existing non-failing Starlette
httpx deprecation warning remains unchanged. Docker-specific operator commands
were not exercised locally because Docker Desktop was unavailable.
