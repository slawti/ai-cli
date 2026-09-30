"""Interactive chat loop: input session, command dispatch, startup flow."""

import sys
from pathlib import Path

from openai import APIError, AuthenticationError, RateLimitError
from rich.console import Console

from .chat import build_client, save_conversation, stream_answer
from .complete import ModelCompleter
from .config import ConfigError, load_settings
from .models import ModelCatalog
from .ui import (
    print_banner,
    print_error,
    print_help,
    print_status,
    show_model_matches,
)

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.formatted_text import HTML
    from prompt_toolkit.history import FileHistory
    from prompt_toolkit.key_binding import KeyBindings

    HAS_PROMPT_TOOLKIT = True
except ImportError:
    PromptSession = None  # type: ignore
    HTML = None  # type: ignore
    FileHistory = None  # type: ignore
    KeyBindings = None  # type: ignore
    HAS_PROMPT_TOOLKIT = False


def _history():
    if not HAS_PROMPT_TOOLKIT:
        return None
    try:
        return FileHistory(str(Path.home() / ".ai_cli_history"))
    except Exception:
        return None


def _key_bindings():
    """Enter sends, Alt+Enter inserts a newline (multiline input)."""
    kb = KeyBindings()

    @kb.add("enter")
    def _(event):
        event.current_buffer.validate_and_handle()

    @kb.add("escape", "enter")
    def _(event):
        event.current_buffer.insert_text("\n")

    return kb


def build_session(state, catalog):
    """Prompt session with history, multiline, toolbar, completion."""
    if not HAS_PROMPT_TOOLKIT:
        return None
    try:
        toolbar = lambda: HTML(  # noqa: E731
            " <b>{}</b>  |  Enter: send  Alt+Enter: newline  Tab: complete  /help".format(
                _escape(str(state["model"]))
            )
        )
        return PromptSession(
            completer=ModelCompleter(catalog),
            history=_history(),
            multiline=True,
            key_bindings=_key_bindings(),
            bottom_toolbar=toolbar,
            complete_while_typing=False,
        )
    except Exception:
        return None


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def handle_model_switch(console, state, catalog, arg):
    arg = (arg or "").strip().strip("\"'")
    if not arg:
        console.print("[yellow]Usage: /model <model_name> (Tab completes)[/yellow]")
        return
    if arg.isdigit() and catalog.last_search:
        idx = int(arg) - 1
        if 0 <= idx < len(catalog.last_search):
            state["model"] = catalog.last_search[idx].get("id", state["model"])
            console.print(f"[green]Switched model to {state['model']}[/green]")
        else:
            console.print("[yellow]Number out of range for last search.[/yellow]")
        return
    exact = catalog.find_exact(arg)
    if exact:
        state["model"] = exact.get("id", arg)
        console.print(f"[green]Switched model to {state['model']}[/green]")
        return
    if len(catalog):
        matches, total = catalog.search(arg)
        if total == 1:
            state["model"] = matches[0].get("id", arg)
            console.print(f"[green]Switched model to {state['model']}[/green]")
            return
        if total > 1:
            show_model_matches(console, catalog, matches, total)
            return
    state["model"] = arg
    console.print(
        f"[green]Switched model to {state['model']}[/green]\n"
        "[dim](Not in cached catalog; will try it on next request.)[/dim]"
    )


def handle_models_command(console, catalog, arg):
    arg = (arg or "").strip()
    if "--refresh" in arg:
        with console.status("Refreshing model list from OpenRouter..."):
            try:
                catalog.refresh()
                console.print(
                    f"[green]Loaded {len(catalog)} models "
                    f"({catalog.free_count} free).[/green]"
                )
            except Exception as e:
                print_error(console, f"Could not refresh model list ({e}).")
                return
        arg = arg.replace("--refresh", "").strip()
        if not arg:
            return
    free_only = "--free" in arg
    query = arg.replace("--free", "").strip().strip("\"'")
    if not len(catalog):
        console.print("[dim]No cached list; fetching from OpenRouter...[/dim]")
        try:
            catalog.refresh()
        except Exception as e:
            print_error(
                console,
                f"Could not fetch model list ({e}).",
                "Manual /model <name> still works.",
            )
            return
    matches, total = catalog.search(query, free_only=free_only)
    scope = "free " if free_only else ""
    if total == 0:
        console.print(
            f"[yellow]No {scope}models match '{query}'. "
            "Try /models --refresh.[/yellow]"
        )
        return
    console.print(
        f"[dim]{total} matching {scope}model(s) "
        f"({len(catalog)} total, {catalog.free_count} free).[/dim]"
    )
    show_model_matches(console, catalog, matches, total, free_only=free_only)


