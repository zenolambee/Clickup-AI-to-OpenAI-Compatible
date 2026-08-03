from __future__ import annotations

import time
from typing import Any

CLAUDE_DEFAULT_MODEL = "claude-sonnet-4-20250514"

MODEL_ALIASES: dict[str, str] = {
    "claude": "claude-sonnet-4-20250514",
    "claude-sonnet-4": "claude-sonnet-4-20250514",
    "sonnet-4": "claude-sonnet-4-20250514",
    "claude-sonnet-4.6": "claude-sonnet-4-20250514",
    "sonnet-4.6": "claude-sonnet-4-20250514",
    "claude-opus-4": "claude-opus-4-20250514",
    "opus-4": "claude-opus-4-20250514",
    "claude-opus-4.7": "claude-opus-4-20250514",
    "opus-4.7": "claude-opus-4-20250514",
    "claude-haiku-4.5": "claude-haiku-4-20250304",
    "haiku-4.5": "claude-haiku-4-20250304",
    "haiku": "claude-haiku-4-20250304",
    "claude-sonnet-3.5": "claude-sonnet-3-5-20241022",
    "sonnet-3.5": "claude-sonnet-3-5-20241022",
    "claude-3.5-sonnet": "claude-sonnet-3-5-20241022",
    "claude-opus-3.5": "claude-3-5-opus-20250620",
    "opus-3.5": "claude-3-5-opus-20250620",
    "claude-3-opus": "claude-3-opus-20240229",
    "opus-3": "claude-3-opus-20240229",
}

KNOWN_MODELS: list[str] = [
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "claude-haiku-4-20250304",
    "claude-sonnet-3-5-20241022",
    "claude-3-5-opus-20250620",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
    "claude-3-haiku-20240307",
]

_models_cache: tuple[float, list[dict[str, Any]]] | None = None
MODELS_CACHE_TTL_SECONDS = 300.0


def _openai_model_entry(model_id: str) -> dict[str, Any]:
    return {
        "id": model_id,
        "object": "model",
        "owned_by": "anthropic",
        "created": int(time.time()),
    }


def resolve_model(model: str | None) -> str:
    if not model:
        return CLAUDE_DEFAULT_MODEL
    cleaned = model.strip().lower().replace(" ", "-")
    while "/" in cleaned:
        cleaned = cleaned.rsplit("/", 1)[-1].strip()
    if cleaned in MODEL_ALIASES:
        return MODEL_ALIASES[cleaned]
    if cleaned in KNOWN_MODELS:
        return cleaned
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
