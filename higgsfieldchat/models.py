from __future__ import annotations

import logging
import time
from typing import Any

log = logging.getLogger(__name__)

DEFAULT_MODEL_MAP: dict[str, str] = {
    "supercomputer": "supercomputer",
    "higgsfield-supercomputer": "supercomputer",
    "higgsfield-ai": "supercomputer",
}

_models_cache: tuple[float, list[dict[str, Any]], dict[str, str]] | None = None
MODELS_CACHE_TTL_SECONDS = 300.0


def _openai_model_entry(model_id: str, *, owned_by: str = "higgsfield") -> dict[str, Any]:
    return {
        "id": model_id,
        "object": "model",
        "owned_by": owned_by,
        "created": int(time.time()),
    }


def list_openai_models(default: str) -> list[dict[str, Any]]:
    seen: set[str] = set()
    models: list[dict[str, Any]] = []
    for name in list(DEFAULT_MODEL_MAP.keys()):
        if name not in seen:
            seen.add(name)
            models.append(_openai_model_entry(name))
    models.sort(key=lambda item: item["id"].lower())
    return models


def cache_openai_models(models: list[dict[str, Any]], alias_map: dict[str, str] | None = None) -> None:
    global _models_cache
    _models_cache = (time.time(), models, alias_map or {})


def get_cached_openai_models() -> list[dict[str, Any]] | None:
    if _models_cache is None:
        return None
    cached_at, models, _ = _models_cache
    if time.time() - cached_at > MODELS_CACHE_TTL_SECONDS:
        return None
    return models


def get_cached_alias_map() -> dict[str, str] | None:
    if _models_cache is None:
        return None
    cached_at, _, alias_map = _models_cache
    if time.time() - cached_at > MODELS_CACHE_TTL_SECONDS:
        return None
    return alias_map or None


def normalize_request_model(model: str | None) -> str | None:
    if not model:
        return model
    cleaned = model.strip()
    while "/" in cleaned:
        cleaned = cleaned.rsplit("/", 1)[-1].strip()
    if not cleaned:
        return model
    return cleaned.lower().replace(" ", "-")


def resolve_model(model: str | None, *, default: str, alias_map: dict[str, str] | None = None) -> str:
    model = normalize_request_model(model)
    default = normalize_request_model(default) or default

    if not model:
        return resolve_model(default, default=default, alias_map=alias_map)

    dynamic = alias_map if alias_map is not None else (get_cached_alias_map() or {})

    if model in dynamic:
        return dynamic[model]
    if model in DEFAULT_MODEL_MAP:
        return DEFAULT_MODEL_MAP[model]

    log.debug("Unknown model %r — passing through", model)
    return model