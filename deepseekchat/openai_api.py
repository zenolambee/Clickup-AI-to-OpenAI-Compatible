from __future__ import annotations

import logging
import threading
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from deepseekchat.client import DeepSeekChatClient
from deepseekchat.config import Settings, load_settings, require_deepseek_key_list
from deepseekchat.exceptions import DeepSeekChatError
from deepseekchat.models import (
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


def _messages_to_dicts(messages: list[ChatMessage]) -> list[dict[str, Any]]:
    return [{"role": m.role, "content": m.content} for m in messages]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="DeepSeekChat", version="0.1.0")
    app.state.settings = settings
    app.state.keys_index = 0
    app.state.keys_lock = threading.Lock()

    def verify_key(authorization: str | None = Header(default=None)) -> None:
        if not settings.api_key:
            return
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        token = authorization.removeprefix("Bearer ").strip()
        if token != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

    def get_client() -> DeepSeekChatClient:
        keys = require_deepseek_key_list(settings)
        with app.state.keys_lock:
            api_key = keys[app.state.keys_index % len(keys)]
            app.state.keys_index += 1
            log.info("using deepseek key %s", api_key[:8] + "...")
        return DeepSeekChatClient(api_key=api_key, base_url=settings.base_url)

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
        client = None
        try:
            client = get_client()
            log.info("chat stream=%s model=%s resolved=%s msgs=%d", req.stream, req.model, model, len(req.messages))
            body, stream = await client.complete(
                messages=_messages_to_dicts(req.messages),
                model=model,
                stream=req.stream,
            )
            if req.stream:
                return StreamingResponse(stream, media_type="text/event-stream")
            return body
        except DeepSeekChatError as e:
            raise HTTPException(status_code=e.status_code, detail=str(e)) from e
        finally:
            if client is not None and not req.stream:
                await client.aclose()

    return app