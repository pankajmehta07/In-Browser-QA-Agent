import asyncio
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from extractors.accessibility import AccessibilitySnapshot


_TRACKED_RESOURCES = {"document", "xhr", "fetch"}
_MAX_STORED_EVENTS = 50
_MAX_REPORTED_EVENTS = 15
_MAX_DIFF_ITEMS = 10
_MAX_TEXT = 160


def _short_url(url: str) -> str:
    # Query strings are dropped so tokens in URLs are not sent to the LLM.
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}{parts.path}"[:200]


class PageMonitor:
    """Records console output, page errors, dialogs, and form/API network results for a page."""

    def __init__(self, page):
        self.page = page
        self._events: list[dict] = []
        self._pending: set = set()
        self._last_activity = 0.0
        on = getattr(page, "on", None)
        self._attached = on is not None
        if not self._attached:
            return
        on("console", self._on_console)
        on("pageerror", self._on_page_error)
        on("dialog", self._on_dialog)
        on("request", self._on_request)
        on("requestfinished", self._on_request_done)
        on("requestfailed", self._on_request_failed)
        on("response", self._on_response)

    def _record(self, event: dict):
        self._events.append(event)
        del self._events[:-_MAX_STORED_EVENTS]

    def _on_console(self, message):
        self._record({"type": f"console_{message.type}", "text": message.text[:_MAX_TEXT * 2]})

    def _on_page_error(self, error):
        self._record({"type": "page_error", "text": str(error)[:_MAX_TEXT * 2]})

    async def _on_dialog(self, dialog):
        self._record({"type": f"dialog_{dialog.type}", "text": dialog.message[:_MAX_TEXT * 2]})
        try:
            # Prompts need input the agent cannot supply; other dialogs are acknowledged.
            if dialog.type == "prompt":
                await dialog.dismiss()
            else:
                await dialog.accept()
        except Exception:
            pass

    def _on_request(self, request):
        if request.resource_type in _TRACKED_RESOURCES:
            self._pending.add(request)
            self._last_activity = time.monotonic()

    def _on_request_done(self, request):
        if request in self._pending:
            self._pending.discard(request)
            self._last_activity = time.monotonic()

    def _on_request_failed(self, request):
        self._on_request_done(request)
        if request.resource_type in _TRACKED_RESOURCES:
            self._record({
                "type": "request_failed",
                "method": request.method,
                "url": _short_url(request.url),
                "error": request.failure,
            })

    def _on_response(self, response):
        request = response.request
        if request.resource_type in _TRACKED_RESOURCES and (
            request.method != "GET" or response.status >= 400
        ):
            self._record({
                "type": "response",
                "method": request.method,
                "url": _short_url(response.url),
                "status": response.status,
            })

    def drain(self) -> list[dict]:
        events, self._events = self._events, []
        return events[-_MAX_REPORTED_EVENTS:]

    async def settle(self, max_wait: float = 3.0, quiet: float = 0.5):
        """Wait briefly for document/XHR/fetch requests triggered by an action to finish."""
        if not self._attached:
            return
        deadline = time.monotonic() + max_wait
        await asyncio.sleep(0.2)
        while time.monotonic() < deadline:
            if not self._pending and time.monotonic() - self._last_activity >= quiet:
                return
            await asyncio.sleep(0.1)


_STATE_SCRIPT = """() => [
    location.href,
    document.title,
    document.body ? document.body.innerText : "",
    [...document.querySelectorAll("button,input,select,textarea,[aria-busy],[role=alert],[role=status]")]
        .map(e => [e.tagName, e.disabled, e.getAttribute("aria-busy"), e.getAttribute("aria-invalid"), (e.value || "").length].join(":"))
        .join("|"),
]"""


async def _page_signature(page) -> tuple | None:
    try:
        return tuple(await page.evaluate(_STATE_SCRIPT))
    except Exception:
        return None


