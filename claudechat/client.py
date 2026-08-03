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

from claudechat.account import ClaudeAccount, build_headers
from claudechat.exceptions import ClaudeChatError
from claudechat.models import resolve_model

log = logging.getLogger(__name__)

CLAUDE_BASE = "https://claude.ai"
DEFAULT_TIMEOUT = 300.0
STREAM_TIMEOUT = 120.0


@dataclass(slots=True)
class ChatResult:
    text: str | None
    conversation_id: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class AccountPool:
    def __init__(self, accounts: list[ClaudeAccount]):
        if not accounts:
            raise ClaudeChatError("No accounts in pool", status_code=500)
        self.accounts = accounts
        self._index = 0

    def next(self) -> ClaudeAccount:
        acc = self.accounts[self._index]
        self._index = (self._index + 1) % len(self.accounts)
        return acc

    def __len__(self) -> int:
        return len(self.accounts)


class ClaudeChatClient:
    def __init__(self, accounts: list[ClaudeAccount], *, base_url: str = CLAUDE_BASE):
        self.pool = AccountPool(accounts)
        self.base_url = base_url.rstrip("/")

    async def aclose(self) -> None:
        pass

    def _uuid(self) -> str:
        u = uuid.uuid4()
        s = str(u)
        return f"{s[0:8]}-{s[9:13]}-{s[14:18]}-{s[19:23]}-{s[24:]}"

    async def _get_organization_id(self, acc: ClaudeAccount) -> str:
        if acc.organization_id:
            return acc.organization_id
        url = f"{self.base_url}/api/organizations"
        headers = build_headers(acc.cookie)
        session = AsyncSession(timeout=DEFAULT_TIMEOUT, impersonate="chrome110")
        try:
            resp = await session.get(url, headers=headers)
            if resp.status_code != 200:
                raise ClaudeChatError(f"Failed to get org ID ({resp.status_code})", status_code=502)
            data = resp.json()
            return data[0].get("uuid") or data[0].get("id", "")
        finally:
            await session.close()

    async def _create_conversation(self, acc: ClaudeAccount, org_id: str) -> str:
        url = f"{self.base_url}/api/organizations/{org_id}/chat_conversations"
        conv_uuid = self._uuid()
        payload = json.dumps({"uuid": conv_uuid, "name": ""})
        headers = build_headers(acc.cookie)
        session = AsyncSession(timeout=DEFAULT_TIMEOUT, impersonate="chrome110")
        try:
            resp = await session.post(url, headers=headers, data=payload)
            if resp.status_code != 200:
                text = await resp.atext()
                raise ClaudeChatError(f"Create conversation failed ({resp.status_code}): {text[:200]}", status_code=502)
            data = resp.json()
            return data.get("uuid") or data.get("id") or conv_uuid
        finally:
            await session.close()

    async def _delete_conversation(self, acc: ClaudeAccount, conv_id: str) -> None:
        org_id = await self._get_organization_id(acc)
        url = f"{self.base_url}/api/organizations/{org_id}/chat_conversations/{conv_id}"
        headers = build_headers(acc.cookie)
        session = AsyncSession(timeout=DEFAULT_TIMEOUT, impersonate="chrome110")
        try:
            await session.delete(url, headers=headers, data=json.dumps(conv_id))
        except Exception:
            pass
        finally:
            await session.close()

    def _build_messages(self, messages: list[dict[str, Any]]) -> str:
        system_parts: list[str] = []
        conversation: list[dict[str, str]] = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                texts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        texts.append(str(item.get("text", "")))
                content = "\n".join(texts)
            if not content:
                continue
            if role == "system":
                system_parts.append(content)
            else:
                conversation.append({"role": role, "content": str(content)})
        result = ""
        if system_parts:
            result = "System: " + "\n".join(system_parts) + "\n\n"
        for msg in conversation:
            if msg["role"] == "user":
                result += f"Human: {msg['content']}\n\n"
            else:
                result += f"Assistant: {msg['content']}\n\n"
        return result.strip()

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
        acc = self.pool.next()
        org_id = await self._get_organization_id(acc)
        conv_id = await self._create_conversation(acc, org_id)
        prompt = self._build_messages(messages)

        payload = json.dumps({
            "completion": {
                "prompt": prompt,
                "timezone": "Asia/Kolkata",
                "model": model_id,
            },
            "organization_uuid": org_id,
            "conversation_uuid": conv_id,
            "text": prompt,
            "attachments": [],
        })

        headers = build_headers(acc.cookie)
        url = f"{self.base_url}/api/append_message"
        session = AsyncSession(timeout=STREAM_TIMEOUT, impersonate="chrome110")
        collected_text = ""

        try:
            resp = await session.post(url, headers=headers, data=payload)
            if resp.status_code != 200:
                body = await resp.atext()
                raise ClaudeChatError(f"Chat completion failed ({resp.status_code}): {body[:300]}", status_code=502)

            decoded = (await resp.atext()).strip()
            decoded = re.sub(r'\n+', '\n', decoded)
            completions = []
            for line in decoded.split('\n'):
                line = line.strip()
                if not line.startswith("data: "):
                    continue
                try:
                    event = json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
                if "completion" in event:
                    completions.append(event["completion"])

            collected_text = "".join(completions)

            return ChatResult(
                text=collected_text or None,
                conversation_id=conv_id,
                model=model_id,
            )
        except Exception as e:
            if not isinstance(e, ClaudeChatError):
                raise ClaudeChatError(f"Claude transport error: {e}", status_code=502) from e
            raise
        finally:
            await session.close()
            asyncio.ensure_future(self._delete_conversation(acc, conv_id))

    async def stream_deltas(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
        temperature: float | None = None,
    ) -> tuple[AsyncIterator[str], str, Callable[[], ChatResult]]:
        model_id = resolve_model(model)
        acc = self.pool.next()
        org_id = await self._get_organization_id(acc)
        conv_id = await self._create_conversation(acc, org_id)
        prompt = self._build_messages(messages)

        url = f"{self.base_url}/api/append_message"
        headers = build_headers(acc.cookie)
        collected_text = ""
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        http_error: list[BaseException] = []

        async def producer() -> None:
            nonlocal collected_text
            session = AsyncSession(timeout=STREAM_TIMEOUT, impersonate="chrome110")
            try:
                payload = json.dumps({
                    "completion": {
                        "prompt": prompt,
                        "timezone": "Asia/Kolkata",
                        "model": model_id,
                    },
                    "organization_uuid": org_id,
                    "conversation_uuid": conv_id,
                    "text": prompt,
                    "attachments": [],
                })
                resp = await session.post(url, headers=headers, data=payload)
                if resp.status_code != 200:
                    body = await resp.atext()
                    raise ClaudeChatError(f"Chat completion failed ({resp.status_code}): {body[:300]}", status_code=502)

                async for raw_line in resp.aiter_lines():
                    if isinstance(raw_line, bytes):
                        raw_line = raw_line.decode("utf-8", errors="replace")
                    line = raw_line.strip()
                    if not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    completion = event.get("completion", "")
                    if completion:
                        delta = completion[len(collected_text):] if completion.startswith(collected_text) else completion
                        if delta:
                            await queue.put(delta)
                            collected_text = completion
            except BaseException as e:
                http_error.append(e)
            finally:
                await queue.put(None)
                await session.close()
                asyncio.ensure_future(self._delete_conversation(acc, conv_id))

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
                conversation_id=conv_id,
                model=model_id,
            )

        return consumer(), conv_id, finalize
