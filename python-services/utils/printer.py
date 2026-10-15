from rich.table import Table
from rich.panel import Panel
from rich.columns import Columns
from rich import box

from utils.logger import console
from extractors.page_content import PageContent
from extractors.accessibility import AccessibilitySnapshot
from core.auditor import AuditReport, StepResult

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
    if not any([m.description, m.keywords, m.author, m.viewport]):
        console.print("[dim]Meta — none found[/dim]\n")
        return

    table = Table(title="Meta Tags", box=box.SIMPLE, show_header=True)
    table.add_column("Key",   style="cyan",  no_wrap=True)
    table.add_column("Value", style="white")

    for key in ["description", "keywords", "author", "viewport"]:
        value = getattr(m, key, None)
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


def print_accessibility_snapshot(snapshot: AccessibilitySnapshot):
    """
    Print full accessibility tree to terminal.
    """
    console.rule("[step]Step 3 — Accessibility Tree[/step]")

    _print_accessibility_summary(snapshot)
    _print_accessibility_nodes(snapshot)
    _print_accessibility_issues(snapshot)

    console.rule("[success]Accessibility extraction complete[/success]")


def _print_accessibility_summary(snapshot: AccessibilitySnapshot):
    table = Table(title="Summary", box=box.SIMPLE)
    table.add_column("Role",  style="cyan")
    table.add_column("Count", style="white", justify="right")

    for role, count in sorted(snapshot.by_role.items()):
        table.add_row(role, str(count))

    table.add_row("[bold]Total[/bold]", f"[bold]{snapshot.total_count}[/bold]")
    console.print(table)


def _print_accessibility_nodes(snapshot: AccessibilitySnapshot):
    if not snapshot.nodes:
        console.print("[dim]No nodes found[/dim]\n")
        return

    table = Table(
        title=f"Interactive Elements ({snapshot.total_count})",
        box=box.SIMPLE,
        show_lines=True,
    )
    table.add_column("Role",      style="cyan",   width=10)
    table.add_column("Name",      style="white",  max_width=25)
    table.add_column("Selector",  style="yellow", max_width=25)
    table.add_column("Visible",   width=7)
    table.add_column("Focusable", width=9)
    table.add_column("Disabled",  width=9)
    table.add_column("ARIA",      style="dim",    max_width=30)

    for node in snapshot.nodes:
        # build compact aria summary
        aria_parts = []
        if node.aria.label:
            aria_parts.append(f"label={node.aria.label[:15]}")
        if node.aria.expanded is not None:
            aria_parts.append(f"expanded={node.aria.expanded}")
        if node.aria.required:
            aria_parts.append("required")
        if node.aria.hidden:
            aria_parts.append("hidden")
        if node.aria.haspopup:
            aria_parts.append(f"popup={node.aria.haspopup}")
        aria_str = ", ".join(aria_parts) or "-"

        table.add_row(
            node.role,
            node.name or "[unnamed]",
            node.selector,
            "[green]yes[/green]" if node.visible  else "[red]no[/red]",
            "[green]yes[/green]" if node.focusable else "[red]no[/red]",
            "[red]yes[/red]"     if node.disabled  else "no",
            aria_str,
        )

    console.print(table)


def _print_accessibility_issues(snapshot: AccessibilitySnapshot):
    if not snapshot.issues:
        console.print("[success]✓ No accessibility issues detected[/success]\n")
        return

    table = Table(
        title=f"Issues ({len(snapshot.issues)})",
        box=box.SIMPLE,
    )
    table.add_column("#",       style="dim",  width=4)
    table.add_column("Issue",   style="red")

    for index, issue in enumerate(snapshot.issues, start=1):
        table.add_row(str(index), issue)

    console.print(table)

def print_audit_report(report: AuditReport):
    """
    Print the full audit report — step results + content + accessibility + combined summary.
    """
    console.rule("[bold cyan]FULL PAGE AUDIT REPORT[/bold cyan]")

    _print_step_results(report)

    if report.content:
        print_page_content(report.content)

    if report.accessibility:
        print_accessibility_snapshot(report.accessibility)

    # combined summary
    _print_combined_summary(report)


def _print_step_results(report: AuditReport):
    table = Table(title="Step Results", box=box.SIMPLE)
    table.add_column("Step",     style="cyan",  width=6)
    table.add_column("Name",     style="white")
    table.add_column("Status",   width=8)
    table.add_column("Duration", style="dim", justify="right", width=10)
    table.add_column("Error",    style="red",   max_width=40)

    for step in report.steps:
        status_str = (
            "[green]passed[/green]" if step.status == "passed"
            else "[red]failed[/red]"
        )
        table.add_row(
            str(step.step),
            step.name,
            status_str,
            f"{step.duration_ms}ms",
            step.error or "-",
        )

    console.print(table)


def _print_combined_summary(report: AuditReport):
    console.rule("[bold]Combined Summary[/bold]")

    # health score panel
    score = report.health_score
    score_color = (
        "green"  if score >= 80 else
        "yellow" if score >= 50 else
        "red"
    )

    breakdown = report.health_breakdown
    console.print(Panel(
        f"[bold {score_color}]Health Score: {score}/100[/bold {score_color}]\n\n"
        f"  Navigation:      {breakdown.get('navigation', 0)}/20\n"
        f"  Content:         {breakdown.get('content', 0)}/30\n"
        f"  Accessibility:   {breakdown.get('accessibility', 0)}/50\n\n"
        f"  Screenshot:      {report.screenshot_path or 'none'}\n"
        f"  Status:          {report.status}",
        title="Audit Summary",
        border_style=score_color,
    ))

    # all issues combined
    if report.all_issues:
        table = Table(title=f"All Issues ({len(report.all_issues)})", box=box.SIMPLE)
        table.add_column("#",     style="dim", width=4)
        table.add_column("Issue", style="red")

        for index, issue in enumerate(report.all_issues, start=1):
            table.add_row(str(index), issue)

        console.print(table)
    else:
        console.print("[success]✓ No issues found across all steps[/success]")

    console.rule("[bold cyan]END OF REPORT[/bold cyan]")