from __future__ import annotations

import time
from typing import Any

GEMINI_DEFAULT_MODEL = "gemini-2.5-flash"

MODEL_ALIASES: dict[str, str] = {
    "gemini": "gemini-2.5-flash",
    "gemini-flash": "gemini-2.5-flash",
    "gemini-pro": "gemini-2.5-pro",
    "gemini-2.5": "gemini-2.5-flash",
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-2.5-pro": "gemini-2.5-pro",
    "gemini-3": "gemini-3-flash",
    "gemini-3-flash": "gemini-3-flash",
    "gemini-3-pro": "gemini-3-pro",
}

KNOWN_MODELS: list[str] = [
    "gemini-3-pro",
    "gemini-3-flash",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
]

_models_cache: tuple[float, list[dict[str, Any]]] | None = None
MODELS_CACHE_TTL_SECONDS = 300.0


def _openai_model_entry(model_id: str) -> dict[str, Any]:
    return {
        "id": model_id,
        "object": "model",
        "owned_by": "google",
        "created": int(time.time()),
    }


def resolve_model(model: str | None) -> str:
    if not model:
        return GEMINI_DEFAULT_MODEL
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
