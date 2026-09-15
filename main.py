import os
import sys
from openai import OpenAI
from openai import APIError, RateLimitError, AuthenticationError
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel


load_dotenv()

api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:
    print("Error: OPENROUTER_API_KEY is not set.")
    exit(1)

MODEL = os.getenv("MODEL", "nvidia/nemotron-3-super-120b-a12b:free")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key,
)

console = Console()

messages = []


def print_help():
    help_text = """[bold]Available Commands:[/bold]

[cyan]/exit[/cyan]     - Exit the application
[cyan]/clear[/cyan]    - Clear conversation history
[cyan]/help[/cyan]     - Show this help message"""
    console.print(Panel(help_text, title="Help", border_style="blue"))


try:
    while True:
        try:
            console.print("\n[bold cyan]You:[/bold cyan] ", end="")
            user_input = input()

            if user_input.lower() == "/exit":
                console.print("[yellow]Goodbye![/yellow]")
                break

            if user_input.lower() == "/clear":
                messages = []
                console.print("[green]Conversation cleared.[/green]")
                continue

            if user_input.lower() == "/help":
                print_help()
                continue

            messages.append({
                "role": "user",
                "content": user_input,
            })

            response = client.chat.completions.create(
                model=MODEL,
                messages=messages,
                stream=True
            )

            answer = ""

            console.print("\n[bold green]AI:[/bold green] ", end="")

            for chunk in response:
                text = chunk.choices[0].delta.content

                if text:
                    console.print(text, end="", highlight=False)
                    answer += text

            console.print()

            messages.append({
                "role": "assistant",
                "content": answer,
            })

        except (APIError, RateLimitError, AuthenticationError) as e:
            console.print(f"\n[red]API Error: {e}[/red]")
        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted. Type /exit to quit.[/yellow]")
        except EOFError:
            console.print("\n[yellow]Goodbye![/yellow]")
            break
        except Exception as e:
            console.print(f"\n[red]Unexpected error: {e}[/red]")

except KeyboardInterrupt:
    console.print("\n[yellow]Goodbye![/yellow]")
    sys.exit(0)