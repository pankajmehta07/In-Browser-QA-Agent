"""Explicit, transactional PostgreSQL migrations; never run on API startup."""

import argparse
import asyncio
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg

from stores.db import _build_conninfo


DEFAULT_DIRECTORY = Path(__file__).resolve().parents[1] / "migrations"
LOCK_ID = 731029184


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    checksum: str
    sql: str


def load_migrations(directory=DEFAULT_DIRECTORY):
    found = []
    versions = set()
    for path in sorted(Path(directory).glob("*.sql")):
        match = re.fullmatch(r"([0-9]{4})_([a-z][a-z0-9_]*)\.sql", path.name)
        if not match or int(match[1]) == 0:
            raise ValueError(f"Invalid migration filename: {path.name}")
        version = int(match[1])
        if version in versions:
            raise ValueError(f"Duplicate migration version: {version}")
        versions.add(version)
        sql = path.read_text(encoding="utf-8")
        if not sql.strip():
            raise ValueError(f"Empty migration: {path.name}")
        found.append(Migration(version, path.name, hashlib.sha256(sql.encode()).hexdigest(), sql))
    if not found:
        raise ValueError("No SQL migrations found")
    return sorted(found, key=lambda item: item.version)


def plan_migrations(available, applied):
    by_version = {item.version: item for item in available}
    applied_versions = set()
    for version, name, checksum in applied:
        item = by_version.get(version)
        if item is None:
            raise ValueError(f"Unknown applied migration: {version}; use matching application code")
        if item.name != name or item.checksum != checksum:
            raise ValueError(f"Applied migration {version} changed; add a new migration instead")
        applied_versions.add(version)
    pending = [item for item in available if item.version not in applied_versions]
    if applied_versions and any(item.version < max(applied_versions) for item in pending):
        raise ValueError("Migration order conflict: an earlier version is not recorded")
    return pending


async def _applied(connection):
    cursor = await connection.execute("SELECT to_regclass('public.schema_migrations')")
    if (await cursor.fetchone())[0] is None:
        return []
    cursor = await connection.execute(
        "SELECT version, name, checksum FROM public.schema_migrations ORDER BY version"
    )
    return await cursor.fetchall()


async def migrate(connection, directory=DEFAULT_DIRECTORY, *, apply=False):
    """Use a dedicated autocommit connection. Status performs no writes."""
    if not connection.autocommit:
        raise ValueError("Migrations require a dedicated autocommit connection")
    available = load_migrations(directory)
    if not apply:
        return plan_migrations(available, await _applied(connection))
    await connection.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
    try:
        # Validate the existing ledger before any schema writes.
        pending = plan_migrations(available, await _applied(connection))
        async with connection.transaction():
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS public.schema_migrations (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL UNIQUE,
                    checksum TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        for item in pending:
            async with connection.transaction():
                await connection.execute("SET LOCAL search_path TO public")
                await connection.execute(item.sql)
                await connection.execute(
                    "INSERT INTO public.schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                    (item.version, item.name, item.checksum),
                )
        return pending
    finally:
        await connection.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))


async def _run(apply):
    async with await psycopg.AsyncConnection.connect(_build_conninfo(), autocommit=True) as connection:
        changes = await migrate(connection, apply=apply)
    for item in changes:
        print(f"{'Applied' if apply else 'Pending'}: {item.name}")
    if not changes:
        print("Database is up to date.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["status", "apply"])
    args = parser.parse_args()
    try:
        loop_factory = asyncio.SelectorEventLoop if sys.platform == "win32" else None
        with asyncio.Runner(loop_factory=loop_factory) as runner:
            runner.run(_run(args.command == "apply"))
    except ValueError as exc:
        print(f"Migration refused: {exc}", file=sys.stderr)
        return 1
    except psycopg.Error as exc:
        # Database exceptions may contain connection details or SQL literals.
        print(f"Migration failed (SQLSTATE {exc.sqlstate or 'unavailable'}). "
              "Check connectivity and schema compatibility. No failing migration was recorded; "
              "consult docs/database-migrations.md.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
