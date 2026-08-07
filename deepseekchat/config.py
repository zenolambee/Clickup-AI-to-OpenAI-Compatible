from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from deepseekchat.exceptions import DeepSeekChatError

DEFAULT_BASE_URL = "https://api.deepseek.com"


def _resolve_home() -> Path | None:
    raw = os.getenv("DEEPSEEKCHAT_HOME", "").strip()
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
    deepseek_api_key: str


def load_settings() -> Settings:
    _load_dotenv_files()
    return Settings(
        api_key=os.getenv("DEEPSEEKCHAT_API_KEY", "sk-deepseekchat"),
        host=os.getenv("DEEPSEEKCHAT_HOST", "127.0.0.1"),
        port=int(os.getenv("DEEPSEEKCHAT_PORT", "1996")),
        base_url=os.getenv("DEEPSEEKCHAT_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        default_model=os.getenv("DEEPSEEKCHAT_DEFAULT_MODEL", "deepseek-v4-flash"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
    )


def require_deepseek_key(settings: Settings) -> str:
    if not settings.deepseek_api_key:
        raise DeepSeekChatError(
            "Missing DEEPSEEK_API_KEY. Get it from https://platform.deepseek.com and set it in .env",
            status_code=500,
        )
    return settings.deepseek_api_key