"""Fullscreen Claude/Codex-style TUI: history pane + bottom prompt box.

Minimal dark aesthetic: neutral grays, one accent per role, thin status line.
Launched from cli.main() unless --no-tui, Textual is missing, or no TTY.
"""

import threading
import time
from datetime import datetime
from pathlib import Path

try:
    from textual import events
    from textual.app import App, ComposeResult
    from textual.containers import Container, Vertical, VerticalScroll
    from textual.screen import ModalScreen
    from textual.widgets import Input, LoadingIndicator, Markdown, OptionList, Static, TextArea
    from textual.widgets._option_list import Option

    HAS_TEXTUAL = True
except ImportError:  # pragma: no cover - fallback handled by cli.py
    HAS_TEXTUAL = False

from .chat import build_export_text, iter_stream_chunks
from .complete import COMMANDS
from .models import is_free_model
from .stats import context_bar, format_compact

HISTORY_FILE = Path.home() / ".ai_cli_history"

HELP_TEXT = """\
/exit               Exit
/clear              Clear conversation + counters
/help               This help
/model              Show current model
/model <name|#>     Switch model (opens picker on multiple matches)
/models [q] [--free]  Browse the OpenRouter catalog
/models --refresh   Re-fetch the catalog
/md                 Toggle Markdown rendering
/save [file]        Export conversation to Markdown

Enter send · Shift/Alt+Enter newline · Tab complete
Up/Down history · Esc cancel generation · Ctrl+D exit
"""


def _short_model(model: str, limit: int = 42) -> str:
    if len(model) <= limit:
        return model
    return model[: limit - 1] + "…"


def _ctx_len(catalog, model):
    try:
        exact = catalog.find_exact(model)
        if exact:
            ctx = exact.get("context_length")
            if isinstance(ctx, int) and ctx > 0:
                return ctx
    except Exception:
        pass
    return None


