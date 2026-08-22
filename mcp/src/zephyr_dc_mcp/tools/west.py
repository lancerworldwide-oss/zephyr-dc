"""West build and board listing tools."""

from __future__ import annotations

import os
from pathlib import Path

from zephyr_dc_mcp.config import get_settings
from zephyr_dc_mcp.jobs import get_job_manager
from zephyr_dc_mcp.process import build_argv, run_command, which
from zephyr_dc_mcp.registry import ToolSpec, register_tool


def _west() -> str:
    path = which("west")
    if not path:
        raise RuntimeError("west not found on PATH")
    return path


def west_build_start(
    board: str,
    source_dir: str,
    build_dir: str | None = None,
    cmake_args: list[str] | None = None,
    cwd: str | None = None,
    pristine: bool = False,
    timeout_sec: float | None = None,
) -> dict:
    argv = build_argv(_west(), "build", "-b", board, source_dir)
    if build_dir:
        argv.extend(["-d", build_dir])
    if pristine:
        argv.append("--pristine")
    if cmake_args:
        argv.append("--")
        argv.extend(cmake_args)
    job = get_job_manager().start(argv, cwd=cwd, timeout_sec=timeout_sec)
    return {"ok": True, "job_id": job.job_id, "argv": job.argv}


def west_list_boards(filter_text: str | None = None, cwd: str | None = None) -> dict:
    settings = get_settings()
    zephyr_base = settings.zephyr_base or os.environ.get("ZEPHYR_BASE")
    argv = build_argv(_west(), "boards")
    result = run_command(argv, cwd=cwd or zephyr_base, timeout_sec=120)
    boards = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    if filter_text:
        needle = filter_text.lower()
        boards = [b for b in boards if needle in b.lower()]
    return {
        "ok": result.returncode == 0,
        "boards": boards,
        "count": len(boards),
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def west_twister_path() -> str | None:
    settings = get_settings()
    base = settings.zephyr_base or os.environ.get("ZEPHYR_BASE")
    if not base:
        return None
    candidate = Path(base) / "scripts" / "twister"
    return str(candidate) if candidate.is_file() else None


def register() -> None:
    register_tool(
        ToolSpec(
            name="west_build_start",
            description="Start a west build as a background job. Poll with job_status/job_wait.",
            parameters={
                "type": "object",
                "properties": {
                    "board": {"type": "string", "description": "Zephyr board target, e.g. qemu_x86"},
                    "source_dir": {"type": "string", "description": "Application source directory"},
                    "build_dir": {"type": "string"},
                    "cmake_args": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Extra CMake args after --",
                    },
                    "cwd": {"type": "string"},
                    "pristine": {"type": "boolean", "default": False},
                    "timeout_sec": {"type": "number"},
                },
                "required": ["board", "source_dir"],
            },
            handler=west_build_start,
            long_running=True,
        )
    )
    register_tool(
        ToolSpec(
            name="west_list_boards",
            description="List Zephyr boards known to west, with optional substring filter.",
            parameters={
                "type": "object",
                "properties": {
                    "filter_text": {"type": "string"},
                    "cwd": {"type": "string"},
                },
            },
            handler=west_list_boards,
        )
    )
