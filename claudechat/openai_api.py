from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from claudechat.client import ChatResult, ClaudeChatClient
from claudechat.config import Settings, load_accounts_from_env, load_settings
from claudechat.exceptions import ClaudeChatError
from claudechat.models import (
    cache_openai_models,
    get_cached_openai_models,
    list_openai_models,
    resolve_model,
)

log = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str
    content: str | list[Any] | None = None


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str = "claude-sonnet-4-20250514"
    messages: list[ChatMessage]
    stream: bool = False
    user: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


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


def _messages_to_dicts(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    return [{"role": m.role, "content": m.content} for m in messages]


def _usage(result: ChatResult) -> dict[str, int]:
    return {
        "prompt_tokens": result.input_tokens,
        "completion_tokens": result.output_tokens,
        "total_tokens": result.input_tokens + result.output_tokens,
    }


def _assistant_message(result: ChatResult) -> dict[str, Any]:
    return {"role": "assistant", "content": result.text or ""}


async def _stream_openai(
    client: ClaudeChatClient,
    req: ChatCompletionRequest,
    settings: Settings,
) -> AsyncIterator[str]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    model = resolve_model(req.model)

    try:
        stream, conv_id, finalize = await client.stream_deltas(
            messages=_messages_to_dicts(req.messages),
            model=req.model,
            temperature=req.temperature,
        )

        async for piece in stream:
            yield _chunk(
                completion_id=completion_id,
                created=created,
                model=model,
                delta={"content": piece},
            )

        result = finalize()

        yield _chunk(
            completion_id=completion_id,
            created=created,
            model=model,
            delta={},
            finish_reason="stop",
        )
        yield "data: [DONE]\n\n"
    except ClaudeChatError as e:
        err = {"error": {"message": str(e), "type": "claude_error", "code": e.status_code}}
        yield f"data: {json.dumps(err)}\n\n"


async def _ensure_models(client: ClaudeChatClient) -> None:
    if get_cached_openai_models() is not None:
        return
    cache_openai_models(list_openai_models())


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="ClaudeChat", version="0.1.0")
    app.state.settings = settings

    def verify_key(authorization: str | None = Header(default=None)) -> None:
        if not settings.api_key:
            return
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        token = authorization.removeprefix("Bearer ").strip()
        if token != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

    def get_client() -> ClaudeChatClient:
        accounts = load_accounts_from_env(settings)
        log.info("Loaded %d Claude account(s) (round-robin)", len(accounts))
        return ClaudeChatClient(accounts, base_url=settings.base_url)

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/models")
    async def list_models(_: None = Depends(verify_key)) -> dict[str, Any]:
        cached = get_cached_openai_models()
        if cached is not None:
            return {"object": "list", "data": cached}
        models = list_openai_models()
        cache_openai_models(models)
        return {"object": "list", "data": models}

    @app.post("/v1/chat/completions")
    async def chat_completions(
        req: ChatCompletionRequest,
        _: None = Depends(verify_key),
    ) -> Any:
        try:
            client = get_client()
            try:
                await _ensure_models(client)
                log.info(
                    "chat stream=%s model=%s resolved=%s msgs=%d accounts=%d",
                    req.stream,
                    req.model,
                    resolve_model(req.model),
                    len(req.messages),
                    len(client.pool),
                )

                if req.stream:
                    return StreamingResponse(
                        _stream_openai(client, req, settings),
                        media_type="text/event-stream",
                    )

                result = await client.complete(
                    messages=_messages_to_dicts(req.messages),
                    model=req.model,
                    stream=False,
                    temperature=req.temperature,
                )
                log.info("chat result text_len=%s", len(result.text or ""))

                completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
                return {
                    "id": completion_id,
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": resolve_model(req.model),
                    "choices": [
                        {
                            "index": 0,
                            "message": _assistant_message(result),
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": _usage(result),
                }
            finally:
                await client.aclose()
        except ClaudeChatError as e:
            if e.status_code == 403:
                log.warning("chat/completions 403: %s", e)
            raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    return app
