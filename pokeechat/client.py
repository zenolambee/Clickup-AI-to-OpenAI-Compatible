from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

from curl_cffi.requests import AsyncSession

from pokeechat.exceptions import PokeeChatError

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 600.0


class PokeeChatClient:
    def __init__(self, *, api_key: str, base_url: str = "https://api.pokee.ai/v1"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def aclose(self) -> None:
        pass

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

    async def list_models(self) -> list[dict[str, Any]]:
        url = f"{self.base_url}/models"
        session = AsyncSession(timeout=DEFAULT_TIMEOUT)
        try:
            resp = await session.get(url, headers=self._headers())
            if resp.status_code >= 400:
                raise PokeeChatError(f"GET /models failed ({resp.status_code}): {resp.text[:300]}", status_code=502)
            data = resp.json()
            return data.get("data", []) or []
        finally:
            await session.close()

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str,
        stream: bool,
    ) -> tuple[dict[str, Any], AsyncIterator[bytes] | None]:
        url = f"{self.base_url}/chat/completions"
        session = AsyncSession(timeout=DEFAULT_TIMEOUT)
        body = {
            "model": model,
            "messages": messages,
            "stream": stream,
        }
        try:
            resp = await session.post(url, json=body, headers=self._headers(), stream=True)
            if resp.status_code >= 400:
                text = await resp.atext()
                raise PokeeChatError(
                    f"POST /chat/completions failed ({resp.status_code}): {text[:300]}",
                    status_code=502,
                )
            if not stream:
                data = resp.json()
                await session.close()
                return data, None
            return {}, _iter_stream_bytes(resp)
        except PokeeChatError:
            raise
        except Exception as e:  # noqa: BLE001
            raise PokeeChatError(f"Pokee request failed: {e}", status_code=502) from e


async def _iter_stream_bytes(resp) -> AsyncIterator[bytes]:
    try:
        async for chunk in resp.aiter_content():
            yield chunk
    finally:
        await resp.aclose()