import json
import dataclasses
from datetime import datetime
from typing import Any

from core.auditor import AuditReport


def serialize_report(report: AuditReport) -> dict:
    """
    Convert AuditReport (nested dataclasses) into a
    JSON-serializable dict.
    """
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "url":           report.url,
        "status":        report.status,
        "health_score":  report.health_score,
        "health_breakdown": report.health_breakdown,
        "screenshot_path":  report.screenshot_path,
        "all_issues":    report.all_issues,
        "steps":         [_serialize(s) for s in report.steps],
        "content":       _serialize(report.content) if report.content else None,
        "accessibility": _serialize_accessibility(report.accessibility),
    }


def _serialize(obj: Any) -> Any:
    """
    Recursively convert dataclasses, lists, dicts to
    JSON-safe types.
    """
    if obj is None:
        return None

    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {
            field.name: _serialize(getattr(obj, field.name))
            for field in dataclasses.fields(obj)
        }

    if isinstance(obj, list):
        return [_serialize(item) for item in obj]

    if isinstance(obj, dict):
        return {key: _serialize(value) for key, value in obj.items()}

    return obj


def _serialize_accessibility(snapshot) -> dict | None:
    """
    Serialize accessibility snapshot — keeps nodes
    and issues, flattens aria attributes inline.
    """
    if not snapshot:
        return None

    return {
        "url":         snapshot.url,
        "total_count": snapshot.total_count,
        "by_role":     snapshot.by_role,
        "issues":      snapshot.issues,
        "nodes": [
            {
                "tag":        node.tag,
                "role":       node.role,
                "name":       node.name,
                "selector":   node.selector,
                "element_id": node.element_id,
                "visible":    node.visible,
                "focusable":  node.focusable,
                "disabled":   node.disabled,
                "aria": {
                    "label":        node.aria.label,
                    "labelledby":   node.aria.labelledby,
                    "describedby":  node.aria.describedby,
                    "expanded":     node.aria.expanded,
                    "disabled":     node.aria.disabled,
                    "required":     node.aria.required,
                    "checked":      node.aria.checked,
                    "selected":     node.aria.selected,
                    "hidden":       node.aria.hidden,
                    "haspopup":     node.aria.haspopup,
                    "live":         node.aria.live,
                    "role_override": node.aria.role_override,
                },
                "source": node.source,
            }
            for node in snapshot.nodes
        ],
    }