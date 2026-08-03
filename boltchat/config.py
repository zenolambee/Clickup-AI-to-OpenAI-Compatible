from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from boltchat.account import BoltAccount, build_bolt_account, load_bolt_account
from boltchat.exceptions import BoltChatError

DEFAULT_BASE_URL = "https://bolt.new"


def _resolve_home() -> Path | None:
    raw = os.getenv("BOLTCHAT_HOME", os.getenv("QWENCHAT_HOME", "")).strip()
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
    # Bolt's AI backend streams over a WebSocket relay. The ws public endpoint
    # can change; keep it configurable so it does not need a code change.
    ws_url: str


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
        api_key=os.getenv("BOLTCHAT_API_KEY", "sk-boltchat"),
        host=os.getenv("BOLTCHAT_HOST", "127.0.0.1"),
        port=int(os.getenv("BOLTCHAT_PORT", "1996")),
        account_path=_env_path("BOLTCHAT_ACCOUNT", "bolt_account.json"),
        base_url=os.getenv("BOLTCHAT_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        default_model=os.getenv("BOLTCHAT_DEFAULT_MODEL", "bolt-agent"),
        ws_url=os.getenv(
            "BOLTCHAT_WS_URL",
            "wss://bolt.new/.well-known/ai/relay",
        ).rstrip("/"),
    )


def load_account_from_env(settings: Settings) -> BoltAccount:
    cookie = os.getenv("BOLTCHAT_COOKIE", "").strip()
    session_token = os.getenv("BOLTCHAT_SESSION_TOKEN", "").strip()

    if cookie or session_token:
        return build_bolt_account(cookie=cookie, session_token=session_token)

    if settings.account_path.exists():
        return load_bolt_account(settings.account_path)

    raise BoltChatError(
        "No Bolt.new credentials found. Set BOLTCHAT_COOKIE or BOLTCHAT_SESSION_TOKEN "
        "in .env, or create bolt_account.json.\n"
        "Get your session by copying document.cookie from https://bolt.new "
        "(Application -> Cookies), then run: boltchat setup",
        status_code=500,
    )
