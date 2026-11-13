import hashlib
import tempfile
import unittest
from pathlib import Path

from stores import migrations


class MigrationPlanTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)

    def write(self, name, text="SELECT 1;\n"):
        (self.path / name).write_text(text, encoding="utf-8")

    def test_orders_migrations_and_hashes_content(self):
        self.write("0002_next.sql")
        self.write("0001_initial.sql")
        found = migrations.load_migrations(self.path)
        self.assertEqual([item.version for item in found], [1, 2])
        self.assertEqual(found[0].checksum, hashlib.sha256(b"SELECT 1;\n").hexdigest())

    def test_line_endings_do_not_change_checksum(self):
        self.write("0001_initial.sql")
        original = migrations.load_migrations(self.path)[0].checksum
        (self.path / "0001_initial.sql").write_bytes(b"SELECT 1;\r\n")
        self.assertEqual(migrations.load_migrations(self.path)[0].checksum, original)

    def test_rejects_duplicate_versions(self):
        self.write("0001_first.sql")
        self.write("0001_other.sql")
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            migrations.load_migrations(self.path)

    def test_rejects_malformed_names_and_empty_directories(self):
        with self.assertRaises(ValueError):
            migrations.load_migrations(self.path)
        self.write("initial.sql")
        with self.assertRaisesRegex(ValueError, "filename"):
            migrations.load_migrations(self.path)

    def test_changed_applied_sql_is_rejected(self):
        self.write("0001_initial.sql")
        with self.assertRaisesRegex(ValueError, "changed"):
            migrations.plan_migrations(migrations.load_migrations(self.path), [(1, "0001_initial.sql", "wrong")])

    def test_newer_database_is_rejected(self):
        self.write("0001_initial.sql")
        with self.assertRaisesRegex(ValueError, "Unknown"):
            migrations.plan_migrations(migrations.load_migrations(self.path), [(2, "0002_future.sql", "abc")])

    def test_cannot_insert_migration_before_applied_version(self):
        self.write("0001_initial.sql")
        self.write("0002_next.sql")
        found = migrations.load_migrations(self.path)
        with self.assertRaisesRegex(ValueError, "order"):
            migrations.plan_migrations(found, [(2, found[1].name, found[1].checksum)])

    def test_only_unapplied_versions_are_pending(self):
        self.write("0001_initial.sql")
        self.write("0002_next.sql")
        found = migrations.load_migrations(self.path)
        pending = migrations.plan_migrations(found, [(1, found[0].name, found[0].checksum)])
        self.assertEqual([item.version for item in pending], [2])
