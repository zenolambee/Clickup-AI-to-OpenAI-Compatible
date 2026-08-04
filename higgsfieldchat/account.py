from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from higgsfieldchat.exceptions import HiggsfieldChatError


@dataclass(slots=True, frozen=True)
class HiggsfieldAccount:
    __session: str
    full_cookie: str = ""
    user_id: str = ""
    user_name: str = ""
    user_email: str = ""
    default_model: str = "supercomputer"
    extras: dict[str, Any] = field(default_factory=dict)


def parse_browser_cookie(cookie: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in cookie.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, _, value = part.partition("=")
        out[name.strip()] = value.strip()
    return out


def load_higgsfield_account(path: Path | str) -> HiggsfieldAccount:
    p = Path(path).expanduser()
    if not p.exists():
        raise HiggsfieldChatError(f"Account file not found: {p}", status_code=500)
    try:
        data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise HiggsfieldChatError(f"Invalid account JSON: {e}", status_code=500) from e

    for field_name in ("__session",):
        if not data.get(field_name):
            raise HiggsfieldChatError(
                f"Account file missing required field: {field_name}",
                status_code=500,
            )

    known = {f.name for f in HiggsfieldAccount.__dataclass_fields__.values()} - {"extras"}
    kwargs = {k: data[k] for k in known if k in data}
    extras = {k: v for k, v in data.items() if k not in known}
    return HiggsfieldAccount(**kwargs, extras=extras)


def save_higgsfield_account(acc: HiggsfieldAccount, path: Path | str) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    for f in HiggsfieldAccount.__dataclass_fields__.values():
        if f.name == "extras":
            continue
        data[f.name] = getattr(acc, f.name)
    data.update(acc.extras)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_cookie_header(acc: HiggsfieldAccount) -> str:
    if acc.full_cookie:
        return acc.full_cookie.strip().rstrip(";")
    parts = [
        f"__session={acc.__session}",
    ]
    return "; ".join(parts)