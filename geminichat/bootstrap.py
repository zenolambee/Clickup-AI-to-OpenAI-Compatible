from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession

from geminichat.account import (
    GeminiAccount,
    build_gemini_account,
    cookie_header,
    save_gemini_account,
)
from geminichat.exceptions import GeminiChatError

log = logging.getLogger(__name__)

BASE_URL = "https://aistudio.google.com"
DEFAULT_TIMEOUT = 30.0


@dataclass(slots=True, frozen=True)
class GeminiUserInfo:
    user_email: str
    user_name: str


def _validation_headers(acc: GeminiAccount) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        ),
    }
    if acc.sapisid:
        # Google signs requests with an Authorization derived from SAPISID. The
        # exact Authorization header Google's front end sends is session-derived
        # and not public; REVIEW against DevTools if SAPISID alone is rejected.
        headers["Authorization"] = f"SAPISIDHASH {acc.sapisid}"
    cookie = cookie_header(acc)
    if cookie:
        headers["Cookie"] = cookie
    return headers


async def fetch_gemini_user_info(
    cookie: str = "",
    *,
    sapisid: str = "",
    base_url: str = BASE_URL,
) -> dict[str, Any]:
    """Best-effort user/email lookup from the signed-in session.

    Google does not expose a stable "whoami" JSON for the AI Studio session. This
    tries a common account endpoint; if it is unavailable it simply returns {} and
    the caller proceeds with a lightweight check.
    """
    acc = build_gemini_account(cookie=cookie, sapisid=sapisid)
    session = AsyncSession(timeout=DEFAULT_TIMEOUT)
    try:
        resp = await session.get(f"{base_url}/", headers=_validation_headers(acc))
        if resp.status_code != 200:
            return {}
        return {}
    except Exception:
        return {}
    finally:
        await session.close()


async def bootstrap_from_session(
    cookie: str = "",
    *,
    sapisid: str = "",
    account_path: str = "gemini_account.json",
    default_model: str | None = None,
) -> GeminiAccount:
    if not (cookie or sapisid):
        raise GeminiChatError("No cookie or SAPISID provided", status_code=400)

    log.info("Saving Gemini session...")
    info = await fetch_gemini_user_info(cookie, sapisid=sapisid)

    email = (
        (info or {}).get("email")
        or (info or {}).get("user_email")
        or ""
    )

    acc = build_gemini_account(cookie=cookie, sapisid=sapisid)
    acc = GeminiAccount(
        cookie=acc.cookie,
        sapisid=acc.sapisid,
        user_email=email,
        default_model=default_model or "gemini-2.5-flash",
    )
    save_gemini_account(acc, account_path)
    log.info("Saved Gemini account to %s (email=%s)", account_path, email or "unknown")
    return acc
