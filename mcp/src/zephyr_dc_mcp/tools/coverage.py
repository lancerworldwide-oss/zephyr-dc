"""Coverage report generation with gcovr / lcov."""

from __future__ import annotations

import sys

from zephyr_dc_mcp.jobs import get_job_manager
from zephyr_dc_mcp.process import which
from zephyr_dc_mcp.registry import ToolSpec, register_tool


def coverage_report_start(
    build_dir: str,
    tool: str = "gcovr",
    root: str | None = None,
    output: str | None = None,
    cwd: str | None = None,
    timeout_sec: float | None = None,
    extra_args: list[str] | None = None,
) -> dict:
    tool = tool.lower()
    if tool not in ("gcovr", "lcov"):
        raise ValueError("tool must be 'gcovr' or 'lcov'")
    if tool == "gcovr" and not which("gcovr"):
        raise RuntimeError("gcovr not found on PATH")
    if tool == "lcov" and (not which("lcov") or not which("genhtml")):
        raise RuntimeError("lcov/genhtml not found on PATH")

    argv = [
        sys.executable,
        "-m",
        "zephyr_dc_mcp.coverage_cli",
        "--tool",
        tool,
        "--build-dir",
        build_dir,
    ]
    if root:
        argv.extend(["--root", root])
    if output:
        argv.extend(["--output", output])
    if which("gcovr"):
        argv.extend(["--gcovr-bin", which("gcovr") or "gcovr"])
    if which("lcov"):
        argv.extend(["--lcov-bin", which("lcov") or "lcov"])
    if which("genhtml"):
        argv.extend(["--genhtml-bin", which("genhtml") or "genhtml"])
    # extra_args only applied for gcovr via appending after module args is awkward;
    # accept them as passthrough after -- for future; ignore unused for now.
    _ = extra_args

    job = get_job_manager().start(argv, cwd=cwd, timeout_sec=timeout_sec)
    return {"ok": True, "job_id": job.job_id, "argv": job.argv, "tool": tool}


def register() -> None:
    register_tool(
        ToolSpec(
            name="coverage_report_start",
            description=(
                "Generate a coverage report from an existing build directory using gcovr or lcov. "
                "For twister-driven coverage prefer twister_run_start with coverage=true."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "build_dir": {"type": "string"},
                    "tool": {"type": "string", "enum": ["gcovr", "lcov"], "default": "gcovr"},
                    "root": {"type": "string", "description": "Source root for report filtering"},
                    "output": {"type": "string"},
                    "cwd": {"type": "string"},
                    "timeout_sec": {"type": "number"},
                    "extra_args": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["build_dir"],
            },
            handler=coverage_report_start,
            long_running=True,
        )
    )