def main(argv=None) -> int:
    console = Console()
    try:
        settings = load_settings(argv)
    except ConfigError as e:
        print_error(console, str(e).split("\n")[0], "\n".join(str(e).split("\n")[1:]))
        return 1
    except SystemExit as e:  # --help / argparse errors
        return int(e.code or 0)

    client = build_client(settings.api_key)
    catalog = ModelCatalog()
    state = {"model": settings.model, "markdown": not settings.no_markdown}

    with console.status("Fetching OpenRouter model catalog..."):
        try:
            catalog.refresh()
        except Exception:
            pass
    if len(catalog):
        console.print(
            f"[green]Loaded {len(catalog)} models "
            f"({catalog.free_count} free).[/green]"
        )
    else:
        console.print(
            "[yellow]Could not fetch model list. "
            "Manual /model <name> still works.[/yellow]"
        )
    if not HAS_PROMPT_TOOLKIT:
        console.print(
            "[yellow]Tip: install prompt_toolkit for Tab autocomplete, "
            "history, and multiline input.[/yellow]"
        )

    messages = []
    if settings.system_prompt:
        messages.append({"role": "system", "content": settings.system_prompt})

    print_banner(
        console,
        state["model"],
        catalog,
        state["markdown"],
        bool(settings.system_prompt),
    )

    session = build_session(state, catalog)

    def read_input():
        if session is not None:
            return session.prompt("\nYou: ")
        console.print("\n[bold cyan]You:[/bold cyan] ", end="")
        return input()

    visible_count = lambda: sum(
        1 for m in messages if m.get("role") in ("user", "assistant")
    )

    try:
        while True:
            try:
                user_input = read_input()
                stripped = user_input.strip()
                lowered = stripped.lower()

                if lowered == "/exit":
                    console.print("[yellow]Goodbye![/yellow]")
                    break
                if lowered == "/clear":
                    messages = (
                        [{"role": "system", "content": settings.system_prompt}]
                        if settings.system_prompt
                        else []
                    )
                    console.print("[green]Conversation cleared.[/green]")
                    print_status(
                        console, state["model"], catalog,
                        visible_count(), state["markdown"],
                    )
                    continue
                if lowered == "/help":
                    print_help(console)
                    continue
                if lowered == "/md":
                    state["markdown"] = not state["markdown"]
                    console.print(
                        "[green]Markdown rendering on.[/green]"
                        if state["markdown"]
                        else "[dim]Markdown rendering off (plain text).[/dim]"
                    )
                    continue
                if lowered == "/model":
                    console.print(f"[cyan]Current model:[/cyan] {state['model']}")
                    continue
                if lowered.startswith("/model "):
                    handle_model_switch(
                        console, state, catalog, stripped.split(maxsplit=1)[1]
                    )
                    continue
                if lowered == "/models" or lowered.startswith("/models "):
                    parts = stripped.split(maxsplit=1)
                    handle_models_command(
                        console, catalog, parts[1] if len(parts) > 1 else ""
                    )
                    continue
                if lowered == "/save" or lowered.startswith("/save "):
                    parts = stripped.split(maxsplit=1)
                    save_conversation(
                        console, messages, state["model"],
                        parts[1] if len(parts) > 1 else None,
                    )
                    continue
                if not stripped:
                    continue

                messages.append({"role": "user", "content": user_input})
                try:
                    answer = stream_answer(
                        console, client, state["model"], messages, state["markdown"]
                    )
                except (APIError, RateLimitError, AuthenticationError) as e:
                    messages.pop()
                    print_error(
                        console, f"API Error: {e}",
                        "Your message was kept out of history; try again or /model.",
                    )
                    continue
                messages.append({"role": "assistant", "content": answer})

            except (APIError, RateLimitError, AuthenticationError) as e:
                print_error(console, f"API Error: {e}")
            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted. Type /exit to quit.[/yellow]")
            except EOFError:
                console.print("\n[yellow]Goodbye![/yellow]")
                break
            except Exception as e:
                print_error(console, f"Unexpected error: {e}")
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
