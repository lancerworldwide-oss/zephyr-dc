"""Doxygen discovery and generation."""

from __future__ import annotations

from pathlib import Path

from zephyr_dc_mcp.jobs import get_job_manager
from zephyr_dc_mcp.process import build_argv, which
from zephyr_dc_mcp.registry import ToolSpec, register_tool


def doxygen_find(path: str = ".", cwd: str | None = None, max_results: int = 50) -> dict:
    root = Path(path)
    if not root.is_absolute() and cwd:
        root = Path(cwd) / root
    root = root.resolve()
    found: list[str] = []
    for name in ("Doxyfile", "Doxyfile.in", "doxygen.cfg"):
        for match in root.rglob(name):
            found.append(str(match))
            if len(found) >= max_results:
                return {"ok": True, "doxyfiles": found, "truncated": True}
    return {"ok": True, "doxyfiles": found, "truncated": False}


def doxygen_run_start(
    doxyfile: str,
    cwd: str | None = None,
    timeout_sec: float | None = None,
) -> dict:
    exe = which("doxygen")
    if not exe:
        raise RuntimeError("doxygen not found on PATH")
    path = Path(doxyfile)
    if not path.is_absolute() and cwd:
        path = Path(cwd) / path
    argv = build_argv(exe, str(path))
    job = get_job_manager().start(argv, cwd=cwd or str(path.parent), timeout_sec=timeout_sec)
    return {"ok": True, "job_id": job.job_id, "argv": job.argv}


def register() -> None:
    register_tool(
        ToolSpec(
            name="doxygen_find",
            description="Find Doxyfile / Doxyfile.in / doxygen.cfg under a path.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "default": "."},
                    "cwd": {"type": "string"},
                    "max_results": {"type": "integer", "default": 50},
                },
            },
            handler=doxygen_find,
        )
    )
    register_tool(
        ToolSpec(
            name="doxygen_run_start",
            description="Run doxygen on a Doxyfile as a background job.",
            parameters={
                "type": "object",
                "properties": {
                    "doxyfile": {"type": "string"},
                    "cwd": {"type": "string"},
                    "timeout_sec": {"type": "number"},
                },
                "required": ["doxyfile"],
            },
            handler=doxygen_run_start,
            long_running=True,
        )
    )
