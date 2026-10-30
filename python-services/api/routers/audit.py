from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.auditor import run_full_audit, AuditReport
from utils.serializer import serialize_report
from utils.file_writer import generate_filename, save_report_to_file

router = APIRouter(prefix="/audit", tags=["audit"])


class AuditRequest(BaseModel):
    url: str
    save: bool = False


class AuditStepResult(BaseModel):
    step: int
    name: str
    status: str
    duration_ms: int
    error: str | None = None


class AuditResponse(BaseModel):
    url: str
    status: str
    health_score: int
    health_breakdown: dict
    screenshot_path: str | None
    all_issues: list[str]
    steps: list[AuditStepResult]
    content: dict | None
    accessibility: dict | None
    saved_file: str | None


@router.post("", response_model=AuditResponse)
async def run_audit(body: AuditRequest):
    """
    Run a full page audit — browser launch, content extraction,
    accessibility tree — and return a combined health report.
    Optionally saves the report to a JSON file with save=true.
    """
    try:
        report: AuditReport = await run_full_audit(
            url=body.url,
            headless=True,
        )
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Audit failed: {error}",
        )

    saved_file = None
    if body.save:
        try:
            filepath = generate_filename(body.url)
            data     = serialize_report(report)
            save_report_to_file(data, filepath)
            saved_file = filepath
        except Exception as error:
            # saving is optional — don't fail the whole request
            saved_file = None

    return AuditResponse(
        url=report.url,
        status=report.status,
        health_score=report.health_score,
        health_breakdown=report.health_breakdown,
        screenshot_path=report.screenshot_path,
        all_issues=report.all_issues,
        steps=[
            AuditStepResult(
                step=s.step,
                name=s.name,
                status=s.status,
                duration_ms=s.duration_ms,
                error=s.error,
            )
            for s in report.steps
        ],
        content=_serialize_content(report),
        accessibility=_serialize_accessibility(report),
        saved_file=saved_file,
    )


@router.post("/compare")
async def compare_urls(body: dict):
    """
    Run audit on two URLs and return both results for comparison.
    Useful for testing original vs variant of the same page.
    """
    url_a = body.get("url_a")
    url_b = body.get("url_b")

    if not url_a or not url_b:
        raise HTTPException(
            status_code=400,
            detail="Both url_a and url_b are required.",
        )

    try:
        report_a, report_b = await _run_both(url_a, url_b)
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Comparison audit failed: {error}",
        )

    return {
        "url_a": {
            "url":              report_a.url,
            "status":           report_a.status,
            "health_score":     report_a.health_score,
            "health_breakdown": report_a.health_breakdown,
            "all_issues":       report_a.all_issues,
        },
        "url_b": {
            "url":              report_b.url,
            "status":           report_b.status,
            "health_score":     report_b.health_score,
            "health_breakdown": report_b.health_breakdown,
            "all_issues":       report_b.all_issues,
        },
        "diff": {
            "score_delta":  report_b.health_score - report_a.health_score,
            "issues_delta": len(report_b.all_issues) - len(report_a.all_issues),
            "new_issues": [
                issue for issue in report_b.all_issues
                if issue not in report_a.all_issues
            ],
            "fixed_issues": [
                issue for issue in report_a.all_issues
                if issue not in report_b.all_issues
            ],
        },
    }


# ── private helpers ────────────────────────────────────────────────────────────

def _serialize_content(report: AuditReport) -> dict | None:
    if not report.content:
        return None

    content = report.content
    meta    = content.meta

    return {
        "url":   content.url,
        "title": content.title,
        "meta": {
            "description": meta.description if hasattr(meta, "description") else meta.get("description"),
            "keywords":    meta.keywords    if hasattr(meta, "keywords")    else meta.get("keywords"),
            "author":      meta.author      if hasattr(meta, "author")      else meta.get("author"),
            "viewport":    meta.viewport    if hasattr(meta, "viewport")    else meta.get("viewport"),
        },
        "headings": [
            {"level": h.level, "text": h.text}
            for h in content.headings
        ],
        "links": [
            {"text": l.text, "href": l.href, "is_external": l.is_external}
            for l in content.links
        ],
        "buttons": [
            {
                "text":        b.text,
                "button_type": b.button_type,
                "element_id":  b.element_id,
            }
            for b in content.buttons
        ],
        "images": [
            {"src": i.src, "alt": i.alt, "has_alt": i.has_alt}
            for i in content.images
        ],
        "forms": [
            {
                "action": f.action,
                "method": f.method,
                "fields": [
                    {
                        "label":       ff.label,
                        "field_type":  ff.field_type,
                        "name":        ff.name,
                        "placeholder": ff.placeholder,
                        "required":    ff.required,
                    }
                    for ff in f.fields
                ],
            }
            for f in content.forms
        ],
    }


def _serialize_accessibility(report: AuditReport) -> dict | None:
    if not report.accessibility:
        return None

    snapshot = report.accessibility

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
                    "label":         node.aria.label,
                    "labelledby":    node.aria.labelledby,
                    "describedby":   node.aria.describedby,
                    "expanded":      node.aria.expanded,
                    "disabled":      node.aria.disabled,
                    "required":      node.aria.required,
                    "checked":       node.aria.checked,
                    "selected":      node.aria.selected,
                    "hidden":        node.aria.hidden,
                    "haspopup":      node.aria.haspopup,
                    "live":          node.aria.live,
                    "role_override": node.aria.role_override,
                },
                "source": node.source,
            }
            for node in snapshot.nodes
        ],
    }


async def _run_both(
    url_a: str,
    url_b: str,
) -> tuple[AuditReport, AuditReport]:
    """
    Run both audits concurrently.
    """
    import asyncio

    report_a, report_b = await asyncio.gather(
        run_full_audit(url=url_a, headless=True),
        run_full_audit(url=url_b, headless=True),
    )

    return report_a, report_b