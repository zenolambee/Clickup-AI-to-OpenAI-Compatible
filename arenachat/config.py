from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from arenachat.account import ArenaAccount, load_arena_account
from arenachat.exceptions import ArenaChatError

DEFAULT_BASE_URL = "https://arena.ai"


def _resolve_home() -> Path | None:
    raw = os.getenv("ARENACHAT_HOME", "").strip()
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
        api_key=os.getenv("ARENACHAT_API_KEY", "sk-arenachat"),
        host=os.getenv("ARENACHAT_HOST", "127.0.0.1"),
        port=int(os.getenv("ARENACHAT_PORT", "1998")),
        account_path=_env_path("ARENACHAT_ACCOUNT", "arena_account.json"),
        base_url=os.getenv("ARENACHAT_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        default_model=os.getenv("ARENACHAT_DEFAULT_MODEL", "gpt-4o"),
    )


def load_account_from_env(settings: Settings) -> ArenaAccount:
    cookie = os.getenv("ARENACHAT_COOKIE", "").strip()

    if cookie:
        return ArenaAccount(
            cookie=cookie,
            default_model=settings.default_model,
        )

    if settings.account_path.exists():
        return load_arena_account(settings.account_path)

    raise ArenaChatError(
        "No Arena AI credentials found. Set ARENACHAT_COOKIE in .env "
        "or run:\n  python -m arenachat init --cookie \"<document.cookie>\"",
        status_code=500,
    )
