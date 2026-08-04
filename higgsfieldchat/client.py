from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession

from higgsfieldchat.account import HiggsfieldAccount, build_cookie_header
from higgsfieldchat.exceptions import HiggsfieldChatError
from higgsfieldchat.models import resolve_model

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 120.0
STREAM_TIMEOUT = 300.0


@dataclass(slots=True)
class ChatResult:
    text: str | None
    thread_id: str
    model: str
    tool_calls: list[dict[str, Any]] | None = None
    input_tokens: int = 0
    output_tokens: int = 0


class HiggsfieldClient:
    def __init__(
        self,
        account: HiggsfieldAccount,
        *,
        base_url: str = "https://higgsfield.ai",
        sc_base_url: str = "https://higgsfield.ai",
    ):
        self.account = account
        self.base_url = base_url.rstrip("/")
        self.sc_base_url = sc_base_url.rstrip("/")

    async def aclose(self) -> None:
        pass

    def _headers(self, referer: str | None = None) -> dict[str, str]:
        return {
            "Cookie": build_cookie_header(self.account),
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": self.base_url,
            "Referer": referer or f"{self.base_url}/supercomputer",
            "X-Request-Id": str(uuid.uuid4()),
        }

    async def _clerk_session(self) -> dict[str, Any]:
        url = f"{self.base_url}/api/auth/session"
        session = AsyncSession(timeout=DEFAULT_TIMEOUT)
        try:
            resp = await session.get(url, headers=self._headers())
            if resp.status_code == 200:
                return resp.json()
            return {}
        except Exception:
            return {}
        finally:
            await session.close()

    async def _get_sc_session_token(self) -> str | None:
        headers = self._headers()
        headers["Accept"] = "text/event-stream"
        session = AsyncSession(timeout=DEFAULT_TIMEOUT)
        try:
            resp = await session.get(
                f"{self.sc_base_url}/api/supercomputer/session",
                headers=headers,
            )
            if resp.status_code == 200:
                data = resp.json()
                return data.get("token") or data.get("sessionToken") or data.get("session_id")
            return None
        except Exception:
            return None
        finally:
            await session.close()

    async def _create_conversation(self) -> str:
        url = f"{self.sc_base_url}/api/supercomputer/conversations"
        session = AsyncSession(timeout=DEFAULT_TIMEOUT)
        try:
            resp = await session.post(
                url,
                json={"title": "HiggsfieldChat API"},
                headers=self._headers(),
            )
            if resp.status_code == 200:
                data = resp.json()
                cid = data.get("id") or data.get("conversation_id") or data.get("data", {}).get("id")
                if cid:
                    return cid
            cid = str(uuid.uuid4())
            return cid
        except Exception:
            return str(uuid.uuid4())
        finally:
            await session.close()

    async def complete(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        thread_id: str | None = None,
        tools_active: bool = False,
        ide_agent_mode: bool = False,
        client_tools: list[dict[str, Any]] | None = None,
    ) -> ChatResult:
        model_id = resolve_model(model, default=self.account.default_model)
        conv_id = thread_id or await self._create_conversation()

        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "model": model_id,
            "conversation_id": conv_id,
            "stream": False,
        }

        url = f"{self.sc_base_url}/api/supercomputer/chat/completions"
        session = AsyncSession(timeout=DEFAULT_TIMEOUT)
        try:
            resp = await session.post(
                url,
                json=payload,
                headers=self._headers(),
            )
            status = resp.status_code

            if status == 404:
                url = f"{self.sc_base_url}/api/chat/completions"
                resp = await session.post(
                    url,
                    json=payload,
                    headers=self._headers(),
                )
                status = resp.status_code

            if status != 200:
                body = await resp.atext()
                raise HiggsfieldChatError(
                    f"Chat completion failed ({status}): {body[:300]}",
                    status_code=502,
                )

            data = resp.json()
            text = ""
            choice = (data.get("choices") or [{}])[0]
            msg = choice.get("message") or {}
            text = msg.get("content") or data.get("content") or data.get("text") or ""
            input_tokens = data.get("usage", {}).get("prompt_tokens", 0) or 0
            output_tokens = data.get("usage", {}).get("completion_tokens", 0) or 0

            return ChatResult(
                text=text or None,
                thread_id=conv_id,
                model=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except HiggsfieldChatError:
            raise
        except Exception as e:
            raise HiggsfieldChatError(f"Higgsfield transport error: {e}", status_code=502) from e
        finally:
            await session.close()

    async def stream_deltas(
        self,
        *,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        thread_id: str | None = None,
        tools_active: bool = False,
        ide_agent_mode: bool = False,
        client_tools: list[dict[str, Any]] | None = None,
        buffer_until_complete: bool = False,
    ) -> tuple[AsyncIterator[str], str, Callable[[], ChatResult]]:
        model_id = resolve_model(model, default=self.account.default_model)
        conv_id = thread_id or await self._create_conversation()

        messages: list[dict[str, Any]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "messages": messages,
            "model": model_id,
            "conversation_id": conv_id,
            "stream": True,
        }

        url = f"{self.sc_base_url}/api/supercomputer/chat/completions"
        collected_text = ""
        input_tokens = 0
        output_tokens = 0
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        http_error: list[BaseException] = []

        async def producer() -> None:
            nonlocal collected_text, input_tokens, output_tokens
            _session = AsyncSession(timeout=STREAM_TIMEOUT)
            try:
                headers = self._headers()
                headers["Accept"] = "text/event-stream"
                headers["x-accel-buffering"] = "no"

                resp = await _session.post(url, json=payload, headers=headers, stream=True)
                status = resp.status_code

                if status == 404:
                    url2 = f"{self.sc_base_url}/api/chat/completions"
                    resp = await _session.post(url2, json=payload, headers=headers, stream=True)
                    status = resp.status_code

                if status != 200:
                    body = await resp.atext()
                    raise HiggsfieldChatError(
                        f"Chat completion failed ({status}): {body[:300]}",
                        status_code=502,
                    )

                async for line in resp.aiter_lines():
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith("data: "):
                        data_str = line[6:]
                    elif line.startswith("data:"):
                        data_str = line[5:]
                    else:
                        continue

                    if data_str.strip() == "[DONE]":
                        break

                    try:
                        event = json.loads(data_str)
                    except json.JSONDecodeError:
                        continue

                    choices = event.get("choices") or []
                    for choice in choices:
                        delta = choice.get("delta") or {}
                        content = delta.get("content") or ""
                        if content:
                            await queue.put(content)
                            collected_text += content

                        finish = choice.get("finish_reason")
                        if finish:
                            usage = event.get("usage") or {}
                            nonlocal input_tokens, output_tokens
                            input_tokens = usage.get("prompt_tokens", 0) or 0
                            output_tokens = usage.get("completion_tokens", 0) or 0

                    content = event.get("content") or event.get("text") or ""
                    if content:
                        delta = content[len(collected_text):] if content.startswith(collected_text) else content
                        if delta:
                            await queue.put(delta)
                            collected_text = content
            except BaseException as e:
                http_error.append(e)
            finally:
                await queue.put(None)
                await _session.close()

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
                thread_id=conv_id,
                model=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        return consumer(), conv_id, finalize