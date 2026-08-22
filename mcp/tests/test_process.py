"""Tests for process helpers."""

from __future__ import annotations

import sys

from zephyr_dc_mcp.process import run_command, truncate_text


def test_truncate_text():
    text, truncated = truncate_text("abcdefghij", 6)
    assert truncated is True
    assert "omitted" in text
    text2, truncated2 = truncate_text("abc", 10)
    assert truncated2 is False
    assert text2 == "abc"


def test_run_command_no_shell():
    result = run_command([sys.executable, "-c", "print('hello')"], timeout_sec=10)
    assert result.returncode == 0
    assert "hello" in result.stdout
    assert result.timed_out is False


def test_run_command_timeout():
    result = run_command(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        timeout_sec=0.2,
    )
    assert result.timed_out is True
    assert result.returncode == -1
