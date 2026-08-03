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

try:  # websockets is optional at import time; required only for streaming.
    import websockets

    _HAVE_WEBSOCKETS = True
except Exception:  # pragma: no cover
    websockets = None  # type: ignore[assignment]
    _HAVE_WEBSOCKETS = False

from boltchat.account import BoltAccount, cookie_header
from boltchat.exceptions import BoltChatError
from boltchat.models import resolve_model

log = logging.getLogger(__name__)

BOLT_BASE = "https://bolt.new"
DEFAULT_TIMEOUT = 300.0
STREAM_TIMEOUT = 60.0

# Bolt.new's AI backend is proprietary and its chat transport is Socket/WebSocket
# based (WebContainers style message framing), NOT a plain REST chat completions
# endpoint like Notion/Qwen. The exact message schema is not public and changes
# without notice. The classes below implement the *publicly documented* StackBlitz
# WebSocket relay framing and clearly mark the Bolt-specific message envelope that
# you must confirm against the live site (DevTools -> Network -> WS) before it will
# stream real answers.
WS_PROTOCOL = "webcontainers/1.0"


@dataclass(slots=True)
class ChatResult:
    text: str | None
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


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


class BoltChatClient:
    def __init__(
        self,
        account: BoltAccount,
        *,
        base_url: str = BOLT_BASE,
        ws_url: str = "wss://bolt.new/.well-known/ai/relay",
    ):
        self.account = account
        self.base_url = base_url.rstrip("/")
        self.ws_url = ws_url

    async def aclose(self) -> None:
        pass

    # --- auth headers -----------------------------------------------------
    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": self.base_url,
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
            ),
            "X-Request-Id": str(uuid.uuid4()),
        }
        if self.account.session_token:
            headers["Authorization"] = f"Bearer {self.account.session_token}"
        cookie = cookie_header(self.account)
        if cookie:
            headers["Cookie"] = cookie
        return headers

    def _ws_headers(self) -> dict[str, str]:
        # Cookies cannot be set as headers on a wss connection; websockets lib
        # applies them via additional_headers only when connecting with origin.
        headers: dict[str, str] = {"Origin": self.base_url}
        if self.account.session_token:
            headers["Authorization"] = f"Bearer {self.account.session_token}"
        cookie = cookie_header(self.account)
        if cookie:
            headers["Cookie"] = cookie
        return headers

    # --- Bolt-specific message envelope -----------------------------------
    # MARKED FOR REVIEW: Bolt's real chat frames are not public. This builds an
    # RPC-style request envelope over the relay. Confirm the actual channel /
    # method / payload shape from DevTools before relying on it.
    def _build_request_msg(self, prompt: str, *, model: str, request_id: str) -> dict[str, Any]:
        return {
            "id": request_id,
            "type": "bolt/chat/completions",
            "payload": {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": True,
            },
        }

    # --- HTTP validation path (non-streaming & /v1/models sanity) ---------
    async def _http_ping(self) -> str:
        """Best-effort REST health check for account validity."""
        url = f"{self.base_url}/api/v1/ping"
        session = AsyncSession(timeout=DEFAULT_TIMEOUT)
        try:
            resp = await session.get(url, headers=self._headers())
            return "ok" if resp.status_code < 500 else f"http {resp.status_code}"
        finally:
            await session.close()

    # --- streaming ---------------------------------------------------------
    async def stream_deltas(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
    ) -> tuple[AsyncIterator[str], str, Callable[[], ChatResult]]:
        if not _HAVE_WEBSOCKETS:
            raise BoltChatError(
                "Streaming requires the 'websockets' library. Install it with: "
                "pip install websockets",
                status_code=500,
            )

        model_id = resolve_model(model)
        prompt = "\n".join(_extract_text(m.get("content", "")) for m in messages if _extract_text(m.get("content", "")))
        if not prompt.strip():
            raise BoltChatError("No text content in messages", status_code=400)

        request_id = str(uuid.uuid4())
        collected_text = ""
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        ws_error: list[BaseException] = []

        async def producer() -> None:
            nonlocal collected_text
            try:
                async with websockets.connect(
                    self.ws_url,
                    additional_headers=self._ws_headers(),
                    subprotocols=[WS_PROTOCOL],
                    open_timeout=DEFAULT_TIMEOUT,
                    ping_interval=20,
                ) as ws:
                    await ws.send(json.dumps(self._build_request_msg(prompt, model=model_id, request_id=request_id)))
                    async for raw in ws:
                        if isinstance(raw, bytes):
                            raw = raw.decode("utf-8", errors="replace")
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        # REVIEW: adapt this switch to Bolt's real frame types.
                        frame_type = msg.get("type") or msg.get("event") or msg.get("msg")
                        if frame_type in ("done", "finish", "complete"):
                            break
                        content = msg.get("content") or msg.get("text") or (msg.get("payload") or {}).get("content")
                        if content:
                            delta = content[len(collected_text):] if content.startswith(collected_text) else content
                            if delta:
                                await queue.put(delta)
                                collected_text = content
            except BaseException as e:
                ws_error.append(e)
            finally:
                await queue.put(None)

        async def consumer() -> AsyncIterator[str]:
            task = asyncio.create_task(producer())
            try:
                while True:
                    chunk = await queue.get()
                    if chunk is None:
                        break
                    yield chunk
                if ws_error:
                    raise ws_error[0]
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
                model=model_id,
            )

        return consumer(), request_id, finalize

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
    ) -> ChatResult:
        stream, _, finalize = await self.stream_deltas(messages=messages, model=model)
        collected: list[str] = []
        async for delta in stream:
            collected.append(delta)
        result = finalize()
        result.text = ("".join(collected)) or result.text
        return result
