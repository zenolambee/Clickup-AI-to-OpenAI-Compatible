from __future__ import annotations

import asyncio
import logging
from typing import Any

from curl_cffi import requests

from gemini.account import (
    GeminiAccount,
    build_auth_headers,
    extract_snlm0e,
    save_gemini_account,
)
from gemini.exceptions import GeminiChatError

log = logging.getLogger(__name__)

BASE_URL = "https://gemini.google.com"


def _fetch_snlm0e_and_user(cookies: str) -> tuple[str, dict[str, Any]]:
    probe = GeminiAccount(cookies=cookies)
    headers = build_auth_headers(probe)
    headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

    resp = requests.get(
        f"{BASE_URL}/",
        headers=headers,
        impersonate="chrome130",
        timeout=30.0,
    )
    if resp.status_code != 200:
        raise GeminiChatError(
            f"Gemini auth failed ({resp.status_code}): {resp.text[:300]!r}",
            status_code=502,
        )

    html = resp.text
    snlm0e = extract_snlm0e(html)
    if not snlm0e:
        raise GeminiChatError(
            "Could not extract SNlM0e token. Cookie may be invalid or expired.",
            status_code=502,
        )

    user_info: dict[str, Any] = {}
    try:
        import re
        m = re.search(r'"userName"\s*:\s*"([^"]+)"', html)
        if m:
            user_info["name"] = m.group(1)
        m = re.search(r'"userEmail"\s*:\s*"([^"]+)"', html)
        if m:
            user_info["email"] = m.group(1)
        m = re.search(r'"userId"\s*:\s*"([^"]+)"', html)
        if m:
            user_info["id"] = m.group(1)
    except Exception:
        pass

    return snlm0e, user_info


def bootstrap_from_cookie_sync(
    cookies: str,
    *,
    account_path: str = "gemini_account.json",
) -> GeminiAccount:
    snlm0e, user_data = _fetch_snlm0e_and_user(cookies)

    acc = GeminiAccount(
        cookies=cookies.strip().rstrip(";"),
        snlm0e_token=snlm0e,
        user_id=user_data.get("id", ""),
        user_name=user_data.get("name", ""),
        user_email=user_data.get("email", ""),
    )
    save_gemini_account(acc, account_path)
    log.info(
        "Bootstrapped Gemini account for %s (%s)",
        acc.user_name or acc.user_id,
        acc.user_email or "no email",
    )
    return acc


async def bootstrap_from_cookie(
    cookies: str,
    *,
    account_path: str = "gemini_account.json",
) -> GeminiAccount:
    return await asyncio.to_thread(
        bootstrap_from_cookie_sync,
        cookies,
        account_path=account_path,
    )
