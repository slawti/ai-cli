"""Backwards-compatible launcher. Prefer the `ai-cli` command (pip install -e .)."""

from ai_cli.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
