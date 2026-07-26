from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession

from qwenchat.account import QwenAccount, build_auth_headers, save_qwen_account
from qwenchat.exceptions import QwenChatError

log = logging.getLogger(__name__)

BASE_URL = "https://chat.qwen.ai"
DEFAULT_TIMEOUT = 30.0


@dataclass(slots=True, frozen=True)
class QwenUserInfo:
    user_id: str
    user_name: str


async def fetch_qwen_user_info(
    token: str,
    *,
    cookies: str = "",
    base_url: str = BASE_URL,
) -> dict[str, Any]:
    url = f"{base_url}/api/v2/user/info"
    acc = QwenAccount(token=token, cookies=cookies)
    headers = build_auth_headers(acc)
    session = AsyncSession(timeout=DEFAULT_TIMEOUT)
    try:
        resp = await session.get(url, headers=headers)
        if resp.status_code != 200:
            body = await resp.atext()
            raise QwenChatError(
                f"Token validation failed ({resp.status_code}): {body[:200]}",
                status_code=502,
            )
        data = resp.json()
        if data.get("code") not in (None, 0, 200):
            raise QwenChatError(
                f"API error: {data.get('message', 'unknown')} (code={data.get('code')})",
                status_code=502,
            )
        result = data.get("data") or data.get("result") or data
        return result if isinstance(result, dict) else {}
    finally:
        await session.close()


async def bootstrap_from_token(
    token: str,
    *,
    cookies: str = "",
    account_path: str = "qwen_account.json",
    default_model: str | None = None,
) -> QwenAccount:
    if not token:
        raise QwenChatError("Token is empty", status_code=400)

    log.info("Validating Qwen token...")
    try:
        user_info = await fetch_qwen_user_info(token, cookies=cookies)
    except QwenChatError:
        log.info("user/info failed, trying lightweight validation...")
        user_info = await _validate_lightweight(token, cookies=cookies)

    user_id = (user_info or {}).get("user_id") or (user_info or {}).get("id") or ""
    user_name = (user_info or {}).get("user_name") or (user_info or {}).get("nickname") or (user_info or {}).get("name") or ""

    acc = QwenAccount(
        token=token,
        cookies=cookies,
        user_id=user_id,
        user_name=user_name,
        default_model=default_model or "qwen3.7-plus",
    )
    save_qwen_account(acc, account_path)
    log.info("Saved Qwen account to %s (user=%s)", account_path, user_name or user_id)
    return acc


async def _validate_lightweight(
    token: str,
    *,
    cookies: str = "",
    base_url: str = BASE_URL,
) -> dict[str, Any]:
    url = f"{base_url}/api/v2/models"
    acc = QwenAccount(token=token, cookies=cookies)
    headers = build_auth_headers(acc)
    session = AsyncSession(timeout=DEFAULT_TIMEOUT)
    try:
        resp = await session.get(url, headers=headers)
        if resp.status_code != 200:
            body = await resp.atext()
            raise QwenChatError(
                f"Token validation failed ({resp.status_code}): {body[:200]}",
                status_code=502,
            )
        return {}
    finally:
        await session.close()
