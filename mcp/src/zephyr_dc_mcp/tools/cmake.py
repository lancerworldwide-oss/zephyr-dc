"""CMake configure and build tools."""

from __future__ import annotations

from pathlib import Path

from zephyr_dc_mcp.jobs import get_job_manager
from zephyr_dc_mcp.process import build_argv, which
from zephyr_dc_mcp.registry import ToolSpec, register_tool


def _cmake() -> str:
    path = which("cmake")
    if not path:
        raise RuntimeError("cmake not found on PATH")
    return path


def cmake_configure_start(
    source_dir: str,
    build_dir: str,
    definitions: dict[str, str] | None = None,
    generator: str | None = None,
    build_type: str | None = None,
    cwd: str | None = None,
    timeout_sec: float | None = None,
) -> dict:
    Path(build_dir).mkdir(parents=True, exist_ok=True)
    argv = build_argv(_cmake(), "-S", source_dir, "-B", build_dir)
    if generator:
        argv.extend(["-G", generator])
    if build_type:
        argv.append(f"-DCMAKE_BUILD_TYPE={build_type}")
    if definitions:
        for key, value in definitions.items():
            argv.append(f"-D{key}={value}")
    job = get_job_manager().start(argv, cwd=cwd, timeout_sec=timeout_sec)
    return {"ok": True, "job_id": job.job_id, "argv": job.argv}


def cmake_build_start(
    build_dir: str,
    target: str | None = None,
    jobs: int | None = None,
    cwd: str | None = None,
    timeout_sec: float | None = None,
) -> dict:
    argv = build_argv(_cmake(), "--build", build_dir)
    if target:
        argv.extend(["--target", target])
    if jobs is not None:
        argv.extend(["-j", str(jobs)])
    job = get_job_manager().start(argv, cwd=cwd, timeout_sec=timeout_sec)
    return {"ok": True, "job_id": job.job_id, "argv": job.argv}


def register() -> None:
    register_tool(
        ToolSpec(
            name="cmake_configure_start",
            description="Run cmake configure (-S/-B) as a background job.",
            parameters={
                "type": "object",
                "properties": {
                    "source_dir": {"type": "string"},
                    "build_dir": {"type": "string"},
                    "definitions": {
                        "type": "object",
                        "additionalProperties": {"type": "string"},
                        "description": "CMake -DKEY=VALUE pairs",
                    },
                    "generator": {"type": "string"},
                    "build_type": {"type": "string"},
                    "cwd": {"type": "string"},
                    "timeout_sec": {"type": "number"},
                },
                "required": ["source_dir", "build_dir"],
            },
            handler=cmake_configure_start,
            long_running=True,
        )
    )
    register_tool(
        ToolSpec(
            name="cmake_build_start",
            description="Run cmake --build as a background job.",
            parameters={
                "type": "object",
                "properties": {
                    "build_dir": {"type": "string"},
                    "target": {"type": "string"},
                    "jobs": {"type": "integer"},
                    "cwd": {"type": "string"},
                    "timeout_sec": {"type": "number"},
                },
                "required": ["build_dir"],
            },
            handler=cmake_build_start,
            long_running=True,
        )
    )
