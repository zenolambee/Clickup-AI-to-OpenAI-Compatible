from __future__ import annotations

import asyncio
import json
import logging
import base64
from typing import Any

from curl_cffi import requests

from grokchat.account import (
    GrokAccount,
    build_auth_headers,
    parse_browser_cookie,
    save_grok_account,
)
from grokchat.exceptions import GrokChatError

log = logging.getLogger(__name__)

BASE_URL = "https://grok.com"


def _decode_jwt_payload(token: str) -> dict[str, Any]:
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
            return json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        pass
    return {}


def _validate_cookies(cookies: str) -> dict[str, Any]:
    probe = GrokAccount(cookies=cookies)
    headers = build_auth_headers(probe)
    headers["Content-Type"] = "application/json"

    payload = {"temporary": True, "title": "GrokChat Validation"}
    resp = requests.post(
        f"{BASE_URL}/rest/app-chat/conversations",
        json=payload,
        headers=headers,
        impersonate="chrome",
        timeout=30.0,
    )
    if resp.status_code != 200:
        raise GrokChatError(
            f"Grok auth failed ({resp.status_code}): {resp.text[:300]!r}",
            status_code=502,
        )
    return resp.json()


def _fetch_bearer_token(cookies: str) -> str | None:
    parsed = parse_browser_cookie(cookies)
    return (
        parsed.get("sso")
        or parsed.get("x-oauth-authorization")
        or parsed.get("bearer")
        or None
    )


def bootstrap_from_cookie_sync(
    cookies: str,
    *,
    account_path: str = "grok_account.json",
) -> GrokAccount:
    conv_data = _validate_cookies(cookies)
    bearer = _fetch_bearer_token(cookies)

    sso_payload = _decode_jwt_payload(bearer or "")
    user_id = sso_payload.get("sub") or sso_payload.get("user_id", "")
    user_name = sso_payload.get("name", "")
    user_email = sso_payload.get("email", "")

    conv_id = conv_data.get("conversationId") or conv_data.get("id", "")

    acc = GrokAccount(
        cookies=cookies.strip().rstrip(";"),
        bearer_token=bearer or "",
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
    )
    save_grok_account(acc, account_path)
    log.info(
        "Bootstrapped Grok account for %s (%s) conv=%s",
        acc.user_name or acc.user_id,
        acc.user_email or "no email",
        conv_id[:8] if conv_id else "?",
    )
    return acc


async def bootstrap_from_cookie(
    cookies: str,
    *,
    account_path: str = "grok_account.json",
) -> GrokAccount:
    return await asyncio.to_thread(
        bootstrap_from_cookie_sync,
        cookies,
        account_path=account_path,
    )
