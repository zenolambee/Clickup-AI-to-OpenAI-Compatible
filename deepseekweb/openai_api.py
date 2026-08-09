from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from curl_cffi.requests import AsyncSession
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from deepseekweb.client import DeepSeekWebClient
from deepseekweb.config import Settings, load_accounts_from_env, load_settings
from deepseekweb.exceptions import DeepSeekWebError
from deepseekweb.models import (
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

    model: str = "deepseek-v4-flash"
    messages: list[ChatMessage]
    stream: bool = False
    user: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None


def _messages_to_datk(messages: list[ChatMessage]) -> str:
    parts: list[str] = []
    for m in messages:
        content = m.content
        if isinstance(content, list):
            texts = [str(i.get("text", "")) for i in content if isinstance(i, dict)]
            content = "\n".join(texts)
        if content:
            parts.append(f"{m.role}: {content}")
    return "\n".join(parts)


def _chunk(*, completion_id: str, created: int, model: str, delta: dict[str, Any], finish_reason: str | None = None) -> str:
    payload = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream_openai(
    client: DeepSeekWebClient,
    req: ChatCompletionRequest,
    model: str,
) -> AsyncIterator[str]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    prompt = _messages_to_datk(req.messages)

    session = AsyncSession(timeout=600.0, impersonate="chrome120")
    try:
        try:
            async for evt in client.complete_stream(prompt=prompt, model=model, session=session):
                if evt["type"] == "thinking":
                    continue
                yield _chunk(completion_id=completion_id, created=created, model=model, delta={"content": evt["content"]})
            yield _chunk(completion_id=completion_id, created=created, model=model, delta={}, finish_reason="stop")
            yield "data: [DONE]\n\n"
        except DeepSeekWebError as e:
            err = {"error": {"message": str(e), "type": "deepseek_error", "code": e.status_code}}
            yield f"data: {json.dumps(err)}\n\n"
    finally:
        await session.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="DeepSeekWeb", version="0.1.0")
    app.state.settings = settings
    app.state.accounts_index = 0
    app.state.accounts_lock = threading.Lock()

    def verify_key(authorization: str | None = Header(default=None)) -> None:
        if not settings.api_key:
            return
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        token = authorization.removeprefix("Bearer ").strip()
        if token != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

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
        model = resolve_model(req.model)
        try:
            accounts = load_accounts_from_env(settings)
            if not accounts:
                raise DeepSeekWebError("No DeepSeek web account configured.", status_code=500)
            with app.state.accounts_lock:
                account = accounts[app.state.accounts_index % len(accounts)]
                app.state.accounts_index += 1
            client = DeepSeekWebClient(account, base_url=settings.base_url)
            log.info("chat stream=%s model=%s resolved=%s msgs=%d account=%s", req.stream, req.model, model, len(req.messages), account.user_token[:10])
            if req.stream:
                return StreamingResponse(
                    _stream_openai(client, req, model),
                    media_type="text/event-stream",
                )
            completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
            created = int(time.time())
            prompt = _messages_to_datk(req.messages)
            text = []
            async with AsyncSession(timeout=600, impersonate="chrome120") as session:
                async for evt in client.complete_stream(prompt=prompt, model=model, session=session):
                    if evt["type"] == "content":
                        text.append(evt["content"])
            return {
                "id": completion_id,
                "object": "chat.completion",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "".join(text)}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }
        except DeepSeekWebError as e:
            raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    return app