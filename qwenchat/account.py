from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qwenchat.exceptions import QwenChatError


@dataclass(slots=True, frozen=True)
class QwenAccount:
    token: str
    cookies: str = ""
    user_id: str = ""
    user_name: str = ""
    default_model: str = "qwen3.7-plus"
    extras: dict[str, Any] = field(default_factory=dict)


def load_qwen_account(path: Path | str) -> QwenAccount:
    p = Path(path).expanduser()
    if not p.exists():
        raise QwenChatError(f"Account file not found: {p}", status_code=500)
    try:
        data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise QwenChatError(f"Invalid account JSON: {e}", status_code=500) from e

    if not data.get("token"):
        raise QwenChatError("Account file missing required field: token", status_code=500)

    known = {f.name for f in QwenAccount.__dataclass_fields__.values()} - {"extras"}
    kwargs = {k: data[k] for k in known if k in data}
    extras = {k: v for k, v in data.items() if k not in known}
    return QwenAccount(**kwargs, extras=extras)


def save_qwen_account(acc: QwenAccount, path: Path | str) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    for f in QwenAccount.__dataclass_fields__.values():
        if f.name == "extras":
            continue
        data[f.name] = getattr(acc, f.name)
    data.update(acc.extras)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_auth_headers(acc: QwenAccount) -> dict[str, str]:
    headers = {
        "Authorization": f"Bearer {acc.token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Origin": "https://chat.qwen.ai",
        "source": "web",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    }
    if acc.cookies:
        headers["Cookie"] = acc.cookies
    return headers
