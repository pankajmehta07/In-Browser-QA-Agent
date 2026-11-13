from dataclasses import dataclass, field
from playwright.async_api import Page

from extractors.accessibility import extract_accessibility_tree
from stores.approval_store import find_approved_mapping
from utils.logger import log_info, log_success, log_warning
from parser.natural_language import resolve_button_with_llm


# ── known synonym pairs ────────────────────────────────────────────────────────
# format: "normalized_expected::normalized_actual" → score
# extend this as more UI patterns are discovered

KNOWN_PAIRS: dict[str, float] = {
    "login::sign in":               0.91,
    "sign in::login":               0.91,
    "log in::sign in":              0.91,
    "sign in::log in":              0.91,
    "login::log in":                0.91,
    "log in::login":                0.91,

    "add user::new user":           0.92,
    "new user::add user":           0.92,

    "create project::new project":  0.92,
    "new project::create project":  0.92,

    "save user::new user":          0.90,
    "new user::save user":          0.90,

    "save project::new project":    0.90,
    "new project::save project":    0.90,

    "save::save changes":           0.90,
    "save changes::save":           0.90,

    "delete::remove":               0.90,
    "remove::delete":               0.90,

    "cancel::dismiss":              0.88,
    "dismiss::cancel":              0.88,

    "submit::send":                 0.88,
    "send::submit":                 0.88,

    "continue::next":               0.88,
    "next::continue":               0.88,

    "go back::back":                0.90,
    "back::go back":                0.90,
}

# minimum score to accept a candidate
SIMILARITY_THRESHOLD = 0.8


# ── result dataclasses ────────────────────────────────────────────────────────

@dataclass
class ResolutionAttempt:
    tier: str
    description: str
    status: str                    # passed | failed | skipped
    confidence: float = 0.0
    estimated_cost_usd: float = 0.0
    error: str | None = None
    best_candidate: str | None = None
    approved_mapping: dict | None = None


@dataclass
class ResolutionResult:
    target_name: str
    resolved_name: str | None      # name to use for get_by_role
    was_healed: bool
    resolution_strategy: str       # exact_role_match | approved_memory |
                                   # accessibility_text_similarity | unresolved
    confidence: float
    estimated_cost_usd: float
    old_selector: str
    new_selector: str | None
    attempts: list[ResolutionAttempt] = field(default_factory=list)


# ── main resolver ─────────────────────────────────────────────────────────────

