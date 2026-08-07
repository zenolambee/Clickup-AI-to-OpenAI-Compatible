from __future__ import annotations

import time
from typing import Any

POKEE_DEFAULT_MODEL = "pokee-isaac"

MODEL_ALIASES: dict[str, str] = {
    "pokee": "pokee-isaac",
    "pokee-isaac": "pokee-isaac",
    "pokee-isaac-high-reasoning": "pokee-isaac",
    "gpt": "pokee-isaac",
    "gpt-4o": "pokee-isaac",
    "gpt-5": "pokee-isaac",
    "gpt-5.6-luna": "pokee-isaac",
    "gemini": "pokee-isaac",
    "gemini-3.5-flash-lite": "pokee-isaac",
    "claude": "pokee-isaac",
    "claude-haiku-4.5": "pokee-isaac",
    "claude-sonnet": "pokee-isaac",
    "claude-opus": "pokee-isaac",
    "nemotron": "pokee-isaac",
    "nemotron-3-super-120b": "pokee-isaac",
    "kimi": "pokee-isaac",
}

KNOWN_MODELS: list[str] = [
    "pokee-isaac",
]

_models_cache: tuple[float, list[dict[str, Any]]] | None = None
MODELS_CACHE_TTL_SECONDS = 300.0


def _openai_model_entry(model_id: str) -> dict[str, Any]:
    return {
        "id": model_id,
        "object": "model",
        "owned_by": "pokee",
        "created": int(time.time()),
    }


def resolve_model(model: str | None) -> str:
    if not model:
        return POKEE_DEFAULT_MODEL
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