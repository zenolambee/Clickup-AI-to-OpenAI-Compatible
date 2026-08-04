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

from higgsfieldchat.client import ChatResult, HiggsfieldClient
from higgsfieldchat.config import Settings, load_account_from_env, load_settings
from higgsfieldchat.exceptions import HiggsfieldChatError
from higgsfieldchat.models import (
    cache_openai_models,
    get_cached_alias_map,
    get_cached_openai_models,
    list_openai_models,
    normalize_request_model,
    resolve_model,
)

log = logging.getLogger(__name__)

_session_threads: dict[str, str] = {}


class FunctionDetails(BaseModel):
    name: str
    arguments: str = "{}"


class ToolCallPart(BaseModel):
    id: str
    type: str = "function"
    function: FunctionDetails


class ToolFunctionSchema(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    description: str | None = None
    parameters: dict[str, Any] | None = None


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: str = "function"
    function: ToolFunctionSchema


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str
    content: str | list[Any] | None = None
    tool_calls: list[ToolCallPart] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str = "supercomputer"
    messages: list[ChatMessage]
    stream: bool = False
    user: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    tools: list[Any] | None = None
    tool_choice: str | dict[str, Any] | None = None
    parallel_tool_calls: bool | None = True


def _resolved_request_model(req: ChatCompletionRequest, settings: Settings) -> str:
    return resolve_model(
        normalize_request_model(req.model) or settings.default_model,
        default=settings.default_model,
        alias_map=get_cached_alias_map(),
    )


def _resolve_thread_id(req: ChatCompletionRequest, settings: Settings) -> str | None:
    if not req.user:
        return None
    return _session_threads.get(req.user)


def _remember_thread(req: ChatCompletionRequest, thread_id: str, settings: Settings) -> None:
    if req.user:
        _session_threads[req.user] = thread_id


def _prepare_messages(messages: list[ChatMessage], tools: list[Any] | None = None) -> tuple[str | None, str, bool]:
    system_parts: list[str] = []
    user_parts: list[str] = []
    has_tools = False

    for msg in messages:
        role = msg.role
        content = msg.content
        if isinstance(content, list):
            text_parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    if item.get("type") == "text":
                        text_parts.append(str(item.get("text", "")))
                elif isinstance(item, str):
                    text_parts.append(item)
            content = "\n".join(text_parts)
        elif not isinstance(content, str):
            content = str(content) if content else ""

        if msg.tool_calls:
            has_tools = True

        if role == "system":
            system_parts.append(content or "")
        elif role == "user":
            user_parts.append(content or "")
        elif role == "assistant":
            if content:
                user_parts.append(content)
        elif role == "tool":
            if content:
                user_parts.append(f"[Tool result: {content}]")

    prompt = "\n".join(user_parts) if user_parts else ""
    system = "\n".join(system_parts) if system_parts else None
    tools_active = has_tools or bool(tools)

    return system, prompt, tools_active


def _assistant_message(result: ChatResult) -> dict[str, Any]:
    msg: dict[str, Any] = {"role": "assistant"}
    if result.tool_calls:
        msg["content"] = result.text
        msg["tool_calls"] = result.tool_calls
    else:
        msg["content"] = result.text or ""
    return msg


def _usage(result: ChatResult) -> dict[str, int]:
    return {
        "prompt_tokens": result.input_tokens,
        "completion_tokens": result.output_tokens,
        "total_tokens": result.input_tokens + result.output_tokens,
    }


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
    client: HiggsfieldClient,
    req: ChatCompletionRequest,
    system: str | None,
    prompt: str,
    thread_id: str | None,
    settings: Settings,
    *,
    tools_active: bool,
) -> AsyncIterator[str]:
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    try:
        deltas, active_thread_id, finalize = await client.stream_deltas(
            prompt=prompt,
            system=system,
            model=req.model,
            thread_id=thread_id,
            tools_active=tools_active,
            client_tools=req.tools,
        )

        async for piece in deltas:
            yield _chunk(
                completion_id=completion_id,
                created=created,
                model=req.model,
                delta={"content": piece},
            )

        result = finalize()
        _remember_thread(req, result.thread_id, settings)

        finish_reason = "stop"
        yield _chunk(
            completion_id=completion_id,
            created=created,
            model=req.model,
            delta={},
            finish_reason=finish_reason,
        )

        yield "data: [DONE]\n\n"
    except HiggsfieldChatError as e:
        err = {"error": {"message": str(e), "type": "higgsfield_error", "code": e.status_code}}
        yield f"data: {json.dumps(err)}\n\n"
    finally:
        await client.aclose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    app = FastAPI(title="HiggsfieldChat", version="0.1.0")
    app.state.settings = settings

    def verify_key(authorization: str | None = Header(default=None)) -> None:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing Bearer token")
        token = authorization.removeprefix("Bearer ").strip()
        if token != settings.api_key:
            raise HTTPException(status_code=401, detail="Invalid API key")

    def get_client() -> HiggsfieldClient:
        account = load_account_from_env(settings)
        return HiggsfieldClient(
            account,
            base_url=settings.base_url,
            sc_base_url=settings.sc_base_url,
        )

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/models")
    async def list_models(_: None = Depends(verify_key)) -> dict[str, Any]:
        cached = get_cached_openai_models()
        if cached is not None:
            return {"object": "list", "data": cached}
        data = list_openai_models(settings.default_model)
        cache_openai_models(data)
        return {"object": "list", "data": data}

    @app.post("/v1/chat/completions")
    async def chat_completions(
        req: ChatCompletionRequest,
        _: None = Depends(verify_key),
    ) -> Any:
        try:
            system, prompt, tools_active = _prepare_messages(req.messages, req.tools)
            client = get_client()
            try:
                log.info(
                    "chat stream=%s model=%s resolved=%s msgs=%d",
                    req.stream,
                    normalize_request_model(req.model) or req.model,
                    _resolved_request_model(req, settings),
                    len(req.messages),
                )
                thread_id = _resolve_thread_id(req, settings) if not tools_active else None

                if req.stream:
                    return StreamingResponse(
                        _stream_openai(
                            client,
                            req,
                            system,
                            prompt,
                            thread_id,
                            settings,
                            tools_active=tools_active,
                        ),
                        media_type="text/event-stream",
                    )

                result = await client.complete(
                    prompt=prompt,
                    system=system,
                    model=req.model,
                    thread_id=thread_id,
                    tools_active=tools_active,
                    client_tools=req.tools,
                )
                log.info(
                    "chat result text_len=%s",
                    len(result.text or ""),
                )
                _remember_thread(req, result.thread_id, settings)

                completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
                return {
                    "id": completion_id,
                    "object": "chat.completion",
                    "created": int(time.time()),
                    "model": req.model,
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
        except HiggsfieldChatError as e:
            raise HTTPException(status_code=e.status_code, detail=str(e)) from e

    return app