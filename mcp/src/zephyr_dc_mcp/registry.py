"""Central tool registry shared by MCP and the OpenAI agent."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

ToolHandler = Callable[..., Awaitable[Any] | Any]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler
    long_running: bool = False

    def openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


_REGISTRY: dict[str, ToolSpec] = {}


def register_tool(spec: ToolSpec) -> ToolSpec:
    if spec.name in _REGISTRY:
        raise ValueError(f"duplicate tool: {spec.name}")
    _REGISTRY[spec.name] = spec
    return spec


def get_tool(name: str) -> ToolSpec | None:
    return _REGISTRY.get(name)


def list_tools() -> list[ToolSpec]:
    return list(_REGISTRY.values())


def openai_tools(*, exclude_prefixes: tuple[str, ...] = ("agent_",)) -> list[dict[str, Any]]:
    tools = []
    for t in list_tools():
        if any(t.name.startswith(p) for p in exclude_prefixes):
            continue
        tools.append(t.openai_schema())
    return tools


async def invoke_tool(name: str, arguments: dict[str, Any] | None = None) -> Any:
    spec = get_tool(name)
    if spec is None:
        raise KeyError(f"unknown tool: {name}")
    args = arguments or {}
    result = spec.handler(**args)
    if hasattr(result, "__await__"):
        result = await result  # type: ignore[misc]
    return result


def result_to_text(result: Any) -> str:
    if isinstance(result, str):
        return result
    try:
        return json.dumps(result, indent=2, default=str)
    except TypeError:
        return str(result)


def clear_registry() -> None:
    _REGISTRY.clear()
