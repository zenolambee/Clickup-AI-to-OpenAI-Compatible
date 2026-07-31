from __future__ import annotations

import time
from typing import Any

KIMI_DEFAULT_MODEL = "kimi"

# Kimi web exposes model choice via `kimiplus_id` + `model`. These aliases map
# common OpenAI-style names to Kimi's internal identifiers.
MODEL_ALIASES: dict[str, str] = {
    "kimi": "kimi",
    "moonshot": "kimi",
    "k2": "kimi",
    "kimi-k2": "kimi",
    "k1.5": "k1.5",
    "kimi-k1.5": "k1.5",
    "k1.5-thinking": "k1.5",
    "kimi-thinking": "k1.5",
}

KNOWN_MODELS: list[str] = [
    "kimi",
    "k1.5",
    "k2",
]

_models_cache: tuple[float, list[dict[str, Any]]] | None = None
MODELS_CACHE_TTL_SECONDS = 300.0


def _openai_model_entry(model_id: str) -> dict[str, Any]:
    return {
        "id": model_id,
        "object": "model",
        "owned_by": "moonshot",
        "created": int(time.time()),
    }


def resolve_model(model: str | None) -> str:
    if not model:
        return KIMI_DEFAULT_MODEL
    cleaned = model.strip().lower().replace(" ", "-")
    while "/" in cleaned:
        cleaned = cleaned.rsplit("/", 1)[-1].strip()
    if cleaned in MODEL_ALIASES:
        return MODEL_ALIASES[cleaned]
    if cleaned in KNOWN_MODELS:
        return cleaned
    return KIMI_DEFAULT_MODEL


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
