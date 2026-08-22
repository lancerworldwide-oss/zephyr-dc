"""Renode emulation tools."""

from __future__ import annotations

import os
from pathlib import Path

from zephyr_dc_mcp.config import get_settings
from zephyr_dc_mcp.jobs import get_job_manager
from zephyr_dc_mcp.process import which
from zephyr_dc_mcp.registry import ToolSpec, register_tool


def _renode_bin() -> str:
    settings = get_settings()
    candidates = [
        which("renode"),
        which("renode-test"),
        str(Path(settings.renode_path) / "renode"),
        str(Path(settings.renode_path) / "Renode.exe"),
        "/opt/renode/renode",
    ]
    for c in candidates:
        if c and Path(c).exists():
            return c
        if c and which(Path(c).name):
            return which(Path(c).name) or c
    # .NET build layout from Dockerfile
    debug = Path(settings.renode_path)
    if debug.is_dir():
        for name in ("renode", "Renode", "renode.dll"):
            p = debug / name
            if p.exists():
                return str(p)
    raise RuntimeError("renode executable not found; set ZEPHYR_DC_RENODE_PATH")


def renode_run_start(
    script: str | None = None,
    script_path: str | None = None,
    extra_args: list[str] | None = None,
    cwd: str | None = None,
    timeout_sec: float | None = 300,
    disable_gui: bool = True,
) -> dict:
    """Start Renode headless. Prefer --disable-xwt / console flags when available."""
    bin_path = _renode_bin()
    argv: list[str] = []
    if bin_path.endswith(".dll"):
        argv = ["dotnet", bin_path]
    else:
        argv = [bin_path]

    if disable_gui:
        # Renode 1.x variants: --disable-xwt is common for headless
        argv.append("--disable-xwt")

    if script_path:
        argv.append(str(Path(script_path).resolve() if cwd is None else Path(cwd) / script_path))
    elif script:
        # Write ephemeral script next to cwd or /tmp
        base = Path(cwd) if cwd else Path("/tmp")
        base.mkdir(parents=True, exist_ok=True)
        script_file = base / f"renode-{os.getpid()}.resc"
        script_file.write_text(script, encoding="utf-8")
        argv.append(str(script_file))

    if extra_args:
        argv.extend(extra_args)

    job = get_job_manager().start(argv, cwd=cwd, timeout_sec=timeout_sec)
    return {"ok": True, "job_id": job.job_id, "argv": job.argv}


def register() -> None:
    register_tool(
        ToolSpec(
            name="renode_run_start",
            description=(
                "Start a headless Renode emulation as a background job. "
                "Provide either script (inline .resc) or script_path."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "script": {"type": "string", "description": "Inline Renode script contents"},
                    "script_path": {"type": "string", "description": "Path to a .resc script"},
                    "extra_args": {"type": "array", "items": {"type": "string"}},
                    "cwd": {"type": "string"},
                    "timeout_sec": {"type": "number", "default": 300},
                    "disable_gui": {"type": "boolean", "default": True},
                },
            },
            handler=renode_run_start,
            long_running=True,
        )
    )
