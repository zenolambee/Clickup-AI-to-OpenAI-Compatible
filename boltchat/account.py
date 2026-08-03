from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from boltchat.exceptions import BoltChatError


@dataclass(slots=True, frozen=True)
class BoltAccount:
    """Browser session material for bolt.new.

    Bolt.new authenticates the *web app* with a StackBlitz session, not with an
    "API key". Useful material that mirrors how notionchat/qwenchat persist a
    browser session:

    * ``cookie``      - raw ``document.cookie`` from bolt.new
    * ``session_token` - ``sb_session`` (or related) token from cookie/localStorage
    * ``user_id``     - StackBlitz user id, when resolvable
    * ``user_name``   - StackBlitz user name, when resolvable
    * ``default_model`- model id sent by default
    """

    cookie: str = ""
    session_token: str = ""
    user_id: str = ""
    user_name: str = ""
    default_model: str = "bolt-agent"
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def has_credentials(self) -> bool:
        return bool(self.cookie or self.session_token)


def load_bolt_account(path: Path | str) -> BoltAccount:
    p = Path(path).expanduser()
    if not p.exists():
        raise BoltChatError(f"Account file not found: {p}", status_code=500)
    try:
        data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise BoltChatError(f"Invalid account JSON: {e}", status_code=500) from e

    if not (data.get("cookie") or data.get("session_token")):
        raise BoltChatError(
            "Account file missing credentials (need 'cookie' or 'session_token')",
            status_code=500,
        )

    known = {f.name for f in BoltAccount.__dataclass_fields__.values()} - {"extras"}
    kwargs = {k: data[k] for k in known if k in data}
    extras = {k: v for k, v in data.items() if k not in known}
    return BoltAccount(**kwargs, extras=extras)


def save_bolt_account(acc: BoltAccount, path: Path | str) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    for f in BoltAccount.__dataclass_fields__.values():
        if f.name == "extras":
            continue
        data[f.name] = getattr(acc, f.name)
    data.update(acc.extras)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _pick_session_token(cookie: str) -> str:
    """Best-effort extraction of a session id from a raw cookie string."""
    for name in ("sb_session", "session", "stackblitz_session", "sb-token"):
        for part in cookie.split(";"):
            part = part.strip()
            if part.startswith(f"{name}="):
                return part.split("=", 1)[1].strip()
    return ""


def build_bolt_account(*, cookie: str = "", session_token: str = "") -> BoltAccount:
    """Normalise the two ways a user can hand us their session."""
    cookie = (cookie or "").strip()
    session_token = (session_token or "").strip()
    if not session_token and cookie:
        session_token = _pick_session_token(cookie)
    return BoltAccount(cookie=cookie, session_token=session_token)


def cookie_header(acc: BoltAccount) -> str:
    return acc.cookie or ""
