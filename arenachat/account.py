from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from arenachat.exceptions import ArenaChatError


@dataclass(slots=True, frozen=True)
class ArenaAccount:
    cookie: str
    user_id: str = ""
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )
    default_model: str = "gpt-4o"
    extras: dict[str, Any] = field(default_factory=dict)


def load_arena_account(path: Path | str) -> ArenaAccount:
    p = Path(path).expanduser()
    if not p.exists():
        raise ArenaChatError(f"Account file not found: {p}", status_code=500)
    try:
        data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ArenaChatError(f"Invalid account JSON: {e}", status_code=500) from e

    if not data.get("cookie"):
        raise ArenaChatError("Account missing cookie field", status_code=500)

    known = {f.name for f in ArenaAccount.__dataclass_fields__.values()} - {"extras"}
    kwargs = {k: data[k] for k in known if k in data}
    extras = {k: v for k, v in data.items() if k not in known}
    return ArenaAccount(**kwargs, extras=extras)


def save_arena_account(acc: ArenaAccount, path: Path | str) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    for f in ArenaAccount.__dataclass_fields__.values():
        if f.name == "extras":
            continue
        data[f.name] = getattr(acc, f.name)
    data.update(acc.extras)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
