import json
import re

from parser.models import ParsedStep, ParseResult
from utils.logger import log_info, log_success, log_warning, log_error


# valid actions the runner supports
VALID_ACTIONS = {"goto", "type", "click", "check_visible", "check_contains"}

# actions that require a value field
ACTIONS_WITH_VALUE = {"type", "check_contains"}


def parse_llm_output(raw: str) -> ParseResult:
    """
    Parse LLM output into a list of validated ParsedStep objects.

    Handles:
      - Clean JSON array
      - JSON wrapped in markdown fences
      - Single step object not in array
    """
    log_info("Parsing LLM output...")

    cleaned, recovery = _clean_raw_input(raw)

    if not cleaned:
        log_error("Could not extract any JSON from LLM output.")
        return ParseResult(
            success=False,
            steps=[],
            raw_input=raw,
            cleaned_input=None,
            error="Could not extract JSON from input.",
            recovery=recovery,
        )

    # parse JSON
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as error:
        log_error(f"JSON decode failed: {error}")
        return ParseResult(
            success=False,
            steps=[],
            raw_input=raw,
            cleaned_input=cleaned,
            error=f"JSON decode error: {error}",
            recovery=recovery,
        )

    # single dict, not a list
    if isinstance(parsed, dict):
        log_warning("LLM returned a single step object — wrapping in array.")
        parsed = [parsed]
        recovery = recovery or "wrapped_in_array"

    if not isinstance(parsed, list):
        log_error(f"Expected list of steps, got {type(parsed).__name__}.")
        return ParseResult(
            success=False,
            steps=[],
            raw_input=raw,
            cleaned_input=cleaned,
            error=f"Expected list of steps, got {type(parsed).__name__}.",
            recovery=recovery,
        )

    # validate each step
    steps, errors = _validate_steps(parsed)

    if errors:
        # partial success — some steps valid, some not
        if steps:
            log_warning(f"Parsed {len(steps)} valid steps, {len(errors)} skipped.")
            return ParseResult(
                success=True,
                steps=steps,
                raw_input=raw,
                cleaned_input=cleaned,
                error=f"Skipped {len(errors)} invalid steps: {'; '.join(errors)}",
                recovery=recovery,
            )
        else:
            log_error("No valid steps found after validation.")
            return ParseResult(
                success=False,
                steps=[],
                raw_input=raw,
                cleaned_input=cleaned,
                error=f"All steps invalid: {'; '.join(errors)}",
                recovery=recovery,
            )

    log_success(f"Parsed {len(steps)} steps successfully.")
    return ParseResult(
        success=True,
        steps=steps,
        raw_input=raw,
        cleaned_input=cleaned,
        error=None,
        recovery=recovery,
    )


# ── private helpers ────────────────────────────────────────────────────────────

def _clean_raw_input(raw: str) -> tuple[str | None, str | None]:
    """
    Clean raw LLM output and return (cleaned_json_string, recovery_label).

    Recovery labels:
      None              — input was already clean
      markdown_stripped — removed markdown fences
    """
    stripped = raw.strip()

    # already looks like raw JSON
    if stripped.startswith("[") or stripped.startswith("{"):
        return stripped, None

    # markdown fences
    # handles ```json ... ``` and ``` ... ```
    markdown_pattern = re.compile(
        r"```(?:json)?\s*([\s\S]*?)```",
        re.IGNORECASE,
    )
    match = markdown_pattern.search(stripped)

    if match:
        extracted = match.group(1).strip()
        log_warning("Markdown fences detected — stripping them.")
        return extracted, "markdown_stripped"

    return None, None


def _validate_steps(raw_steps: list) -> tuple[list[ParsedStep], list[str]]:
    """
    Validate and convert raw dicts into ParsedStep objects.
    Returns (valid_steps, error_messages).
    """
    valid = []
    errors = []

    for index, raw in enumerate(raw_steps):
        label = f"Step {index + 1}"

        # must be a dict
        if not isinstance(raw, dict):
            errors.append(f"{label}: expected object, got {type(raw).__name__}")
            continue

        # action must exist and be valid
        action = raw.get("action")
        if not action:
            errors.append(f"{label}: missing 'action' field")
            continue

        if action not in VALID_ACTIONS:
            errors.append(
                f"{label}: unknown action '{action}' "
                f"(valid: {', '.join(sorted(VALID_ACTIONS))})"
            )
            continue

        # target must exist and be a non-empty string
        target = raw.get("target")
        if not target or not str(target).strip():
            errors.append(f"{label}: missing or empty 'target' field")
            continue

        # value required for some actions
        value = raw.get("value")
        if action in ACTIONS_WITH_VALUE:
            if not value or not str(value).strip():
                errors.append(
                    f"{label}: action '{action}' requires a 'value' field"
                )
                continue

        valid.append(ParsedStep(
            action=action,
            target=str(target).strip(),
            value=str(value).strip() if value else None,
        ))

    return valid, errors