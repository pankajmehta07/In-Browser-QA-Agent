"""Read-only preflight for explicitly exported prototype records; no import mode."""

import argparse
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import UUID

import psycopg
from pydantic import ValidationError

from parser.test_plan import TestPlan
from stores.db import _build_conninfo


TABLES = {"test": "tests", "run": "runs", "approval": "healed_selectors", "revision": "test_revisions"}
TEST_FIELDS = {"id", "name", "instruction", "variant", "reruns", "plan", "revision", "createdAt", "updatedAt"}
MAX_BYTES = 20 * 1024 * 1024
MAX_ROWS = 10000


def _uuid(value):
    try:
        return str(UUID(value)) if isinstance(value, str) else None
    except ValueError:
        return None


def _integer(value, minimum=1, maximum=10000):
    return type(value) is int and minimum <= value <= maximum


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _date_issues(data, names):
    for name in names:
        if name in data:
            try:
                date = datetime.fromisoformat(data[name])
                if date.utcoffset() is None:
                    raise ValueError()
            except (ValueError, TypeError):
                return ["invalid_timestamp"]
    return []


def _plan(value):
    if value is None:
        return None
    if isinstance(value, dict) and "schema_version" not in value:
        # Only the mechanically equivalent prototype fields are convertible.
        if set(value) - {"steps", "setupSteps", "cleanupSteps"}:
            raise ValueError("Unmapped prototype plan fields")
        value = {"schema_version": 1, "steps": value.get("steps"),
                 "setup": value.get("setupSteps", []), "cleanup": value.get("cleanupSteps", [])}
    return TestPlan.model_validate(value).model_dump()


def _definition(data):
    issues = []
    if set(data) - TEST_FIELDS:
        issues.append("unmapped_test_fields")
    if not _text(data.get("name")) or not _text(data.get("instruction")):
        issues.append("invalid_test_definition")
    if data.get("variant", "original") not in ("original", "changed", "flaky"):
        issues.append("unsupported_variant")
    if not _integer(data.get("reruns", 1), maximum=5) or not _integer(data.get("revision", 1)):
        issues.append("invalid_test_version_or_reruns")
    try:
        _plan(data.get("plan"))
    except (ValidationError, ValueError):
        issues.append("unsupported_plan")
    return issues + _date_issues(data, ("createdAt", "updatedAt"))


def _run(data):
    issues = []
    allowed = {"id", "savedAt", "status", "targetUrl", "durationMs", "runCount", "healedCount", "wasHealed", "metrics", "result", "totalCostUsd", "testId", "screenshotPath"}
    if set(data) - allowed:
        issues.append("unmapped_run_fields")
    result = data.get("result")
    if not isinstance(result, dict):
        return issues + ["invalid_run_result"]
    if data.get("status") not in ("passed", "failed", "flaky") or result.get("status", data.get("status")) != data.get("status"):
        issues.append("invalid_run_status")
    if result.get("type") == "suite" or result.get("runs") or data.get("runCount", 1) != 1:
        issues.append("unsupported_aggregate_run")
    if "testId" in data and "testId" in result and data["testId"] != result["testId"]:
        issues.append("conflicting_test_reference")
    for name in ("durationMs", "healedCount"):
        if data.get(name) is not None and not _integer(data[name], minimum=0, maximum=2147483647):
            issues.append("invalid_run_numbers")
    cost = data.get("totalCostUsd", 0)
    if type(cost) not in (int, float) or not math.isfinite(cost) or not 0 <= cost < 10000:
        issues.append("invalid_run_numbers")
    return issues + _date_issues(data, ("savedAt",))


def _approval(data):
    allowed = {"id", "savedAt", "runId", "stepName", "oldSelector", "newSelector", "oldTarget", "newTarget", "decision", "confidence", "strategy"}
    issues = ["unmapped_approval_fields"] if set(data) - allowed else []
    if data.get("decision") != "approved" or any(not _text(data.get(key)) for key in ("stepName", "oldTarget", "newTarget")):
        issues.append("unsupported_approval")
    confidence = data.get("confidence")
    if confidence is not None and (type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1):
        issues.append("invalid_confidence")
    return issues + _date_issues(data, ("savedAt",))


