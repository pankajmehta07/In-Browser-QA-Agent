from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from parser.llm_output_parser import parse_llm_output
from parser.natural_language import respond_to_instruction
from core.runner import run_test
from core.browser import launch_browser, navigate_to, close_browser
from extractors.accessibility import extract_accessibility_tree

router = APIRouter(prefix="/instructions", tags=["instructions"])


class RunInstructionRequest(BaseModel):
    instruction: str
    url: str
    variant: str = "original"
    reruns: int = 1
    use_natural_language: bool = False


class RunInstructionResponse(BaseModel):
    status: str
    saved_run_id: str | None
    total_steps: int
    passed_steps: int
    failed_steps: int
    duration_ms: int
    flaky: bool
    root_cause: dict | None


@router.post("/run")
async def run_instruction(body: RunInstructionRequest):
    """
    Parse an instruction and execute it against a live page.

    Two modes:
      use_natural_language=false → instruction is raw JSON steps
      use_natural_language=true  → instruction is plain English, sent to LLM
    """
    reruns = min(max(1, body.reruns), 5)

    # ── natural language mode ─────────────────────────────────────────────────
    if body.use_natural_language:
        session = await launch_browser(headless=True)

        try:
            success = await navigate_to(session.page, body.url)
            if not success:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not navigate to {body.url}",
                )

            snapshot = await extract_accessibility_tree(session.page)
            if not snapshot:
                raise HTTPException(
                    status_code=500,
                    detail="Could not extract page context.",
                )

            page_title = await session.page.title()
            page_text  = await session.page.locator("body").inner_text(timeout=5000)

            try:
                response = await respond_to_instruction(
                    instruction=body.instruction,
                    snapshot=snapshot,
                    page_title=page_title,
                    page_text=page_text,
                )
            except Exception as error:
                raise HTTPException(
                    status_code=502,
                    detail=f"LLM request failed: {error}",
                )

            if response.kind == "answer":
                return {
                    "kind":   "answer",
                    "answer": response.answer,
                }

            raw_steps = response.steps_json or "[]"

        finally:
            await close_browser(session)

    # ── structured JSON mode ──────────────────────────────────────────────────
    else:
        raw_steps = body.instruction

    # parse steps
    parse_result = parse_llm_output(raw_steps)

    if not parse_result.success or not parse_result.steps:
        raise HTTPException(
            status_code=400,
            detail=f"Could not parse instruction: {parse_result.error}",
        )

    # run via orchestrator
    report = await run_test(
        url=body.url,
        steps=parse_result.steps,
        reruns=reruns,
        variant=body.variant,
        instruction=body.instruction,
        headless=True,
        save_to_db=True,
    )

    classified = report.classified
    root_cause = classified.root_cause

    return RunInstructionResponse(
        status=classified.status,
        saved_run_id=str(report.saved_run_id),
        total_steps=classified.runs[-1].total_steps if classified.runs else 0,
        passed_steps=classified.runs[-1].passed_steps if classified.runs else 0,
        failed_steps=classified.runs[-1].failed_steps if classified.runs else 0,
        duration_ms=classified.duration_ms,
        flaky=classified.flaky,
        root_cause={
            "title":          root_cause.title,
            "summary":        root_cause.summary,
            "likely_cause":   root_cause.likely_cause,
            "recommendation": root_cause.recommendation,
            "evidence":       root_cause.evidence,
        } if root_cause else None,
    )