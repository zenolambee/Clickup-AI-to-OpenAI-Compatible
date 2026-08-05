from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path

from dotenv import load_dotenv

from higgsfieldchat.account import (
    HiggsfieldAccount,
    load_higgsfield_account,
    parse_browser_cookie,
    save_higgsfield_account,
)
from higgsfieldchat.exceptions import HiggsfieldChatError

DEFAULT_BASE_URL = "https://higgsfield.ai"
DEFAULT_SC_BASE_URL = "https://higgsfield.ai"


def _resolve_home() -> Path | None:
    raw = os.getenv("HIGGSFIELDCHAT_HOME", "").strip()
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
    sc_base_url: str
    default_model: str

    def __post_init__(self) -> None:
        self.account_path = Path(self.account_path).expanduser() if isinstance(self.account_path, (str, bytes)) else self.account_path


def _env_path(name: str, default: str) -> Path:
    p = Path(os.getenv(name, default)).expanduser()
    if not p.is_absolute():
        home = _resolve_home()
        if home is not None:
            return (home / p).resolve()
    return p


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def load_settings() -> Settings:
    _load_dotenv_files()
    return Settings(
        api_key=os.getenv("HIGGSFIELDCHAT_API_KEY", "sk-higgsfieldchat"),
        host=os.getenv("HIGGSFIELDCHAT_HOST", "127.0.0.1"),
        port=int(os.getenv("HIGGSFIELDCHAT_PORT", "1992")),
        account_path=_env_path("HIGGSFIELDCHAT_ACCOUNT", "higgsfield_account.json"),
        base_url=os.getenv("HIGGSFIELDCHAT_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        sc_base_url=os.getenv("HIGGSFIELDCHAT_SC_BASE_URL", DEFAULT_SC_BASE_URL).rstrip("/"),
        default_model=os.getenv("HIGGSFIELDCHAT_DEFAULT_MODEL", "supercomputer"),
    )


def _cookie_identity_changed(acc: HiggsfieldAccount, cookie: str) -> bool:
    parsed = parse_browser_cookie(cookie)
    new_session = parsed.get("__session", "")
    if new_session and acc.session and new_session != acc.session:
        return True
    return False


def load_account_from_env(settings: Settings) -> HiggsfieldAccount:
    cookie = os.getenv("HIGGSFIELD_COOKIE", "").strip()

    if settings.account_path.exists():
        acc = load_higgsfield_account(settings.account_path)
        if cookie:
            if _cookie_identity_changed(acc, cookie):
                acc = replace(acc, full_cookie=cookie.strip().rstrip(";"), session=parse_browser_cookie(cookie).get("__session", acc.session))
                save_higgsfield_account(acc, settings.account_path)
            else:
                acc = replace(acc, full_cookie=cookie.strip().rstrip(";"))
        return acc

    if cookie:
        parsed = parse_browser_cookie(cookie)
        acc = HiggsfieldAccount(
            session=parsed.get("__session", ""),
            full_cookie=cookie.strip().rstrip(";"),
        )
        save_higgsfield_account(acc, settings.account_path)
        return acc

    raise HiggsfieldChatError(
        "No Higgsfield credentials found. Set HIGGSFIELD_COOKIE in .env or create higgsfield_account.json",
        status_code=500,
    )