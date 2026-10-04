"""Application configuration: .env loading, defaults, CLI flags.

API key search order (first hit wins):
  1. `--api-key` flag
  2. `OPENROUTER_API_KEY` environment variable
  3. project `.env` (current directory — developer override)
  4. user config `~/.ai-cli/.env` (written by the first-run prompt)

On first run with no key found, an interactive terminal is asked once
and the key is saved to the user config so it works from any folder.
"""

import argparse
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when the app cannot start (e.g. missing API key)."""


DEFAULT_MODEL = "openrouter/free"

ENV_API_KEY = "OPENROUTER_API_KEY"
ENV_MODEL = "MODEL"
ENV_SYSTEM_PROMPT = "SYSTEM_PROMPT"

USER_CONFIG_DIR = Path.home() / ".ai-cli"
USER_ENV_FILE = USER_CONFIG_DIR / ".env"


@dataclass
class Settings:
    api_key: str
    model: str
    system_prompt: str
    no_markdown: bool = False
    no_tui: bool = False


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ai-cli",
        description="Command-line AI chatbot using the OpenRouter API.",
    )
    p.add_argument(
        "--model",
        default=None,
        help="Model id to start with (overrides MODEL from .env).",
    )
    p.add_argument(
        "--api-key",
        default=None,
        help="OpenRouter API key for this run (overrides env/.env files).",
    )
    p.add_argument(
        "--no-markdown",
        action="store_true",
        help="Stream plain text instead of rendered Markdown.",
    )
    p.add_argument(
        "--no-tui",
        action="store_true",
        help="Use the legacy inline prompt instead of the fullscreen TUI.",
    )
    return p


def _project_env_file() -> Path:
    """Project override = `.env` in the current directory only.

    NOTE: bare load_dotenv() searches upward from the *caller's file*
    when run as a script, which would load the repo .env instead of the
    user's CWD. An explicit path keeps the semantics predictable.
    """
    try:
        return Path.cwd() / ".env"
    except Exception:
        return Path(".env")


def _interactive() -> bool:
    try:
        return sys.stdin.isatty() and sys.stdout.isatty()
    except Exception:
        return False


def _is_key_line(line: str) -> bool:
    s = line.strip()
    if s.startswith("export "):
        s = s[len("export "):].strip()
    return s.startswith(ENV_API_KEY + "=") or s == ENV_API_KEY


def save_key_to_user_config(api_key: str) -> Path:
    """Upsert the key into the user config, preserving other lines."""
    USER_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    if USER_ENV_FILE.exists():
        try:
            lines = USER_ENV_FILE.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
    lines = [ln for ln in lines if not _is_key_line(ln)]
    if not USER_ENV_FILE.exists():
        lines.append("# ai-cli user config — created on first run. Do not share this file.")
    lines.append(f"{ENV_API_KEY}={api_key}")
    USER_ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return USER_ENV_FILE


def _prompt_for_api_key() -> str:
    """Ask once; return the key or "" when declined/unavailable."""
    print("ai-cli needs an OpenRouter API key (get one at https://openrouter.ai/keys).")
    print(f"Enter it once - it will be saved to {USER_ENV_FILE}.")
    try:
        from getpass import getpass

        return getpass(f"{ENV_API_KEY}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return ""
    except Exception:
        return ""


def load_settings(argv=None) -> Settings:
    load_dotenv(_project_env_file())  # CWD only; missing file is a no-op
    try:
        if USER_ENV_FILE.exists():
            load_dotenv(USER_ENV_FILE)  # override=False: fills gaps only
    except Exception:
        pass
    args = build_parser().parse_args(argv)

    api_key = (args.api_key or os.getenv(ENV_API_KEY) or "").strip()
    if not api_key and _interactive():
        api_key = _prompt_for_api_key()
        if api_key:
            try:
                saved = save_key_to_user_config(api_key)
                print(f"Saved to {saved} (delete it or set {ENV_API_KEY} to change it).")
            except OSError as e:
                print(f"Note: could not save the key ({e}); continuing for this session only.")
    if not api_key:
        raise ConfigError(
            "OPENROUTER_API_KEY is not set.\n"
            "Run ai-cli in a terminal to enter it once, "
            f"set the {ENV_API_KEY} environment variable, or pass --api-key."
        )

    model = (args.model or os.getenv(ENV_MODEL, DEFAULT_MODEL) or DEFAULT_MODEL).strip()
    system_prompt = (os.getenv(ENV_SYSTEM_PROMPT, "") or "").strip()
    return Settings(
        api_key=api_key,
        model=model,
        system_prompt=system_prompt,
        no_markdown=args.no_markdown,
        no_tui=args.no_tui,
    )
