from dataclasses import dataclass, field
from playwright.async_api import Page

from utils.logger import log_info, log_success, log_error


@dataclass
class AriaAttributes:
    label: str | None           # aria-label
    labelledby: str | None      # aria-labelledby (resolved text)
    describedby: str | None     # aria-describedby (resolved text)
    expanded: bool | None       # aria-expanded
    disabled: bool | None       # aria-disabled
    required: bool | None       # aria-required
    checked: bool | None        # aria-checked
    selected: bool | None       # aria-selected
    hidden: bool | None         # aria-hidden
    haspopup: str | None        # aria-haspopup
    live: str | None            # aria-live
    role_override: str | None   # explicit role= attribute


@dataclass
class AccessibilityNode:
    # identity
    tag: str                    # button, a, input, select, textarea
    role: str                   # resolved role
    name: str                   # accessible name (how screen reader sees it)

    # locator info
    selector: str               # best available CSS selector
    element_id: str | None      # id attribute

    # state
    visible: bool
    focusable: bool
    disabled: bool

    # aria
    aria: AriaAttributes

    # source
    source: str                 # button | link | input | select


@dataclass
class AccessibilitySnapshot:
    url: str
    total_count: int
    by_role: dict[str, int] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    nodes: list[AccessibilityNode] = field(default_factory=list)