async def wait_for_page_change(page, timeout: float, quiet: float = 1.0) -> bool:
    """Wait until the page differs from its current state and then stays stable for `quiet` seconds."""
    deadline = time.monotonic() + timeout
    baseline = last = await _page_signature(page)
    last_change = None
    while time.monotonic() < deadline:
        await asyncio.sleep(0.25)
        current = await _page_signature(page)
        now = time.monotonic()
        if current != last:
            last, last_change = current, now
        if last_change is not None and last != baseline and now - last_change >= quiet:
            return True
    return last_change is not None and last != baseline


# validity.valid is read instead of checkValidity() so no "invalid" events are fired.
_INVALID_FIELDS_SCRIPT = """() => [...document.querySelectorAll("input,select,textarea,[aria-invalid=true]")]
    .filter(e => (e.willValidate && e.validity && !e.validity.valid) || e.getAttribute("aria-invalid") === "true")
    .filter(e => e.offsetParent !== null)
    .slice(0, 10)
    .map(e => {
        const label = (e.labels && e.labels[0] && e.labels[0].innerText) || e.getAttribute("aria-label")
            || e.getAttribute("placeholder") || e.name || e.id || e.tagName.toLowerCase();
        const describedBy = (e.getAttribute("aria-describedby") || "").split(/\\s+/)
            .map(id => document.getElementById(id)).filter(Boolean).map(el => el.innerText.trim()).join(" ");
        return {field: label.trim().slice(0, 80), message: (e.validationMessage || describedBy).slice(0, 160)};
    })"""


async def collect_invalid_fields(page) -> list[dict]:
    """Visible form fields that currently fail native or ARIA validation, with their messages."""
    try:
        return await page.evaluate(_INVALID_FIELDS_SCRIPT)
    except Exception:
        return []


@dataclass
class PageState:
    url: str
    title: str
    text: str
    snapshot: AccessibilitySnapshot | None


def _node_summary(node) -> dict:
    return {"role": node.role, "name": node.name[:80], "disabled": node.disabled, "visible": node.visible}


def _capped(items: list, key: str, changes: dict):
    if items:
        changes[key] = items[:_MAX_DIFF_ITEMS]
        if len(items) > _MAX_DIFF_ITEMS:
            changes[f"{key}_total"] = len(items)


def diff_page_states(before: PageState, after: PageState) -> dict:
    """Summarize what changed between two page states; empty when nothing changed."""
    changes: dict = {}
    if before.url != after.url:
        changes["url"] = {"from": before.url, "to": after.url}
        return changes
    if before.title != after.title:
        changes["title"] = {"from": before.title, "to": after.title}

    old_nodes = {(n.role, n.selector): n for n in (before.snapshot.nodes if before.snapshot else [])}
    new_nodes = {(n.role, n.selector): n for n in (after.snapshot.nodes if after.snapshot else [])}
    changed = []
    for key, node in new_nodes.items():
        old = old_nodes.get(key)
        if old is None:
            continue
        old_summary, new_summary = _node_summary(old), _node_summary(node)
        fields = [field for field in ("name", "disabled", "visible") if old_summary[field] != new_summary[field]]
        if fields:
            changed.append({
                "role": node.role,
                "name": old_summary["name"],
                **{field: {"from": old_summary[field], "to": new_summary[field]} for field in fields},
            })
    _capped([_node_summary(n) for k, n in new_nodes.items() if k not in old_nodes], "elements_appeared", changes)
    _capped([_node_summary(n) for k, n in old_nodes.items() if k not in new_nodes], "elements_disappeared", changes)
    _capped(changed, "elements_changed", changes)

    old_lines = [line.strip() for line in before.text.splitlines() if line.strip()]
    new_lines = [line.strip() for line in after.text.splitlines() if line.strip()]
    old_set, new_set = set(old_lines), set(new_lines)
    _capped([line[:_MAX_TEXT] for line in dict.fromkeys(new_lines) if line not in old_set], "text_added", changes)
    _capped([line[:_MAX_TEXT] for line in dict.fromkeys(old_lines) if line not in new_set], "text_removed", changes)
    return changes
