"""Explicit dashboard aliases for known saved-result schemas, not a key renamer."""

import math
from uuid import UUID
from copy import deepcopy
from datetime import datetime
from decimal import Decimal


def _date(value):
    return value.isoformat() if isinstance(value, datetime) else value


def _number(value):
    if value is None:
        return None
    number = float(value) if isinstance(value, Decimal) else value
    if type(number) not in (int, float) or not math.isfinite(number):
        raise ValueError("Invalid stored number")
    return number


def _aliases(source, aliases):
    return {camel: deepcopy(source[camel] if camel in source else source[snake])
            for camel, snake in aliases.items() if camel in source or snake in source}


def test_dto(row):
    return {"id": str(row["id"]), "name": row["name"], "instruction": row["instruction"],
            "variant": row["variant"], "reruns": row["reruns"],
            "createdAt": _date(row["created_at"]), "updatedAt": _date(row["updated_at"]),
            "revision": row.get("revision", 1), "plan": deepcopy(row.get("plan"))}


def approval_dto(row):
    return {"id": str(row["id"]), "savedAt": _date(row["saved_at"]),
            "runId": str(row["run_id"]) if row.get("run_id") else None,
            "stepName": row["step_name"], "oldSelector": row.get("old_selector"),
            "newSelector": row.get("new_selector"), "oldTarget": row["old_target"],
            "newTarget": row["new_target"], "decision": row["decision"],
            "confidence": _number(row.get("confidence")), "strategy": row.get("strategy")}


