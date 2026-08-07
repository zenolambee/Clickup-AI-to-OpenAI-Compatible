from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger(__name__)

MODELS_CACHE_TTL_SECONDS = 300.0
_models_cache: tuple[float, list[dict[str, Any]]] | None = None


def _openai_model_entry(model_id: str, *, owned_by: str = "arena") -> dict[str, Any]:
    return {
        "id": model_id,
        "object": "model",
        "owned_by": owned_by,
        "created": int(time.time()),
    }


DEFAULT_MODELS: list[dict[str, Any]] = [
    _openai_model_entry("gpt-4o"),
    _openai_model_entry("gpt-4o-mini"),
    _openai_model_entry("claude-3-opus"),
    _openai_model_entry("claude-3-sonnet"),
    _openai_model_entry("claude-3-haiku"),
    _openai_model_entry("gemini-pro"),
    _openai_model_entry("gemini-flash"),
    _openai_model_entry("grok-2"),
    _openai_model_entry("grok-3"),
]


def list_openai_models() -> list[dict[str, Any]]:
    return DEFAULT_MODELS


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
