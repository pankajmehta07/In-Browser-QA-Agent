"""Opt-in tests create/drop uniquely named databases, never application tables."""

import asyncio
import os
import sys
import tempfile
import unittest
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import AsyncMock, patch

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo
from psycopg_pool import AsyncConnectionPool

from stores.migrations import migrate


def setUpModule():
    global _previous_policy
    if sys.platform == "win32":
        _previous_policy = asyncio.get_event_loop_policy()
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def tearDownModule():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(_previous_policy)


@unittest.skipUnless(os.getenv("MIGRATION_TEST_ADMIN_DSN"), "Requires isolated PostgreSQL admin DSN")
class PostgresMigrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.database = "qa_migration_test_" + uuid.uuid4().hex
        self.admin = await psycopg.AsyncConnection.connect(os.environ["MIGRATION_TEST_ADMIN_DSN"], autocommit=True)
        await self.admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(self.database)))
        self.addAsyncCleanup(self.drop_database)
        self.connection = await psycopg.AsyncConnection.connect(
            make_conninfo(os.environ["MIGRATION_TEST_ADMIN_DSN"], dbname=self.database), autocommit=True
        )
        self.addAsyncCleanup(self.connection.close)

    async def drop_database(self):
        try:
            await self.admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(self.database)))
        finally:
            await self.admin.close()

    async def scalar(self, query, params=None):
        cursor = await self.connection.execute(query, params)
        return (await cursor.fetchone())[0]

    async def test_status_does_not_create_ledger_or_tables(self):
        self.assertEqual([item.version for item in await migrate(self.connection)], [1, 2])
        self.assertIsNone(await self.scalar("SELECT to_regclass('public.schema_migrations')"))
        self.assertIsNone(await self.scalar("SELECT to_regclass('public.tests')"))

    async def test_fresh_install_repeat_and_existing_data_preserved(self):
        await migrate(self.connection, apply=True)
        await self.connection.execute("INSERT INTO tests (name, instruction) VALUES ('Keep me', '[]')")
        self.assertEqual(await migrate(self.connection, apply=True), [])
        self.assertEqual(await self.scalar("SELECT name FROM tests"), "Keep me")
        self.assertEqual(await self.scalar("SELECT COUNT(*) FROM schema_migrations"), 2)

    async def test_adopts_legacy_schema_and_preserves_history_on_delete(self):
        baseline = Path(__file__).resolve().parents[1] / "migrations" / "0001_initial.sql"
        await self.connection.execute(baseline.read_text(encoding="utf-8"))
        test_id = uuid.uuid4()
        await self.connection.execute("INSERT INTO tests (id, name, instruction) VALUES (%s, 'Legacy', '[]')", (test_id,))
        await self.connection.execute("INSERT INTO runs (test_id, status, result_json) VALUES (%s, 'passed', '{\"evidence\":\"original\"}')", (test_id,))
        await migrate(self.connection, apply=True)
        self.assertEqual(await self.scalar("SELECT name FROM tests"), "Legacy")
        self.assertEqual(await self.scalar("SELECT snapshot->>'name' FROM test_revisions"), "Legacy")
        await self.connection.execute("DELETE FROM tests WHERE id = %s", (test_id,))
        self.assertIsNone(await self.scalar("SELECT test_id FROM runs"))
        self.assertEqual(await self.scalar("SELECT result_json->>'evidence' FROM runs"), "original")

    async def test_failed_migration_rolls_back_ddl_and_ledger_entry(self):
        await migrate(self.connection, apply=True)
        with tempfile.TemporaryDirectory() as directory:
            from stores.migrations import DEFAULT_DIRECTORY
            target = Path(directory)
            for source in DEFAULT_DIRECTORY.glob("*.sql"):
                (target / source.name).write_text(source.read_text(), encoding="utf-8")
            (target / "0003_broken.sql").write_text("CREATE TABLE must_rollback (id INT); SELECT 1/0;", encoding="utf-8")
            with self.assertRaises(psycopg.errors.DivisionByZero):
                await migrate(self.connection, target, apply=True)
        self.assertIsNone(await self.scalar("SELECT to_regclass('public.must_rollback')"))
        self.assertEqual(await self.scalar("SELECT COUNT(*) FROM schema_migrations"), 2)

    async def test_checksum_conflict_prevents_further_changes(self):
        await migrate(self.connection, apply=True)
        await self.connection.execute("UPDATE schema_migrations SET checksum = 'changed'")
        with self.assertRaisesRegex(ValueError, "changed"):
            await migrate(self.connection, apply=True)

    async def test_concurrent_migrators_apply_once(self):
        async with await psycopg.AsyncConnection.connect(
            make_conninfo(os.environ["MIGRATION_TEST_ADMIN_DSN"], dbname=self.database), autocommit=True
        ) as other:
            changes = await asyncio.gather(migrate(self.connection, apply=True), migrate(other, apply=True))
        self.assertEqual(sorted(len(items) for items in changes), [0, 2])
        self.assertEqual(await self.scalar("SELECT COUNT(*) FROM schema_migrations"), 2)

    async def test_fresh_init_and_migrations_are_compatible(self):
        fresh = Path(__file__).resolve().parents[2] / "db" / "init.sql"
        await self.connection.execute(fresh.read_text(encoding="utf-8"))
        await self.connection.execute("INSERT INTO tests (name, instruction) VALUES ('Fresh', 'Click Login')")
        self.assertEqual(await self.scalar("SELECT revision FROM test_revisions"), 1)
        await migrate(self.connection, apply=True)
        self.assertEqual(await self.scalar("SELECT COUNT(*) FROM test_revisions"), 1)

    @asynccontextmanager
    async def version_store(self):
        from stores import test_store
        await migrate(self.connection, apply=True)
        async with AsyncConnectionPool(
            make_conninfo(os.environ["MIGRATION_TEST_ADMIN_DSN"], dbname=self.database), open=False
        ) as pool:
            with patch("stores.test_store.get_pool", new_callable=AsyncMock, return_value=pool):
                yield test_store

    async def test_store_records_create_edit_and_noop_without_duplicate_revision(self):
        async with self.version_store() as store:
            saved = await store.save_test({"name": "Original", "instruction": "Click Login"})
            self.assertEqual(saved["revision"], 1)
            updated = await store.update_test(str(saved["id"]), {"name": "Edited", "expected_revision": 1})
            self.assertEqual(updated["revision"], 2)
            unchanged = await store.update_test(str(saved["id"]), {"name": "Edited", "expected_revision": 2})
            self.assertEqual(unchanged["revision"], 2)
            history = await store.list_test_revisions(str(saved["id"]))
        self.assertEqual([item["snapshot"]["name"] for item in history], ["Edited", "Original"])

    async def test_simultaneous_edit_rejects_stale_writer(self):
        async with self.version_store() as store:
            saved = await store.save_test({"name": "Original", "instruction": "Click Login"})
            outcomes = await asyncio.gather(
                store.update_test(str(saved["id"]), {"name": "First", "expected_revision": 1}),
                store.update_test(str(saved["id"]), {"name": "Second", "expected_revision": 1}),
                return_exceptions=True,
            )
            self.assertEqual(sum(isinstance(item, store.RevisionConflict) for item in outcomes), 1)
            self.assertEqual(len(await store.list_test_revisions(str(saved["id"]))), 2)

    async def test_plan_roundtrip_clear_and_retained_history_after_delete(self):
        plan = {"schema_version": 1, "setup": [], "steps": [{"action": "click", "target": "Login", "value": None}], "cleanup": []}
        async with self.version_store() as store:
            saved = await store.save_test({"name": "Plan", "instruction": "Click Login", "plan": plan})
            self.assertEqual(saved["plan"], plan)
            updated = await store.update_test(str(saved["id"]), {"instruction": "Click Projects", "expected_revision": 1})
            self.assertIsNone(updated["plan"])
            await store.delete_test(str(saved["id"]))
            history = await store.list_test_revisions(str(saved["id"]))
        self.assertEqual(len(history), 2)
        self.assertIsNone(history[0]["test_id"])
        self.assertEqual(history[1]["snapshot"]["plan"], plan)

    async def test_direct_legacy_sql_update_also_creates_revision(self):
        async with self.version_store() as store:
            saved = await store.save_test({"name": "Legacy", "instruction": "Click Login"})
            await self.connection.execute("UPDATE tests SET name = 'Legacy edited' WHERE id = %s", (saved["id"],))
            history = await store.list_test_revisions(str(saved["id"]))
        self.assertEqual([item["revision"] for item in history], [2, 1])

    async def test_snapshot_failure_rolls_back_definition_edit(self):
        async with self.version_store() as store:
            saved = await store.save_test({"name": "Original", "instruction": "Click Login"})
            await self.connection.execute("ALTER TABLE test_revisions ADD CONSTRAINT reject_new_snapshot CHECK (revision < 2)")
            with self.assertRaises(psycopg.errors.CheckViolation):
                await store.update_test(str(saved["id"]), {"name": "Must roll back", "expected_revision": 1})
            current = await store.get_test_by_id(str(saved["id"]))
            self.assertEqual(current["name"], "Original")
            self.assertEqual(current["revision"], 1)
            self.assertEqual(len(await store.list_test_revisions(str(saved["id"]))), 1)

    async def test_import_preview_reads_destination_without_writing(self):
        from stores.import_preview import preview, read_destination
        async with self.version_store() as store:
            saved = await store.save_test({"name": "Retain", "instruction": "Click Login"})
            conninfo = make_conninfo(os.environ["MIGRATION_TEST_ADMIN_DSN"], dbname=self.database)
            destination = await asyncio.to_thread(read_destination, conninfo)
            report = preview({"format_version": 1, "records": [{"team_id": "local", "kind": "test", "id": str(saved["id"]), "data": {"name": "Imported", "instruction": "Click Login"}}]}, team="local", destination=destination)
            self.assertEqual(report["counts"]["rejected"], 1)
            self.assertEqual(report["items"][0]["issues"], ["destination_id_conflict"])
            self.assertEqual((await store.get_test_by_id(str(saved["id"])))["name"], "Retain")
            self.assertEqual(len(await store.list_test_revisions(str(saved["id"]))), 1)

    async def test_prototype_export_sql_is_team_scoped_and_excludes_secrets(self):
        await self.connection.execute("CREATE TABLE records (team_id TEXT, kind TEXT, id TEXT, data JSONB)")
        await self.connection.execute("CREATE TABLE test_revisions (team_id TEXT, test_id TEXT, revision INT, data JSONB)")
        await self.connection.execute("""INSERT INTO records VALUES
            ('local','test','one','{}'), ('other','test','two','{}'),
            ('local','secret','private','{}'), ('local','job','queued','{}')""")
        await self.connection.execute("INSERT INTO test_revisions VALUES ('local','one',1,'{}'), ('other','two',1,'{}')")
        query = (Path(__file__).resolve().parents[2] / "db" / "export-prototype.sql").read_text()
        cursor = await self.connection.execute(query.replace(":'team'", "%s"), ("local", "local"))
        exported = (await cursor.fetchone())[0]
        self.assertEqual([row["id"] for row in exported["records"]], ["one"])
        self.assertEqual([row["test_id"] for row in exported["revisions"]], ["one"])
        self.assertEqual(await self.scalar("SELECT COUNT(*) FROM records"), 4)

    async def test_saved_plan_persists_exact_snapshot_despite_later_edit_and_delete(self):
        from types import SimpleNamespace
        from core.saved_plan import execute_saved_plan
        candidate = {"schema_version": 1, "steps": [{"action": "check_visible", "target": "Login"}]}
        async with self.version_store() as store:
            saved = await store.save_test({"name": "Pinned original", "instruction": "Check Login", "plan": candidate})
            async def execute(*args, **kwargs):
                await store.update_test(str(saved["id"]), {"name": "Edited during execution", "expected_revision": 1})
                return {"status": "passed", "steps": [], "phases": {}}
            with patch("stores.run_store.get_pool", new_callable=AsyncMock, return_value=await store.get_pool()), \
                 patch("core.saved_plan.launch_browser", new_callable=AsyncMock, return_value=SimpleNamespace(page=SimpleNamespace(url="http://127.0.0.1:5173/"))), \
                 patch("core.saved_plan.navigate_to", new_callable=AsyncMock, return_value=True), \
                 patch("core.saved_plan.close_browser", new_callable=AsyncMock), \
                 patch("core.saved_plan.execute_plan", side_effect=execute):
                report = await execute_saved_plan(str(saved["id"]), 1, "http://127.0.0.1:5173/")
            await store.delete_test(str(saved["id"]))
        self.assertEqual(await self.scalar("SELECT result_json->'definition_snapshot'->>'name' FROM runs WHERE id = %s", (report["saved_run_id"],)), "Pinned original")
        self.assertEqual(await self.scalar("SELECT result_json->>'test_revision' FROM runs"), "1")
        self.assertTrue(await self.scalar("SELECT started_at IS NOT NULL FROM runs"))

    async def test_selected_suite_saves_only_selected_individual_runs(self):
        from types import SimpleNamespace
        from core.saved_suite import execute_selected_suite
        candidate = {"schema_version": 1, "steps": [{"action": "check_visible", "target": "Login"}]}
        async with self.version_store() as store:
            one = await store.save_test({"name": "One", "instruction": "Check Login", "plan": candidate})
            two = await store.save_test({"name": "Two", "instruction": "Check Login", "plan": candidate})
            await store.save_test({"name": "Excluded", "instruction": "Check Login", "plan": candidate})
            await store.update_test(str(one["id"]), {"name": "One edited", "expected_revision": 1})
            async def execute(*args, **kwargs):
                return {"status": "passed", "steps": [], "phases": {}}
            with patch("stores.run_store.get_pool", new_callable=AsyncMock, return_value=await store.get_pool()), \
                 patch("core.saved_plan.launch_browser", new_callable=AsyncMock, side_effect=lambda **kwargs: SimpleNamespace(page=SimpleNamespace(url="http://127.0.0.1:5173/"))), \
                 patch("core.saved_plan.navigate_to", new_callable=AsyncMock, return_value=True), \
                 patch("core.saved_plan.close_browser", new_callable=AsyncMock), \
                 patch("core.saved_plan.execute_plan", side_effect=execute):
                report = await execute_selected_suite([{"test_id": str(one["id"]), "revision": 1}, {"test_id": str(two["id"]), "revision": 1}], "http://127.0.0.1:5173/")
        self.assertEqual(report["counts"]["completed"], 2)
        self.assertEqual(await self.scalar("SELECT COUNT(*) FROM runs"), 2)
        cursor = await self.connection.execute("SELECT result_json->'definition_snapshot'->>'name' FROM runs")
        self.assertEqual({row[0] for row in await cursor.fetchall()}, {"One", "Two"})