def _root_cause(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("Invalid stored root cause")
    result = {key: deepcopy(value[key]) for key in ("title", "summary", "recommendation", "evidence") if key in value}
    result.update(_aliases(value, {"likelyCause": "likely_cause", "expectedResult": "expected_result"}))
    return result


def _step(value):
    if not isinstance(value, dict) or value.get("status") not in ("passed", "failed", "skipped"):
        raise ValueError("Invalid stored step")
    result = {key: deepcopy(value[key]) for key in ("status", "action", "target", "value", "error", "phase", "confidence") if key in value}
    result["name"] = value.get("name") or f"{value.get('action', 'Step')} {value.get('target', '')}".strip()
    result.update(_aliases(value, {
        "durationMs": "duration_ms", "selectorUsed": "selector_used", "wasHealed": "was_healed",
        "oldSelector": "old_selector", "newSelector": "new_selector", "resolutionStrategy": "resolution_strategy",
        "estimatedCostUsd": "estimated_cost_usd", "stepNumber": "step_number", "phaseStep": "phase_step",
    }))
    for field in ("durationMs", "estimatedCostUsd"):
        if field in result:
            result[field] = _number(result[field])
    if "resolutionAttempts" in value or "resolution_attempts" in value:
        attempts = value.get("resolutionAttempts", value.get("resolution_attempts"))
        if not isinstance(attempts, list) or any(not isinstance(item, dict) for item in attempts):
            raise ValueError("Invalid stored resolution attempts")
        result["resolutionAttempts"] = [
            {**{key: deepcopy(item[key]) for key in ("tier", "description", "status", "confidence", "error") if key in item},
             **_aliases(item, {"estimatedCostUsd": "estimated_cost_usd"})} for item in attempts
        ]
    return result


def _result(value, *, depth=0):
    if not isinstance(value, dict) or depth > 10:
        raise ValueError("Invalid stored execution result")
    if value.get("type") in ("suite", "selected_plan_suite"):
        raise ValueError("Suite result adaptation is not installed")
    result = {key: deepcopy(value[key]) for key in ("status", "flaky", "startedAt", "finishedAt", "accessibility", "phases", "parser") if key in value}
    result.update(_aliases(value, {
        "durationMs": "duration_ms", "errorMessage": "error_message", "runNumber": "run_number",
        "testId": "test_id", "testRevision": "test_revision", "targetUrl": "target_url",
        "definitionSnapshot": "definition_snapshot",
        "startedAt": "started_at", "finishedAt": "finished_at",
    }))
    if "durationMs" in result:
        result["durationMs"] = _number(result["durationMs"])
    steps = value.get("steps", [])
    if not isinstance(steps, list):
        raise ValueError("Invalid stored steps")
    result["steps"] = [_step(item) for item in steps]
    if "errorMessage" not in result:
        error = next((item.get("error") for item in result["steps"] if item["status"] == "failed" and item.get("error")), None)
        if error:
            result["errorMessage"] = error
    if "runs" in value:
        if not isinstance(value["runs"], list):
            raise ValueError("Invalid stored reruns")
        result["runs"] = [_result(item, depth=depth + 1) for item in value["runs"]]
    if "rootCause" in value or "root_cause" in value:
        result["rootCause"] = _root_cause(value.get("rootCause", value.get("root_cause")))
    if "accessibilityAudit" in value:
        if not isinstance(value["accessibilityAudit"], dict):
            raise ValueError("Invalid stored audit")
        result["accessibilityAudit"] = deepcopy(value["accessibilityAudit"])
        # Counts alone do not prove that an accessibility audit passed.
        result["accessibilityAudit"].setdefault("status", "unknown")
    if any(value.get(key) for key in ("screenshot", "screenshot_path", "screenshotPath", "trace", "trace_path", "tracePath")):
        result["artifactAvailability"] = "not_exposed"
    return result


def run_dto(row):
    result = _result(row["result_json"])
    if "status" in result and result["status"] != row["status"]:
        raise ValueError("Stored status disagrees with summary")
    result.setdefault("status", row["status"])
    result.setdefault("durationMs", row.get("duration_ms"))
    result["savedRunId"] = str(row["id"])
    if row.get("screenshot_path"):
        result["artifactAvailability"] = "not_exposed"
    return {"id": str(row["id"]), "savedAt": _date(row["saved_at"]), "status": row["status"],
            "flaky": row.get("flaky", False), "durationMs": row.get("duration_ms"),
            "runCount": row.get("run_count", 1), "healedCount": row.get("healed_count", 0),
            "wasHealed": row.get("was_healed", False), "totalCostUsd": _number(row.get("total_cost_usd")),
            "rootCauseTitle": row.get("root_cause_title"),
            "accessibilityIssueCount": row.get("accessibility_issue_count", 0),
            "accessibilityWarningCount": row.get("accessibility_warning_count", 0), "result": result}


def suite_dto(report):
    """Adapt the transient selected-suite report, not a persisted run row."""
    tests = []
    for entry in report["tests"]:
        state = entry["state"]
        if state not in {"completed", "completed_unsaved", "interrupted", "not_run"}:
            raise ValueError("Invalid suite state")
        item = {"testId": str(UUID(entry["test_id"])), "testRevision": entry["test_revision"],
                "state": state, "status": entry["status"], "savedRunId": None}
        if state == "completed":
            result = _result(entry["result"])
            if item["status"] not in {"passed", "failed"} or result.get("status") != item["status"]:
                raise ValueError("Invalid completed suite result")
            item["savedRunId"] = str(UUID(entry["saved_run_id"]))
            result["savedRunId"] = item["savedRunId"]
            item["result"] = result
        elif item["status"] != "unknown":
            raise ValueError("Uncompleted execution has no assertion outcome")
        if state in {"completed_unsaved", "interrupted"}:
            item["errorMessage"] = (
                "Execution finished but its result could not be saved. Do not automatically rerun."
                if state == "completed_unsaved" else
                "Execution was interrupted; website changes may have occurred. Review before retrying."
            )
        tests.append(item)
    counts = {"selected": len(tests), "completed": sum(item["state"] == "completed" for item in tests),
              "passed": sum(item["status"] == "passed" for item in tests),
              "failed": sum(item["status"] == "failed" for item in tests),
              "errors": sum(item["state"] in {"completed_unsaved", "interrupted"} for item in tests),
              "notRun": sum(item["state"] == "not_run" for item in tests)}
    status = "incomplete" if counts["errors"] or counts["notRun"] else "failed" if counts["failed"] else "passed"
    if not tests or report["status"] != status:
        raise ValueError("Suite status disagrees with outcomes")
    result = {"type": "selected_plan_suite", "suiteId": str(UUID(report["suite_id"])), "status": status,
              "stopReason": report["stop_reason"], "safeToRetry": False, "counts": counts, "tests": tests,
              "startedAt": report["started_at"], "finishedAt": report["finished_at"],
              "durationMs": _number(report["duration_ms"])}
    if status == "incomplete":
        result["errorMessage"] = "Suite stopped early. Review completed results and website state before retrying."
    return result
