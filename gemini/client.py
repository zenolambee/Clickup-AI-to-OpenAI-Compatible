from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession

from gemini.account import GeminiAccount, build_auth_headers
from gemini.exceptions import GeminiChatError
from gemini.models import resolve_model

log = logging.getLogger(__name__)

GEMINI_BASE = "https://gemini.google.com"
DEFAULT_TIMEOUT = 300.0
STREAM_TIMEOUT = 120.0

_JSON_ARRAY_RE = re.compile(r"^\[")


@dataclass(slots=True)
class ChatResult:
    text: str | None
    chat_id: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class GeminiChatClient:
    def __init__(self, account: GeminiAccount, *, base_url: str = GEMINI_BASE):
        self.account = account
        self.base_url = base_url.rstrip("/")
        self._conversation_id: str | None = None
        self._response_id: str | None = None
        self._choice_id: str | None = None

    async def aclose(self) -> None:
        pass

    def _headers(self) -> dict[str, str]:
        return build_auth_headers(self.account)

    def _build_payload(
        self,
        messages: list[dict[str, Any]],
        model_id: str,
    ) -> list[Any]:
        user_text = ""
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(str(item.get("text", "")))
                content = "\n".join(parts)
            if not isinstance(content, str):
                content = str(content) if content else ""
            if role == "user":
                user_text = content
            elif role == "system":
                user_text = f"[System instruction: {content}]\n\n{user_text}" if user_text else f"[System instruction: {content}]"

        req_id = str(uuid.uuid4())
        conv_id = self._conversation_id or req_id

        request = [
            [user_text],
            None,
            [conv_id, None, None, None, None, None, None, None],
        ]

        if self._conversation_id and self._response_id and self._choice_id:
            request[2][1] = self._response_id
            request[2][2] = self._choice_id

        return [
            [request],
            None,
            None,
            None,
            [model_id],
            None,
            [],
            None,
            None,
            None,
            None,
            0,
            1,
        ]

    def _parse_gemini_response(self, data: Any) -> str | None:
        try:
            if isinstance(data, list) and len(data) >= 4:
                inner = data[0]
                if isinstance(inner, list) and len(inner) >= 2:
                    choices = inner[1]
                    if isinstance(choices, list) and len(choices) >= 2:
                        content_parts = choices[1]
                        if isinstance(content_parts, list):
                            text_parts = []
                            for part in content_parts:
                                if isinstance(part, list) and len(part) >= 2:
                                    text_parts.append(str(part[1]) if part[1] else "")
                            if text_parts:
                                return "".join(text_parts)
                    result_text = choices[0] if isinstance(choices, list) and choices else None
                    if isinstance(result_text, str):
                        return result_text

            if isinstance(data, list) and len(data) >= 2:
                val = data[1]
                if isinstance(val, str):
                    return val
                if isinstance(val, list) and val:
                    if isinstance(val[0], str):
                        return val[0]
        except Exception:
            pass
        return None

    def _extract_ids(self, data: Any) -> None:
        try:
            if isinstance(data, list) and len(data) >= 4:
                inner = data[0]
                if isinstance(inner, list) and len(inner) >= 3:
                    ids_block = inner[2]
                    if isinstance(ids_block, list) and len(ids_block) >= 4:
                        if ids_block[0]:
                            self._conversation_id = str(ids_block[0])
                        if ids_block[1]:
                            self._response_id = str(ids_block[1])
                        if ids_block[2]:
                            self._choice_id = str(ids_block[2])
                        if not self._conversation_id and ids_block[3]:
                            self._conversation_id = str(ids_block[3])
        except Exception:
            pass

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
        payload = self._build_payload(messages, model_id)

        snlm0e = self.account.snlm0e_token
        url = f"{self.base_url}/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"

        params = {
            "bl": snlm0e,
            "_reqid": str(int(time.time() * 1000)),
            "rt": "c",
        }

        body = {
            "f.req": json.dumps(payload),
            "at": snlm0e,
        }

        session = AsyncSession(timeout=STREAM_TIMEOUT)
        collected_text = ""
        input_tokens = 0
        output_tokens = 0

        try:
            resp = await session.post(
                url,
                params=params,
                data=body,
                headers={
                    **self._headers(),
                    "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                },
                stream=True,
            )
            if resp.status_code != 200:
                body_text = await resp.atext()
                raise GeminiChatError(
                    f"Chat completion failed ({resp.status_code}): {body_text[:300]}",
                    status_code=502,
                )

            async for line in resp.aiter_lines():
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                line = line.strip()
                if not line:
                    continue

                if _JSON_ARRAY_RE.match(line):
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    self._extract_ids(data)

                    text = self._parse_gemini_response(data)
                    if text:
                        delta = text[len(collected_text):] if text.startswith(collected_text) else text
                        if delta:
                            if on_delta:
                                on_delta(delta)
                            collected_text = text

            return ChatResult(
                text=collected_text or None,
                chat_id=self._conversation_id or "",
                model=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception as e:
            if not isinstance(e, GeminiChatError):
                raise GeminiChatError(f"Gemini transport error: {e}", status_code=502) from e
            raise
        finally:
            await session.close()

    async def stream_deltas(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
    ) -> tuple[AsyncIterator[str], str, Callable[[], ChatResult]]:
        model_id = resolve_model(model)
        payload = self._build_payload(messages, model_id)

        snlm0e = self.account.snlm0e_token
        url = f"{self.base_url}/_/BardChatUi/data/assistant.lamda.BardFrontendService/StreamGenerate"

        params = {
            "bl": snlm0e,
            "_reqid": str(int(time.time() * 1000)),
            "rt": "c",
        }

        body = {
            "f.req": json.dumps(payload),
            "at": snlm0e,
        }

        collected_text = ""
        input_tokens = 0
        output_tokens = 0
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        http_error: list[BaseException] = []

        async def producer() -> None:
            nonlocal collected_text, input_tokens, output_tokens
            session = AsyncSession(timeout=STREAM_TIMEOUT)
            try:
                resp = await session.post(
                    url,
                    params=params,
                    data=body,
                    headers={
                        **self._headers(),
                        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                    },
                    stream=True,
                )
                if resp.status_code != 200:
                    body_text = await resp.atext()
                    raise GeminiChatError(
                        f"Chat completion failed ({resp.status_code}): {body_text[:300]}",
                        status_code=502,
                    )

                async for line in resp.aiter_lines():
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    line = line.strip()
                    if not line:
                        continue

                    if _JSON_ARRAY_RE.match(line):
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        self._extract_ids(data)

                        text = self._parse_gemini_response(data)
                        if text:
                            delta = text[len(collected_text):] if text.startswith(collected_text) else text
                            if delta:
                                await queue.put(delta)
                                collected_text = text
            except BaseException as e:
                http_error.append(e)
            finally:
                await queue.put(None)
                await session.close()

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
                chat_id=self._conversation_id or "",
                model=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        return consumer(), self._conversation_id or "", finalize