def _load_input_history() -> list:
    try:
        if HISTORY_FILE.exists():
            return [ln.rstrip("\n") for ln in HISTORY_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except Exception:
        pass
    return []


def _append_input_history(line: str) -> None:
    try:
        single = " ".join(line.splitlines()).strip()
        if single:
            with HISTORY_FILE.open("a", encoding="utf-8") as f:
                f.write(single + "\n")
    except Exception:
        pass


class HelpScreen(ModalScreen):
    """Minimal help overlay. Esc closes (built-in)."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def compose(self) -> ComposeResult:
        with Container(id="help-box"):
            yield Static("help  ·  esc to close", classes="box-title")
            yield Static(HELP_TEXT, classes="help-body")


class ModelPickerScreen(ModalScreen):
    """Fuzzy model picker: filter input + live option list."""

    BINDINGS = [("escape", "dismiss", "Close")]

    def __init__(self, catalog, initial: str = "", free_only: bool = False):
        super().__init__()
        self.catalog = catalog
        self.free_only = free_only
        self.initial = initial
        self._ids: list = []

    def compose(self) -> ComposeResult:
        with Container(id="picker-box"):
            yield Static("models  ·  type to filter  ·  enter selects  ·  esc closes", classes="box-title")
            yield Input(placeholder="filter models…", id="picker-filter", value=self.initial)
            yield OptionList(id="picker-list")

    def on_mount(self) -> None:
        self._refresh(self.initial)
        self.query_one("#picker-filter", Input).focus()

    def _refresh(self, query: str) -> None:
        from .models import ModelCatalog  # local: keeps module import light

        catalog: ModelCatalog = self.catalog
        matches, total = catalog.search(query, free_only=self.free_only)
        catalog.last_search = matches
        lst = self.query_one("#picker-list", OptionList)
        lst.clear_options()
        self._ids = []
        for m in matches[:50]:
            mid = m.get("id", "")
            tag = "free" if is_free_model(m) else "paid"
            ctx = m.get("context_length")
            ctx_s = f"{ctx // 1000}k" if isinstance(ctx, int) and ctx >= 1000 else (str(ctx) if isinstance(ctx, int) else "-")
            label = f"{mid}  [{tag}] {ctx_s}"
            lst.add_option(Option(label, id=mid))
            self._ids.append(mid)
        if total > len(matches):
            lst.add_option(Option(f"… {total - len(matches)} more — refine filter", disabled=True))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "picker-filter":
            self._refresh(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Enter while the filter has focus selects the top match
        # (the OptionList only sees Enter when it is focused itself).
        if event.input.id == "picker-filter" and self._ids:
            self.dismiss(self._ids[0])

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        opt_id = getattr(event.option, "id", None)
        if opt_id:
            self.dismiss(opt_id)


class PromptArea(TextArea):
    """Bottom prompt box: Enter sends, Shift/Alt+Enter newline, Tab completes."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("placeholder", "Type a message…  (Enter send · Shift+Enter newline · / for commands)")
        kwargs.setdefault("show_line_numbers", False)
        kwargs.setdefault("tab_behavior", "indent")
        super().__init__(*args, **kwargs)

    async def on_key(self, event: events.Key) -> None:
        app = self.app
        if event.key == "enter":
            event.prevent_default()
            event.stop()
            await app.submit_prompt(self.text)
        elif event.key in ("shift+enter", "alt+enter"):
            event.prevent_default()
            event.stop()
            self.insert("\n")
        elif event.key == "tab":
            event.prevent_default()
            event.stop()
            app.complete_prompt(self)
        elif event.key == "up" and "\n" not in self.text:
            event.prevent_default()
            event.stop()
            app.history_prev(self)
        elif event.key == "down" and "\n" not in self.text:
            event.prevent_default()
            event.stop()
            app.history_next(self)


class AiCliApp(App):
    """Minimal fullscreen chat app."""

    CSS = """
    Screen { background: #0d1117; color: #e6edf3; }
    #topbar {
        height: 1; color: #8b949e; background: #0d1117;
        border-bottom: solid #21262d; padding: 0 1;
    }
    #history { height: 1fr; background: #0d1117; padding: 0 1; }
    .user-label { color: #79c0ff; text-style: bold; margin-top: 1; }
    .user-text { color: #e6edf3; margin-left: 2; }
    .ai-label { color: #7ee787; text-style: bold; margin-top: 1; }
    .ai-body { margin-left: 2; }
    .turn-footer { color: #6e7681; margin-left: 2; }
    .notice { color: #8b949e; }
    .notice-green { color: #7ee787; }
    .notice-yellow { color: #d29922; }
    .notice-red { color: #f85149; }
    #prompt-box {
        height: auto; min-height: 5; max-height: 9;
        border: round #30363d; background: #161b22; padding: 0 1; margin: 0 1;
    }
    #prompt-box:focus-within { border: round #58a6ff; }
    #prompt { background: #161b22; }
    #hint { height: 1; color: #6e7681; background: #0d1117; padding: 0 2; }
    #statusbar { height: 1; color: #8b949e; background: #0d1117; padding: 0 1; }
    #help-box, #picker-box {
        width: 70; max-width: 90; height: auto; max-height: 24;
        border: round #30363d; background: #161b22; padding: 1 2;
    }
    .box-title { color: #8b949e; margin-bottom: 1; }
    .help-body { color: #e6edf3; }
    #picker-filter { background: #0d1117; border: round #30363d; margin-bottom: 1; }
    #picker-list { height: 12; background: #161b22; }
    LoadingIndicator { color: #8b949e; height: 1; }
    """

    BINDINGS = [
        ("ctrl+d", "quit_app", "Quit"),
        ("escape", "cancel_generation", "Cancel"),
    ]

    def __init__(self, settings, client, catalog):
        super().__init__()
        self.settings = settings
        self.client = client
        self.catalog = catalog
        self.messages: list = []
        if settings.system_prompt:
            self.messages.append({"role": "system", "content": settings.system_prompt})
        from .stats import SessionStats

        self.stats = SessionStats()
        self.model = settings.model
        self.markdown = not settings.no_markdown
        self.generating = False
        self._cancel_event = threading.Event()
        self._input_history = _load_input_history()
        self._hist_idx: int | None = None

    # -- layout ---------------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Static("", id="topbar")
        with VerticalScroll(id="history"):
            pass
        with Container(id="prompt-box"):
            yield PromptArea(id="prompt")
        yield Static(" enter: send · shift+enter: newline · tab: complete · /help · ctrl+d: exit", id="hint")
        yield Static("", id="statusbar")

    def on_mount(self) -> None:
        self._refresh_chrome()
        catalog_n = len(self.catalog)
        if catalog_n:
            self._notice(f"{catalog_n} models ({self.catalog.free_count} free) · /models to browse", "notice")
        else:
            self._notice("model catalog offline — manual /model <name> still works", "notice-yellow")
        if self.settings.system_prompt:
            self._notice("system prompt loaded", "notice")
        md = "on" if self.markdown else "off"
        self._notice(f"model: {self.model} · markdown {md} · /help for commands", "notice")
        if not catalog_n:
            self.run_worker(self._fetch_catalog, thread=True, exclusive=True)
        self.query_one("#prompt", PromptArea).focus()

    # -- chrome (topbar / statusbar) ------------------------------------
    def _visible_count(self) -> int:
        return sum(1 for m in self.messages if m.get("role") in ("user", "assistant"))

    def _refresh_chrome(self) -> None:
        short = _short_model(self.model)
        n = len(self.catalog)
        cat = f"{n} models" if n else "catalog:offline"
        try:
            self.query_one("#topbar", Static).update(f" ai-cli · {short} · {cat}")
        except Exception:
            pass
        md = "md:on" if self.markdown else "md:off"
        tok = self.stats.token_line
        ctx_len = _ctx_len(self.catalog, self.model)
        pct = None
        if ctx_len and getattr(self.stats, "has_usage", False):
            try:
                pct = self.stats.total_tokens / float(ctx_len)
            except Exception:
                pct = None
        bar = context_bar(pct, width=8)
        ctx_txt = f"ctx {bar}" if pct is not None else ("ctx ?" if not ctx_len else "ctx 0%")
        try:
            self.query_one("#statusbar", Static).update(
                f" {short} · {tok} · {ctx_txt} · msgs:{self._visible_count()} {md}"
            )
        except Exception:
            pass

    # -- history helpers -------------------------------------------------
    def _history_view(self) -> VerticalScroll:
        return self.query_one("#history", VerticalScroll)

    def _scroll_bottom(self) -> None:
        try:
            self._history_view().scroll_end(animate=False)
        except Exception:
            pass

    def _stamp(self) -> str:
        return datetime.now().strftime("%H:%M")

    def _notice(self, text: str, cls: str = "notice") -> None:
        try:
            self._history_view().mount(Static(text, classes=cls))
            self._scroll_bottom()
        except Exception:
            pass

    def _add_user(self, text: str) -> None:
        view = self._history_view()
        view.mount(Static(f"You · {self._stamp()}", classes="user-label"))
        view.mount(Static(text, classes="user-text"))
        self._scroll_bottom()

    # -- submit / dispatch -----------------------------------------------
    async def submit_prompt(self, raw: str) -> None:
        text = (raw or "").strip("\n")
        if self.generating:
            self.notify("wait for the current answer — Esc cancels", severity="warning")
            return
        if not text.strip():
            return
        prompt = self.query_one("#prompt", PromptArea)
        prompt.load_text("")
        _append_input_history(text)
        self._input_history.append(" ".join(text.splitlines()).strip())
        self._hist_idx = None
        stripped = text.strip()
        lowered = stripped.lower()
        if lowered == "/exit":
            self.exit()
            return
        if lowered == "/clear":
            self._do_clear()
            return
        if lowered == "/help":
            self.push_screen(HelpScreen())
            return
        if lowered == "/md":
            self.markdown = not self.markdown
            self._notice(f"markdown {'on' if self.markdown else 'off'}", "notice-green")
            self._refresh_chrome()
            return
        if lowered == "/model":
            self._notice(f"current model: {self.model}", "notice")
            return
        if lowered.startswith("/model "):
            self._do_model_switch(stripped.split(None, 1)[1])
            return
        if lowered == "/models" or lowered.startswith("/models "):
            parts = stripped.split(None, 1)
            self._do_models(parts[1] if len(parts) > 1 else "")
            return
        if lowered == "/save" or lowered.startswith("/save "):
            parts = stripped.split(None, 1)
            self._do_save(parts[1] if len(parts) > 1 else None)
            return
        if stripped.startswith("/"):
            self._notice(f"unknown command {stripped.split()[0]} — /help", "notice-yellow")
            return
        self.messages.append({"role": "user", "content": text})
        self._add_user(text)
        self._refresh_chrome()
        self._start_generation()

    def _do_clear(self) -> None:
        self.messages = (
            [{"role": "system", "content": self.settings.system_prompt}]
            if self.settings.system_prompt
            else []
        )
        self.stats.reset()
        try:
            self._history_view().remove_children()
        except Exception:
            pass
        self._notice("conversation + counters cleared", "notice-green")
        self._refresh_chrome()

    def _do_model_switch(self, arg: str) -> None:
        arg = (arg or "").strip().strip("\"'")
        if not arg:
            self._notice("usage: /model <name> — /models to browse", "notice-yellow")
            return
        if arg.isdigit() and self.catalog.last_search:
            idx = int(arg) - 1
            if 0 <= idx < len(self.catalog.last_search):
                self.model = self.catalog.last_search[idx].get("id", self.model)
                self._notice(f"switched to {self.model}", "notice-green")
                self._refresh_chrome()
            else:
                self._notice("number out of range for last search", "notice-yellow")
            return
        exact = self.catalog.find_exact(arg)
        if exact:
            self.model = exact.get("id", arg)
            self._notice(f"switched to {self.model}", "notice-green")
            self._refresh_chrome()
            return
        if len(self.catalog):
            matches, total = self.catalog.search(arg)
            if total == 1:
                self.model = matches[0].get("id", arg)
                self._notice(f"switched to {self.model}", "notice-green")
                self._refresh_chrome()
                return
            if total > 1:
                self._open_picker(arg, False)
                return
        self.model = arg
        self._notice(f"switched to {self.model} (not in catalog — will try anyway)", "notice-yellow")
        self._refresh_chrome()

    def _do_models(self, arg: str) -> None:
        arg = (arg or "").strip()
        if "--refresh" in arg:
            self._notice("refreshing model list…", "notice")
            self.run_worker(lambda: self._refresh_catalog(arg), thread=True, exclusive=True)
            return
        free_only = "--free" in arg
        query = arg.replace("--free", "").strip().strip("\"'")
        if not len(self.catalog):
            self._notice("no cached list — fetching…", "notice")
            self.run_worker(lambda: self._refresh_catalog(arg), thread=True, exclusive=True)
            return
        matches, total = self.catalog.search(query, free_only=free_only)
        if total == 0:
            self._notice(f"no {'free ' if free_only else ''}models match '{query}'", "notice-yellow")
            return
        self._open_picker(query, free_only)

    def _refresh_catalog(self, pending_arg: str = "") -> None:
        try:
            self.catalog.refresh()
            ok, n, free = True, len(self.catalog), self.catalog.free_count
        except Exception as e:
            ok, err = False, str(e)
        def _done():
            if ok:
                self._notice(f"loaded {n} models ({free} free)", "notice-green")
                self._refresh_chrome()
                if pending_arg is not None and pending_arg.replace("--refresh", "").strip():
                    self._do_models(pending_arg.replace("--refresh", "").strip())
            else:
                self._notice(f"could not refresh model list ({err})", "notice-red")
        self.call_from_thread(_done)

    def _fetch_catalog(self) -> None:
        try:
            self.catalog.refresh()
            ok = True
        except Exception:
            ok = False
        def _done():
            if ok:
                self._notice(f"{len(self.catalog)} models ({self.catalog.free_count} free) loaded", "notice-green")
            else:
                self._notice("model catalog unavailable (offline?)", "notice-yellow")
            self._refresh_chrome()
        self.call_from_thread(_done)

    def _open_picker(self, query: str, free_only: bool) -> None:
        def _picked(model_id: str | None) -> None:
            if model_id:
                self.model = model_id
                self._notice(f"switched to {self.model}", "notice-green")
                self._refresh_chrome()
        try:
            self.push_screen(ModelPickerScreen(self.catalog, query, free_only), _picked)
        except Exception:
            matches, _ = self.catalog.search(query, free_only=free_only)
            if matches:
                self._picked_fallback(matches)

    def _picked_fallback(self, matches) -> None:
        self.catalog.last_search = matches
        lines = [f" {i}. {m.get('id', '')}" for i, m in enumerate(matches[:15], 1)]
        self._notice("matches:\n" + "\n".join(lines) + "\n/model <#>", "notice")

    def _do_save(self, filename: str | None) -> None:
        visible = [m for m in self.messages if m.get("role") in ("user", "assistant")]
        if not visible:
            self._notice("nothing to save", "notice-yellow")
            return
        name = (filename or "").strip().strip("\"'")
        if name:
            path = Path(name)
            if not path.suffix:
                path = path.with_suffix(".md")
        else:
            path = Path(f"chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
        try:
            path.write_text(build_export_text(self.messages, self.model), encoding="utf-8")
        except OSError as e:
            self._notice(f"save failed: {e}", "notice-red")
            return
        self._notice(f"saved to {path}", "notice-green")

    # -- completion + input history ---------------------------------------
    def _candidates(self, text: str) -> list:
        before = text.split("\n")[-1] if "\n" in text else text
        if not before.startswith("/"):
            return []
        if " " not in before:
            return [c for c in COMMANDS if c.startswith(before.lower())]
        cmd, _, partial = before.partition(" ")
        if cmd.lower() not in ("/model", "/models"):
            return []
        if partial.startswith("--"):
            return [f for f in ("--free", "--refresh") if f.startswith(partial.lower())]
        q = partial.strip().lower()
        out = []
        for m in self.catalog.models:
            mid = m.get("id", "")
            if not q or q in mid.lower() or q in str(m.get("name", "")).lower():
                out.append(mid)
                if len(out) >= 50:
                    break
        return out

    def complete_prompt(self, area: PromptArea) -> None:
        cands = self._candidates(area.text)
        if not cands:
            return
        cur = area.text
        if " " not in cur.lstrip():
            area.insert(cands[0][len(cur):])
            return
        head, _, partial = cur.rpartition(" ")
        if cur.endswith(" ") or not partial:
            area.insert(cands[0])
            return
        for c in cands:
            if c.lower().startswith(partial.strip().lower()):
                area.insert(c[len(partial.strip()):])
                return
        area.insert(cands[0])

    def history_prev(self, area: PromptArea) -> None:
        if not self._input_history:
            return
        if self._hist_idx is None:
            self._hist_idx = len(self._input_history) - 1
        elif self._hist_idx > 0:
            self._hist_idx -= 1
        area.load_text(self._input_history[self._hist_idx])

    def history_next(self, area: PromptArea) -> None:
        if self._hist_idx is None:
            return
        if self._hist_idx < len(self._input_history) - 1:
            self._hist_idx += 1
            area.load_text(self._input_history[self._hist_idx])
        else:
            self._hist_idx = None
            area.load_text("")

    # -- generation (streaming worker) --------------------------------------
    def _start_generation(self) -> None:
        self.generating = True
        self._cancel_event.clear()
        view = self._history_view()
        try:
            view.mount(Static(f"AI · {_short_model(self.model)}", classes="ai-label"))
            body = Markdown("…", classes="ai-body") if self.markdown else Static("…", classes="ai-body")
            view.mount(body)
            spin = LoadingIndicator()
            view.mount(spin)
            self._scroll_bottom()
        except Exception:
            self.generating = False
            return
        self.run_worker(lambda: self._generate(body, spin), thread=True, exclusive=True)

    def _generate(self, body_widget, spin_widget) -> None:
        from openai import APIError, AuthenticationError, RateLimitError

        answer = ""
        usage = None
        t0 = time.monotonic()
        last_push = 0.0
        first_token = False
        try:
            for text, maybe_usage in iter_stream_chunks(
                self.client, self.model, self.messages, cancel_event=self._cancel_event
            ):
                if maybe_usage:
                    usage = maybe_usage
                if not text:
                    continue
                answer += text
                if not first_token:
                    first_token = True
                    self.call_from_thread(spin_widget.remove)
                now = time.monotonic()
                if now - last_push >= 0.12:
                    last_push = now
                    snapshot = answer
                    self.call_from_thread(self._update_body, body_widget, snapshot)
            if self._cancel_event.is_set():
                self.call_from_thread(self._finish_cancelled, body_widget, spin_widget, answer)
                return
            latency = time.monotonic() - t0
            self.call_from_thread(self._finish_ok, body_widget, spin_widget, answer, usage, latency)
        except (APIError, RateLimitError, AuthenticationError) as e:
            self.call_from_thread(self._finish_error, body_widget, spin_widget, f"API error: {e}")
        except Exception as e:
            self.call_from_thread(self._finish_error, body_widget, spin_widget, f"error: {e}")

    def _update_body(self, widget, snapshot: str) -> None:
        try:
            if isinstance(widget, Markdown):
                widget.update(snapshot or "…")
            else:
                widget.update(snapshot)
            self._scroll_bottom()
        except Exception:
            pass

    def _turn_footer(self, usage) -> str:
        if usage is None:
            return "└ usage n/a"
        if isinstance(usage, dict):
            p = usage.get("prompt_tokens", 0) or 0
            c = usage.get("completion_tokens", 0) or 0
        else:
            p = getattr(usage, "prompt_tokens", 0) or 0
            c = getattr(usage, "completion_tokens", 0) or 0
        return f"└ ↑{format_compact(p)} ↓{format_compact(c)}"

    def _finish_ok(self, body_widget, spin_widget, answer: str, usage, latency: float) -> None:
        self.generating = False
        try:
            spin_widget.remove()
        except Exception:
            pass
        if not answer:
            try:
                body_widget.update("(empty response)")
            except Exception:
                pass
        else:
            self._update_body(body_widget, answer)
        try:
            self._history_view().mount(Static(self._turn_footer(usage), classes="turn-footer"))
            self._scroll_bottom()
        except Exception:
            pass
        self.messages.append({"role": "assistant", "content": answer})
        try:
            self.stats.add(usage, latency=latency)
        except Exception:
            pass
        self._refresh_chrome()
        try:
            self.query_one("#prompt", PromptArea).focus()
        except Exception:
            pass

    def _finish_cancelled(self, body_widget, spin_widget, answer: str) -> None:
        self.generating = False
        try:
            spin_widget.remove()
        except Exception:
            pass
        # Keep the user message but drop the half-answer from context,
        # mirroring the legacy CLI (pop on error). User message was already
        # appended before generation; remove it so retry is clean.
        if self.messages and self.messages[-1].get("role") == "user":
            self.messages.pop()
        try:
            self._history_view().mount(Static("cancelled — message kept out of history, try again", classes="notice-yellow"))
            self._scroll_bottom()
        except Exception:
            pass
        self._refresh_chrome()

    def _finish_error(self, body_widget, spin_widget, message: str) -> None:
        self.generating = False
        try:
            spin_widget.remove()
        except Exception:
            pass
        try:
            body_widget.update(f"({message})")
        except Exception:
            pass
        if self.messages and self.messages[-1].get("role") == "user":
            self.messages.pop()
        self._notice(message, "notice-red")
        self._refresh_chrome()

    # -- actions -------------------------------------------------------------
    def action_cancel_generation(self) -> None:
        if self.generating:
            self._cancel_event.set()
        # Esc on a modal dismisses it automatically; nothing else needed.

    def action_quit_app(self) -> None:
        self._cancel_event.set()
        self.exit()


def run_tui(settings, client, catalog) -> int:
    """Entry point used by cli.main(). Returns process exit code."""
    if not HAS_TEXTUAL:
        raise RuntimeError("Textual is not installed (pip install textual).")
    app = AiCliApp(settings, client, catalog)
    app.run()
    return 0
