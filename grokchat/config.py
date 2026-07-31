from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from grokchat.account import GrokAccount, load_grok_account
from grokchat.exceptions import GrokChatError

DEFAULT_BASE_URL = "https://grok.com"


def _resolve_home() -> Path | None:
    raw = os.getenv("GROKCHAT_HOME", "").strip()
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
        api_key=os.getenv("GROKCHAT_API_KEY", "sk-grokchat"),
        host=os.getenv("GROKCHAT_HOST", "127.0.0.1"),
        port=int(os.getenv("GROKCHAT_PORT", "1996")),
        account_path=_env_path("GROKCHAT_ACCOUNT", "grok_account.json"),
        base_url=os.getenv("GROKCHAT_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        default_model=os.getenv("GROKCHAT_DEFAULT_MODEL", "grok-3"),
    )


def _build_cookies_from_env() -> str:
    parts: list[str] = []
    sso = os.getenv("GROKCHAT_SSO", "").strip()
    sso_rw = os.getenv("GROKCHAT_SSO_RW", "").strip()
    xuid = os.getenv("GROKCHAT_X_USERID", "").strip()
    if sso:
        parts.append(f"sso={sso}")
    if sso_rw:
        parts.append(f"sso-rw={sso_rw}")
    if xuid:
        parts.append(f"x-userid={xuid}")
    combined = "; ".join(parts)
    extra = os.getenv("GROKCHAT_COOKIES", "").strip()
    if extra:
        combined = f"{combined}; {extra}" if combined else extra
    return combined


def load_account_from_env(settings: Settings) -> GrokAccount:
    cookies = os.getenv("GROKCHAT_COOKIES", "").strip()
    bearer = os.getenv("GROKCHAT_BEARER_TOKEN", "").strip()
    sso = os.getenv("GROKCHAT_SSO", "").strip()

    built_cookies = _build_cookies_from_env()

    if built_cookies or bearer:
        return GrokAccount(
            cookies=built_cookies,
            bearer_token=bearer,
            default_model=settings.default_model,
        )

    if settings.account_path.exists():
        return load_grok_account(settings.account_path)

    raise GrokChatError(
        "No Grok credentials found. Set GROKCHAT_SSO in .env "
        "or run:\n  python -m grokchat init --cookies \"...\"",
        status_code=500,
    )
