"""Job status / wait / log tools."""

from __future__ import annotations

from zephyr_dc_mcp.jobs import get_job_manager
from zephyr_dc_mcp.registry import ToolSpec, register_tool


def job_status(job_id: str) -> dict:
    job = get_job_manager().get(job_id)
    if job is None:
        return {"ok": False, "error": f"unknown job_id: {job_id}"}
    return {"ok": True, **job.to_dict(include_output=False)}


def job_log(job_id: str, tail: int = 8000) -> dict:
    job = get_job_manager().get(job_id)
    if job is None:
        return {"ok": False, "error": f"unknown job_id: {job_id}"}
    return {"ok": True, **job.to_dict(include_output=True, log_tail=tail)}


def job_wait(job_id: str, timeout_sec: float | None = None) -> dict:
    job = get_job_manager().wait(job_id, timeout_sec=timeout_sec)
    if job is None:
        return {"ok": False, "error": f"unknown job_id: {job_id}"}
    return {"ok": True, **job.to_dict(include_output=True, log_tail=20000)}


def job_cancel(job_id: str) -> dict:
    job = get_job_manager().cancel(job_id)
    if job is None:
        return {"ok": False, "error": f"unknown job_id: {job_id}"}
    return {"ok": True, **job.to_dict(include_output=False)}


def register() -> None:
    register_tool(
        ToolSpec(
            name="job_status",
            description="Get status of a background job without full logs.",
            parameters={
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
            handler=job_status,
        )
    )
    register_tool(
        ToolSpec(
            name="job_log",
            description="Get stdout/stderr tail for a background job.",
            parameters={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "tail": {"type": "integer", "default": 8000},
                },
                "required": ["job_id"],
            },
            handler=job_log,
        )
    )
    register_tool(
        ToolSpec(
            name="job_wait",
            description="Wait for a background job to finish (optional timeout).",
            parameters={
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "timeout_sec": {"type": "number"},
                },
                "required": ["job_id"],
            },
            handler=job_wait,
        )
    )
    register_tool(
        ToolSpec(
            name="job_cancel",
            description="Cancel a running background job.",
            parameters={
                "type": "object",
                "properties": {"job_id": {"type": "string"}},
                "required": ["job_id"],
            },
            handler=job_cancel,
        )
    )
