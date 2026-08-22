"""Tests for west/cmake argv construction (mocked which/job manager)."""

from __future__ import annotations

from types import SimpleNamespace

from zephyr_dc_mcp.tools import cmake as cmake_mod
from zephyr_dc_mcp.tools import west as west_mod


def test_west_build_start_argv(monkeypatch):
    monkeypatch.setattr(west_mod, "_west", lambda: "/usr/bin/west")

    def fake_start(argv, **kwargs):
        return SimpleNamespace(job_id="jid", argv=list(argv))

    monkeypatch.setattr(
        "zephyr_dc_mcp.tools.west.get_job_manager",
        lambda: SimpleNamespace(start=fake_start),
    )

    result = west_mod.west_build_start(
        board="qemu_x86",
        source_dir="/app",
        build_dir="/app/build",
        cmake_args=["-DCONFIG_FOO=y"],
        pristine=True,
    )
    assert result["ok"] is True
    argv = result["argv"]
    assert argv[0] == "/usr/bin/west"
    assert "build" in argv
    assert "-b" in argv and "qemu_x86" in argv
    assert "--pristine" in argv
    assert "--" in argv
    assert "-DCONFIG_FOO=y" in argv


def test_cmake_configure_argv(monkeypatch, tmp_path):
    monkeypatch.setattr(cmake_mod, "_cmake", lambda: "/usr/bin/cmake")

    def fake_start(argv, **kwargs):
        return SimpleNamespace(job_id="c1", argv=list(argv))

    monkeypatch.setattr(
        "zephyr_dc_mcp.tools.cmake.get_job_manager",
        lambda: SimpleNamespace(start=fake_start),
    )
    build = tmp_path / "build"
    result = cmake_mod.cmake_configure_start(
        source_dir=str(tmp_path),
        build_dir=str(build),
        definitions={"FOO": "1"},
        build_type="Debug",
    )
    assert result["ok"] is True
    argv = result["argv"]
    assert argv[0] == "/usr/bin/cmake"
    assert "-S" in argv
    assert "-B" in argv
    assert "-DFOO=1" in argv
    assert "-DCMAKE_BUILD_TYPE=Debug" in argv
