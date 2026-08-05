from __future__ import annotations

import asyncio
import json
import logging
import uuid
import time
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession

from qwenchat.account import QwenAccount, build_auth_headers
from qwenchat.exceptions import QwenChatError
from qwenchat.models import resolve_model

log = logging.getLogger(__name__)

QWEN_BASE = "https://chat.qwen.ai"
DEFAULT_TIMEOUT = 300.0
STREAM_TIMEOUT = 120.0


@dataclass(slots=True)
class ChatResult:
    text: str | None
    chat_id: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class QwenChatClient:
    def __init__(self, account: QwenAccount, *, base_url: str = QWEN_BASE):
        self.account = account
        self.base_url = base_url.rstrip("/")

    async def aclose(self) -> None:
        pass

    def _headers(self, chat_id: str | None = None) -> dict[str, str]:
        headers = build_auth_headers(self.account)
        headers["X-Request-Id"] = str(uuid.uuid4())
        headers["Accept"] = "application/json"
        if chat_id:
            headers["Referer"] = f"{self.base_url}/c/{chat_id}"
        return headers

    def _uuid(self) -> str:
        return str(uuid.uuid4())

    async def _create_chat(self, model_id: str) -> str:
        url = f"{self.base_url}/api/v2/chats/new"
        payload = {
            "title": "QwenChat API",
            "models": [model_id],
            "chat_mode": "normal",
            "chat_type": "t2t",
            "timestamp": int(time.time() * 1000),
            "project_id": "",
        }
        session = AsyncSession(timeout=DEFAULT_TIMEOUT)
        try:
            resp = await session.post(url, json=payload, headers=self._headers())
            status = resp.status_code
            if status != 200:
                text = await resp.atext()
                raise QwenChatError(f"Create chat failed ({status}): {text[:200]}", status_code=502)
            data = resp.json()
            chat_id = (data.get("data") or {}).get("id")
            if not chat_id:
                raise QwenChatError(f"Create chat: no id in response: {data}", status_code=502)
            return chat_id
        finally:
            await session.close()

    async def _delete_chat(self, chat_id: str) -> None:
        url = f"{self.base_url}/api/v2/chats/{chat_id}"
        session = AsyncSession(timeout=DEFAULT_TIMEOUT)
        try:
            await session.delete(url, headers=self._headers())
        except Exception:
            log.warning("Failed to delete chat %s", chat_id[:8])
        finally:
            await session.close()

    def _build_messages(self, messages: list[dict[str, Any]]) -> str:
        system_parts: list[str] = []
        conversation: list[str] = []
        pending_user: str | None = None

        def _extract_text(content: Any) -> str:
            if isinstance(content, str):
                return content
            if isinstance(content, list):
                parts: list[str] = []
                for item in content:
                    if isinstance(item, dict):
                        t = item.get("type", "")
                        if t == "text":
                            parts.append(str(item.get("text", "")))
                return "\n".join(parts)
            return str(content) if content else ""

        for msg in messages:
            role = msg.get("role", "")
            content = _extract_text(msg.get("content", ""))
            if not content:
                continue
            if role == "system":
                system_parts.append(content)
            elif role == "user":
                if pending_user is not None:
                    conversation.append(pending_user)
                pending_user = content
            elif role == "assistant":
                if pending_user is not None:
                    conversation.append(f"{pending_user}<｜Assistant｜>{content}<｜end of sentence｜>")
                    pending_user = None
                else:
                    conversation.append(f"<｜Assistant｜>{content}<｜end of sentence｜>")

        if pending_user is not None:
            conversation.append(pending_user)

        user_content = "<｜User｜>".join(conversation) if conversation else ""
        if system_parts:
            system_text = "\n\n".join(system_parts)
            if user_content:
                user_content = f"{system_text}\n\n{user_content}"
            else:
                user_content = system_text
        return user_content

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
        chat_id = await self._create_chat(model_id)
        user_content = self._build_messages(messages)

        fid = self._uuid()
        child_id = self._uuid()
        ts = int(time.time())

        feature_config = {
            "thinking_enabled": True,
            "output_schema": "phase",
            "research_mode": "normal",
            "auto_thinking": True,
            "thinking_mode": "Auto",
            "thinking_format": "summary",
            "auto_search": False,
        }

        payload = {
            "stream": True,
            "version": "2.1",
            "incremental_output": True,
            "chat_id": chat_id,
            "chat_mode": "normal",
            "model": model_id,
            "parent_id": None,
            "messages": [
                {
                    "fid": fid,
                    "parentId": None,
                    "childrenIds": [child_id],
                    "role": "user",
                    "content": user_content,
                    "user_action": "chat",
                    "files": [],
                    "timestamp": ts,
                    "models": [model_id],
                    "chat_type": "t2t",
                    "feature_config": feature_config,
                    "extra": {"meta": {"subChatType": "t2t"}},
                    "sub_chat_type": "t2t",
                    "parent_id": None,
                },
            ],
            "timestamp": ts + 1,
        }

        url = f"{self.base_url}/api/v2/chat/completions?chat_id={chat_id}"
        session = AsyncSession(timeout=STREAM_TIMEOUT)
        collected_text = ""
        input_tokens = 0
        output_tokens = 0

        try:
            resp = await session.post(
                url,
                json=payload,
                headers={
                    **self._headers(chat_id),
                    "x-accel-buffering": "no",
                },
                stream=True,
            )
            if resp.status_code != 200:
                body = await resp.atext()
                raise QwenChatError(f"Chat completion failed ({resp.status_code}): {body[:300]}", status_code=502)

            async for line in resp.aiter_lines():
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                line = line.strip()
                if not line or not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue

                event_type = event.get("type") or event.get("event")
                if event_type == "phase" and event.get("phase") == "response":
                    content = event.get("content") or ""
                    if content:
                        delta = content[len(collected_text):] if content.startswith(collected_text) else content
                        if delta:
                            if on_delta:
                                on_delta(delta)
                            collected_text = content
                elif event_type == "phase" and event.get("phase") == "thinking":
                    pass
                elif event_type == "done":
                    usage = event.get("usage") or {}
                    content = event.get("content") or ""
                    if content and not collected_text:
                        collected_text = content
                    input_tokens = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
                    output_tokens = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0)

            return ChatResult(
                text=collected_text or None,
                chat_id=chat_id,
                model=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception as e:
            if not isinstance(e, QwenChatError):
                raise QwenChatError(f"Qwen transport error: {e}", status_code=502) from e
            raise
        finally:
            await session.close()
            asyncio.ensure_future(self._cleanup_chat(chat_id))

    async def _cleanup_chat(self, chat_id: str) -> None:
        try:
            await self._delete_chat(chat_id)
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
        chat_id = await self._create_chat(model_id)
        user_content = self._build_messages(messages)

        fid = self._uuid()
        child_id = self._uuid()
        ts = int(time.time())

        feature_config = {
            "thinking_enabled": True,
            "output_schema": "phase",
            "research_mode": "normal",
            "auto_thinking": True,
            "thinking_mode": "Auto",
            "thinking_format": "summary",
            "auto_search": False,
        }

        payload = {
            "stream": True,
            "version": "2.1",
            "incremental_output": True,
            "chat_id": chat_id,
            "chat_mode": "normal",
            "model": model_id,
            "parent_id": None,
            "messages": [
                {
                    "fid": fid,
                    "parentId": None,
                    "childrenIds": [child_id],
                    "role": "user",
                    "content": user_content,
                    "user_action": "chat",
                    "files": [],
                    "timestamp": ts,
                    "models": [model_id],
                    "chat_type": "t2t",
                    "feature_config": feature_config,
                    "extra": {"meta": {"subChatType": "t2t"}},
                    "sub_chat_type": "t2t",
                    "parent_id": None,
                },
            ],
            "timestamp": ts + 1,
        }

        url = f"{self.base_url}/api/v2/chat/completions?chat_id={chat_id}"
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
                    json=payload,
                    headers={
                        **self._headers(chat_id),
                        "x-accel-buffering": "no",
                    },
                    stream=True,
                )
                if resp.status_code != 200:
                    body = await resp.atext()
                    raise QwenChatError(f"Chat completion failed ({resp.status_code}): {body[:300]}", status_code=502)

                async for line in resp.aiter_lines():
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    line = line.strip()
                    if not line or not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue

                    event_type = event.get("type") or event.get("event")
                    if event_type == "phase" and event.get("phase") == "response":
                        content = event.get("content") or ""
                        if content:
                            delta = content[len(collected_text):] if content.startswith(collected_text) else content
                            if delta:
                                await queue.put(delta)
                                collected_text = content
                    elif event_type == "done":
                        usage = event.get("usage") or {}
                        content = event.get("content") or ""
                        if content and not collected_text:
                            collected_text = content
                        input_tokens = usage.get("input_tokens", 0) or usage.get("prompt_tokens", 0)
                        output_tokens = usage.get("output_tokens", 0) or usage.get("completion_tokens", 0)
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
                text=collected_text or None,
                chat_id=chat_id,
                model=model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        return consumer(), chat_id, finalize
