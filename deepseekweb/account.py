from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from deepseekweb.exceptions import DeepSeekWebError


@dataclass(slots=True, frozen=True)
class DeepSeekWebAccount:
    user_token: str
    ds_session_id: str = ""
    user_id: str = ""
    user_name: str = ""
    default_model: str = "deepseek-v4-flash"
    extras: dict[str, Any] = field(default_factory=dict)


def load_deepseek_account(path: Path | str) -> DeepSeekWebAccount:
    p = Path(path).expanduser()
    if not p.exists():
        raise DeepSeekWebError(f"Account file not found: {p}", status_code=500)
    try:
        data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise DeepSeekWebError(f"Invalid account JSON: {e}", status_code=500) from e

    if not data.get("user_token"):
        raise DeepSeekWebError("Account file missing required field: user_token", status_code=500)

    known = {f.name for f in DeepSeekWebAccount.__dataclass_fields__.values()} - {"extras"}
    kwargs = {k: data[k] for k in known if k in data}
    extras = {k: v for k, v in data.items() if k not in known}
    return DeepSeekWebAccount(**kwargs, extras=extras)


def save_deepseek_account(acc: DeepSeekWebAccount, path: Path | str) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    for f in DeepSeekWebAccount.__dataclass_fields__.values():
        if f.name == "extras":
            continue
        data[f.name] = getattr(acc, f.name)
    data.update(acc.extras)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_headers(acc: DeepSeekWebAccount, *, x_client_version: str | None = None) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {acc.user_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://chat.deepseek.com/",
        "Origin": "https://chat.deepseek.com",
        "x-client-locale": "en_US",
        "x-client-timezone-offset": "10800",
        "x-app-version": "20241129.1",
        "x-client-platform": "web",
        "x-client-version": x_client_version or "2.0.0",
    }
    if acc.ds_session_id:
        headers["Cookie"] = f"ds_session_id={acc.ds_session_id}"
    return headers