from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession

from kimichat.account import KimiAccount, build_auth_headers
from kimichat.bootstrap import refresh_access_token
from kimichat.exceptions import KimiChatError
from kimichat.models import resolve_model

log = logging.getLogger(__name__)

KIMI_BASE = "https://www.kimi.com"
DEFAULT_TIMEOUT = 300.0
STREAM_TIMEOUT = 120.0


@dataclass(slots=True)
class ChatResult:
    text: str | None
    chat_id: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class KimiChatClient:
    def __init__(self, account: KimiAccount, *, base_url: str = KIMI_BASE):
        self.account = account
        self.base_url = base_url.rstrip("/")
        self._access_token = account.access_token
        self._refresh_token = account.refresh_token

    async def aclose(self) -> None:
        pass

    # ---- auth -----------------------------------------------------------

    async def ensure_token(self, *, force: bool = False) -> None:
        """Make sure we hold a usable access_token, minting one if needed."""
        if self._access_token and not force:
            return
        if not self._refresh_token:
            if self._access_token:
                return
            raise KimiChatError(
                "No access_token and no refresh_token available to mint one.",
                status_code=401,
            )
        tokens = await refresh_access_token(
            self._refresh_token,
            cookies=self.account.cookies,
            device_id=self.account.device_id,
            base_url=self.base_url,
        )
        self._access_token = tokens["access_token"]
        self._refresh_token = tokens["refresh_token"]

    def _headers(self, chat_id: str | None = None) -> dict[str, str]:
        acc = KimiAccount(
            refresh_token=self._refresh_token,
            access_token=self._access_token,
            cookies=self.account.cookies,
            device_id=self.account.device_id,
        )
        headers = build_auth_headers(acc)
        if chat_id:
            headers["Referer"] = f"{self.base_url}/chat/{chat_id}"
        return headers

    # ---- conversation lifecycle ----------------------------------------

    async def _create_chat(self, kimiplus_id: str) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "name": "KimiChat API",
            "is_example": False,
            "enter_method": "new_chat",
            "kimiplus_id": kimiplus_id,
        }
        session = AsyncSession(timeout=DEFAULT_TIMEOUT, impersonate="chrome")
        try:
            resp = await session.post(url, json=payload, headers=self._headers())
            if resp.status_code == 401:
                await self.ensure_token(force=True)
                resp = await session.post(url, json=payload, headers=self._headers())
            if resp.status_code != 200:
                text = await resp.atext()
                raise KimiChatError(
                    f"Create chat failed ({resp.status_code}): {text[:200]}",
                    status_code=502,
                )
            data = resp.json()
            chat_id = data.get("id") or (data.get("data") or {}).get("id")
            if not chat_id:
                raise KimiChatError(f"Create chat: no id in response: {data}", status_code=502)
            return str(chat_id)
        finally:
            await session.close()

    async def _delete_chat(self, chat_id: str) -> None:
        url = f"{self.base_url}/api/chat/{chat_id}"
        session = AsyncSession(timeout=DEFAULT_TIMEOUT, impersonate="chrome")
        try:
            await session.delete(url, headers=self._headers())
        except Exception:
            log.warning("Failed to delete chat %s", chat_id[:8])
        finally:
            await session.close()

    async def _cleanup_chat(self, chat_id: str) -> None:
        with suppress(Exception):
            await self._delete_chat(chat_id)

    # ---- message shaping ------------------------------------------------

    @staticmethod
    def _extract_text(content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
            return "\n".join(parts)
        return str(content) if content else ""

    def _build_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, str]]:
        """Kimi web accepts a role/content list. System prompts are folded into
        the first user turn since the web persona ignores a standalone system
        role."""
        system_parts: list[str] = []
        turns: list[dict[str, str]] = []
        for msg in messages:
            role = msg.get("role", "")
            text = self._extract_text(msg.get("content", ""))
            if not text:
                continue
            if role == "system":
                system_parts.append(text)
            elif role in ("user", "assistant"):
                turns.append({"role": role, "content": text})

        if system_parts:
            prefix = "\n\n".join(system_parts)
            for turn in turns:
                if turn["role"] == "user":
                    turn["content"] = f"{prefix}\n\n{turn['content']}"
                    break
            else:
                turns.insert(0, {"role": "user", "content": prefix})
        return turns or [{"role": "user", "content": ""}]

    def _completion_payload(
        self, messages: list[dict[str, str]], kimiplus_id: str
    ) -> dict[str, Any]:
        return {
            "kimiplus_id": kimiplus_id,
            "messages": messages,
            "refs": [],
            "history": [],
            "use_search": False,
            "use_research": False,
            "extend": {"sidebar": True},
            "model": kimiplus_id,
        }

    @staticmethod
    def _parse_event(event: dict[str, Any]) -> tuple[str, dict[str, int]]:
        """Return (text_delta, usage_updates) for one SSE event."""
        etype = event.get("event")
        if etype == "cmpl":
            return event.get("text") or "", {}
        if etype == "all_done":
            usage: dict[str, int] = {}
            # Kimi sometimes reports token counts on completion.
            if "tokens" in event:
                usage["output_tokens"] = int(event.get("tokens") or 0)
            return "", usage
        if etype == "error":
            err = event.get("error") or {}
            raise KimiChatError(
                f"Kimi stream error: {err.get('message') or err or 'unknown'}",
                status_code=502,
            )
        return "", {}

    # ---- non-streaming --------------------------------------------------

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
        stream: bool = True,
        temperature: float | None = None,
        on_delta: Callable[[str], None] | None = None,
    ) -> ChatResult:
        kimiplus_id = resolve_model(model)
        await self.ensure_token()
        chat_id = await self._create_chat(kimiplus_id)
        payload = self._completion_payload(self._build_messages(messages), kimiplus_id)

        url = f"{self.base_url}/api/chat/{chat_id}/completion/stream"
        session = AsyncSession(timeout=STREAM_TIMEOUT, impersonate="chrome")
        collected = ""
        output_tokens = 0
        try:
            resp = await session.post(
                url,
                json=payload,
                headers={**self._headers(chat_id), "x-accel-buffering": "no"},
                stream=True,
            )
            if resp.status_code != 200:
                body = await resp.atext()
                raise KimiChatError(
                    f"Chat completion failed ({resp.status_code}): {body[:300]}",
                    status_code=502,
                )
            async for line in resp.aiter_lines():
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                line = line.strip()
                if not line or not line.startswith("data:"):
                    continue
                try:
                    event = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    continue
                delta, usage = self._parse_event(event)
                if delta:
                    if on_delta:
                        on_delta(delta)
                    collected += delta
                if "output_tokens" in usage:
                    output_tokens = usage["output_tokens"]

            return ChatResult(
                text=collected or None,
                chat_id=chat_id,
                model=kimiplus_id,
                output_tokens=output_tokens,
            )
        except Exception as e:
            if not isinstance(e, KimiChatError):
                raise KimiChatError(f"Kimi transport error: {e}", status_code=502) from e
            raise
        finally:
            await session.close()
            asyncio.ensure_future(self._cleanup_chat(chat_id))

    # ---- streaming ------------------------------------------------------

    async def stream_deltas(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
    ) -> tuple[AsyncIterator[str], str, Callable[[], ChatResult]]:
        kimiplus_id = resolve_model(model)
        await self.ensure_token()
        chat_id = await self._create_chat(kimiplus_id)
        payload = self._completion_payload(self._build_messages(messages), kimiplus_id)

        url = f"{self.base_url}/api/chat/{chat_id}/completion/stream"
        collected = ""
        output_tokens = 0
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        http_error: list[BaseException] = []

        async def producer() -> None:
            nonlocal collected, output_tokens
            session = AsyncSession(timeout=STREAM_TIMEOUT, impersonate="chrome")
            try:
                resp = await session.post(
                    url,
                    json=payload,
                    headers={**self._headers(chat_id), "x-accel-buffering": "no"},
                    stream=True,
                )
                if resp.status_code != 200:
                    body = await resp.atext()
                    raise KimiChatError(
                        f"Chat completion failed ({resp.status_code}): {body[:300]}",
                        status_code=502,
                    )
                async for line in resp.aiter_lines():
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    line = line.strip()
                    if not line or not line.startswith("data:"):
                        continue
                    try:
                        event = json.loads(line[5:].strip())
                    except json.JSONDecodeError:
                        continue
                    delta, usage = self._parse_event(event)
                    if delta:
                        await queue.put(delta)
                        collected += delta
                    if "output_tokens" in usage:
                        output_tokens = usage["output_tokens"]
            except BaseException as e:
                http_error.append(e)
            finally:
                await queue.put(None)
                await session.close()
                asyncio.ensure_future(self._cleanup_chat(chat_id))

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
                text=collected or None,
                chat_id=chat_id,
                model=kimiplus_id,
                output_tokens=output_tokens,
            )

        return consumer(), chat_id, finalize
