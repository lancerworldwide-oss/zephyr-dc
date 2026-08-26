"""Tests for static analysis argv construction (mocked which/job manager)."""

from __future__ import annotations

from types import SimpleNamespace

from zephyr_dc_mcp.tools import analysis as analysis_mod


def test_semgrep_start_argv(monkeypatch):
    monkeypatch.setattr(analysis_mod, "_require", lambda cmd: "/usr/bin/semgrep")

    def fake_start(argv, **kwargs):
        return SimpleNamespace(job_id="s1", argv=list(argv))

    monkeypatch.setattr(
        "zephyr_dc_mcp.tools.analysis.get_job_manager",
        lambda: SimpleNamespace(start=fake_start),
    )

    result = analysis_mod.semgrep_start(
        path="/work/src",
        extra_args=["--json"],
    )
    assert result["ok"] is True
    assert result["job_id"] == "s1"
    argv = result["argv"]
    assert argv == [
        "/usr/bin/semgrep",
        "scan",
        "--metrics=off",
        "--config",
        "auto",
        "/work/src",
        "--json",
    ]
