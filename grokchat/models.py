from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_MODEL_MAP: dict[str, str] = {
    "grok-3": "grok-3",
    "grok-3-mini": "grok-3-mini",
    "grok-3-mini-fast": "grok-3-mini-fast",
    "grok-3-fast": "grok-3-fast",
    "grok-2": "grok-2",
    "grok-2-mini": "grok-2-mini",
    "grok-latest": "grok-3",
    "grok-3.5": "grok-3.5",
    "grok-3.5-mini": "grok-3.5-mini",
    "grok-super": "grok-super",
    "grok-reasoning": "grok-3-reasoning",
    "deepsearch": "deepsearch",
    "grok-reasoning-v2": "grok-3-reasoning-v2",
}

_models_cache: tuple[float, list[dict[str, Any]]] | None = None
MODELS_CACHE_TTL_SECONDS = 300.0


def friendly_alias(model_message: str) -> str:
    return model_message.strip().lower().replace(" ", "-")


def list_openai_models(*, default_model: str | None = None) -> list[dict[str, Any]]:
    del default_model
    models: list[dict[str, Any]] = []
    seen: set[str] = set()
    for display, model_id in DEFAULT_MODEL_MAP.items():
        if model_id not in seen:
            seen.add(model_id)
            models.append(_openai_model_entry(display))
    models.sort(key=lambda item: item["id"].lower())
    return models


def _openai_model_entry(model_id: str, *, owned_by: str = "xai") -> dict[str, Any]:
    return {
        "id": model_id,
        "object": "model",
        "owned_by": owned_by,
        "created": int(time.time()),
    }


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


def resolve_model(model: str | None) -> str:
    if not model:
        return "grok-3"
    cleaned = model.strip()
    while "/" in cleaned:
        cleaned = cleaned.rsplit("/", 1)[-1].strip()
    key = friendly_alias(cleaned)
    if key in DEFAULT_MODEL_MAP:
        return DEFAULT_MODEL_MAP[key]
    for alias, mid in DEFAULT_MODEL_MAP.items():
        if key.endswith(alias) or alias.endswith(key):
            return mid
    if key in DEFAULT_MODEL_MAP.values():
        return key
    log.debug("Unknown model %r — falling back to grok-3", model)
    return "grok-3"
