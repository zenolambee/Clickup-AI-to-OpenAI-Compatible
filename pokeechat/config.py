from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from pokeechat.exceptions import PokeeChatError

DEFAULT_BASE_URL = "https://api.pokee.ai/v1"


def _resolve_home() -> Path | None:
    raw = os.getenv("POKEECHAT_HOME", "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return None


def _load_dotenv_files() -> None:
    home = _resolve_home()
    if home is not None:
        load_dotenv(home / ".env", override=False)
    load_dotenv(override=False)


_load_dotenv_files()


@dataclass(slots=True)
class Settings:
    api_key: str
    host: str
    port: int
    base_url: str
    default_model: str
    pokee_api_key: str


def load_settings() -> Settings:
    _load_dotenv_files()
    return Settings(
        api_key=os.getenv("POKEECHAT_API_KEY", "sk-pokeechat"),
        host=os.getenv("POKEECHAT_HOST", "127.0.0.1"),
        port=int(os.getenv("POKEECHAT_PORT", "1993")),
        base_url=os.getenv("POKEECHAT_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        default_model=os.getenv("POKEECHAT_DEFAULT_MODEL", "pokee-isaac"),
        pokee_api_key=os.getenv("POKEE_API_KEY", "").strip(),
    )


def require_pokee_key(settings: Settings) -> str:
    if not settings.pokee_api_key:
        raise PokeeChatError(
            "Missing POKEE_API_KEY. Get it from https://console.pokee.ai/keys and set it in .env",
            status_code=500,
        )
    return settings.pokee_api_key