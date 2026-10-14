from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box

from utils.logger import console
from extractors.page_content import PageContent


def print_page_content(content: PageContent):
    """
    Print full extracted page content to terminal in a clean format.
    """
    console.rule("[step]Step 2 — Page Content Extraction[/step]")

    _print_overview(content)
    _print_meta(content)
    _print_headings(content)
    _print_links(content)
    _print_buttons(content)
    _print_images(content)
    _print_forms(content)

    console.rule("[success]Extraction complete[/success]")


def _print_overview(content: PageContent):
    console.print(Panel(
        f"[bold]Title:[/bold]  {content.title}\n"
        f"[bold]URL:[/bold]    {content.url}",
        title="Overview",
        border_style="cyan",
    ))


def _print_meta(content: PageContent):
    m = content.meta
    if not any([m.get("description"), m.get("keywords"), m.get("author"), m.get("viewport")]):
        console.print("[dim]Meta — none found[/dim]\n")
        return

    table = Table(title="Meta Tags", box=box.SIMPLE, show_header=True)
    table.add_column("Key",   style="cyan",  no_wrap=True)
    table.add_column("Value", style="white")

    for key in ["description", "keywords", "author", "viewport"]:
        value = m.get(key)
        if value:
            table.add_row(key, value)

    console.print(table)


def _print_headings(content: PageContent):
    if not content.headings:
        console.print("[dim]Headings — none found[/dim]\n")
        return

    table = Table(title=f"Headings ({len(content.headings)})", box=box.SIMPLE)
    table.add_column("Level", style="cyan",  width=6)
    table.add_column("Text",  style="white")

    for h in content.headings:
        table.add_row(h.level.upper(), h.text)

    console.print(table)


def _print_links(content: PageContent):
    if not content.links:
        console.print("[dim]Links — none found[/dim]\n")
        return

    table = Table(title=f"Links ({len(content.links)})", box=box.SIMPLE)
    table.add_column("Text",     style="white",   max_width=30)
    table.add_column("URL",      style="cyan",    max_width=50)
    table.add_column("External", style="yellow",  width=8)

    for l in content.links:
        table.add_row(
            l.text or "-",
            l.href,
            "yes" if l.is_external else "no",
        )

    console.print(table)


def _print_buttons(content: PageContent):
    if not content.buttons:
        console.print("[dim]Buttons — none found[/dim]\n")
        return

    table = Table(title=f"Buttons ({len(content.buttons)})", box=box.SIMPLE)
    table.add_column("Text",  style="white",  max_width=30)
    table.add_column("Type",  style="cyan",   width=8)
    table.add_column("ID",    style="yellow", max_width=20)

    for b in content.buttons:
        table.add_row(
            b.text or "[unnamed]",
            b.button_type,
            b.element_id or "-",
        )

    console.print(table)


def _print_images(content: PageContent):
    if not content.images:
        console.print("[dim]Images — none found[/dim]\n")
        return

    table = Table(title=f"Images ({len(content.images)})", box=box.SIMPLE)
    table.add_column("Src",     style="cyan",   max_width=50)
    table.add_column("Alt",     style="white",  max_width=30)
    table.add_column("Has Alt", style="yellow", width=8)

    for i in content.images:
        table.add_row(
            i.src,
            i.alt or "-",
            "[green]yes[/green]" if i.has_alt else "[red]no[/red]",
        )

    console.print(table)


def _print_forms(content: PageContent):
    if not content.forms:
        console.print("[dim]Forms — none found[/dim]\n")
        return

    for index, form in enumerate(content.forms, start=1):
        table = Table(
            title=f"Form {index} — action={form.action or 'none'} method={form.method or 'none'}",
            box=box.SIMPLE,
        )
        table.add_column("Label",       style="white",  max_width=20)
        table.add_column("Type",        style="cyan",   width=10)
        table.add_column("Name",        style="yellow", max_width=20)
        table.add_column("Placeholder", style="dim",    max_width=25)
        table.add_column("Required",    style="red",    width=8)

        for f in form.fields:
            table.add_row(
                f.label or "-",
                f.field_type,
                f.name or "-",
                f.placeholder or "-",
                "[red]yes[/red]" if f.required else "no",
            )

        console.print(table)