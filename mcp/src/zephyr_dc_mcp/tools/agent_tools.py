"""MCP-facing agent control tools."""

from __future__ import annotations

from zephyr_dc_mcp.agent import get_agent_manager
from zephyr_dc_mcp.config import get_settings
from zephyr_dc_mcp.registry import ToolSpec, register_tool


def agent_run(prompt: str, system: str | None = None, model: str | None = None) -> dict:
    settings = get_settings()
    if not settings.openai_configured:
        return {"ok": False, "error": "OPENAI_API_KEY is not set"}
    run = get_agent_manager().start_background(prompt, system=system, model=model)
    return {"ok": True, "run_id": run.run_id, "status": run.status.value}


def agent_status(run_id: str) -> dict:
    run = get_agent_manager().get(run_id)
    if run is None:
        return {"ok": False, "error": f"unknown run_id: {run_id}"}
    data = run.to_dict()
    # Keep payload smaller by default
    data.pop("messages", None)
    return {"ok": True, **data}


def agent_cancel(run_id: str) -> dict:
    run = get_agent_manager().cancel(run_id)
    if run is None:
        return {"ok": False, "error": f"unknown run_id: {run_id}"}
    return {"ok": True, "run_id": run.run_id, "status": run.status.value}


def register() -> None:
    register_tool(
        ToolSpec(
            name="agent_run",
            description=(
                "Start an in-container OpenAI function-calling agent with access to all firmware tools. "
                "Returns run_id; poll agent_status."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "prompt": {"type": "string"},
                    "system": {"type": "string"},
                    "model": {"type": "string"},
                },
                "required": ["prompt"],
            },
            handler=agent_run,
            long_running=True,
        )
    )
    register_tool(
        ToolSpec(
            name="agent_status",
            description="Get status and final_text for an agent run.",
            parameters={
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
            },
            handler=agent_status,
        )
    )
    register_tool(
        ToolSpec(
            name="agent_cancel",
            description="Cancel an in-flight agent run.",
            parameters={
                "type": "object",
                "properties": {"run_id": {"type": "string"}},
                "required": ["run_id"],
            },
            handler=agent_cancel,
        )
    )
