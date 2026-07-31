from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from gemini.account import GeminiAccount, load_gemini_account
from gemini.exceptions import GeminiChatError

DEFAULT_BASE_URL = "https://gemini.google.com"


def _resolve_home() -> Path | None:
    raw = os.getenv("GEMINICHAT_HOME", "").strip()
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
        api_key=os.getenv("GEMINICHAT_API_KEY", "sk-geminichat"),
        host=os.getenv("GEMINICHAT_HOST", "127.0.0.1"),
        port=int(os.getenv("GEMINICHAT_PORT", "1993")),
        account_path=_env_path("GEMINICHAT_ACCOUNT", "gemini_account.json"),
        base_url=os.getenv("GEMINICHAT_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        default_model=os.getenv("GEMINICHAT_DEFAULT_MODEL", "gemini-2.0-flash"),
    )


def load_account_from_env(settings: Settings) -> GeminiAccount:
    cookies = os.getenv("GEMINICHAT_COOKIES", "").strip()
    snlm0e = os.getenv("GEMINICHAT_SNLM0E", "").strip()

    if cookies:
        return GeminiAccount(
            cookies=cookies,
            snlm0e_token=snlm0e,
            default_model=settings.default_model,
        )

    if settings.account_path.exists():
        return load_gemini_account(settings.account_path)

    raise GeminiChatError(
        "No Gemini credentials found. Set GEMINICHAT_COOKIES in .env "
        "or run:\n  python -m gemini init --cookies \"...\"",
        status_code=500,
    )
