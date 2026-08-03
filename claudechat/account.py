from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from claudechat.exceptions import ClaudeChatError


@dataclass(slots=True, frozen=True)
class ClaudeAccount:
    cookie: str
    organization_id: str = ""
    user_id: str = ""
    user_name: str = ""
    default_model: str = "claude-sonnet-4-20250514"
    extras: dict[str, Any] = field(default_factory=dict)


def load_claude_accounts(path: Path | str) -> list[ClaudeAccount]:
    p = Path(path).expanduser()

    if p.is_dir():
        return _load_accounts_from_dir(p)

    if p.is_file():
        return _load_accounts_from_file(p)

    raise ClaudeChatError(f"Account path not found: {p}", status_code=500)


def _load_accounts_from_file(p: Path) -> list[ClaudeAccount]:
    try:
        raw = p.read_text(encoding="utf-8").strip()
    except Exception as e:
        raise ClaudeChatError(f"Failed to read {p}: {e}", status_code=500) from e

    if not raw:
        raise ClaudeChatError(f"Account file is empty: {p}", status_code=500)

    data: Any = json.loads(raw)

    if isinstance(data, dict):
        data = [data]
    if not isinstance(data, list):
        raise ClaudeChatError(f"Account file must contain a JSON object or array: {p}", status_code=500)

    return _parse_accounts(data, p)


def _load_accounts_from_dir(p: Path) -> list[ClaudeAccount]:
    txt_files = sorted(p.glob("cookie_*.txt"))
    if not txt_files:
        raise ClaudeChatError(f"No cookie_*.txt files found in account directory: {p}", status_code=500)

    accounts: list[ClaudeAccount] = []
    for f in txt_files:
        raw = f.read_text(encoding="utf-8").strip()
        if not raw:
            continue
        accounts.append(ClaudeAccount(cookie=raw))

    if not accounts:
        raise ClaudeChatError(f"No valid accounts found in directory: {p}", status_code=500)

    return accounts


def _parse_accounts(data: list[dict[str, Any]], source: Path) -> list[ClaudeAccount]:
    accounts: list[ClaudeAccount] = []
    known = {f.name for f in ClaudeAccount.__dataclass_fields__.values()} - {"extras"}
    for i, entry in enumerate(data):
        if not entry.get("cookie"):
            raise ClaudeChatError(
                f"{source.name}[{i}] missing required field: cookie", status_code=500
            )
        kwargs = {k: entry[k] for k in known if k in entry}
        extras = {k: v for k, v in entry.items() if k not in known}
        accounts.append(ClaudeAccount(**kwargs, extras=extras))
    return accounts


def save_claude_accounts(accounts: list[ClaudeAccount], path: Path | str) -> None:
    p = Path(path).expanduser()

    if p.suffix == ".json":
        p.parent.mkdir(parents=True, exist_ok=True)
        _save_as_single_file(accounts, p)
    else:
        p.mkdir(parents=True, exist_ok=True)
        _save_as_directory(accounts, p)


def _save_as_single_file(accounts: list[ClaudeAccount], p: Path) -> None:
    if len(accounts) == 1:
        entry = _account_to_dict(accounts[0])
        p.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        data_list = [_account_to_dict(a) for a in accounts]
        p.write_text(json.dumps(data_list, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _save_as_directory(accounts: list[ClaudeAccount], p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)
    for i, acc in enumerate(accounts, start=1):
        file_path = p / f"cookie_{i}.txt"
        file_path.write_text(acc.cookie + "\n", encoding="utf-8")


def _account_to_dict(acc: ClaudeAccount) -> dict[str, Any]:
    entry: dict[str, Any] = {}
    for f in ClaudeAccount.__dataclass_fields__.values():
        if f.name == "extras":
            continue
        entry[f.name] = getattr(acc, f.name)
    entry.update(acc.extras)
    return entry


def build_headers(cookie: str) -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
        "Accept": "text/event-stream, text/event-stream",
        "Accept-Language": "en-US,en;q=0.5",
        "Referer": "https://claude.ai/chats",
        "Content-Type": "application/json",
        "Origin": "https://claude.ai",
        "DNT": "1",
        "Connection": "keep-alive",
        "Cookie": cookie,
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "TE": "trailers",
    }
