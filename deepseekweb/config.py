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
    else:
        load_dotenv(Path("deepseekweb.env"), override=False)
    load_dotenv(Path(".env"), override=False)


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


def _parse_list(value: str) -> list[str]:
    return [part.strip() for part in (value or "").split(",") if part.strip()]


def _parse_indexed_accounts() -> list[DeepSeekWebAccount]:
    accounts: list[DeepSeekWebAccount] = []
    i = 1
    while True:
        token = os.getenv(f"DEEPSEEKWEB_TOKEN_{i}", "").strip()
        if not token:
            break
        sid = os.getenv(f"DEEPSEEK_WEB_DS_SESSION_ID_{i}", "").strip()
        accounts.append(DeepSeekWebAccount(user_token=token, ds_session_id=sid))
        i += 1
    return accounts


def _merge_account(a: DeepSeekWebAccount, b: DeepSeekWebAccount) -> DeepSeekWebAccount:
    return DeepSeekWebAccount(
        user_token=a.user_token,
        ds_session_id=a.ds_session_id or b.ds_session_id,
        user_id=a.user_id or b.user_id,
        user_name=a.user_name or b.user_name,
        default_model=a.default_model or b.default_model,
        extras=b.extras,
    )


def load_accounts_from_env(settings: Settings) -> list[DeepSeekWebAccount]:
    indexed = _parse_indexed_accounts()
    if indexed:
        if len(indexed) == 1 and settings.account_path.exists():
            indexed[0] = _merge_account(indexed[0], load_deepseek_account(settings.account_path))
        for acc in indexed:
            save_deepseek_account(acc, settings.account_path)
        return indexed

    tokens = _parse_list(os.getenv("DEEPSEEKWEB_TOKEN", ""))
    sessions = _parse_list(os.getenv("DEEPSEEK_WEB_DS_SESSION_ID", ""))

    accounts: list[DeepSeekWebAccount] = []
    if tokens:
        for i, token in enumerate(tokens):
            sid = sessions[i] if i < len(sessions) else ""
            accounts.append(DeepSeekWebAccount(user_token=token, ds_session_id=sid))
        if len(accounts) == 1 and settings.account_path.exists():
            saved = load_deepseek_account(settings.account_path)
            accounts[0] = _merge_account(accounts[0], saved)
        for acc in accounts:
            save_deepseek_account(acc, settings.account_path)
        return accounts

    if settings.account_path.exists():
        acc = load_deepseek_account(settings.account_path)
        if sessions:
            acc = DeepSeekWebAccount(
                user_token=acc.user_token,
                ds_session_id=",".join(sessions),
                user_id=acc.user_id,
                user_name=acc.user_name,
                default_model=acc.default_model,
                extras=acc.extras,
            )
            save_deepseek_account(acc, settings.account_path)
        return [acc]

    raise DeepSeekWebError(
        "No DeepSeek web credentials found. Set DEEPSEEKWEB_TOKEN in deepseekweb.env "
        "(comma-separated for multiple cookies) or run:\n"
        "  python -m deepseekweb init --token \"<userToken>\"",
        status_code=500,
    )


def load_account_from_env(settings: Settings) -> DeepSeekWebAccount:
    return load_accounts_from_env(settings)[0]