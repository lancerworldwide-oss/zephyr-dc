"""Tests for file tools and registry."""

from __future__ import annotations

from pathlib import Path

from zephyr_dc_mcp.registry import clear_registry, invoke_tool, list_tools
from zephyr_dc_mcp.tools import register_all_tools
from zephyr_dc_mcp.tools.files import read_file, write_file


def setup_function():
    clear_registry()
    register_all_tools()


def test_register_all_tools_idempotent():
    names = {t.name for t in list_tools()}
    assert "read_file" in names
    assert "west_build_start" in names
    assert "agent_run" in names
    assert "twister_run_start" in names
    register_all_tools()
    assert len(list_tools()) == len(names)


def test_write_and_read_file(tmp_path: Path):
    path = tmp_path / "a.txt"
    written = write_file(str(path), "hello zephyr")
    assert written["ok"] is True
    read = read_file(str(path))
    assert read["ok"] is True
    assert read["content"] == "hello zephyr"


async def test_invoke_read_file(tmp_path: Path):
    path = tmp_path / "b.txt"
    path.write_text("via registry", encoding="utf-8")
    result = await invoke_tool("read_file", {"path": str(path)})
    assert result["ok"] is True
    assert "via registry" in result["content"]