def _evidence(data, root):
    result = data.get("result", {})
    references = [data.get("screenshotPath")]
    for key in ("screenshot", "trace"):
        entry = result.get(key)
        if isinstance(entry, dict):
            references.append(entry.get("urlPath"))
    issues, evidence = [], []
    for reference in references:
        if reference is None:
            continue
        if not isinstance(reference, str):
            issues.append("unsafe_evidence_reference")
            continue
        parsed = urlsplit(reference)
        parts = unquote(parsed.path).lstrip("/").split("/")
        if (parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or "\\" in reference
                or len(parts) != 2 or parts[0] not in {"screenshots", "traces"} or parts[1] in {"", ".", ".."}):
            issues.append("unsafe_evidence_reference")
            continue
        if root is None:
            issues.append("evidence_not_checked")
            continue
        path = (root / parts[0] / parts[1]).resolve()
        if not path.is_relative_to(root):
            issues.append("unsafe_evidence_reference")
        elif not path.is_file():
            issues.append("evidence_missing")
        elif path.stat().st_size > MAX_BYTES:
            issues.append("evidence_too_large")
        else:
            checksum = hashlib.sha256()
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(65536), b""):
                    checksum.update(chunk)
            evidence.append({"kind": parts[0], "sha256": checksum.hexdigest()})
    return issues, evidence


def preview(source, *, team, destination=None, artifact_root=None):
    if (not isinstance(source, dict) or type(source.get("format_version")) is not int
            or source["format_version"] != 1 or not isinstance(source.get("records"), list)
            or not isinstance(source.get("revisions", []), list) or not _text(team)):
        raise ValueError("Invalid export envelope; expected format_version 1, records and revisions arrays")
    if len(source["records"]) + len(source.get("revisions", [])) > MAX_ROWS:
        raise ValueError("Export exceeds 10000 rows; use reviewed bounded exports")
    destination_checked = destination is not None
    destination = destination or {table: set() for table in TABLES.values()}
    root = Path(artifact_root).resolve() if artifact_root is not None else None
    entries = [("records", item) for item in source["records"]] + [("revisions", item) for item in source.get("revisions", [])]
    items, internals, keys = [], [], defaultdict(list)
    for index, (section, row) in enumerate(entries):
        out = {"index": index, "section": section, "kind": "unsupported", "destination_id": None,
               "outcome": "rejected", "issues": [], "evidence": []}
        items.append(out)
        internals.append(None)
        if not isinstance(row, dict) or not _text(row.get("team_id")):
            out["issues"].append("invalid_source_row")
            continue
        if row["team_id"] != team:
            out.update(outcome="skipped", issues=["other_team"])
            continue
        kind = "revision" if section == "revisions" else row.get("kind")
        if not isinstance(kind, str) or kind not in TABLES:
            out.update(outcome="skipped", issues=["unsupported_or_sensitive_kind"])
            continue
        out.update(kind=kind, destination_table=TABLES[kind])
        identifier = _uuid(row.get("test_id") if kind == "revision" else row.get("id"))
        data = row.get("data")
        if identifier is None or not isinstance(data, dict):
            out["issues"].append("invalid_id_or_data")
            continue
        out["destination_id"] = identifier
        if "id" in data and _uuid(data["id"]) != identifier:
            out["issues"].append("source_id_mismatch")
        revision = row.get("revision") if kind == "revision" else None
        if kind == "revision" and (not _integer(revision) or data.get("revision", revision) != revision):
            out["issues"].append("invalid_revision")
            continue
        key = (kind, identifier, revision)
        keys[key].append(index)
        out["outcome"] = "candidate"
        if kind == "revision":
            out["revision"] = revision
        conflicts = destination.get(TABLES[kind], set())
        conflict_key = (identifier, revision) if kind == "revision" else identifier
        if conflict_key in conflicts:
            out["issues"].append("destination_id_conflict")
        if kind == "test" and any(test_id == identifier for test_id, _ in destination.get("test_revisions", set())):
            if "destination_id_conflict" not in out["issues"]:
                out["issues"].append("destination_id_conflict")
        if kind in {"test", "revision"}:
            out["issues"].extend(_definition(data))
        elif kind == "run":
            out["issues"].extend(_run(data))
            if isinstance(data.get("result"), dict):
                errors, evidence = _evidence(data, root)
                out["issues"].extend(errors)
                out["evidence"] = evidence
        else:
            out["issues"].extend(_approval(data))
        internals[index] = (kind, identifier, revision, data)
    for indices in keys.values():
        if len(indices) > 1:
            for index in indices:
                items[index]["issues"].append("duplicate_source_id")
    history_by_id = defaultdict(list)
    for index, entry in enumerate(internals):
        if entry is not None and entry[0] == "revision":
            history_by_id[entry[1]].append(index)
    for index, entry in enumerate(internals):
        if entry is None or entry[0] != "test":
            continue
        _, identifier, _, data = entry
        revision = data.get("revision", 1)
        history_indices = history_by_id[identifier]
        history = [internals[i][2] for i in history_indices]
        if _integer(revision) and (revision > 1 or history) and set(history) != set(range(1, revision + 1)):
            items[index]["issues"].append("incomplete_revision_history")
        if any(items[i]["issues"] for i in history_indices):
            items[index]["issues"].append("invalid_revision_history")
        latest = [internals[i][3] for i in history_indices if internals[i][2] == revision]
        for snapshot in latest:
            if any(snapshot.get(key, default) != data.get(key, default) for key, default in (
                    ("name", None), ("instruction", None), ("variant", "original"), ("reruns", 1))):
                items[index]["issues"].append("latest_revision_mismatch")
                break
            try:
                if _plan(snapshot.get("plan")) != _plan(data.get("plan")):
                    items[index]["issues"].append("latest_revision_mismatch")
            except (ValidationError, ValueError):
                # The field-level validator already reported unsupported plans.
                pass
    # Propagate failed dependencies; no dangling reference becomes a candidate.
    source_ids = {(kind, identifier) for kind, identifier, _ in keys}
    for _ in range(4):
        available = {kind: {entry[1] for index, entry in enumerate(internals) if entry and entry[0] == kind and not items[index]["issues"]} for kind in TABLES}
        for index, entry in enumerate(internals):
            if entry is None:
                continue
            kind, identifier, _, data = entry
            references = []
            if kind == "run" and isinstance(data.get("result"), dict):
                references.append(("test", data["testId"] if "testId" in data else data["result"].get("testId")))
            elif kind == "approval":
                references.append(("run", data.get("runId")))
            elif kind == "revision":
                references.append(("test", identifier))
            for parent_kind, raw in references:
                if raw is None:
                    continue
                parent = _uuid(raw)
                source_present = (parent_kind, parent) in source_ids
                if parent is None or (parent not in available[parent_kind] and (source_present or parent not in destination.get(TABLES[parent_kind], set()))):
                    code = f"missing_{parent_kind}_reference"
                    if code not in items[index]["issues"]:
                        items[index]["issues"].append(code)
    for item in items:
        if item["outcome"] == "candidate" and item["issues"]:
            item["outcome"] = "rejected"
    counts = Counter(item["outcome"] for item in items)
    return {"mode": "preview", "writes_performed": False, "destination_checked": destination_checked,
            "counts": {"total": len(items), **{key: counts[key] for key in ("candidate", "skipped", "rejected")}}, "items": items}


