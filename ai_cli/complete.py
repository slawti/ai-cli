"""Tab completion for slash-commands and model ids."""

try:
    from prompt_toolkit.completion import Completer, Completion

    _HAS_TOOLKIT = True
except ImportError:  # pragma: no cover
    Completer = object  # type: ignore
    Completion = None  # type: ignore
    _HAS_TOOLKIT = False

COMMANDS = ["/exit", "/clear", "/help", "/model", "/models", "/md", "/save"]
MODEL_COMMANDS = ("/model", "/models")


class ModelCompleter(Completer):
    """Complete command names, flags, and model ids from the catalog."""

    def __init__(self, catalog):
        self.catalog = catalog

    def get_completions(self, document, complete_event):
        if not _HAS_TOOLKIT or Completion is None:
            return
        text = document.text_before_cursor
        lowered = text.lower()
        if not lowered.startswith("/"):
            return
        # Bare command names: "/mo" -> "/model".
        if " " not in text:
            for cmd in COMMANDS:
                if cmd.startswith(lowered):
                    yield Completion(cmd, start_position=-len(text))
            return
        parts = text.split(maxsplit=1)
        cmd, partial = parts[0].lower(), (parts[1] if len(parts) > 1 else "")
        if cmd not in MODEL_COMMANDS:
            return
        if partial.startswith("--"):
            for flag in ("--free", "--refresh"):
                if flag.startswith(partial.lower()):
                    yield Completion(flag, start_position=-len(partial))
            return
        q = partial.strip().lower()
        shown = 0
        for m in self.catalog.models:
            mid = m.get("id", "")
            if not q or q in mid.lower() or q in str(m.get("name", "")).lower():
                from .models import is_free_model

                tag = "free" if is_free_model(m) else "paid"
                yield Completion(
                    mid,
                    start_position=-len(partial),
                    display_meta=f"{m.get('name', '')} [{tag}]",
                )
                shown += 1
                if shown >= 50:
                    break
