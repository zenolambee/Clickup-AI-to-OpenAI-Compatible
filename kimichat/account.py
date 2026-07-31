from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from kimichat.exceptions import KimiChatError


@dataclass(slots=True, frozen=True)
class KimiAccount:
    """Credentials for the Kimi web API.

    Kimi uses a two-token scheme (like most SPA apps):
      * refresh_token — long-lived, taken from kimi.com localStorage / cookies.
      * access_token  — short-lived Bearer token, obtained by calling
                        /api/auth/token/refresh with the refresh_token.

    You normally only need to supply ``refresh_token``; the access_token is
    minted automatically on startup / on 401. ``cookies`` and ``device_id``
    are optional and only help when Kimi enforces device fingerprinting.
    """

    refresh_token: str = ""
    access_token: str = ""
    cookies: str = ""
    device_id: str = ""
    user_id: str = ""
    user_name: str = ""
    default_model: str = "kimi"
    extras: dict[str, Any] = field(default_factory=dict)


def parse_browser_cookie(cookie: str) -> dict[str, str]:
    """Turn a raw ``document.cookie`` string into a name->value map."""
    out: dict[str, str] = {}
    for part in cookie.split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        name, _, value = part.partition("=")
        out[name.strip()] = value.strip()
    return out


def extract_refresh_token(raw: str) -> tuple[str, str]:
    """Best-effort split of pasted input into (refresh_token, cookies).

    Accepts either a bare JWT (``eyJ...``) or a full cookie string that may
    contain ``refresh_token=...``.
    """
    raw = raw.strip()
    if not raw:
        return "", ""
    # Bare JWT
    if raw.startswith("eyJ") and raw.count(".") == 2 and ";" not in raw:
        return raw, ""
    # Cookie string
    if "=" in raw:
        jar = parse_browser_cookie(raw)
        token = jar.get("refresh_token") or jar.get("kimi-auth") or ""
        return token, raw
    return raw, ""


def build_auth_headers(acc: KimiAccount, *, token: str | None = None) -> dict[str, str]:
    """Headers for authenticated Kimi API calls.

    ``token`` overrides the Bearer value (used to send the refresh_token to the
    token-refresh endpoint instead of the access_token).
    """
    bearer = token if token is not None else acc.access_token
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.kimi.com",
        "Referer": "https://www.kimi.com/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
    }
    if bearer:
        headers["Authorization"] = f"Bearer {bearer}"
    if acc.device_id:
        # Kimi fingerprint headers (names vary between builds; harmless if unused).
        headers["x-msh-device-id"] = acc.device_id
        headers["X-Traffic-Id"] = acc.device_id
    if acc.cookies:
        headers["Cookie"] = acc.cookies.strip().rstrip(";")
    return headers


def load_kimi_account(path: Path | str) -> KimiAccount:
    p = Path(path).expanduser()
    if not p.exists():
        raise KimiChatError(f"Account file not found: {p}", status_code=500)
    try:
        data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise KimiChatError(f"Invalid account JSON: {e}", status_code=500) from e

    if not (data.get("refresh_token") or data.get("access_token")):
        raise KimiChatError(
            "Account file missing required field: refresh_token (or access_token)",
            status_code=500,
        )

    known = {f.name for f in KimiAccount.__dataclass_fields__.values()} - {"extras"}
    kwargs = {k: data[k] for k in known if k in data}
    extras = {k: v for k, v in data.items() if k not in known}
    return KimiAccount(**kwargs, extras=extras)


def save_kimi_account(acc: KimiAccount, path: Path | str) -> None:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {}
    for f in KimiAccount.__dataclass_fields__.values():
        if f.name == "extras":
            continue
        data[f.name] = getattr(acc, f.name)
    data.update(acc.extras)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