def read_destination(conninfo=None):
    """Use a consistent read-only transaction; never initialize/migrate a database."""
    with psycopg.connect(conninfo or _build_conninfo()) as connection:
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        snapshot = {}
        for table in ("tests", "runs", "healed_selectors"):
            # Table names are fixed constants, never source input.
            snapshot[table] = {str(row[0]) for row in connection.execute(f"SELECT id FROM public.{table}")}
        snapshot["test_revisions"] = {(str(row[0]), row[1]) for row in connection.execute("SELECT original_test_id, revision FROM public.test_revisions")}
        return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument("--team", required=True)
    parser.add_argument("--artifact-root", type=Path)
    parser.add_argument("--against-database", action="store_true")
    args = parser.parse_args()
    try:
        if args.export.stat().st_size > MAX_BYTES:
            raise ValueError("Export exceeds 20 MiB")
        source = json.loads(args.export.read_text(encoding="utf-8-sig"))
        destination = read_destination() if args.against_database else None
        report = preview(source, team=args.team, destination=destination, artifact_root=args.artifact_root)
        print(json.dumps(report, indent=2, allow_nan=False))
        return 2 if report["counts"]["rejected"] else 0
    except (ValueError, OSError, psycopg.Error, RecursionError):
        print("Preview failed: check export format, file access and read-only database connectivity. No data was written.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
