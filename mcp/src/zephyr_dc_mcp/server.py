"""ASGI entrypoint: MCP Streamable HTTP + OpenAI-compatible API (MCP SDK 2.x)."""

from __future__ import annotations

import inspect
from typing import Any

import uvicorn
from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from zephyr_dc_mcp.agent import run_agent_loop
from zephyr_dc_mcp.config import get_settings
from zephyr_dc_mcp.http_app import (
    BearerAuthMiddleware,
    chat_completions,
    health,
    list_models,
)
from zephyr_dc_mcp.registry import invoke_tool, list_tools, result_to_text
from zephyr_dc_mcp.tools import register_all_tools


def _annotation_for_schema(pschema: dict[str, Any]) -> Any:
    t = pschema.get("type")
    if isinstance(t, list):
        # nullable unions etc.
        if "null" in t:
            non_null = [x for x in t if x != "null"]
            base = _annotation_for_schema({**pschema, "type": non_null[0] if non_null else "string"})
            return base | None
        t = t[0] if t else "string"
    if t == "string":
        return str
    if t == "integer":
        return int
    if t == "number":
        return float
    if t == "boolean":
        return bool
    if t == "array":
        return list
    if t == "object":
        return dict
    if "anyOf" in pschema or "oneOf" in pschema:
        return Any
    return Any


def _make_mcp_handler(tool_name: str, parameters: dict[str, Any], description: str):
    """Build an async callable with a real signature derived from JSON Schema."""
    props: dict[str, Any] = dict(parameters.get("properties") or {})
    required = set(parameters.get("required") or [])

    params: list[inspect.Parameter] = []
    for pname, pschema in props.items():
        if not isinstance(pschema, dict):
            pschema = {}
        annotation = _annotation_for_schema(pschema)
        if pname in required and "default" not in pschema:
            params.append(
                inspect.Parameter(
                    pname,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    annotation=annotation,
                )
            )
        else:
            default = pschema.get("default", None)
            params.append(
                inspect.Parameter(
                    pname,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    default=default,
                    annotation=annotation,
                )
            )

    async def impl(**kwargs: Any) -> str:
        result = await invoke_tool(tool_name, kwargs)
        return result_to_text(result)

    impl.__signature__ = inspect.Signature(params, return_annotation=str)  # type: ignore[attr-defined]
    impl.__name__ = tool_name
    impl.__doc__ = description
    return impl


def create_mcp() -> MCPServer:
    register_all_tools()
    mcp = MCPServer(
        name="zephyr-dc-mcp",
        instructions=(
            "Zephyr firmware MCP server. Tools wrap west, cmake, Renode, twister, "
            "static analysis, coverage, and Doxygen. Use agent_run for the in-container OpenAI agent."
        ),
    )

    for spec in list_tools():
        handler = _make_mcp_handler(spec.name, spec.parameters, spec.description)
        mcp.add_tool(handler, name=spec.name, description=spec.description)
        # Prefer the exact registry JSON schema for list_tools.
        tool = mcp._tool_manager.get_tool(spec.name)
        if tool is not None:
            tool.parameters = spec.parameters

    @mcp.custom_route("/health", methods=["GET"])
    async def health_route(request: Request) -> Response:
        return await health(request)

    @mcp.custom_route("/v1/models", methods=["GET"])
    async def models_route(request: Request) -> Response:
        return await list_models(request)

    @mcp.custom_route("/v1/chat/completions", methods=["POST"])
    async def chat_route(request: Request) -> Response:
        return await chat_completions(request)

    return mcp


def create_asgi_app():
    settings = get_settings()
    mcp = create_mcp()
    app = mcp.streamable_http_app(
        streamable_http_path="/mcp",
        host=settings.mcp_host,
        json_response=True,
        stateless_http=True,
    )
    if settings.api_token:
        app.add_middleware(BearerAuthMiddleware, token=settings.api_token)
    return app


def main() -> None:
    settings = get_settings()
    app = create_asgi_app()
    uvicorn.run(
        app,
        host=settings.mcp_host,
        port=settings.mcp_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
