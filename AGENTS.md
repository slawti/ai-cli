# AGENTS.md

## Run
- Dev setup: `pip install -e .` (uses `.venv`); end users install via pipx/pip from git (see README) — no venv needed. Launch with `ai-cli`, `python -m ai_cli`, or legacy `python main.py`.
- API key resolution: `--api-key` > `OPENROUTER_API_KEY` env > project `.env` > `~/.ai-cli/.env`. Missing key + TTY triggers a one-time secure prompt that saves to `~/.ai-cli/.env`; headless raises `ConfigError`. Never commit a key (project `.env` is gitignored).
- No tests, lint, or CI exist. Verify with `python -m py_compile ai_cli/cli.py ai_cli/ui.py ai_cli/tui.py ai_cli/chat.py` plus small import-level checks.

## Source of truth
- Entry: `ai_cli.cli:main` (console script in `pyproject.toml`).
- Module roles: `cli.py` (loop, session, dispatch; launches TUI unless `--no-tui`/headless), `config.py` (.env + `--model`/`--no-markdown`/`--no-tui`), `models.py` (catalog fetch), `chat.py` (streaming; `iter_stream_chunks()` shared by both UIs), `tui.py` (fullscreen Textual app: history + prompt box + status), `ui.py` (legacy Rich output + toolbar), `stats.py` (token accumulation), `complete.py` (Tab completion).
- `DEFAULT_MODEL` lives in `config.py` (currently `openrouter/free`). README examples (model name, file list) lag the code — trust the code.
- `stream_answer()` returns `(answer, usage)`; `usage` may be `None`. `/clear` resets stats too.

## Windows terminal gotchas (PowerShell is the primary target)
- Always use `ui.create_console()` (`legacy_windows=True` + VT enable). Never a bare `Console()` for app output.
- Never emit raw ANSI escapes or `console.print(Spinner(...))`; use `console.status(...)` for spinners (self-clearing).
- `patch_stdout()` wraps `session.prompt()` only — never the streaming path (corrupts Rich Live/Status, leaks `?[2K`/`?25h` artifacts).
- `build_toolbar_html()` must stay plain text: no `<b>`/`<i>` tags, no box-drawing `│` (use `·`). Keep `_escape()` on all interpolated text for prompt_toolkit HTML parsing.
- Import direction: `cli` imports `ui` at module level; `ui` may only import from `cli` inside functions (cycle).

## Interactive input
- `build_session()` returns `None` without prompt_toolkit or without a real console (`NoConsoleScreenBufferError` headless); the loop falls back to plain `input()`. Don't assert a session exists in headless checks.
