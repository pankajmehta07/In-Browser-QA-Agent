"""Observe one configured page and draft a plan; never execute generated steps."""

import asyncio
import json
import os
import time
from dataclasses import replace
from urllib.parse import urlsplit, urlunsplit

from fastapi import HTTPException

from core import browser
from core.saved_plan import _origin
from extractors import accessibility
from parser import natural_language
from parser.test_plan import TestPlan


def grounding_issues(plan, nodes, headings):
    issues = []
    for number, step in enumerate(plan.steps, 1):
        matches = [node for node in nodes if node.name == step.target]
        if step.action == "goto":
            valid = headings.count(step.target) == 1
        elif step.action == "check_visible":
            valid = bool(matches) or step.target in headings
        else:
            roles = {"button", "link"} if step.action == "click" else {"textbox"}
            matches = [node for node in matches if node.role in roles]
            if step.action in {"type", "check_contains"}:
                matches = [node for node in matches if node.tag in {"input", "textarea"}]
            valid = len(matches) == 1 and not matches[0].disabled
        if not valid:
            issues.append({"step": number, "action": step.action, "target": step.target,
                           "reason": "Target is not uniquely observed with a supported, enabled control type on this page. Provide the required page state or revise this step."})
    return issues


async def preview_instruction(instruction):
    target = os.getenv("TARGET_APP_URL", "http://127.0.0.1:5173/")
    try:
        origin = _origin(target)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Review the server-configured target before previewing") from exc
    session = await browser.launch_browser(headless=True)
    try:
        if not await browser.navigate_to(session.page, target) or _origin(session.page.url) != origin:
            raise HTTPException(status_code=409, detail="The configured page could not be inspected within its origin")
        snapshot = await accessibility.extract_accessibility_tree(session.page)
        if snapshot is None:
            raise HTTPException(status_code=503, detail="Page controls could not be inspected")
        nodes = [node for node in snapshot.nodes if node.visible and isinstance(node.name, str) and 0 < len(node.name) <= 200][:100]
        headings = [text.strip() for text in await session.page.get_by_role("heading").all_text_contents()
                    if text.strip() and len(text.strip()) <= 200][:20]
        title = (await session.page.title())[:200]
        if _origin(session.page.url) != origin or _origin(snapshot.url) != origin:
            raise HTTPException(status_code=409, detail="Page origin changed during inspection")
        parsed_url = urlsplit(snapshot.url)
        compact = replace(snapshot, nodes=nodes, total_count=len(nodes),
                          url=urlunsplit((parsed_url.scheme, parsed_url.netloc, parsed_url.path, "", "")))
        started = time.perf_counter()
        try:
            response = await asyncio.wait_for(natural_language.respond_to_instruction(
                instruction=instruction, snapshot=compact, page_title=title,
                page_text="\n".join(headings)), timeout=45)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="AI planning was unavailable or timed out; no test actions were executed") from exc
        parser = {"source": "llm", "model": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
                  "durationMs": int((time.perf_counter() - started) * 1000)}
        if response.kind != "test":
            return {"status": "needs_input", "reviewRequired": True, "plan": None, "parser": parser,
                    "issues": [{"reason": "The AI did not produce a test plan. Clarify the workflow and expected outcome."}]}
        try:
            steps = json.loads(response.steps_json)
            plan = TestPlan.model_validate({"schema_version": 1, "steps": steps})
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=502, detail="AI returned an invalid or unsupported plan; no steps were accepted") from exc
        issues = grounding_issues(plan, nodes, headings)
        return {"status": "needs_input" if issues else "draft", "reviewRequired": True,
                "plan": plan.model_dump(), "issues": issues, "parser": parser,
                "coverage": "current_page_only"}
    finally:
        await browser.close_browser(session)
