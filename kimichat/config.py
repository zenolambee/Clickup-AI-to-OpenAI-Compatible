from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from kimichat.account import KimiAccount, load_kimi_account
from kimichat.exceptions import KimiChatError

DEFAULT_BASE_URL = "https://www.kimi.com"


def _resolve_home() -> Path | None:
    raw = os.getenv("KIMICHAT_HOME", "").strip()
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
    account_path: Path
    base_url: str
    default_model: str


def _env_path(name: str, default: str) -> Path:
    p = Path(os.getenv(name, default)).expanduser()
    if not p.is_absolute():
        home = _resolve_home()
        if home is not None:
            return (home / p).resolve()
    return p


def load_settings() -> Settings:
    _load_dotenv_files()
    return Settings(
        api_key=os.getenv("KIMICHAT_API_KEY", "sk-kimichat"),
        host=os.getenv("KIMICHAT_HOST", "127.0.0.1"),
        port=int(os.getenv("KIMICHAT_PORT", "1997")),
        account_path=_env_path("KIMICHAT_ACCOUNT", "kimi_account.json"),
        base_url=os.getenv("KIMICHAT_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        default_model=os.getenv("KIMICHAT_DEFAULT_MODEL", "kimi"),
    )


def load_account_from_env(settings: Settings) -> KimiAccount:
    refresh_token = os.getenv("KIMICHAT_REFRESH_TOKEN", "").strip()
    access_token = os.getenv("KIMICHAT_ACCESS_TOKEN", "").strip()
    cookies = os.getenv("KIMICHAT_COOKIES", "").strip()
    device_id = os.getenv("KIMICHAT_DEVICE_ID", "").strip() or uuid.uuid4().hex

    if refresh_token or access_token:
        return KimiAccount(
            refresh_token=refresh_token,
            access_token=access_token,
            cookies=cookies,
            device_id=device_id,
            default_model=settings.default_model,
        )

    if settings.account_path.exists():
        return load_kimi_account(settings.account_path)

    raise KimiChatError(
        "No Kimi credentials found. Set KIMICHAT_REFRESH_TOKEN in .env, or run:\n"
        '  python -m kimichat init --refresh-token "eyJ..."\n'
        "Get the refresh_token from kimi.com DevTools -> Application -> "
        'Local Storage -> key "refresh_token".',
        status_code=500,
    )
