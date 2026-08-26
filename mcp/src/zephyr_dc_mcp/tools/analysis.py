"""Static analysis tools: cppcheck, cpplint, flawfinder, semgrep, clang-tidy, clang-format."""

from __future__ import annotations

from pathlib import Path

from zephyr_dc_mcp.jobs import get_job_manager
from zephyr_dc_mcp.process import build_argv, run_command, which
from zephyr_dc_mcp.registry import ToolSpec, register_tool


def _require(cmd: str) -> str:
    path = which(cmd)
    if not path:
        raise RuntimeError(f"{cmd} not found on PATH")
    return path


def cppcheck_start(
    path: str,
    cwd: str | None = None,
    extra_args: list[str] | None = None,
    timeout_sec: float | None = None,
) -> dict:
    argv = build_argv(_require("cppcheck"), "--enable=all", "--inconclusive", path)
    if extra_args:
        argv.extend(extra_args)
    job = get_job_manager().start(argv, cwd=cwd, timeout_sec=timeout_sec)
    return {"ok": True, "job_id": job.job_id, "argv": job.argv}


def cpplint_start(
    path: str,
    cwd: str | None = None,
    extra_args: list[str] | None = None,
    timeout_sec: float | None = None,
) -> dict:
    argv = build_argv(_require("cpplint"), path)
    if extra_args:
        argv.extend(extra_args)
    job = get_job_manager().start(argv, cwd=cwd, timeout_sec=timeout_sec)
    return {"ok": True, "job_id": job.job_id, "argv": job.argv}


def flawfinder_start(
    path: str,
    cwd: str | None = None,
    extra_args: list[str] | None = None,
    timeout_sec: float | None = None,
) -> dict:
    argv = build_argv(_require("flawfinder"), path)
    if extra_args:
        argv.extend(extra_args)
    job = get_job_manager().start(argv, cwd=cwd, timeout_sec=timeout_sec)
    return {"ok": True, "job_id": job.job_id, "argv": job.argv}


def semgrep_start(
    path: str,
    cwd: str | None = None,
    extra_args: list[str] | None = None,
    timeout_sec: float | None = None,
) -> dict:
    argv = build_argv(
        _require("semgrep"),
        "scan",
        "--metrics=off",
        "--config",
        "auto",
        path,
    )
    if extra_args:
        argv.extend(extra_args)
    job = get_job_manager().start(argv, cwd=cwd, timeout_sec=timeout_sec)
    return {"ok": True, "job_id": job.job_id, "argv": job.argv}


def clang_tidy_start(
    path: str,
    compile_commands_dir: str | None = None,
    checks: str | None = None,
    cwd: str | None = None,
    extra_args: list[str] | None = None,
    timeout_sec: float | None = None,
) -> dict:
    argv = build_argv(_require("clang-tidy"), path)
    if checks:
        argv.extend([f"--checks={checks}"])
    if compile_commands_dir:
        argv.extend(["-p", compile_commands_dir])
    elif cwd and (Path(cwd) / "compile_commands.json").is_file():
        argv.extend(["-p", cwd])
    if extra_args:
        argv.extend(extra_args)
    job = get_job_manager().start(argv, cwd=cwd, timeout_sec=timeout_sec)
    return {"ok": True, "job_id": job.job_id, "argv": job.argv}


def clang_format(
    path: str,
    inplace: bool = False,
    cwd: str | None = None,
) -> dict:
    argv = build_argv(_require("clang-format"))
    if inplace:
        argv.append("-i")
    else:
        argv.append("--dry-run")
        argv.append("--Werror")
    argv.append(path)
    # dry-run with Werror may not show diff; also support style dump via -n style
    if not inplace:
        # Prefer showing formatted output for agent consumption when not inplace
        argv = build_argv(_require("clang-format"), path)
        result = run_command(argv, cwd=cwd, timeout_sec=60)
        return {"ok": result.returncode == 0, "mode": "formatted_output", **result.to_dict()}
    result = run_command(argv, cwd=cwd, timeout_sec=60)
    return {"ok": result.returncode == 0, "mode": "inplace", **result.to_dict()}


def register() -> None:
    for name, handler, desc in [
        ("cppcheck_start", cppcheck_start, "Run cppcheck as a background job."),
        ("cpplint_start", cpplint_start, "Run cpplint as a background job."),
        ("flawfinder_start", flawfinder_start, "Run flawfinder as a background job."),
        ("semgrep_start", semgrep_start, "Run semgrep scan as a background job."),
    ]:
        register_tool(
            ToolSpec(
                name=name,
                description=desc,
                parameters={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "cwd": {"type": "string"},
                        "extra_args": {"type": "array", "items": {"type": "string"}},
                        "timeout_sec": {"type": "number"},
                    },
                    "required": ["path"],
                },
                handler=handler,
                long_running=True,
            )
        )

    register_tool(
        ToolSpec(
            name="clang_tidy_start",
            description="Run clang-tidy as a background job. Uses -p for compile_commands.json when provided.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "compile_commands_dir": {"type": "string"},
                    "checks": {"type": "string"},
                    "cwd": {"type": "string"},
                    "extra_args": {"type": "array", "items": {"type": "string"}},
                    "timeout_sec": {"type": "number"},
                },
                "required": ["path"],
            },
            handler=clang_tidy_start,
            long_running=True,
        )
    )
    register_tool(
        ToolSpec(
            name="clang_format",
            description="Run clang-format on a file. inplace=false returns formatted text; inplace=true rewrites the file.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "inplace": {"type": "boolean", "default": False},
                    "cwd": {"type": "string"},
                },
                "required": ["path"],
            },
            handler=clang_format,
        )
    )