async def extract_accessibility_tree(page: Page) -> AccessibilitySnapshot | None:
    """
    Extract accessibility tree for all interactive elements —
    buttons, links, inputs, selects — with full ARIA attributes.
    """
    log_info("Extracting accessibility tree...")

    try:
        raw_nodes = await page.evaluate("""
            () => {
                // ── helpers ───────────────────────────────────────────────

                function resolveText(id) {
                    if (!id) return null;
                    const el = document.getElementById(id);
                    return el ? (el.innerText || el.textContent || "").trim() : null;
                }

                function resolveDescribedBy(ids) {
                    if (!ids) return null;
                    return ids
                        .split(/\\s+/)
                        .map(id => resolveText(id))
                        .filter(Boolean)
                        .join(" ") || null;
                }

                function getAccessibleName(el) {
                    // priority: aria-label > aria-labelledby > label[for] > placeholder > text content
                    const ariaLabel = el.getAttribute("aria-label");
                    if (ariaLabel) return ariaLabel.trim();

                    const labelledBy = el.getAttribute("aria-labelledby");
                    if (labelledBy) {
                        const resolved = resolveText(labelledBy);
                        if (resolved) return resolved;
                    }

                    if (el.id) {
                        const label = document.querySelector(`label[for="${el.id}"]`);
                        if (label) return (label.innerText || label.textContent || "").trim();
                    }

                    const closestLabel = el.closest("label");
                    if (closestLabel) return (closestLabel.innerText || closestLabel.textContent || "").trim();

                    const placeholder = el.getAttribute("placeholder");
                    if (placeholder) return placeholder.trim();

                    return (el.innerText || el.textContent || "").trim();
                }

                function getRole(el) {
                    const explicit = el.getAttribute("role");
                    if (explicit) return explicit;

                    const tag = el.tagName.toLowerCase();
                    const type = (el.getAttribute("type") || "").toLowerCase();

                    if (tag === "button") return "button";
                    if (tag === "a" && el.hasAttribute("href")) return "link";
                    if (tag === "select") return "combobox";
                    if (tag === "textarea") return "textbox";
                    if (tag === "input") {
                        if (["submit", "button", "reset"].includes(type)) return "button";
                        if (type === "checkbox") return "checkbox";
                        if (type === "radio") return "radio";
                        return "textbox";
                    }
                    return tag;
                }

                function getBestSelector(el) {
                    if (el.id) return `#${el.id}`;

                    // try data attributes
                    for (const attr of ["data-testid", "data-cy", "data-qa"]) {
                        const val = el.getAttribute(attr);
                        if (val) return `[${attr}="${val}"]`;
                    }

                    // try name attribute
                    const name = el.getAttribute("name");
                    const tag  = el.tagName.toLowerCase();
                    if (name) return `${tag}[name="${name}"]`;

                    // try aria-label
                    const ariaLabel = el.getAttribute("aria-label");
                    if (ariaLabel) return `${tag}[aria-label="${ariaLabel}"]`;

                    // fallback to tag
                    return tag;
                }

                function isVisible(el) {
                    const style = window.getComputedStyle(el);
                    if (style.display === "none") return false;
                    if (style.visibility === "hidden") return false;
                    if (parseFloat(style.opacity) === 0) return false;
                    const rect = el.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                }

                function isFocusable(el) {
                    if (el.tabIndex < 0) return false;
                    if (el.disabled) return false;
                    return true;
                }

                function getAriaAttributes(el) {
                    return {
                        label:         el.getAttribute("aria-label")    || null,
                        labelledby:    resolveText(el.getAttribute("aria-labelledby")),
                        describedby:   resolveDescribedBy(el.getAttribute("aria-describedby")),
                        expanded:      el.hasAttribute("aria-expanded")
                                         ? el.getAttribute("aria-expanded") === "true"
                                         : null,
                        disabled:      el.hasAttribute("aria-disabled")
                                         ? el.getAttribute("aria-disabled") === "true"
                                         : null,
                        required:      el.hasAttribute("aria-required")
                                         ? el.getAttribute("aria-required") === "true"
                                         : null,
                        checked:       el.hasAttribute("aria-checked")
                                         ? el.getAttribute("aria-checked") === "true"
                                         : null,
                        selected:      el.hasAttribute("aria-selected")
                                         ? el.getAttribute("aria-selected") === "true"
                                         : null,
                        hidden:        el.hasAttribute("aria-hidden")
                                         ? el.getAttribute("aria-hidden") === "true"
                                         : null,
                        haspopup:      el.getAttribute("aria-haspopup") || null,
                        live:          el.getAttribute("aria-live")     || null,
                        role_override: el.getAttribute("role")          || null,
                    };
                }

                function extractNodes(selector, source) {
                    return Array.from(document.querySelectorAll(selector)).map(el => {
                        return {
                            tag:        el.tagName.toLowerCase(),
                            role:       getRole(el),
                            name:       getAccessibleName(el),
                            selector:   getBestSelector(el),
                            element_id: el.id || null,
                            visible:    isVisible(el),
                            focusable:  isFocusable(el),
                            disabled:   el.disabled || false,
                            aria:       getAriaAttributes(el),
                            source,
                        };
                    });
                }

                // ── collect all interactive elements ──────────────────────

                const nodes = [
                    ...extractNodes("button, input[type='submit'], input[type='button'], input[type='reset']", "button"),
                    ...extractNodes("a[href]", "link"),
                    ...extractNodes("input:not([type='submit']):not([type='button']):not([type='reset']):not([type='hidden']), textarea", "input"),
                    ...extractNodes("select", "select"),
                ];

                // deduplicate by selector + role
                const seen = new Set();
                return nodes.filter(node => {
                    const key = `${node.role}::${node.selector}::${node.name}`;
                    if (seen.has(key)) return false;
                    seen.add(key);
                    return true;
                });
            }
        """)

        # ── build dataclasses ─────────────────────────────────────────────

        nodes = []
        for r in raw_nodes:
            aria = AriaAttributes(
                label=r["aria"]["label"],
                labelledby=r["aria"]["labelledby"],
                describedby=r["aria"]["describedby"],
                expanded=r["aria"]["expanded"],
                disabled=r["aria"]["disabled"],
                required=r["aria"]["required"],
                checked=r["aria"]["checked"],
                selected=r["aria"]["selected"],
                hidden=r["aria"]["hidden"],
                haspopup=r["aria"]["haspopup"],
                live=r["aria"]["live"],
                role_override=r["aria"]["role_override"],
            )
            nodes.append(AccessibilityNode(
                tag=r["tag"],
                role=r["role"],
                name=r["name"],
                selector=r["selector"],
                element_id=r["element_id"],
                visible=r["visible"],
                focusable=r["focusable"],
                disabled=r["disabled"],
                aria=aria,
                source=r["source"],
            ))

        # ── compute summary ───────────────────────────────────────────────

        by_role: dict[str, int] = {}
        for node in nodes:
            by_role[node.role] = by_role.get(node.role, 0) + 1

        issues = _detect_issues(nodes)

        log_success(f"Accessibility tree extracted — {len(nodes)} nodes, {len(issues)} issues.")

        return AccessibilitySnapshot(
            url=page.url,
            total_count=len(nodes),
            by_role=by_role,
            issues=issues,
            nodes=nodes,
        )

    except Exception as error:
        log_error(f"Accessibility extraction failed: {error}")
        return None


def _detect_issues(nodes: list[AccessibilityNode]) -> list[str]:
    """
    Basic issue detection on the extracted nodes.
    """
    issues = []

    for node in nodes:
        label = f"<{node.tag}> [{node.selector}]"

        # missing accessible name
        if not node.name or not node.name.strip():
            issues.append(f"Missing accessible name: {label} (role={node.role})")

        # aria-hidden but still focusable
        if node.aria.hidden and node.focusable:
            issues.append(f"aria-hidden=true but element is focusable: {label}")

        # disabled via aria but not via HTML attribute
        if node.aria.disabled and not node.disabled:
            issues.append(f"aria-disabled=true but missing HTML disabled attribute: {label}")

        # input with no label at all
        if node.source == "input" and not node.name:
            issues.append(f"Input field has no label: {label} (type={node.tag})")

    # duplicate accessible names within same role
    seen_names: dict[str, list[str]] = {}
    for node in nodes:
        key = f"{node.role}::{(node.name or '').strip().lower()}"
        seen_names.setdefault(key, []).append(node.selector)

    for key, selectors in seen_names.items():
        if len(selectors) > 1:
            role, name = key.split("::", 1)
            issues.append(
                f"Duplicate accessible name '{name}' for role '{role}': {', '.join(selectors)}"
            )

    return issues