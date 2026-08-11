from __future__ import annotations

import logging
import re
import time
from typing import Any

log = logging.getLogger(__name__)

MODELS_CACHE_TTL_SECONDS = 300.0
_models_cache: tuple[float, list[dict[str, Any]], dict[str, str]] | None = None

DEFAULT_MODELS: list[dict[str, Any]] = []


def _openai_model_entry(model_id: str, *, owned_by: str = "arena") -> dict[str, Any]:
    return {
        "id": model_id,
        "object": "model",
        "owned_by": owned_by,
        "created": int(time.time()),
    }


def parse_available_models(response: dict[str, Any]) -> dict[str, str]:
    """Friendly alias -> Arena internal model id."""
    out: dict[str, str] = {}
    for entry in response.get("models") or []:
        if not isinstance(entry, dict):
            continue
        mid = entry.get("id") or entry.get("model")
        name = entry.get("name") or entry.get("modelName") or entry.get("displayName")
        if not isinstance(mid, str) or not isinstance(name, str):
            continue
        if not mid or not name:
            continue
        out[name] = mid
        # Add lowercase variant
        out[name.lower()] = mid
        # Add common aliases
        if "gpt" in name.lower():
            out["gpt-4o"] = mid
        if "claude" in name.lower():
            if "opus" in name.lower():
                out["claude-3-opus"] = mid
            elif "sonnet" in name.lower():
                out["claude-3-sonnet"] = mid
            elif "haiku" in name.lower():
                out["claude-3-haiku"] = mid
        if "gemini" in name.lower():
            out["gemini-pro"] = mid
            out["gemini-flash"] = mid
        if "grok" in name.lower():
            out["grok-2"] = mid
            out["grok-3"] = mid
    return out


def list_openai_models_from_arena(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Build OpenAI /v1/models list from Arena API response."""
    models: list[dict[str, Any]] = []
    seen: set[str] = set()

    for entry in response.get("models") or []:
        if not isinstance(entry, dict):
            continue
        mid = entry.get("id") or entry.get("model")
        name = entry.get("name") or entry.get("modelName") or entry.get("displayName")
        if not isinstance(mid, str) or not isinstance(name, str):
            continue
        if not mid or not name:
            continue
        if mid in seen:
            continue
        seen.add(mid)
        models.append(_openai_model_entry(name, owned_by="arena"))

    models.sort(key=lambda item: item["id"].lower())
    return models




def parse_models_from_direct_html(html: str) -> list[dict[str, Any]]:
    """Extract OpenAI-style model entries from arena.ai/direct SSR HTML.

    The arena frontend ships the available model catalog inside Next.js
    flight data (publicName/name/displayName triples).
    """
    models: list[dict[str, Any]] = []
    seen: set[str] = set()
    triples = re.findall(
        r'publicName\\":\\"([^\\"]+)\\",\\"name\\":\\"([^\\"]+)\\",'
        r'\\"displayName\\":\\"([^\\"]+)\\"',
        html,
    )
    for _pub, mid, _disp in triples:
        if _pub in seen or not _pub:
            continue
        seen.add(_pub)
        mid = _pub  # use publicName as id (matches how arena exposes it)
        models.append(_openai_model_entry(mid, owned_by="arena"))
    models.sort(key=lambda item: item["id"].lower())
    return models


def list_openai_models() -> list[dict[str, Any]]:
    return DEFAULT_MODELS


def cache_openai_models(
    models: list[dict[str, Any]],
    alias_map: dict[str, str] | None = None,
) -> None:
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
    return cleaned or model


def resolve_model(model: str | None, *, default: str, alias_map: dict[str, str] | None = None) -> str:
    dynamic = alias_map if alias_map is not None else (get_cached_alias_map() or {})
    model = normalize_request_model(model)
    default = normalize_request_model(default) or default

    if not model:
        return resolve_model(default, default=default, alias_map=alias_map)

    if model in dynamic:
        return dynamic[model]

    # Try lowercase match
    lower = model.lower()
    for alias, mid in dynamic.items():
        if alias.lower() == lower:
            return mid

    log.debug("Unknown model %r — passing through to Arena", model)
    return model
