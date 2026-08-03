from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession

from claudechat.account import ClaudeAccount, build_headers, save_claude_accounts
from claudechat.exceptions import ClaudeChatError

log = logging.getLogger(__name__)

BASE_URL = "https://claude.ai"
DEFAULT_TIMEOUT = 30.0


@dataclass(slots=True, frozen=True)
class ClaudeUserInfo:
    user_id: str
    user_name: str
    organization_id: str


async def fetch_claude_organization_id(
    cookie: str,
    *,
    base_url: str = BASE_URL,
) -> tuple[str, dict[str, Any]]:
    url = f"{base_url}/api/organizations"
    headers = build_headers(cookie)
    session = AsyncSession(timeout=DEFAULT_TIMEOUT, impersonate="chrome110")
    try:
        resp = await session.get(url, headers=headers)
        if resp.status_code != 200:
            body = await resp.atext()
            raise ClaudeChatError(
                f"Cookie validation failed ({resp.status_code}): {body[:200]}",
                status_code=502,
            )
        data = resp.json()
        if not isinstance(data, list) or not data:
            raise ClaudeChatError("No organizations found for this cookie", status_code=502)
        org = data[0]
        org_uuid = org.get("uuid") or org.get("id") or ""
        if not org_uuid:
            raise ClaudeChatError(f"No organization UUID in response: {data}", status_code=502)
        return org_uuid, org
    finally:
        await session.close()


async def bootstrap_from_cookies(
    cookies: list[str],
    *,
    account_path: str = "claude_accounts.json",
    default_model: str | None = None,
) -> list[ClaudeAccount]:
    if not cookies:
        raise ClaudeChatError("No cookies provided", status_code=400)

    accounts: list[ClaudeAccount] = []
    for i, cookie in enumerate(cookies):
        log.info("Validating Claude cookie #%d...", i + 1)
        try:
            org_uuid, org_info = await fetch_claude_organization_id(cookie)
            user_name = org_info.get("name") or org_info.get("display_name") or ""
            user_id = org_info.get("uuid") or org_info.get("id") or ""
        except ClaudeChatError as e:
            log.warning("Cookie #%d validation failed: %s", i + 1, e)
            continue

        acc = ClaudeAccount(
            cookie=cookie,
            organization_id=org_uuid,
            user_id=user_id,
            user_name=user_name,
            default_model=default_model or "claude-sonnet-4-20250514",
        )
        accounts.append(acc)
        log.info("Cookie #%d valid: org=%s user=%s", i + 1, org_uuid[:8], user_name or user_id)

    if not accounts:
        raise ClaudeChatError("No valid cookies found. Check your cookies and try again.", status_code=400)

    save_claude_accounts(accounts, account_path)
    log.info("Saved %d Claude account(s) to %s", len(accounts), account_path)
    return accounts
