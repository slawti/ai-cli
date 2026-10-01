"""Session token-usage accounting from real OpenRouter `usage` chunks."""

from dataclasses import dataclass, field


def format_compact(n) -> str:
    """1_234 -> '1.2k', None -> '-'."""
    if n is None:
        return "-"
    try:
        n = int(n)
    except (ValueError, TypeError):
        return "-"
    if n < 1000:
        return str(n)
    if n < 1_000_000:
        v = n / 1000
        return f"{v:.1f}k".replace(".0k", "k")
    v = n / 1_000_000
    return f"{v:.1f}M".replace(".0M", "M")


def context_bar(pct: float | None, width: int = 10) -> str:
    if pct is None:
        return "░" * width + " ?"
    pct = max(0.0, min(1.0, pct))
    filled = round(pct * width)
    return "▓" * filled + "░" * (width - filled) + f" {pct * 100:.0f}%"


@dataclass
class SessionStats:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost: float = 0.0
    turns: int = 0
    last_latency: float | None = None
    has_usage: bool = False
    _history: list = field(default_factory=list, repr=False)

    def add(self, usage, latency: float | None = None) -> None:
        """Accumulate one turn's OpenRouter `usage` object (or dict)."""
        if usage is None:
            if latency is not None:
                self.last_latency = latency
            return
        if isinstance(usage, dict):
            prompt = usage.get("prompt_tokens", 0) or 0
            completion = usage.get("completion_tokens", 0) or 0
            total = usage.get("total_tokens", 0) or (prompt + completion)
            cost = usage.get("cost", 0) or 0
        else:
            prompt = getattr(usage, "prompt_tokens", 0) or 0
            completion = getattr(usage, "completion_tokens", 0) or 0
            total = getattr(usage, "total_tokens", 0) or (prompt + completion)
            cost = getattr(usage, "cost", 0) or 0
        try:
            self.prompt_tokens += int(prompt)
            self.completion_tokens += int(completion)
            self.total_tokens += int(total)
            self.cost += float(cost)
        except (ValueError, TypeError):
            pass
        self.turns += 1
        self.has_usage = True
        if latency is not None:
            self.last_latency = latency
        self._history.append((prompt, completion))

    def reset(self) -> None:
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.cost = 0.0
        self.turns = 0
        self.last_latency = None
        self.has_usage = False
        self._history.clear()

    @property
    def token_line(self) -> str:
        if not self.has_usage:
            return "tokens: n/a"
        return (
            f"↑{format_compact(self.prompt_tokens)} "
            f"↓{format_compact(self.completion_tokens)} "
            f"={format_compact(self.total_tokens)}"
        )
