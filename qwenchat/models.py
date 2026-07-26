from __future__ import annotations

import time
from typing import Any

QWEN_DEFAULT_MODEL = "qwen3.7-plus"

MODEL_ALIASES: dict[str, str] = {
    "qwen": "qwen3.7-max",
    "qwen3": "qwen3.7-max",
    "qwen3.8": "qwen3.8-preview",
    "qwen3.7": "qwen3.7-plus",
    "qwen3.6": "qwen3.6-plus",
    "qwen3.5": "qwen3.5-plus",
    "qwen3-coder": "qwen3-coder-plus",
    "qwen3-flash": "qwen3.6-flash",
    "qwen3-vl": "qwen3-vl-235b-a22b",
    "qwen3-omni": "qwen3-omni-flash",
    "qwen2.5": "qwen2.5-max",
    "qwen-turbo": "qwen-turbo",
    "qwen-plus": "qwen-plus",
    "qwen-max": "qwen3.7-max",
}

KNOWN_MODELS: list[str] = [
    "qwen3.8-preview",
    "qwen3.7-plus",
    "qwen3.7-max",
    "qwen3.6-max-preview",
    "qwen3.6-plus",
    "qwen3.6-flash",
    "qwen3.6-27b",
    "qwen3.5-plus",
    "qwen3.5-flash",
    "qwen3-coder-plus",
    "qwen3-coder-flash",
    "qwen3-vl-235b-a22b",
    "qwen3-omni-flash",
    "qwen3-max",
    "qwen-plus",
    "qwen-max",
    "qwen-turbo",
    "qwen-flash",
]

_models_cache: tuple[float, list[dict[str, Any]]] | None = None
MODELS_CACHE_TTL_SECONDS = 300.0


def _openai_model_entry(model_id: str) -> dict[str, Any]:
    return {
        "id": model_id,
        "object": "model",
        "owned_by": "qwen",
        "created": int(time.time()),
    }


def resolve_model(model: str | None) -> str:
    if not model:
        return QWEN_DEFAULT_MODEL
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
