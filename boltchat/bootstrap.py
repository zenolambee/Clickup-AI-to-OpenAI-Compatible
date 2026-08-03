from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession

from boltchat.account import BoltAccount, build_bolt_account, cookie_header, save_bolt_account
from boltchat.exceptions import BoltChatError

log = logging.getLogger(__name__)

BASE_URL = "https://bolt.new"
DEFAULT_TIMEOUT = 30.0


@dataclass(slots=True, frozen=True)
class BoltUserInfo:
    user_id: str
    user_name: str


def _validation_headers(acc: BoltAccount) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
        ),
    }
    if acc.session_token:
        headers["Authorization"] = f"Bearer {acc.session_token}"
    cookie = cookie_header(acc)
    if cookie:
        headers["Cookie"] = cookie
    return headers


async def fetch_bolt_user_info(
    cookie: str = "",
    *,
    session_token: str = "",
    base_url: str = BASE_URL,
) -> dict[str, Any]:
    """Best-effort user lookup.

    Bolt's account endpoint is not a documented public API. This uses the generic
    StackBlitz auth introspection endpoint when reachable. If it is not available,
    caller should fall back to lightweight validation.
    """
    acc = build_bolt_account(cookie=cookie, session_token=session_token)
    url = f"{base_url}/api/v1/account"
    session = AsyncSession(timeout=DEFAULT_TIMEOUT)
    try:
        resp = await session.get(url, headers=_validation_headers(acc))
        if resp.status_code != 200:
            return {}
        data = resp.json()
        if isinstance(data, dict):
            return data.get("data") or data.get("user") or data
        return {}
    except Exception:
        return {}
    finally:
        await session.close()


async def bootstrap_from_session(
    cookie: str = "",
    *,
    session_token: str = "",
    account_path: str = "bolt_account.json",
    default_model: str | None = None,
) -> BoltAccount:
    if not (cookie or session_token):
        raise BoltChatError("No cookie or session token provided", status_code=400)

    log.info("Validating Bolt.new session...")
    user_info = await fetch_bolt_user_info(cookie, session_token=session_token)

    user_id = (
        (user_info or {}).get("user_id")
        or (user_info or {}).get("id")
        or (user_info or {}).get("uid")
        or ""
    )
    user_name = (
        (user_info or {}).get("user_name")
        or (user_info or {}).get("nickname")
        or (user_info or {}).get("name")
        or (user_info or {}).get("username")
        or ""
    )

    acc = build_bolt_account(cookie=cookie, session_token=session_token)
    acc = BoltAccount(
        cookie=acc.cookie,
        session_token=acc.session_token,
        user_id=user_id,
        user_name=user_name,
        default_model=default_model or "bolt-agent",
    )
    save_bolt_account(acc, account_path)
    log.info("Saved Bolt account to %s (user=%s)", account_path, user_name or user_id)
    return acc
