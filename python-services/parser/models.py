from dataclasses import dataclass, field


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


@dataclass
class StepExecutionResult:
    step_number: int
    action: str
    target: str
    value: str | None

    status: str          # passed | failed
    duration_ms: int
    error: str | None = None

    # for click steps
    selector_used: str | None = None
    was_healed: bool = False
    old_selector: str | None = None
    new_selector: str | None = None
    resolution_strategy: str | None = None
    confidence: float | None = None


@dataclass
class RunResult:
    status: str                    # passed | failed
    total_steps: int
    passed_steps: int
    failed_steps: int
    duration_ms: int
    steps: list[StepExecutionResult] = field(default_factory=list)