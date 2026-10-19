from dataclasses import dataclass


@dataclass
class ParsedStep:
    action: str           # goto | type | click | check_visible | check_contains
    target: str
    value: str | None = None   # only for type and check_contains


@dataclass
class ParseResult:
    success: bool
    steps: list[ParsedStep]
    raw_input: str
    cleaned_input: str | None  # what we actually parsed
    error: str | None = None
    recovery: str | None = None  # which recovery path was used
    # none | markdown_stripped | wrapped_in_array