async def resolve_button(page: Page, target_name: str) -> ResolutionResult:
    """
    Try to resolve a button name through four tiers:
      Tier 1 — exact role match
      Tier 2 — approved memory (from DB)
      Tier 3 — accessibility text similarity
      Tier 4 — vision/LLM fallback (stub for LLM team)
    """
    attempts: list[ResolutionAttempt] = []
    old_selector = f'role=button[name="{target_name}"]'

    # ── Tier 1: Exact Role Match ───────────────────────────────────────────────

    log_info(f'Tier 1 — exact match for "{target_name}"...')

    tier1 = ResolutionAttempt(
        tier="exact_role_match",
        description=f'Try exact button name "{target_name}"',
        status="failed",
        confidence=0.0,
        estimated_cost_usd=0.0,
    )

    try:
        locator = page.get_by_role("button", name=target_name)
        await locator.wait_for(state="visible", timeout=1000)

        tier1.status     = "passed"
        tier1.confidence = 1.0
        attempts.append(tier1)

        log_success(f'Tier 1 passed — exact match found.')

        return ResolutionResult(
            target_name=target_name,
            resolved_name=target_name,
            was_healed=False,
            resolution_strategy="exact_role_match",
            confidence=1.0,
            estimated_cost_usd=0.0,
            old_selector=None,
            new_selector=f'role=button[name="{target_name}"]',
            attempts=attempts,
        )

    except Exception as error:
        tier1.error = str(error)
        attempts.append(tier1)
        log_warning(f"Tier 1 failed — {error}")

    # ── Tier 2: Approved Memory ────────────────────────────────────────────────

    log_info(f'Tier 2 — checking approved memory for "{target_name}"...')

    tier2 = ResolutionAttempt(
        tier="approved_memory",
        description=f'Check approved healing memory for "{target_name}"',
        status="failed",
        confidence=0.0,
        estimated_cost_usd=0.0,
    )

    try:
        mapping = await find_approved_mapping(target_name)

        if mapping:
            tier2.status           = "passed"
            tier2.confidence       = 1.0
            tier2.approved_mapping = {
                "old_target": mapping["old_target"],
                "new_target": mapping["new_target"],
                "saved_at":   str(mapping.get("saved_at", "")),
            }
            attempts.append(tier2)

            log_success(
                f'Tier 2 passed — '
                f'"{mapping["old_target"]}" → "{mapping["new_target"]}"'
            )

            return ResolutionResult(
                target_name=target_name,
                resolved_name=mapping["new_target"],
                was_healed=True,
                resolution_strategy="approved_memory",
                confidence=1.0,
                estimated_cost_usd=0.0,
                old_selector=old_selector,
                new_selector=f'role=button[name="{mapping["new_target"]}"]',
                attempts=attempts,
            )

        tier2.error = "No approved mapping found."
        attempts.append(tier2)
        log_warning("Tier 2 failed — no approved mapping.")

    except Exception as error:
        tier2.error = str(error)
        attempts.append(tier2)
        log_warning(f"Tier 2 error — {error}")

    # ── Tier 3: Accessibility Text Similarity ─────────────────────────────────

    log_info(f'Tier 3 — accessibility similarity for "{target_name}"...')

    tier3 = ResolutionAttempt(
        tier="accessibility_text_similarity",
        description=f'Search accessibility snapshot for button similar to "{target_name}"',
        status="failed",
        confidence=0.0,
        estimated_cost_usd=0.0,
    )

    try:
        snapshot = await extract_accessibility_tree(page)

        if snapshot:
            candidates = [
                node for node in snapshot.nodes
                if node.role == "button"
            ]

            scored = sorted(
                [
                    (node, _score_candidate(target_name, node.name))
                    for node in candidates
                ],
                key=lambda x: x[1],
                reverse=True,
            )

            if scored:
                best_node, best_score = scored[0]
                tier3.confidence     = best_score
                tier3.best_candidate = best_node.name

                if best_score >= SIMILARITY_THRESHOLD:
                    tier3.status = "passed"
                    attempts.append(tier3)

                    log_success(
                        f'Tier 3 passed — '
                        f'"{target_name}" → "{best_node.name}" '
                        f'(score={best_score:.2f})'
                    )

                    return ResolutionResult(
                        target_name=target_name,
                        resolved_name=best_node.name,
                        was_healed=True,
                        resolution_strategy="accessibility_text_similarity",
                        confidence=best_score,
                        estimated_cost_usd=0.0,
                        old_selector=old_selector,
                        new_selector=f'role=button[name="{best_node.name}"]',
                        attempts=attempts,
                    )

                tier3.error = (
                    f'Best candidate "{best_node.name}" '
                    f"scored {best_score:.2f} — below threshold {SIMILARITY_THRESHOLD}."
                )
            else:
                tier3.error = "No button candidates found in accessibility snapshot."

        else:
            tier3.error = "Accessibility snapshot returned None."

        attempts.append(tier3)
        log_warning(f"Tier 3 failed — {tier3.error}")

    except Exception as error:
        tier3.error = str(error)
        attempts.append(tier3)
        log_warning(f"Tier 3 error — {error}")

    # ── Tier 4: LLM Fallback ─────────────────────────────────────────

    log_info("Tier 4 — LLM fallback...")

    tier4 = ResolutionAttempt(
        tier="llm_fallback",
        description=(
            f'Ask LLM to identify the best match for "{target_name}" '
            f'from visible button names.'
        ),
        status="failed",
        confidence=0.0,
        estimated_cost_usd=0.004,
    )

    try:
        # collect visible button names from accessibility snapshot
        snapshot   = await extract_accessibility_tree(page)
        candidates = []

        if snapshot:
            candidates = [
                node.name
                for node in snapshot.nodes
                if node.role == "button"
                and node.visible
                and node.name
            ]

        if not candidates:
            tier4.error = "No visible button candidates found for LLM."
            attempts.append(tier4)
            log_warning("Tier 4 skipped — no candidates.")

        else:
            resolved_name = await resolve_button_with_llm(target_name, candidates)

            if resolved_name:
                # verify it actually exists on the page
                try:
                    locator = page.get_by_role("button", name=resolved_name)
                    await locator.wait_for(state="visible", timeout=2000)

                    tier4.status         = "passed"
                    tier4.confidence     = 0.75
                    tier4.best_candidate = resolved_name
                    attempts.append(tier4)

                    log_success(
                        f'Tier 4 passed — '
                        f'"{target_name}" → "{resolved_name}" via LLM.'
                    )

                    return ResolutionResult(
                        target_name=target_name,
                        resolved_name=resolved_name,
                        was_healed=True,
                        resolution_strategy="llm_fallback",
                        confidence=0.75,
                        estimated_cost_usd=0.004,
                        old_selector=old_selector,
                        new_selector=f'role=button[name="{resolved_name}"]',
                        attempts=attempts,
                    )

                except Exception:
                    tier4.error = (
                        f'LLM suggested "{resolved_name}" '
                        f'but it was not found on the page.'
                    )
            else:
                tier4.error = "LLM returned NO_MATCH."

    except Exception as error:
        tier4.error = str(error)
        log_warning(f"Tier 4 error — {error}")

    attempts.append(tier4)
    log_warning(f"Tier 4 failed — {tier4.error}")

    # ── Unresolved ────────────────────────────────────────────────────────────

    total_cost = sum(a.estimated_cost_usd for a in attempts)

    return ResolutionResult(
        target_name=target_name,
        resolved_name=None,
        was_healed=False,
        resolution_strategy="unresolved",
        confidence=0.0,
        estimated_cost_usd=total_cost,
        old_selector=old_selector,
        new_selector=None,
        attempts=attempts,
    )


# ── scoring ───────────────────────────────────────────────────────────────────

def _score_candidate(expected: str, actual: str) -> float:
    """
    Score how likely `actual` is the same button as `expected`.
    Returns a float between 0.0 and 1.0.
    """
    norm_expected = _normalize(expected)
    norm_actual   = _normalize(actual)

    # exact match
    if norm_expected == norm_actual:
        return 1.0

    # known synonym pairs
    pair_key = f"{norm_expected}::{norm_actual}"
    if pair_key in KNOWN_PAIRS:
        return KNOWN_PAIRS[pair_key]

    # substring containment
    if norm_actual in norm_expected or norm_expected in norm_actual:
        return 0.85

    return 0.0


def _normalize(value: str) -> str:
    return (value or "").strip().lower().replace(r"\s+", " ")