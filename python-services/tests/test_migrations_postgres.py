"""Opt-in tests create/drop uniquely named databases, never application tables."""

import asyncio
import os
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.conninfo import make_conninfo

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
        self.assertEqual([item.version for item in await migrate(self.connection)], [1])
        self.assertIsNone(await self.scalar("SELECT to_regclass('public.schema_migrations')"))
        self.assertIsNone(await self.scalar("SELECT to_regclass('public.tests')"))

    async def test_fresh_install_repeat_and_existing_data_preserved(self):
        await migrate(self.connection, apply=True)
        await self.connection.execute("INSERT INTO tests (name, instruction) VALUES ('Keep me', '[]')")
        self.assertEqual(await migrate(self.connection, apply=True), [])
        self.assertEqual(await self.scalar("SELECT name FROM tests"), "Keep me")
        self.assertEqual(await self.scalar("SELECT COUNT(*) FROM schema_migrations"), 1)

    async def test_adopts_legacy_schema_and_preserves_history_on_delete(self):
        baseline = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
        await self.connection.execute(baseline.read_text(encoding="utf-8"))
        test_id = uuid.uuid4()
        await self.connection.execute("INSERT INTO tests (id, name, instruction) VALUES (%s, 'Legacy', '[]')", (test_id,))
        await self.connection.execute("INSERT INTO runs (test_id, status, result_json) VALUES (%s, 'passed', '{\"evidence\":\"original\"}')", (test_id,))
        await migrate(self.connection, apply=True)
        self.assertEqual(await self.scalar("SELECT name FROM tests"), "Legacy")
        await self.connection.execute("DELETE FROM tests WHERE id = %s", (test_id,))
        self.assertIsNone(await self.scalar("SELECT test_id FROM runs"))
        self.assertEqual(await self.scalar("SELECT result_json->>'evidence' FROM runs"), "original")

    async def test_failed_migration_rolls_back_ddl_and_ledger_entry(self):
        await migrate(self.connection, apply=True)
        with tempfile.TemporaryDirectory() as directory:
            from stores.migrations import DEFAULT_DIRECTORY
            target = Path(directory)
            (target / "0001_initial.sql").write_text((DEFAULT_DIRECTORY / "0001_initial.sql").read_text(), encoding="utf-8")
            (target / "0002_broken.sql").write_text("CREATE TABLE must_rollback (id INT); SELECT 1/0;", encoding="utf-8")
            with self.assertRaises(psycopg.errors.DivisionByZero):
                await migrate(self.connection, target, apply=True)
        self.assertIsNone(await self.scalar("SELECT to_regclass('public.must_rollback')"))
        self.assertEqual(await self.scalar("SELECT COUNT(*) FROM schema_migrations"), 1)

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
        self.assertEqual(sorted(len(items) for items in changes), [0, 1])
        self.assertEqual(await self.scalar("SELECT COUNT(*) FROM schema_migrations"), 1)
