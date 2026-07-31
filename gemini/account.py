from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gemini.exceptions import GeminiChatError


_SNlM0e_RE = re.compile(r'"SNlM0e"\s*:\s*"([^"]+)"')


@dataclass(slots=True, frozen=True)
class GeminiAccount:
    cookies: str = ""
    snlm0e_token: str = ""
    user_id: str = ""
    user_name: str = ""
    user_email: str = ""
    default_model: str = "gemini-2.0-flash"
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


def build_auth_headers(acc: GeminiAccount) -> dict[str, str]:
    headers: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://gemini.google.com",
        "Referer": "https://gemini.google.com/",
    }
    if acc.cookies:
        headers["Cookie"] = acc.cookies.strip().rstrip(";")
    if acc.snlm0e_token:
        headers["X-Same-Domain"] = "1"
    return headers


def extract_snlm0e(html_text: str) -> str | None:
    m = _SNlM0e_RE.search(html_text)
    if m:
        return m.group(1)
    return None


def load_gemini_account(path: Path | str) -> GeminiAccount:
    p = Path(path).expanduser()
    if not p.exists():
        raise GeminiChatError(f"Account file not found: {p}", status_code=500)
    try:
        data: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise GeminiChatError(f"Invalid account JSON: {e}", status_code=500) from e

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
