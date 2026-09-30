"""Chat backend: OpenRouter client, streaming, conversation export."""

from datetime import datetime
from pathlib import Path

from openai import OpenAI
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.spinner import Spinner


def build_client(api_key: str) -> OpenAI:
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


def stream_answer(console: Console, client: OpenAI, model: str, messages: list,
                  markdown_on: bool) -> str:
    """Stream a completion; live-render Markdown, fall back to raw text."""
    response = client.chat.completions.create(
        model=model, messages=messages, stream=True
    )
    answer = ""
    console.print("\n[bold green]AI:[/bold green]")

    if not markdown_on:
        for chunk in response:
            text = chunk.choices[0].delta.content
            if text:
                console.print(text, end="", highlight=False)
                answer += text
        console.print()
        return answer

    # Markdown mode: spinner until first token, then live-rendered Markdown.
    spinner = Spinner("dots", text="thinking...")
    console.print(spinner)
    first = True
    try:
        with Live(Markdown(""), console=console, refresh_per_second=8) as live:
            for chunk in response:
                text = chunk.choices[0].delta.content
                if not text:
                    continue
                answer += text
                if first:
                    first = False
                try:
                    live.update(Markdown(answer))
                except Exception:
                    pass
    finally:
        # Clear the spinner line before live output settles.
        console.print("\x1b[1A\x1b[2K", end="")
    if not answer:
        console.print("[dim](empty response)[/dim]")
    else:
        console.print()
    return answer


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

    lines = [
        f"# Chat Export - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
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

    try:
        path.write_text("\n".join(lines), encoding="utf-8")
    except OSError as e:
        console.print(f"[red]Failed to save conversation: {e}[/red]")
        return

    console.print(f"[green]Conversation saved to {path}[/green]")
