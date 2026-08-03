from __future__ import annotations

import asyncio
import json
import logging
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from curl_cffi.requests import AsyncSession

from geminichat.account import GeminiAccount, cookie_header
from geminichat.exceptions import GeminiChatError
from geminichat.models import resolve_model

log = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 300.0
STREAM_TIMEOUT = 120.0


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


class GeminiChatClient:
    def __init__(
        self,
        account: GeminiAccount,
        *,
        base_url: str = "https://aistudio.google.com",
        api_base_url: str = "https://generativelanguage.googleapis.com",
    ):
        self.account = account
        self.base_url = base_url.rstrip("/")
        self.api_base_url = api_base_url.rstrip("/")

    async def aclose(self) -> None:
        pass

    def _headers(self, *, accept_json: bool = True) -> dict[str, str]:
        headers = {
            "Accept": "application/json" if accept_json else "text/event-stream",
            "Content-Type": "application/json",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
            ),
            "X-Goog-Api-Client": f"genai-js/{secrets.token_hex(4)}",
        }
        if self.account.sapisid:
            # REVIEW: the Authorization signature Google's front end sends is derived
            # from SAPISID + timestamp + origin. This placeholder may be rejected;
            # capture the exact header in DevTools (Network -> the generateContent
            # request -> request headers) and mirror it here.
            headers["Authorization"] = f"SAPISIDHASH {self.account.sapisid}"
        cookie = cookie_header(self.account)
        if cookie:
            headers["Cookie"] = cookie
        return headers

    def _build_contents(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        contents: list[dict[str, Any]] = []
        for smsg in messages:
            role = smsg.get("role", "user")
            text = _extract_text(smsg.get("content", ""))
            if not text:
                continue
            gemini_role = "model" if role in ("assistant", "model") else "user"
            contents.append(
                {"role": gemini_role, "parts": [{"text": text}]}
            )
        return contents

    async def _health_check(self) -> str:
        try:
            url = f"{self.base_url}/api/health"
            session = AsyncSession(timeout=30)
            try:
                resp = await session.get(url, headers=self._headers())
                return "ok" if resp.status_code < 500 else f"http {resp.status_code}"
            finally:
                await session.close()
        except Exception as e:  # pragma: no cover
            return f"err {e}"

    async def complete(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
        stream: bool = True,
        on_delta: Callable[[str], None] | None = None,
    ) -> ChatResult:
        model_id = resolve_model(model)
        contents = self._build_contents(messages)
        if not contents:
            raise GeminiChatError("No text content in messages", status_code=400)

        payload: dict[str, Any] = {
            "contents": contents,
        }
        url = f"{self.api_base_url}/v1beta/models/{model_id}:streamGenerateContent"

        session = AsyncSession(timeout=STREAM_TIMEOUT)
        collected_text = ""
        input_tokens = 0
        output_tokens = 0

        try:
            resp = await session.post(
                url,
                json=payload,
                headers=self._headers(accept_json=False),
                stream=True,
            )
            if resp.status_code != 200:
                body = await resp.atext()
                raise GeminiChatError(
                    f"Gemini request failed ({resp.status_code}): {body[:300]}",
                    status_code=502,
                )

            # Google returns a stream of plain JSON objects (one per line), not
            # "data: " prefixed SSE. REVIEW: confirm the exact framing from
            # DevTools if nothing is parsed.
            async for line in resp.aiter_lines():
                if isinstance(line, bytes):
                    line = line.decode("utf-8", errors="replace")
                line = line.strip()
                if not line or line.startswith("data:"):
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                text = self._candidate_text(obj)
                if text:
                    delta = text[len(collected_text):] if text.startswith(collected_text) else text
                    if delta:
                        if on_delta:
                            on_delta(delta)
                        collected_text = text
                u = self._usage(obj)
                input_tokens = u[0] or input_tokens
                output_tokens = u[1] or output_tokens

            return ChatResult(
                text=collected_text or None,
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

    @staticmethod
    def _candidate_text(obj: dict[str, Any]) -> str:
        parts = []
        for cand in obj.get("candidates") or []:
            for part in (cand.get("content") or {}).get("parts") or []:
                if "text" in part:
                    parts.append(part["text"])
        return "".join(parts)

    @staticmethod
    def _usage(obj: dict[str, Any]) -> tuple[int, int]:
        meta = obj.get("usageMetadata") or {}
        return (
            int(meta.get("promptTokenCount") or 0),
            int(meta.get("candidatesTokenCount") or 0),
        )

    async def stream_deltas(
        self,
        *,
        messages: list[dict[str, Any]],
        model: str | None = None,
    ) -> tuple[AsyncIterator[str], str, Callable[[], ChatResult]]:
        model_id = resolve_model(model)
        contents = self._build_contents(messages)
        if not contents:
            raise GeminiChatError("No text content in messages", status_code=400)

        payload: dict[str, Any] = {"contents": contents}
        url = f"{self.api_base_url}/v1beta/models/{model_id}:streamGenerateContent"

        collected_text = ""
        input_tokens = 0
        output_tokens = 0
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        errors: list[BaseException] = []

        async def producer() -> None:
            nonlocal collected_text, input_tokens, output_tokens
            session = AsyncSession(timeout=STREAM_TIMEOUT)
            try:
                resp = await session.post(
                    url,
                    json=payload,
                    headers=self._headers(accept_json=False),
                    stream=True,
                )
                if resp.status_code != 200:
                    body = await resp.atext()
                    raise GeminiChatError(
                        f"Gemini request failed ({resp.status_code}): {body[:300]}",
                        status_code=502,
                    )
                async for line in resp.aiter_lines():
                    if isinstance(line, bytes):
                        line = line.decode("utf-8", errors="replace")
                    line = line.strip()
                    if not line or line.startswith("data:"):
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    text = self._candidate_text(obj)
                    if text:
                        delta = text[len(collected_text):] if text.startswith(collected_text) else text
                        if delta:
                            await queue.put(delta)
                            collected_text = text
                    u = self._usage(obj)
                    input_tokens = u[0] or input_tokens
                    output_tokens = u[1] or output_tokens
            except BaseException as e:
                errors.append(e)
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
                if errors:
                    raise errors[0]
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
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

        return consumer(), model_id, finalize


async def _sanity() -> None:  # pragma: no cover
    """Simple smoke test used by the CLI --test flag."""
    ...
