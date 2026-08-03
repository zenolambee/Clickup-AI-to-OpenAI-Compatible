from __future__ import annotations

import time
from typing import Any

# Bolt.new does not publish a stable model list. It routes automatically to the
# "best model for the task" (Claude / Gemini family). These are the *display*
# tiers surfaced on the app. Actual model ids are chosen server-side and are not
# part of Bolt's documented, stable public surface, so treat these as labels
# that map to whatever backend Bolt happens to route to for your session.
BOLT_DEFAULT_MODEL = "bolt-agent"

MODEL_ALIASES: dict[str, str] = {
    "bolt": "bolt-agent",
    "bolt-agent": "bolt-agent",
    "bolt-standard": "bolt-agent",
    "standard": "bolt-agent",
    "auto": "bolt-agent",
    "bolt-pro": "bolt-pro",
    "pro": "bolt-pro",
    "bolt-max": "bolt-max",
    "max": "bolt-max",
}

KNOWN_MODELS: list[str] = [
    "bolt-agent",
    "bolt-pro",
    "bolt-max",
]

_models_cache: tuple[float, list[dict[str, Any]]] | None = None
MODELS_CACHE_TTL_SECONDS = 300.0


def _openai_model_entry(model_id: str) -> dict[str, Any]:
    return {
        "id": model_id,
        "object": "model",
        "owned_by": "stackblitz",
        "created": int(time.time()),
    }


def resolve_model(model: str | None) -> str:
    """Normalise a user-supplied model name to a bolt tier label."""
    if not model:
        return BOLT_DEFAULT_MODEL
    cleaned = model.strip().lower().replace(" ", "-")
    while "/" in cleaned:
        cleaned = cleaned.rsplit("/", 1)[-1].strip()
    if cleaned in MODEL_ALIASES:
        return MODEL_ALIASES[cleaned]
    if cleaned in KNOWN_MODELS:
        return cleaned
    # Unknown names pass through; Bolt may still accept/route them, but we don't
    # vouch for them.
    return cleaned


def list_openai_models() -> list[dict[str, Any]]:
    return [_openai_model_entry(m) for m in KNOWN_MODELS]


def cache_openai_models(models: list[dict[str, Any]]) -> None:
    global _models_cache
    _models_cache = (time.time(), models)


def get_cached_openai_models() -> list[dict[str, Any]] | None:
    if _models_cache is None:
        return None
    cached_at, models = _models_cache
    if time.time() - cached_at > MODELS_CACHE_TTL_SECONDS:
        return None
    return models
