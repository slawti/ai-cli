"""Terminal UI: banner, status, help, model picker, errors."""

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from . import __version__
from .models import ModelCatalog, is_free_model


def print_banner(
    console: Console,
    model: str,
    catalog: ModelCatalog,
    markdown_on: bool,
    system_loaded: bool,
) -> None:
    if len(catalog):
        catalog_line = (
            f"[green]{len(catalog)} models ({catalog.free_count} free)[/green] loaded. "
            "Press [cyan]Tab[/cyan] after /model for suggestions."
        )
    else:
        catalog_line = (
            "[yellow]Model catalog unavailable (offline?). "
            "Manual /model <name> still works.[/yellow]"
        )
    md_line = "Markdown rendering [green]on[/green] (/md to toggle)." if markdown_on else (
        "Markdown rendering [dim]off[/dim] (/md to toggle)."
    )
    sys_line = "System prompt loaded." if system_loaded else "No system prompt."
    body = (
        f"[bold]ai-cli[/bold] [dim]v{__version__} — OpenRouter chat[/dim]\n\n"
        f"[cyan]Model:[/cyan] {model}\n"
        f"{catalog_line}\n"
        f"[dim]{md_line} {sys_line}[/dim]\n\n"
        "[dim]Enter sends · Alt+Enter newline · Ctrl+D exits · /help for commands[/dim]"
    )
    console.print(Panel(body, title="Welcome", border_style="blue"))


def print_status(
    console: Console,
    model: str,
    catalog: ModelCatalog,
    n_messages: int,
    markdown_on: bool,
) -> None:
    md = "md:on" if markdown_on else "md:off"
    if len(catalog):
        cat = f"{len(catalog)} models"
    else:
        cat = "catalog:offline"
    console.print(
        f"[dim]model: {model} · {cat} · msgs: {n_messages} · {md}[/dim]"
    )


def print_help(console: Console) -> None:
    help_text = """[bold]Available Commands:[/bold]

[cyan]/exit[/cyan]                    - Exit the application
[cyan]/clear[/cyan]                   - Clear conversation history
[cyan]/help[/cyan]                    - Show this help message
[cyan]/model[/cyan]                   - Show current model
[cyan]/model <name>[/cyan]            - Switch model (Tab completes, number selects)
[cyan]/models [query] [--free][/cyan] - List/search all OpenRouter models
[cyan]/models --refresh[/cyan]        - Re-fetch fresh model list from OpenRouter
[cyan]/md[/cyan]                      - Toggle Markdown rendering on/off
[cyan]/save [filename][/cyan]         - Save conversation to a Markdown file"""
    console.print(Panel(help_text, title="Help", border_style="blue"))


def show_model_matches(
    console: Console,
    catalog: ModelCatalog,
    matches: list,
    total: int,
    free_only: bool = False,
) -> None:
    catalog.last_search = matches
    scope = "free " if free_only else ""
    if not matches:
        console.print(
            "[yellow]No matching models found. "
            "Try a different query or /models --refresh.[/yellow]"
        )
        return
    table = Table(title=f"Matching {scope}models", show_header=True)
    table.add_column("#", style="cyan", width=4)
    table.add_column("Model ID", style="white")
    table.add_column("Name", style="dim")
    table.add_column("Price", width=6)
    table.add_column("Ctx", justify="right", width=8)
    for i, m in enumerate(matches, start=1):
        tag = "[green]free[/green]" if is_free_model(m) else "[dim]paid[/dim]"
        ctx = m.get("context_length")
        if isinstance(ctx, int) and ctx >= 1000:
            ctx_str = f"{ctx // 1000}k"
        elif isinstance(ctx, int):
            ctx_str = str(ctx)
        else:
            ctx_str = "-"
        table.add_row(
            str(i), m.get("id", ""), str(m.get("name", ""))[:40], tag, ctx_str
        )
    console.print(table)
    if total > len(matches):
        console.print(
            f"[dim]... {total - len(matches)} more. Refine your query.[/dim]"
        )
    console.print("[dim]Select with /model <number> or /model <full-id>[/dim]")


def print_error(console: Console, message: str, hint: str = "") -> None:
    body = f"[red]{message}[/red]"
    if hint:
        body += f"\n[dim]{hint}[/dim]"
    console.print(Panel(body, title="Error", border_style="red"))


def render_answer(console: Console, answer: str, markdown_on: bool) -> None:
    if markdown_on:
        try:
            console.print(Markdown(answer or "*(empty response)*"))
            return
        except Exception:
            pass
    console.print(answer, highlight=False)
