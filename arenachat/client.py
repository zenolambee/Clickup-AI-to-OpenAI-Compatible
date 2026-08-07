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
        """Fetch available models from Arena AI."""
        url = f"{self.base_url}/api/models"
        headers = self._headers()
        async with AsyncSession(timeout=DEFAULT_TIMEOUT) as session:
            resp = await session.get(url, headers=headers)
            if resp.status_code != 200:
                raise ArenaChatError(
                    f"Failed to fetch models ({resp.status_code})",
                    status_code=502,
                )
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("models") or data.get("data") or []
            return []

    async def complete(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        stream: bool = False,
    ) -> ChatResult:
        """Send a chat completion request to Arena AI."""
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

        async with AsyncSession(timeout=DEFAULT_TIMEOUT) as session:
            resp = await session.post(url, json=payload, headers=headers)
            if resp.status_code != 200:
                body = await resp.atext()
                raise ArenaChatError(
                    f"Arena AI API error ({resp.status_code}): {body[:300]}",
                    status_code=502,
                )

            if stream:
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
                data = resp.json()
                text = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                )

            return ChatResult(
                text=text or None,
                model=model or self.account.default_model,
            )
