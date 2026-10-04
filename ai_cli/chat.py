"""Chat backend: OpenRouter client, streaming, conversation export."""

from datetime import datetime
from pathlib import Path

from openai import OpenAI
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel

from .stats import format_compact


def build_client(api_key: str) -> OpenAI:
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


def _chunk_text(chunk) -> str | None:
    """Safely extract delta content; usage chunks have content-free deltas."""
    try:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            return None
        delta = getattr(choices[0], "delta", None)
        return getattr(delta, "content", None)
    except Exception:
        return None


def _chunk_usage(chunk):
    try:
        usage = getattr(chunk, "usage", None)
    except Exception:
        return None
    return usage


def _short_model(model: str, limit: int = 42) -> str:
    if len(model) <= limit:
        return model
    return model[: limit - 1] + "…"


def iter_stream_chunks(client: OpenAI, model: str, messages: list,
                       cancel_event=None):
    """Yield (text, usage) per stream chunk; shared by Rich CLI and Textual TUI.

    `text` is delta content (None when the chunk carries no text).
    `usage` is the OpenRouter usage object when present on the chunk.
    When `cancel_event` is set, the underlying stream is closed and
    iteration stops so Esc/Ctrl+C can interrupt generation.
    """
    response = client.chat.completions.create(
        model=model, messages=messages, stream=True
    )
    try:
        for chunk in response:
            if cancel_event is not None:
                try:
                    if cancel_event.is_set():
                        break
                except Exception:
                    pass
            yield _chunk_text(chunk), _chunk_usage(chunk)
    finally:
        try:
            close = getattr(response, "close", None)
            if close is not None:
                close()
        except Exception:
            pass


def build_export_text(conversation: list, model_name: str) -> str:
    """Pure export builder shared by the legacy CLI and the TUI."""
    from datetime import datetime as _dt

    visible = [m for m in conversation if m.get("role") in ("user", "assistant")]
    lines = [
        f"# Chat Export - {_dt.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"Model: `{model_name}`",
        "",
    ]
    for msg in visible:
        role_label = "You" if msg["role"] == "user" else "AI"
        lines.append(f"## {role_label}")
        lines.append("")
        lines.append(msg.get("content", ""))
        lines.append("")
    return "\n".join(lines)


def stream_answer(console: Console, client: OpenAI, model: str, messages: list,
                  markdown_on: bool) -> tuple:
    """Stream a completion; return (answer, usage).

    `usage` is the real OpenRouter usage object from the terminal stream
    chunk (or None when the provider did not send one). Callers accumulate
    it into SessionStats.
    """
    answer = ""
    usage = None
    stamp = datetime.now().strftime("%H:%M")
    console.print(
        Panel(
            f"[dim]{stamp}[/dim]",
            title=f"[bold green]AI · {_short_model(model)}[/bold green]",
            border_style="green",
            padding=(0, 1),
        )
    )

    if not markdown_on or not console.is_terminal:
        # Plain streaming: no Status/Live control codes, so nothing can
        # leak as "?[2K" / "?[?25h" on PowerShell or dumb terminals.
        for text, maybe_usage in iter_stream_chunks(client, model, messages):
            if maybe_usage:
                usage = maybe_usage
            if text:
                if markdown_on:
                    # non-terminal but markdown requested: accumulate
                    # quietly, render once at the end via render below.
                    answer += text
                else:
                    console.print(text, end="", highlight=False)
                    answer += text
        if markdown_on and answer:
            from rich.markdown import Markdown as _Md

            try:
                console.print(_Md(answer))
            except Exception:
                console.print(answer, highlight=False)
        elif not markdown_on:
            console.print()
        else:
            console.print("[dim](empty response)[/dim]")
        _print_turn_footer(console, usage)
        return answer, usage

    # Markdown mode: status spinner until first token, then live Markdown.
    # Rich's Status/Live clear after themselves — never emit raw ANSI here
    # (a manual "\x1b[1A\x1b[2K" leaks as "?[1A?[2K" on Windows PowerShell,
    # and console.print(Spinner(...)) leaves a stray "⠋ thinking..." line).
    live = None
    status = console.status("thinking...", spinner="dots")
    status.start()
    try:
        for text, maybe_usage in iter_stream_chunks(client, model, messages):
            if maybe_usage:
                usage = maybe_usage
            if not text:
                continue
            answer += text
            if live is None:
                try:
                    status.stop()
                except Exception:
                    pass
                live = Live(Markdown(answer), console=console, refresh_per_second=8)
                try:
                    live.start()
                except Exception:
                    live = None
            else:
                try:
                    live.update(Markdown(answer))
                except Exception:
                    pass
    finally:
        try:
            if live is not None:
                live.stop()
            else:
                status.stop()
        except Exception:
            pass
    if not answer:
        console.print("[dim](empty response)[/dim]")
    else:
        console.print()
    _print_turn_footer(console, usage)
    return answer, usage


def _print_turn_footer(console: Console, usage) -> None:
    if usage is None:
        console.print("[dim]└ usage n/a[/dim]")
        return
    if isinstance(usage, dict):
        p = usage.get("prompt_tokens", 0) or 0
        c = usage.get("completion_tokens", 0) or 0
    else:
        p = getattr(usage, "prompt_tokens", 0) or 0
        c = getattr(usage, "completion_tokens", 0) or 0
    console.print(
        f"[dim]└ ↑{format_compact(p)} ↓{format_compact(c)}[/dim]"
    )


def save_conversation(console: Console, conversation: list, model_name: str,
                      filename=None) -> None:
    visible = [m for m in conversation if m.get("role") in ("user", "assistant")]

    if not visible:
        console.print("[yellow]Nothing to save.[/yellow]")
        return

    if filename:
        filename = filename.strip().strip("\"'")
        path = Path(filename)
        if not path.suffix:
            path = path.with_suffix(".md")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(f"chat_{timestamp}.md")

    try:
        path.write_text(build_export_text(conversation, model_name), encoding="utf-8")
    except OSError as e:
        console.print(f"[red]Failed to save conversation: {e}[/red]")
        return

    console.print(f"[green]Conversation saved to {path}[/green]")
