from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from geminichat.exceptions import GeminiChatError


@dataclass(slots=True, frozen=True)
class GeminiAccount:
    """Browser session material for Google AI Studio (aistudio.google.com).

    This is a **session**, not an API key. Useful material:
    * ``cookie``     - raw document.cookie from aistudio.google.com
    * ``sapisid``    - the SID / SAPISID token used to authorize internal calls
    * ``user_email`` - detected Google account email (when resolvable)
    * ``default_model`` - default Gemini model
    """

    cookie: str = ""
    sapisid: str = ""
    user_email: str = ""
    default_model: str = "gemini-2.5-flash"
    extras: dict[str, Any] = field(default_factory=dict)

    @property
    def has_credentials(self) -> bool:
        return bool(self.cookie or self.sapisid)


def load_gemini_account(path: Path | str) -> GeminiAccount:
    p = Path(path).expanduser()
    if not p.exists():
        raise GeminiChatError(f"Account file not found: {p}", status_code=500)
    try:
        data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise GeminiChatError(f"Invalid account JSON: {e}", status_code=500) from e

    if not (data.get("cookie") or data.get("sapisid")):
        raise GeminiChatError(
            "Account file missing credentials (need 'cookie' or 'sapisid')",
            status_code=500,
        )

    known = {f.name for f in GeminiAccount.__dataclass_fields__.values()} - {"extras"}
    kwargs = {k: data[k] for k in known if k in data}
    extras = {k: v for k, v in data.items() if k not in known}
    return GeminiAccount(**kwargs, extras=extras)


def save_gemini_account(acc: GeminiAccount, path: Path | str) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    for f in GeminiAccount.__dataclass_fields__.values():
        if f.name == "extras":
            continue
        data[f.name] = getattr(acc, f.name)
    data.update(acc.extras)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _pick_cookie_value(cookie: str, name: str) -> str:
    for part in cookie.split(";"):
        part = part.strip()
        if part.startswith(f"{name}="):
            return part.split("=", 1)[1].strip()
    return ""


def build_gemini_account(*, cookie: str = "", sapisid: str = "") -> GeminiAccount:
    cookie = (cookie or "").strip()
    sapisid = (sapisid or "").strip()
    if not sapisid and cookie:
        sapisid = _pick_cookie_value(cookie, "SAPISID")
    return GeminiAccount(cookie=cookie, sapisid=sapisid)


def cookie_header(acc: GeminiAccount) -> str:
    return acc.cookie or ""
