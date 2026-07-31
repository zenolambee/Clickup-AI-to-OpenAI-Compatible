from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession

from grokchat.account import GrokAccount, build_auth_headers
from grokchat.exceptions import GrokChatError
from grokchat.models import resolve_model

log = logging.getLogger(__name__)

GROK_BASE = "https://grok.com"
DEFAULT_TIMEOUT = 300.0
STREAM_TIMEOUT = 120.0


@dataclass(slots=True)
class ChatResult:
    text: str | None
    chat_id: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class GrokChatClient:
    def __init__(self, account: GrokAccount, *, base_url: str = GROK_BASE):
        self.account = account
        self.base_url = base_url.rstrip("/")

    async def aclose(self) -> None:
        pass

    def _headers(self) -> dict[str, str]:
        headers = build_auth_headers(self.account)
        headers["Content-Type"] = "application/json"
        headers["X-Request-Id"] = str(uuid.uuid4())
        return headers

    def _parse_sse_line(self, line: str) -> dict[str, Any] | None:
        line = line.strip()
        if not line or not line.startswith("data: "):
            return None
        payload = line[6:].strip()
        if payload == "[DONE]":
            return None
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            return None

    def _build_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return messages

    async def _create_conversation(self) -> str:
        url = f"{self.base_url}/rest/app-chat/conversations"
        payload = {"temporary": True, "title": "GrokChat API"}
        session = AsyncSession(timeout=DEFAULT_TIMEOUT, impersonate="chrome")
        try:
            resp = await session.post(url, json=payload, headers=self._headers())
            status = resp.status_code
            if status != 200:
                text = await resp.atext()
                raise GrokChatError(f"Create conversation failed ({status}): {text[:200]}", status_code=502)
            data = resp.json()
            conv_id = data.get("conversationId") or data.get("id")
            if not conv_id:
                raise GrokChatError(f"Create conversation: no id in response: {data}", status_code=502)
            return conv_id
        finally:
            await session.close()

    async def _delete_conversation(self, conv_id: str) -> None:
        url = f"{self.base_url}/rest/app-chat/conversations/{conv_id}"
        session = AsyncSession(timeout=DEFAULT_TIMEOUT, impersonate="chrome")
        try:
            await session.delete(url, headers=self._headers())
        except Exception:
            log.warning("Failed to delete conversation %s", conv_id[:8])
        finally:
            await session.close()

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
        stream: bool = True,
        temperature: float | None = None,
        on_delta: Callable[[str], None] | None = None,
    ) -> ChatResult:
        model_id = resolve_model(model)
        conv_id = await self._create_conversation()

        grok_messages = self._build_messages(messages)
        payload: dict[str, Any] = {
            "model": model_id,
            "messages": grok_messages,
            "stream": True,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        url = f"{self.base_url}/rest/app-chat/conversations/{conv_id}/responses"
        session = AsyncSession(timeout=STREAM_TIMEOUT, impersonate="chrome")
        collected_text = ""
        input_tokens = 0
        output_tokens = 0

        try:
            resp = await session.post(
                url,
                json=payload,
                headers=self._headers(),
                stream=True,
            )
            if resp.status_code != 200:
                body = await resp.atext()
                raise GrokChatError(
                    f"Chat completion failed ({resp.status_code}): {body[:300]}", status_code=502
                )

            async for line in resp.aiter_lines():
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                event = self._parse_sse_line(line)
                if not event:
                    continue

                choices = event.get("choices") or []
                for choice in choices:
                    delta = choice.get("delta") or {}
                    content = delta.get("content", "")
                    if content:
                        if on_delta:
                            on_delta(content)
                        collected_text += content

                    finish = choice.get("finish_reason")
                    if finish == "stop":
                        usage = event.get("usage") or {}
                        input_tokens = usage.get("prompt_tokens", 0)
                        output_tokens = usage.get("completion_tokens", 0)

            return ChatResult(
                text=collected_text or None,
                chat_id=conv_id,
                model=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception as e:
            if not isinstance(e, GrokChatError):
                raise GrokChatError(f"Grok transport error: {e}", status_code=502) from e
            raise
        finally:
            await session.close()
            asyncio.ensure_future(self._cleanup_conversation(conv_id))

    async def _cleanup_conversation(self, conv_id: str) -> None:
        try:
            await self._delete_conversation(conv_id)
        except Exception:
            pass

    async def stream_deltas(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
    ) -> tuple[AsyncIterator[str], str, Callable[[], ChatResult]]:
        model_id = resolve_model(model)
        conv_id = await self._create_conversation()
        grok_messages = self._build_messages(messages)

        payload: dict[str, Any] = {
            "model": model_id,
            "messages": grok_messages,
            "stream": True,
        }
        if temperature is not None:
            payload["temperature"] = temperature

        url = f"{self.base_url}/rest/app-chat/conversations/{conv_id}/responses"
        collected_text = ""
        input_tokens = 0
        output_tokens = 0
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        http_error: list[BaseException] = []

        async def producer() -> None:
            nonlocal collected_text, input_tokens, output_tokens
            session = AsyncSession(timeout=STREAM_TIMEOUT, impersonate="chrome")
            try:
                resp = await session.post(
                    url,
                    json=payload,
                    headers=self._headers(),
                    stream=True,
                )
                if resp.status_code != 200:
                    body = await resp.atext()
                    raise GrokChatError(
                        f"Chat completion failed ({resp.status_code}): {body[:300]}", status_code=502
                    )

                async for line in resp.aiter_lines():
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    event = self._parse_sse_line(line)
                    if not event:
                        continue

                    choices = event.get("choices") or []
                    for choice in choices:
                        delta = choice.get("delta") or {}
                        content = delta.get("content", "")
                        if content:
                            await queue.put(content)
                            collected_text += content

                        finish = choice.get("finish_reason")
                        if finish == "stop":
                            usage = event.get("usage") or {}
                            input_tokens = usage.get("prompt_tokens", 0)
                            output_tokens = usage.get("completion_tokens", 0)
            except BaseException as e:
                http_error.append(e)
            finally:
                await queue.put(None)
                await session.close()
                asyncio.ensure_future(self._cleanup_conversation(conv_id))

        async def consumer() -> AsyncIterator[str]:
            task = asyncio.create_task(producer())
            try:
                while True:
                    chunk = await queue.get()
                    if chunk is None:
                        break
                    yield chunk
                if http_error:
                    raise http_error[0]
            finally:
                if not task.done():
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
                else:
                    await task

        def finalize() -> ChatResult:
            return ChatResult(
                text=collected_text or None,
                chat_id=conv_id,
                model=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        return consumer(), conv_id, finalize
