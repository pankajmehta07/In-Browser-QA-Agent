from dataclasses import dataclass, field
from playwright.async_api import Page

from utils.logger import log_info, log_success, log_error


@dataclass
class MetaInfo:
    description: str | None
    keywords: str | None
    author: str | None
    viewport: str | None


@dataclass
class Heading:
    level: str   # h1, h2, h3 etc
    text: str


@dataclass
class Link:
    text: str
    href: str
    is_external: bool


@dataclass
class Button:
    text: str
    button_type: str    # button, submit, reset
    has_id: bool
    element_id: str | None


@dataclass
class Image:
    src: str
    alt: str | None
    has_alt: bool


@dataclass
class FormField:
    label: str | None
    field_type: str     # text, email, password, textarea, select etc
    name: str | None
    placeholder: str | None
    required: bool


@dataclass
class Form:
    action: str | None
    method: str | None
    fields: list[FormField] = field(default_factory=list)


@dataclass
class PageContent:
    url: str
    title: str
    meta: MetaInfo
    headings: list[Heading] = field(default_factory=list)
    links: list[Link] = field(default_factory=list)
    buttons: list[Button] = field(default_factory=list)
    images: list[Image] = field(default_factory=list)
    forms: list[Form] = field(default_factory=list)


async def extract_page_content(page: Page) -> PageContent | None:
    """
    Extract full page content from a loaded Playwright page.
    Returns a PageContent dataclass or None if extraction fails.
    """
    log_info("Extracting page content...")

    try:
        url   = page.url
        title = await page.title()

        meta    = await _extract_meta(page)
        headings = await _extract_headings(page)
        links   = await _extract_links(page, url)
        buttons = await _extract_buttons(page)
        images  = await _extract_images(page)
        forms   = await _extract_forms(page)

        log_success("Page content extracted successfully.")

        return PageContent(
            url=url,
            title=title,
            meta=meta,
            headings=headings,
            links=links,
            buttons=buttons,
            images=images,
            forms=forms,
        )

    except Exception as error:
        log_error(f"Page content extraction failed: {error}")
        return None


# ─── private helpers ──────────────────────────────────────────────────────────

async def _extract_meta(page: Page) -> MetaInfo:
    raw = await page.evaluate("""
        () => {
            function getMeta(name) {
                const el = document.querySelector(
                    `meta[name="${name}"], meta[property="${name}"]`
                );
                return el ? el.getAttribute("content") : null;
            }
            return {
                description: getMeta("description"),
                keywords:    getMeta("keywords"),
                author:      getMeta("author"),
                viewport:    getMeta("viewport"),
            };
        }
    """)

    return MetaInfo(**raw)


async def _extract_headings(page: Page) -> list[Heading]:
    raw = await page.evaluate("""
        () => {
            const headings = [];
            document.querySelectorAll("h1, h2, h3, h4, h5, h6").forEach(el => {
                const text = el.innerText.trim();
                if (text) {
                    headings.push({ level: el.tagName.toLowerCase(), text });
                }
            });
            return headings;
        }
    """)
    return [Heading(**h) for h in raw]


async def _extract_links(page: Page, base_url: str) -> list[Link]:
    raw = await page.evaluate("""
        (baseUrl) => {
            const links = [];
            document.querySelectorAll("a[href]").forEach(el => {
                const href = el.getAttribute("href");
                const text = el.innerText.trim();
                if (!href || href.startsWith("#")) return;
                const isExternal = href.startsWith("http") &&
                    !href.includes(new URL(baseUrl).hostname);
                links.push({ text: text || href, href, is_external: isExternal });
            });
            return links;
        }
    """, base_url)
    return [Link(**l) for l in raw]


async def _extract_buttons(page: Page) -> list[Button]:
    raw = await page.evaluate("""
        () => {
            const buttons = [];

            // <button> elements
            document.querySelectorAll("button").forEach(el => {
                buttons.push({
                    text:        el.innerText.trim() || el.getAttribute("aria-label") || "",
                    button_type: el.getAttribute("type") || "button",
                    has_id:      Boolean(el.id),
                    element_id:  el.id || null,
                });
            });

            // <input type="submit|button|reset">
            document.querySelectorAll(
                "input[type='submit'], input[type='button'], input[type='reset']"
            ).forEach(el => {
                buttons.push({
                    text:        el.getAttribute("value") || el.getAttribute("aria-label") || "",
                    button_type: el.getAttribute("type") || "button",
                    has_id:      Boolean(el.id),
                    element_id:  el.id || null,
                });
            });

            return buttons;
        }
    """)
    return [Button(**b) for b in raw]


async def _extract_images(page: Page) -> list[Image]:
    raw = await page.evaluate("""
        () => {
            const images = [];
            document.querySelectorAll("img").forEach(el => {
                const src = el.getAttribute("src") || "";
                const alt = el.getAttribute("alt");
                if (src) {
                    images.push({ src, alt: alt || null, has_alt: alt !== null });
                }
            });
            return images;
        }
    """)
    return [Image(**i) for i in raw]


async def _extract_forms(page: Page) -> list[Form]:
    raw = await page.evaluate("""
        () => {
            const forms = [];

            document.querySelectorAll("form").forEach(form => {
                const fields = [];

                form.querySelectorAll(
                    "input:not([type='hidden']):not([type='submit']):not([type='button']):not([type='reset']), textarea, select"
                ).forEach(el => {
                    // find associated label
                    let label = null;

                    if (el.id) {
                        const labelEl = document.querySelector(`label[for="${el.id}"]`);
                        if (labelEl) label = labelEl.innerText.trim();
                    }

                    if (!label) {
                        const closest = el.closest("label");
                        if (closest) label = closest.innerText.trim();
                    }

                    fields.push({
                        label:       label || null,
                        field_type:  el.tagName === "TEXTAREA" ? "textarea"
                                   : el.tagName === "SELECT"   ? "select"
                                   : el.getAttribute("type")   || "text",
                        name:        el.getAttribute("name")        || null,
                        placeholder: el.getAttribute("placeholder") || null,
                        required:    el.hasAttribute("required"),
                    });
                });

                forms.push({
                    action: form.getAttribute("action") || null,
                    method: form.getAttribute("method") || null,
                    fields,
                });
            });

            return forms;
        }
    """)

    result = []
    for f in raw:
        form = Form(
            action=f["action"],
            method=f["method"],
            fields=[FormField(**field) for field in f["fields"]],
        )
        result.append(form)

    return result