"""HTTP handlers and auth middleware for zephyr-dc-mcp."""

from __future__ import annotations

import json
import time
import uuid
from typing import Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse

from zephyr_dc_mcp.agent import DEFAULT_SYSTEM, run_agent_loop
from zephyr_dc_mcp.config import Settings, get_settings


class BearerAuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, token: str | None):
        super().__init__(app)
        self.token = token

    async def dispatch(self, request: Request, call_next):
        if not self.token:
            return await call_next(request)
        if request.url.path in ("/health", "/"):
            return await call_next(request)
        auth = request.headers.get("authorization") or ""
        if auth == f"Bearer {self.token}":
            return await call_next(request)
        return JSONResponse({"error": "unauthorized"}, status_code=401)


async def health(_: Request) -> Response:
    settings = get_settings()
    return JSONResponse(
        {
            "status": "ok",
            "service": "zephyr-dc-mcp",
            "openai_configured": settings.openai_configured,
            "model": settings.openai_model if settings.openai_configured else None,
        }
    )


async def list_models(_: Request) -> Response:
    settings = get_settings()
    model = settings.openai_model
    return JSONResponse(
        {
            "object": "list",
            "data": [
                {
                    "id": model,
                    "object": "model",
                    "created": int(time.time()),
                    "owned_by": "zephyr-dc-mcp",
                }
            ],
        }
    )


async def chat_completions(request: Request) -> Response:
    settings: Settings = get_settings()
    if not settings.openai_configured:
        return JSONResponse(
            {"error": {"message": "OPENAI_API_KEY is not set", "type": "config_error"}},
            status_code=503,
        )

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"error": {"message": "invalid JSON body"}}, status_code=400)

    messages = body.get("messages") or []
    if not isinstance(messages, list) or not messages:
        return JSONResponse({"error": {"message": "messages required"}}, status_code=400)

    model = body.get("model") or settings.openai_model
    stream = bool(body.get("stream"))

    system = None
    chat_messages: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "system" and system is None:
            content = msg.get("content")
            system = content if isinstance(content, str) else DEFAULT_SYSTEM
        else:
            chat_messages.append(msg)

    if not chat_messages:
        chat_messages = [{"role": "user", "content": "Hello"}]

    result = await run_agent_loop(
        chat_messages,
        settings=settings,
        system=system,
        model=model,
    )
    if result.get("error") and not result.get("final_text"):
        return JSONResponse(
            {"error": {"message": result["error"], "type": "agent_error"}},
            status_code=502,
        )

    final_text = result.get("final_text") or ""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())
    transcript = result.get("messages") or []

    if stream:

        async def event_gen():
            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"role": "assistant", "content": final_text},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk)}\n\n"
            done = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
            }
            yield f"data: {json.dumps(done)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    return JSONResponse(
        {
            "id": completion_id,
            "object": "chat.completion",
            "created": created,
            "model": model,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": final_text},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            "zephyr_dc_transcript": transcript,
        }
    )
