from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from deepseekweb.account import (
    DeepSeekWebAccount,
    load_deepseek_account,
    save_deepseek_account,
)
from deepseekweb.exceptions import DeepSeekWebError

DEFAULT_BASE_URL = "https://chat.deepseek.com/api/v0"


def _resolve_home() -> Path | None:
    raw = os.getenv("DEEPSEEKWEB_HOME", os.getenv("QWENCHAT_HOME", "")).strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return None


def _load_dotenv_files() -> None:
    home = _resolve_home()
    if home is not None:
        load_dotenv(home / "deepseekweb.env", override=False)
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
        api_key=os.getenv("DEEPSEEKWEB_API_KEY", "sk-deepseekweb"),
        host=os.getenv("DEEPSEEKWEB_HOST", "127.0.0.1"),
        port=int(os.getenv("DEEPSEEKWEB_PORT", "1997")),
        account_path=_env_path("DEEPSEEKWEB_ACCOUNT", "deepseek_account.json"),
        base_url=os.getenv("DEEPSEEKWEB_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        default_model=os.getenv("DEEPSEEKWEB_DEFAULT_MODEL", "deepseek-v4-flash"),
    )


def load_account_from_env(settings: Settings) -> DeepSeekWebAccount:
    token = os.getenv("DEEPSEEKWEB_TOKEN", "").strip()
    ds_session = os.getenv("DEEPSEEK_WEB_DS_SESSION_ID", "").strip()

    if settings.account_path.exists():
        acc = load_deepseek_account(settings.account_path)
        if token:
            acc = DeepSeekWebAccount(
                user_token=token.strip(),
                ds_session_id=ds_session or acc.ds_session_id,
                user_id=acc.user_id,
                user_name=acc.user_name,
                default_model=acc.default_model,
                extras=acc.extras,
            )
            save_deepseek_account(acc, settings.account_path)
        return acc

    if token:
        acc = DeepSeekWebAccount(
            user_token=token.strip(),
            ds_session_id=ds_session,
        )
        save_deepseek_account(acc, settings.account_path)
        return acc

    raise DeepSeekWebError(
        "No DeepSeek web credentials found. Set DEEPSEEKWEB_TOKEN in .env or run:\n"
        "  python -m deepseekweb init --token \"<userToken>\"",
        status_code=500,
    )