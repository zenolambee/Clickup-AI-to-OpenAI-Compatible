from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from curl_cffi.requests import AsyncSession

from deepseekweb.account import DeepSeekWebAccount, build_headers
from deepseekweb.exceptions import DeepSeekWebError
from deepseekweb.pow import DeepSeekPOW, has_pow_libs

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 600.0


class DeepSeekWebClient:
    def __init__(self, account: DeepSeekWebAccount, *, base_url: str = "https://chat.deepseek.com/api/v0"):
        self.account = account
        self.base_url = base_url.rstrip("/")
        self.chat_session_id: str | None = None
        self.parent_message_id: str | None = None

    async def aclose(self) -> None:
        pass

    async def _create_session(self, session: AsyncSession) -> str:
        url = f"{self.base_url}/chat_session/create"
        headers = build_headers(self.account)
        resp = await session.post(url, headers=headers, json={"character_id": None})
        if resp.status_code >= 400:
            raise DeepSeekWebError(f"Create session failed ({resp.status_code}): {resp.text[:300]}", status_code=502)
        biz = (resp.json().get("data") or {}).get("biz_data", {})
        sid = biz.get("id") or (biz.get("chat_session") or {}).get("id")
        if not sid:
            raise DeepSeekWebError(f"No session id in response: {resp.text[:300]}", status_code=502)
        return sid

    async def _solve_pow(self, session: AsyncSession, target_path: str) -> str | None:
        if not has_pow_libs():
            log.warning("POW libs missing (wasmtime, numpy); request may be rejected.")
            return None
        try:
            url = f"{self.base_url}/chat/create_pow_challenge"
            headers = build_headers(self.account)
            resp = await session.post(url, headers=headers, json={"target_path": target_path})
            if resp.status_code != 200:
                return None
            challenge = (resp.json().get("data") or {}).get("biz_data", {}).get("challenge")
            if not challenge:
                return None
            return await asyncio.to_thread(DeepSeekPOW().solve_challenge, challenge)
        except Exception as e:  # noqa: BLE001
            log.warning("POW solve failed: %s", e)
            return None

    async def complete_stream(
        self,
        *,
        prompt: str,
        model: str,
        session: AsyncSession,
    ) -> AsyncIterator[dict[str, Any]]:
        if not self.chat_session_id:
            self.chat_session_id = await self._create_session(session)

        if self.parent_message_id is None:
            parent = None
        else:
            parent = self.parent_message_id

        url = f"{self.base_url}/chat/completion"
        headers = build_headers(self.account)
        pow_resp = await self._solve_pow(session, "/api/v0/chat/completion")
        if pow_resp:
            headers["x-ds-pow-response"] = pow_resp

        payload = {
            "chat_session_id": self.chat_session_id,
            "parent_message_id": parent,
            "prompt": prompt,
            "ref_file_ids": [],
            "thinking_enabled": model == "deepseek-v4-pro",
            "search_enabled": False,
            "action": None,
            "preempt": False,
            "model_type": "expert" if model == "deepseek-v4-pro" else "default",
        }

        resp = await session.post(url, headers=headers, json=payload, stream=True)
        if resp.status_code >= 400:
            raise DeepSeekWebError(f"Completion failed ({resp.status_code}): {resp.text[:300]}", status_code=502)
        if "text/event-stream" not in resp.headers.get("Content-Type", ""):
            body = await resp.atext()
            raise DeepSeekWebError(f"Unexpected content type: {resp.headers.get('Content-Type')} {body[:300]}", status_code=502)

        current_fragment_type = "RESPONSE"
        async for line in resp.aiter_lines():
            line = line.decode("utf-8", errors="replace") if isinstance(line, bytes) else line
            stripped = line.strip()
            if not stripped.startswith("data: ") or stripped == "data: [DONE]":
                continue
            raw = stripped[6:].strip()
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if "response_message_id" in data:
                self.parent_message_id = data["response_message_id"]
            elif data.get("v") and isinstance(data["v"], dict) and "response" in data["v"]:
                self.parent_message_id = data["v"]["response"].get("message_id", self.parent_message_id)

            if "choices" in data:
                choices = data.get("choices") or []
                if choices:
                    delta = choices[0].get("delta", {})
                    if delta.get("reasoning_content"):
                        yield {"type": "thinking", "content": delta["reasoning_content"]}
                    if delta.get("content"):
                        yield {"type": "content", "content": delta["content"]}
            elif "v" in data:
                val = data["v"]
                if isinstance(val, dict) and "response" in val:
                    fragments = val["response"].get("fragments", [])
                    if fragments:
                        current_fragment_type = fragments[0].get("type", "RESPONSE")
                        frag_content = fragments[0].get("content", "")
                        if frag_content:
                            key = "thinking" if current_fragment_type == "THINK" else "content"
                            yield {"type": key, "content": frag_content}
                elif isinstance(val, list) and data.get("p") == "response/fragments":
                    for frag in val:
                        if isinstance(frag, dict):
                            ftype = frag.get("type", "RESPONSE")
                            current_fragment_type = ftype
                            frag_content = frag.get("content", "")
                            if frag_content:
                                key = "thinking" if ftype == "THINK" else "content"
                                yield {"type": key, "content": frag_content}
                elif isinstance(val, str):
                    if data.get("p") == "response/status":
                        continue
                    key = "thinking" if current_fragment_type == "THINK" else "content"
                    if val:
                        yield {"type": key, "content": val}