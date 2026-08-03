from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from claudechat.account import ClaudeAccount, load_claude_accounts, save_claude_accounts
from claudechat.exceptions import ClaudeChatError

DEFAULT_BASE_URL = "https://claude.ai"


def _resolve_home() -> Path | None:
    raw = os.getenv("CLAUDE_HOME", "").strip()
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
        api_key=os.getenv("CLAUDE_API_KEY", "sk-claudechat"),
        host=os.getenv("CLAUDE_HOST", "127.0.0.1"),
        port=int(os.getenv("CLAUDE_PORT", "1998")),
        account_path=_env_path("CLAUDE_ACCOUNT", "claude_accounts"),
        base_url=os.getenv("CLAUDE_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        default_model=os.getenv("CLAUDE_DEFAULT_MODEL", "claude-sonnet-4-20250514"),
    )


def load_accounts_from_env(settings: Settings) -> list[ClaudeAccount]:
    cookies_raw = os.getenv("CLAUDE_COOKIES", "").strip()
    if cookies_raw:
        cookies_list = [c.strip() for c in cookies_raw.split("||") if c.strip()]
        if cookies_list:
            return [ClaudeAccount(cookie=c, default_model=settings.default_model) for c in cookies_list]

    if settings.account_path.exists():
        return load_claude_accounts(settings.account_path)

    raise ClaudeChatError(
        "No Claude credentials found. Set CLAUDE_COOKIES in .env (separate multiple cookies with ||)\n"
        "or create claude_accounts.json.\n"
        "Get your cookie from claude.ai browser DevTools → Network → copy Cookie header.",
        status_code=500,
    )
