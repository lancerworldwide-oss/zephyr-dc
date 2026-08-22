"""Twister, ztest, and fuzz tooling."""

from __future__ import annotations

import os
from pathlib import Path

from zephyr_dc_mcp.config import get_settings
from zephyr_dc_mcp.jobs import get_job_manager
from zephyr_dc_mcp.process import which
from zephyr_dc_mcp.registry import ToolSpec, register_tool


def _twister_cmd() -> list[str]:
    settings = get_settings()
    base = settings.zephyr_base or os.environ.get("ZEPHYR_BASE")
    if base:
        script = Path(base) / "scripts" / "twister"
        if script.is_file():
            return ["python3", str(script)]
    tw = which("twister")
    if tw:
        return [tw]
    raise RuntimeError("twister not found; ensure ZEPHYR_BASE is set")


def twister_run_start(
    platform: str | None = None,
    test_path: str | None = None,
    extra_args: list[str] | None = None,
    coverage: bool = False,
    coverage_tool: str | None = None,
    cwd: str | None = None,
    timeout_sec: float | None = None,
) -> dict:
    argv = _twister_cmd()
    if platform:
        argv.extend(["-p", platform])
    if test_path:
        argv.extend(["-T", test_path])
    if coverage:
        argv.append("--coverage")
        if coverage_tool:
            argv.extend(["--coverage-tool", coverage_tool])
    if extra_args:
        argv.extend(extra_args)
    job = get_job_manager().start(argv, cwd=cwd, timeout_sec=timeout_sec)
    return {"ok": True, "job_id": job.job_id, "argv": job.argv}


def fuzz_run_start(
    source_dir: str,
    board: str = "native_sim/native/64",
    cwd: str | None = None,
    timeout_sec: float | None = 600,
    extra_cmake_args: list[str] | None = None,
) -> dict:
    """Build and run a Zephyr libFuzzer sample via west build -t run."""
    west = which("west")
    if not west:
        raise RuntimeError("west not found on PATH")
    env = {
        "ZEPHYR_TOOLCHAIN_VARIANT": os.environ.get("ZEPHYR_TOOLCHAIN_VARIANT", "host"),
    }
    argv = [west, "build", "-t", "run", "-b", board, source_dir]
    if extra_cmake_args:
        argv.append("--")
        argv.extend(extra_cmake_args)
    job = get_job_manager().start(argv, cwd=cwd, env=env, timeout_sec=timeout_sec)
    return {"ok": True, "job_id": job.job_id, "argv": job.argv, "env": env}


def register() -> None:
    register_tool(
        ToolSpec(
            name="twister_run_start",
            description=(
                "Start Zephyr twister (ztest / integration / coverage) as a background job. "
                "Use coverage=true with coverage_tool gcovr or lcov for coverage reports."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "platform": {"type": "string"},
                    "test_path": {"type": "string", "description": "Path passed to twister -T"},
                    "extra_args": {"type": "array", "items": {"type": "string"}},
                    "coverage": {"type": "boolean", "default": False},
                    "coverage_tool": {"type": "string", "enum": ["gcovr", "lcov"]},
                    "cwd": {"type": "string"},
                    "timeout_sec": {"type": "number"},
                },
            },
            handler=twister_run_start,
            long_running=True,
        )
    )
    register_tool(
        ToolSpec(
            name="fuzz_run_start",
            description=(
                "Start a Zephyr libFuzzer-style fuzz run via west build -t run "
                "(typically native_sim/native/64 with host/llvm toolchain)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "source_dir": {"type": "string"},
                    "board": {"type": "string", "default": "native_sim/native/64"},
                    "cwd": {"type": "string"},
                    "timeout_sec": {"type": "number", "default": 600},
                    "extra_cmake_args": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["source_dir"],
            },
            handler=fuzz_run_start,
            long_running=True,
        )
    )
