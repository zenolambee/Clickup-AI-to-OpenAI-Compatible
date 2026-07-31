from __future__ import annotations

import logging
from typing import Any

from curl_cffi.requests import AsyncSession

from kimichat.account import KimiAccount, build_auth_headers, save_kimi_account
from kimichat.exceptions import KimiChatError

log = logging.getLogger(__name__)

BASE_URL = "https://www.kimi.com"
DEFAULT_TIMEOUT = 30.0


async def refresh_access_token(
    refresh_token: str,
    *,
    cookies: str = "",
    device_id: str = "",
    base_url: str = BASE_URL,
) -> dict[str, str]:
    """Exchange a refresh_token for a fresh access_token.

    Kimi web calls ``GET /api/auth/token/refresh`` with the refresh_token as
    the Bearer credential. The response contains new ``access_token`` and
    ``refresh_token`` values (the refresh_token may rotate).
    """
    if not refresh_token:
        raise KimiChatError("refresh_token is empty", status_code=400)

    url = f"{base_url}/api/auth/token/refresh"
    acc = KimiAccount(refresh_token=refresh_token, cookies=cookies, device_id=device_id)
    # Send the refresh_token (not the access_token) as the Bearer credential.
    headers = build_auth_headers(acc, token=refresh_token)

    session = AsyncSession(timeout=DEFAULT_TIMEOUT, impersonate="chrome")
    try:
        resp = await session.get(url, headers=headers)
        if resp.status_code != 200:
            body = await resp.atext()
            raise KimiChatError(
                f"Token refresh failed ({resp.status_code}): {body[:200]}",
                status_code=502 if resp.status_code >= 500 else 401,
            )
        data = resp.json()
    finally:
        await session.close()

    access = data.get("access_token") or ""
    new_refresh = data.get("refresh_token") or refresh_token
    if not access:
        raise KimiChatError(
            f"Token refresh returned no access_token: {str(data)[:200]}",
            status_code=502,
        )
    return {"access_token": access, "refresh_token": new_refresh}


async def fetch_user_info(
    access_token: str,
    *,
    cookies: str = "",
    device_id: str = "",
    base_url: str = BASE_URL,
) -> dict[str, Any]:
    url = f"{base_url}/api/user"
    acc = KimiAccount(access_token=access_token, cookies=cookies, device_id=device_id)
    headers = build_auth_headers(acc)
    session = AsyncSession(timeout=DEFAULT_TIMEOUT, impersonate="chrome")
    try:
        resp = await session.get(url, headers=headers)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}
    finally:
        await session.close()


async def bootstrap_from_token(
    refresh_token: str,
    *,
    cookies: str = "",
    device_id: str = "",
    account_path: str = "kimi_account.json",
    default_model: str | None = None,
) -> KimiAccount:
    log.info("Validating Kimi refresh_token...")
    tokens = await refresh_access_token(
        refresh_token, cookies=cookies, device_id=device_id
    )
    access = tokens["access_token"]
    new_refresh = tokens["refresh_token"]

    info = await fetch_user_info(access, cookies=cookies, device_id=device_id)
    user_id = str(info.get("id") or info.get("user_id") or "")
    user_name = str(info.get("name") or info.get("nickname") or "")

    acc = KimiAccount(
        refresh_token=new_refresh,
        access_token=access,
        cookies=cookies,
        device_id=device_id,
        user_id=user_id,
        user_name=user_name,
        default_model=default_model or "kimi",
    )
    save_kimi_account(acc, account_path)
    log.info("Saved Kimi account to %s (user=%s)", account_path, user_name or user_id)
    return acc
