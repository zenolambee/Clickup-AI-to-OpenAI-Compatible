from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from qwenchat.account import QwenAccount, load_qwen_account, save_qwen_account
from qwenchat.exceptions import QwenChatError

DEFAULT_BASE_URL = "https://chat.qwen.ai"


def _resolve_home() -> Path | None:
    raw = os.getenv("QWENCHAT_HOME", "").strip()
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
        api_key=os.getenv("QWENCHAT_API_KEY", "sk-qwenchat"),
        host=os.getenv("QWENCHAT_HOST", "127.0.0.1"),
        port=int(os.getenv("QWENCHAT_PORT", "1995")),
        account_path=_env_path("QWENCHAT_ACCOUNT", "qwen_account.json"),
        base_url=os.getenv("QWENCHAT_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
        default_model=os.getenv("QWENCHAT_DEFAULT_MODEL", "qwen3.7-plus"),
    )


def load_account_from_env(settings: Settings) -> QwenAccount:
    token = os.getenv("QWENCHAT_TOKEN", "").strip()
    cookies = os.getenv("QWENCHAT_COOKIES", "").strip()

    if token:
        acc = QwenAccount(
            token=token,
            cookies=cookies,
            default_model=settings.default_model,
        )
        return acc

    if settings.account_path.exists():
        return load_qwen_account(settings.account_path)

    raise QwenChatError(
        "No Qwen credentials found. Set QWENCHAT_TOKEN in .env or create qwen_account.json.\n"
        "Get your token from chat.qwen.ai Local Storage (key: token).",
        status_code=500,
    )
