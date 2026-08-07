from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession

from arenachat.account import ArenaAccount
from arenachat.exceptions import ArenaChatError

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300.0


@dataclass(slots=True)
class ChatResult:
    text: str | None
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class ArenaChatClient:
    def __init__(self, account: ArenaAccount, *, base_url: str):
        self.account = account
        self.base_url = base_url.rstrip("/")

    async def aclose(self) -> None:
        pass

    def _headers(self) -> dict[str, str]:
        return {
            "User-Agent": self.account.user_agent,
            "Content-Type": "application/json",
            "Cookie": self.account.cookie,
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/",
        }

    async def fetch_available_models(self) -> list[dict[str, Any]]:
        url = f"{self.base_url}/api/models"
        headers = self._headers()
        data = await self._request("GET", url, headers=headers, stream=False)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            return data.get("models") or data.get("data") or []
        return []

    async def _request(self, method: str, url: str, **kwargs: Any) -> Any:
        async with AsyncSession(timeout=DEFAULT_TIMEOUT) as session:
            resp = await session.request(method, url, stream=True, **kwargs)
            body = await resp.atext()
            if resp.status_code != 200:
                raise ArenaChatError(
                    f"Arena AI API error ({resp.status_code}): {body[:300]}",
                    status_code=502,
                )
            return json.loads(body)

    async def complete(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        stream: bool = False,
    ) -> ChatResult:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        url = f"{self.base_url}/api/chat"
        headers = self._headers()

        payload: dict[str, Any] = {
            "messages": messages,
            "model": model or self.account.default_model,
            "stream": stream,
        }

        if stream:
            async with AsyncSession(timeout=DEFAULT_TIMEOUT) as session:
                resp = await session.request("POST", url, json=payload, headers=headers, stream=True)
                if resp.status_code != 200:
                    body = await resp.atext()
                    raise ArenaChatError(
                        f"Arena AI API error ({resp.status_code}): {body[:300]}",
                        status_code=502,
                    )
                collected: list[str] = []
                async for line in resp.aiter_lines():
                    decoded = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
                    if decoded.startswith("data: "):
                        data_str = decoded[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = (
                                data.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content", "")
                            )
                            if delta:
                                collected.append(delta)
                        except json.JSONDecodeError:
                            pass
                text = "".join(collected) if collected else None
        else:
            data = await self._request("POST", url, json=payload, headers=headers, stream=False)
            text = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content")
            )

        return ChatResult(
            text=text or None,
            model=model or self.account.default_model,
        )
