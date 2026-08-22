"""Firmware tool implementations."""

from __future__ import annotations

from zephyr_dc_mcp.tools import agent_tools as agent_tools
from zephyr_dc_mcp.tools import analysis as analysis
from zephyr_dc_mcp.tools import cmake as cmake
from zephyr_dc_mcp.tools import coverage as coverage
from zephyr_dc_mcp.tools import doxygen as doxygen
from zephyr_dc_mcp.tools import files as files
from zephyr_dc_mcp.tools import jobs_tools as jobs_tools
from zephyr_dc_mcp.tools import renode as renode
from zephyr_dc_mcp.tools import twister as twister
from zephyr_dc_mcp.tools import west as west


def register_all_tools() -> None:
    """Idempotently register all firmware tools into the shared registry."""
    from zephyr_dc_mcp.registry import list_tools

    if list_tools():
        return
    files.register()
    jobs_tools.register()
    west.register()
    cmake.register()
    renode.register()
    twister.register()
    analysis.register()
    coverage.register()
    doxygen.register()
    agent_tools.register()
