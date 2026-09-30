"""OpenRouter model catalog: fetch, free-filter, search."""

import json
import urllib.error
import urllib.request

MODELS_URL = "https://openrouter.ai/api/v1/models"


def is_free_model(m: dict) -> bool:
    pricing = m.get("pricing") or {}
    try:
        prompt_free = float(pricing.get("prompt", "1") or "1") == 0
        completion_free = float(pricing.get("completion", "1") or "1") == 0
    except (ValueError, TypeError):
        prompt_free = completion_free = False
    return (prompt_free and completion_free) or str(m.get("id", "")).endswith(":free")


def fetch_openrouter_models(timeout: int = 20) -> list:
    req = urllib.request.Request(
        MODELS_URL, headers={"User-Agent": "ai-cli", "Accept": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    models = data.get("data", [])
    models.sort(key=lambda m: m.get("id", ""))
    return models


class ModelCatalog:
    """In-memory catalog (always fresh per session, no file cache)."""

    def __init__(self):
        self.models: list = []
        self.last_search: list = []

    def __len__(self):
        return len(self.models)

    @property
    def free_count(self) -> int:
        return sum(1 for m in self.models if is_free_model(m))

    def refresh(self) -> None:
        self.models = fetch_openrouter_models()

    def find_exact(self, name: str):
        lowered = (name or "").strip().lower()
        for m in self.models:
            if m.get("id", "").lower() == lowered:
                return m
        return None

    def search(self, query: str = "", free_only: bool = False, limit: int = 15):
        q = (query or "").strip().lower()
        results = self.models
        if free_only:
            results = [m for m in results if is_free_model(m)]
        if q:
            results = [
                m
                for m in results
                if q in m.get("id", "").lower()
                or q in str(m.get("name", "")).lower()
            ]
        return results[:limit], len(results)
