"""Application configuration: .env loading, defaults, CLI flags."""

import argparse
import os
from dataclasses import dataclass

from dotenv import load_dotenv


class ConfigError(Exception):
    """Raised when the app cannot start (e.g. missing API key)."""


DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"

ENV_API_KEY = "OPENROUTER_API_KEY"
ENV_MODEL = "MODEL"
ENV_SYSTEM_PROMPT = "SYSTEM_PROMPT"


@dataclass
class Settings:
    api_key: str
    model: str
    system_prompt: str
    no_markdown: bool = False


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
        "--no-markdown",
        action="store_true",
        help="Stream plain text instead of rendered Markdown.",
    )
    return p


def load_settings(argv=None) -> Settings:
    load_dotenv()
    args = build_parser().parse_args(argv)

    api_key = (os.getenv(ENV_API_KEY) or "").strip()
    if not api_key:
        raise ConfigError(
            "OPENROUTER_API_KEY is not set.\n"
            "Create a .env file with OPENROUTER_API_KEY=your_key_here, "
            "or export it in your shell."
        )

    model = (args.model or os.getenv(ENV_MODEL, DEFAULT_MODEL) or DEFAULT_MODEL).strip()
    system_prompt = (os.getenv(ENV_SYSTEM_PROMPT, "") or "").strip()
    return Settings(
        api_key=api_key,
        model=model,
        system_prompt=system_prompt,
        no_markdown=args.no_markdown,
    )
