"""Filesystem tools."""

from __future__ import annotations

import os
from pathlib import Path

from zephyr_dc_mcp.config import get_settings
from zephyr_dc_mcp.process import build_argv, run_command, which
from zephyr_dc_mcp.registry import ToolSpec, register_tool


def _resolve(path: str, cwd: str | None = None) -> Path:
    p = Path(path)
    if not p.is_absolute() and cwd:
        p = Path(cwd) / p
    return p.resolve()


def read_file(path: str, cwd: str | None = None, max_bytes: int | None = None) -> dict:
    settings = get_settings()
    limit = max_bytes if max_bytes is not None else settings.max_read_bytes
    target = _resolve(path, cwd)
    if not target.is_file():
        return {"ok": False, "error": f"not a file: {target}"}
    size = target.stat().st_size
    data = target.read_bytes()[:limit]
    truncated = size > limit
    try:
        text = data.decode("utf-8")
        binary = False
    except UnicodeDecodeError:
        text = data.decode("utf-8", errors="replace")
        binary = True
    return {
        "ok": True,
        "path": str(target),
        "size": size,
        "truncated": truncated,
        "binary": binary,
        "content": text,
    }


def write_file(path: str, content: str, cwd: str | None = None, create_dirs: bool = True) -> dict:
    target = _resolve(path, cwd)
    if create_dirs:
        target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"ok": True, "path": str(target), "bytes_written": target.stat().st_size}


def list_dir(path: str = ".", cwd: str | None = None, recursive: bool = False) -> dict:
    target = _resolve(path, cwd)
    if not target.exists():
        return {"ok": False, "error": f"path not found: {target}"}
    entries: list[dict] = []
    if recursive:
        for root, dirs, files_ in os.walk(target):
            for name in dirs:
                p = Path(root) / name
                entries.append({"path": str(p), "type": "dir"})
            for name in files_:
                p = Path(root) / name
                entries.append({"path": str(p), "type": "file", "size": p.stat().st_size})
    else:
        for child in sorted(target.iterdir()):
            item: dict = {"path": str(child), "type": "dir" if child.is_dir() else "file"}
            if child.is_file():
                item["size"] = child.stat().st_size
            entries.append(item)
    return {"ok": True, "path": str(target), "entries": entries}


def search_files(
    pattern: str,
    path: str = ".",
    cwd: str | None = None,
    glob: str | None = None,
    max_results: int = 200,
) -> dict:
    target = _resolve(path, cwd)
    rg = which("rg")
    if rg:
        argv = build_argv(rg, "--line-number", "--no-heading", "--color", "never")
        if glob:
            argv.extend(["--glob", glob])
        argv.extend(["--max-count", str(max_results), pattern, str(target)])
        result = run_command(argv, cwd=cwd, timeout_sec=120)
        return {"ok": result.returncode in (0, 1), "engine": "rg", **result.to_dict()}

    # Fallback: simple walk + substring match on text files
    matches: list[dict] = []
    for root, _dirs, files_ in os.walk(target):
        for name in files_:
            if glob and not Path(name).match(glob):
                continue
            file_path = Path(root) / name
            try:
                text = file_path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if pattern in line:
                    matches.append({"path": str(file_path), "line": i, "text": line[:500]})
                    if len(matches) >= max_results:
                        return {"ok": True, "engine": "python", "matches": matches}
    return {"ok": True, "engine": "python", "matches": matches}


def register() -> None:
    register_tool(
        ToolSpec(
            name="read_file",
            description="Read a text file from the filesystem (size-capped).",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path (absolute or relative to cwd)"},
                    "cwd": {"type": "string", "description": "Base directory for relative paths"},
                    "max_bytes": {"type": "integer", "description": "Optional read size cap"},
                },
                "required": ["path"],
            },
            handler=read_file,
        )
    )
    register_tool(
        ToolSpec(
            name="write_file",
            description="Write text content to a file, creating parent directories by default.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "cwd": {"type": "string"},
                    "create_dirs": {"type": "boolean", "default": True},
                },
                "required": ["path", "content"],
            },
            handler=write_file,
        )
    )
    register_tool(
        ToolSpec(
            name="list_dir",
            description="List directory entries.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "default": "."},
                    "cwd": {"type": "string"},
                    "recursive": {"type": "boolean", "default": False},
                },
            },
            handler=list_dir,
        )
    )
    register_tool(
        ToolSpec(
            name="search_files",
            description="Search file contents with ripgrep (or a Python fallback).",
            parameters={
                "type": "object",
                "properties": {
                    "pattern": {"type": "string"},
                    "path": {"type": "string", "default": "."},
                    "cwd": {"type": "string"},
                    "glob": {"type": "string"},
                    "max_results": {"type": "integer", "default": 200},
                },
                "required": ["pattern"],
            },
            handler=search_files,
        )
    )
