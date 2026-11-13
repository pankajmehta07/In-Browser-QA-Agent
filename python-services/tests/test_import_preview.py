import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from stores.import_preview import preview


TEST_ID = "00000000-0000-0000-0000-000000000001"
RUN_ID = "00000000-0000-0000-0000-000000000002"


def bundle(*records, revisions=None):
    return {"format_version": 1, "records": list(records), "revisions": revisions or []}


def record(kind="test", id=TEST_ID, **changes):
    data = {"id": id, "name": "Login", "instruction": "Click Login", **changes}
    return {"team_id": "local", "kind": kind, "id": id, "data": data}


class ImportPreviewTests(unittest.TestCase):
    def test_valid_definition_is_candidate_without_mutating_source(self):
        source = bundle(record())
        before = copy.deepcopy(source)
        report = preview(source, team="local")
        self.assertEqual(report["counts"], {"total": 1, "candidate": 1, "skipped": 0, "rejected": 0})
        self.assertFalse(report["destination_checked"])
        self.assertFalse(report["writes_performed"])
        self.assertEqual(source, before)

    def test_duplicate_ids_reject_both_rows(self):
        report = preview(bundle(record(), record()), team="local")
        self.assertEqual(report["counts"]["rejected"], 2)
        self.assertTrue(all("duplicate_source_id" in row["issues"] for row in report["items"]))

    def test_other_teams_and_secrets_are_not_candidates_or_echoed(self):
        foreign = record()
        foreign["team_id"] = "other"
        secret = record(kind="secret", id="private-value", password="do-not-print-this")
        report = preview(bundle(foreign, secret), team="local")
        self.assertEqual(report["counts"]["skipped"], 2)
        self.assertNotIn("do-not-print-this", json.dumps(report))
        self.assertNotIn("private-value", json.dumps(report))

    def test_existing_destination_id_requires_conflict_review(self):
        report = preview(bundle(record()), team="local", destination={"tests": {TEST_ID}, "runs": set(), "healed_selectors": set(), "test_revisions": set()})
        self.assertTrue(report["destination_checked"])
        self.assertEqual(report["items"][0]["issues"], ["destination_id_conflict"])

    def test_invalid_id_and_unsupported_test_configuration_are_rejected(self):
        for row in [record(id="not-a-uuid"), record(targetUrl="https://example.com"), record(plan={"steps": [{"action": "select", "target": "Owner", "value": "Alice"}]})]:
            with self.subTest(row=row):
                self.assertEqual(preview(bundle(row), team="local")["counts"]["rejected"], 1)

    def test_missing_test_reference_and_invalid_status_are_reported(self):
        row = {"team_id": "local", "kind": "run", "id": RUN_ID, "data": {"id": RUN_ID, "status": "passed", "result": {"status": "passed", "testId": TEST_ID}}}
        report = preview(bundle(row), team="local")
        self.assertIn("missing_test_reference", report["items"][0]["issues"])
        with_test = preview(bundle(record(), row), team="local")
        self.assertEqual(with_test["counts"]["candidate"], 2)
        row["data"]["status"] = "queued"
        self.assertIn("invalid_run_status", preview(bundle(row), team="local")["items"][0]["issues"])

    def test_conflicting_top_level_and_result_test_ids_are_rejected(self):
        row = {"team_id": "local", "kind": "run", "id": RUN_ID, "data": {"id": RUN_ID, "status": "passed", "testId": RUN_ID, "result": {"testId": TEST_ID}}}
        report = preview(bundle(record(), row), team="local")
        self.assertIn("conflicting_test_reference", report["items"][1]["issues"])

    def test_revision_requires_parent_and_contiguous_history(self):
        history = [{"team_id": "local", "test_id": TEST_ID, "revision": 2, "data": record()["data"]}]
        report = preview(bundle(record(revision=2), revisions=history), team="local")
        self.assertIn("incomplete_revision_history", report["items"][0]["issues"])
        self.assertEqual(report["counts"]["rejected"], 2)

    def test_artifact_escape_and_missing_files_do_not_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            for reference, issue in [("/screenshots/missing.png", "evidence_missing"), ("/screenshots/../../private.txt", "unsafe_evidence_reference")]:
                row = {"team_id": "local", "kind": "run", "id": RUN_ID, "data": {"id": RUN_ID, "status": "failed", "result": {"screenshot": {"urlPath": reference}}}}
                report = preview(bundle(row), team="local", artifact_root=Path(directory))
                self.assertIn(issue, report["items"][0]["issues"])

    def test_bad_envelope_is_rejected_without_echoing_contents(self):
        for source in [{"format_version": 9}, {"format_version": True, "records": []}, {"format_version": 1, "records": "private"}]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                preview(source, team="local")

    def test_cli_reports_json_without_creating_files(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "export.json"
            path.write_text(json.dumps(bundle(record())), encoding="utf-8")
            completed = subprocess.run([sys.executable, "-m", "stores.import_preview", str(path), "--team", "local"], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(json.loads(completed.stdout)["counts"]["candidate"], 1)
            self.assertEqual([item.name for item in Path(directory).iterdir()], ["export.json"])

    def test_malformed_field_types_are_rejected_not_crashed(self):
        rows = [record(variant=[]), record(kind="run", status=[], result={}), record(reruns=True)]
        for row in rows:
            with self.subTest(row=row):
                self.assertEqual(preview(bundle(row), team="local")["counts"]["rejected"], 1)

    def test_valid_evidence_is_hashed_and_never_modified(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "screenshots").mkdir()
            path = root / "screenshots" / "failure.png"
            path.write_bytes(b"sample evidence")
            row = {"team_id": "local", "kind": "run", "id": RUN_ID, "data": {"id": RUN_ID, "status": "failed", "result": {"screenshot": {"urlPath": "/screenshots/failure.png"}}}}
            report = preview(bundle(row), team="local", artifact_root=root)
            self.assertEqual(report["counts"]["candidate"], 1)
            self.assertEqual(report["items"][0]["evidence"][0]["sha256"], hashlib.sha256(b"sample evidence").hexdigest())
            self.assertEqual(path.read_bytes(), b"sample evidence")

    def test_rejected_history_rejects_parent_definition(self):
        data = record()["data"]
        history = [{"team_id": "local", "test_id": TEST_ID, "revision": 1, "data": {**data, "name": "Wrong latest name"}}]
        report = preview(bundle(record(), revisions=history), team="local")
        self.assertEqual(report["counts"]["candidate"], 0)
        self.assertIn("latest_revision_mismatch", report["items"][0]["issues"])

    def test_approved_selector_requires_existing_or_candidate_run(self):
        approval = {"team_id": "local", "kind": "approval", "id": RUN_ID, "data": {"id": RUN_ID, "stepName": "Click", "oldTarget": "Old", "newTarget": "New", "decision": "approved", "runId": TEST_ID}}
        report = preview(bundle(approval), team="local")
        self.assertIn("missing_run_reference", report["items"][0]["issues"])

    def test_valid_legacy_plan_and_complete_history_are_candidates(self):
        row = record(plan={"setupSteps": [], "steps": [{"action": "click", "target": "Login"}], "cleanupSteps": []})
        history = [{"team_id": "local", "test_id": TEST_ID, "revision": 1, "data": row["data"]}]
        report = preview(bundle(row, revisions=history), team="local")
        self.assertEqual(report["counts"]["candidate"], 2)
