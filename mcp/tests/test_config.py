"""Unit tests for config loading."""

from __future__ import annotations

import os

from zephyr_dc_mcp.config import Settings, reset_settings_cache


def test_settings_defaults(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("ZEPHYR_DC_MCP_PORT", raising=False)
    reset_settings_cache()
    s = Settings()
    assert s.openai_api_key is None
    assert s.openai_base_url == "https://api.openai.com/v1"
    assert s.mcp_port == 8765
    assert s.openai_configured is False


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("OPENAI_MODEL", "local-model")
    monkeypatch.setenv("ZEPHYR_DC_MCP_PORT", "9000")
    monkeypatch.setenv("ZEPHYR_DC_API_TOKEN", "secret")
    reset_settings_cache()
    s = Settings()
    assert s.openai_api_key == "sk-test"
    assert s.openai_base_url == "http://localhost:11434/v1"
    assert s.openai_model == "local-model"
    assert s.mcp_port == 9000
    assert s.api_token == "secret"
    assert s.openai_configured is True
    reset_settings_cache()
