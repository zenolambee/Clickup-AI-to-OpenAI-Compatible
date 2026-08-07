from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from arenachat.client import ArenaChatClient, ChatResult
from arenachat.config import Settings, load_account_from_env, load_settings
from arenachat.exceptions import ArenaChatError
from arenachat.models import (
    cache_openai_models,
    get_cached_openai_models,
    list_openai_models,
)

log = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str
    content: str | list[Any] | None = None


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str = "gpt-4o"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


def _build_prompt(messages: list[ChatMessage]) -> tuple[str | None, str]:
    system: str | None = None
    parts: list[str] = []
    for msg in messages:
        if msg.role == "system":
            system = msg.content if isinstance(msg.content, str) else str(msg.content or "")
        elif msg.role == "user":
            content = msg.content if isinstance(msg.content, str) else str(msg.content or "")
            parts.append(f"User: {content}")
        elif msg.role == "assistant":
            content = msg.content if isinstance(msg.content, str) else str(msg.content or "")
            parts.append(f"Assistant: {content}")
    prompt = "\n".join(parts) if parts else ""
    return system, prompt


def _chunk(
    *,
    completion_id: str,
    created: int,
    model: str,
    delta: dict[str, Any],
    finish_reason: str | None = None,
) -> str:
    payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_openai(
    client: ArenaChatClient,
    req: ChatCompletionRequest,
    system: str | None,
    prompt: str,
) -> AsyncIterator[str]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    try:
        result = await client.complete(
            prompt=prompt,
            system=system,
            model=req.model,
            stream=True,
        )
        text = result.text or ""
        step = max(1, len(text) // 4)
        for pos in range(0, len(text), step):
            yield _chunk(
                completion_id=completion_id,
                created=created,
                model=req.model,
                delta={"content": text[pos : pos + step]},
            )
        yield _chunk(
            completion_id=completion_id,
            created=created,
            model=req.model,
            delta={},
            finish_reason="stop",
        )
        yield "data: [DONE]\n\n"
    except ArenaChatError as e:
        err = {"error": {"message": str(e), "type": "arena_error", "code": e.status_code}}
        yield f"data: {json.dumps(err)}\n\n"
    finally:
        await client.aclose()


async def _ensure_model_aliases(client: ArenaChatClient, settings: Settings) -> None:
    if get_cached_openai_models() is not None:
        return
    try:
        raw = await client.fetch_available_models()
        if raw:
            cache_openai_models(raw)
            log.info("Prefetched %d Arena models", len(raw))
    except ArenaChatError as e:
        log.warning("Could not prefetch Arena models: %s", e)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="ArenaChat", version="0.1.0")
    app.state.settings = settings

    def verify_key(authorization: str | None = Header(default=None)) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        token = authorization.removeprefix("Bearer ").strip()
        if token != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

    def get_client() -> ArenaChatClient:
        account = load_account_from_env(settings)
        return ArenaChatClient(account, base_url=settings.base_url)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/models")
    async def list_models(_: None = Depends(verify_key)) -> dict[str, Any]:
        cached = get_cached_openai_models()
        if cached is not None:
            return {"object": "list", "data": cached}

        client = get_client()
        try:
            raw = await client.fetch_available_models()
            if raw:
                cache_openai_models(raw)
                return {"object": "list", "data": raw}
        except ArenaChatError as e:
            log.warning("fetchAvailableModels failed: %s", e)
        finally:
            await client.aclose()

        return {"object": "list", "data": list_openai_models()}

    @app.post("/v1/chat/completions")
    async def chat_completions(
        req: ChatCompletionRequest,
        _: None = Depends(verify_key),
    ) -> Any:
        try:
            system, prompt = _build_prompt(req.messages)
            if not prompt.strip():
                raise HTTPException(status_code=400, detail="No user message found")

            client = get_client()
            try:
                await _ensure_model_aliases(client, settings)

                log.info(
                    "chat stream=%s model=%s msgs=%d",
                    req.stream,
                    req.model,
                    len(req.messages),
                )

                if req.stream:
                    return StreamingResponse(
                        _stream_openai(client, req, system, prompt),
                        media_type="text/event-stream",
                    )

                result = await client.complete(
                    prompt=prompt,
                    system=system,
                    model=req.model,
                    stream=False,
                )

                completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
                return {
                    "id": completion_id,
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": req.model,
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": result.text or "",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": result.input_tokens,
                        "completion_tokens": result.output_tokens,
                        "total_tokens": result.input_tokens + result.output_tokens,
                    },
                }
            finally:
                await client.aclose()
        except ArenaChatError as e:
            raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    return app
