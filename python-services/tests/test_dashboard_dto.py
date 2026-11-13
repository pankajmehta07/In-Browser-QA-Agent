import copy
from datetime import datetime, timezone
from decimal import Decimal
from unittest import TestCase
from uuid import UUID

from api.dashboard_dto import run_dto, test_dto


ID = UUID("00000000-0000-0000-0000-000000000001")
STAMP = datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc)


def run_row(result):
    return {"id": ID, "saved_at": STAMP, "status": "failed", "flaky": False,
            "duration_ms": 19, "run_count": 1, "healed_count": 0, "was_healed": False,
            "total_cost_usd": Decimal("0.125000"), "root_cause_title": None,
            "accessibility_issue_count": 0, "accessibility_warning_count": 0, "result_json": result}


class DashboardDtoTests(TestCase):
    def test_definition_dates_ids_and_plan_are_mapped_without_mutation(self):
        row = {"id": ID, "name": "Custom name", "instruction": "Click Login", "variant": "original", "reruns": 1,
               "revision": 2, "plan": {"schema_version": 1, "steps": [{"action": "click", "target": "Login"}]}, "created_at": STAMP, "updated_at": STAMP}
        original = copy.deepcopy(row)
        dto = test_dto(row)
        self.assertEqual(dto["id"], str(ID))
        self.assertEqual(dto["createdAt"], "2026-01-02T03:04:00+00:00")
        self.assertEqual(dto["revision"], 2)
        self.assertEqual(row, original)

    def test_native_phase_results_become_dashboard_step_fields(self):
        payload = {"status": "failed", "duration_ms": 19, "test_id": str(ID), "test_revision": 1,
                   "definition_snapshot": {"name": "Historical"}, "phases": {"test": {"status": "failed"}},
                   "steps": [{"action": "click", "target": "Login", "status": "failed", "duration_ms": 5,
                              "selector_used": "role=button", "was_healed": False, "error": "Not visible", "phase": "test"}]}
        row = run_row(payload)
        original = copy.deepcopy(row)
        dto = run_dto(row)
        self.assertEqual(dto["totalCostUsd"], 0.125)
        self.assertEqual(dto["result"]["savedRunId"], str(ID))
        self.assertEqual(dto["result"]["steps"][0]["name"], "click Login")
        self.assertEqual(dto["result"]["steps"][0]["selectorUsed"], "role=button")
        self.assertEqual(dto["result"]["steps"][0]["durationMs"], 5)
        self.assertEqual(dto["result"]["definitionSnapshot"]["name"], "Historical")
        self.assertEqual(dto["result"]["errorMessage"], "Not visible")
        self.assertEqual(row, original)

    def test_existing_camelcase_diagnostics_and_reruns_are_preserved(self):
        payload = {"status": "failed", "durationMs": 19,
                   "rootCause": {"title": "Assertion", "likelyCause": "Missing", "evidence": "Observed"},
                   "accessibilityAudit": {"issueCount": 0, "warningCount": 0},
                   "steps": [{"name": "Click Login", "status": "failed", "durationMs": 0, "confidence": 0}],
                   "runs": [{"status": "failed", "durationMs": 19, "runNumber": 1, "steps": []}]}
        dto = run_dto(run_row(payload))["result"]
        self.assertEqual(dto["rootCause"]["evidence"], "Observed")
        self.assertEqual(dto["runs"][0]["runNumber"], 1)
        self.assertEqual(dto["steps"][0]["durationMs"], 0)
        self.assertNotEqual(dto["accessibilityAudit"].get("status"), "passed")

    def test_local_artifact_paths_are_not_exposed_as_working_links(self):
        row = run_row({"status": "failed", "screenshot": {"path": "C:/private/failure.png", "urlPath": "/screenshots/failure.png"}, "trace_path": "C:/private/trace.zip", "steps": []})
        row["screenshot_path"] = "C:/private/failure.png"
        dto = run_dto(row)
        self.assertNotIn("C:/private", str(dto))
        self.assertNotIn("screenshot", dto["result"])
        self.assertEqual(dto["result"]["artifactAvailability"], "not_exposed")

    def test_malformed_result_is_not_presented_as_success(self):
        with self.assertRaises(ValueError):
            run_dto(run_row("not an object"))

    def test_invalid_durations_and_unsupported_suite_shapes_are_rejected(self):
        for payload in [
            {"status": "failed", "duration_ms": "not-a-number", "steps": []},
            {"status": "failed", "type": "suite", "tests": []},
        ]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                run_dto(run_row(payload))
