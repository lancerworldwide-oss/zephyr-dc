"""Tests for OpenAI agent loop and HTTP chat endpoint."""

from __future__ import annotations

import json

import httpx
import pytest
import respx
from starlette.testclient import TestClient

from zephyr_dc_mcp.agent import run_agent_loop
from zephyr_dc_mcp.config import Settings, reset_settings_cache
from zephyr_dc_mcp.http_app import chat_completions, health
from zephyr_dc_mcp.registry import clear_registry
from zephyr_dc_mcp.tools import register_all_tools
from starlette.applications import Starlette
from starlette.routing import Route


@pytest.fixture(autouse=True)
def _tools():
    clear_registry()
    register_all_tools()
    reset_settings_cache()
    yield
    reset_settings_cache()
    clear_registry()


@pytest.mark.asyncio
async def test_agent_requires_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reset_settings_cache()
    result = await run_agent_loop([{"role": "user", "content": "hi"}])
    assert result["error"]
    assert "OPENAI_API_KEY" in result["error"]


@pytest.mark.asyncio
@respx.mock
async def test_agent_tool_loop(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    reset_settings_cache()

    path = tmp_path / "note.txt"
    path.write_text("payload", encoding="utf-8")

    route = respx.post("https://example.test/v1/chat/completions")
    route.side_effect = [
        httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "type": "function",
                                    "function": {
                                        "name": "read_file",
                                        "arguments": json.dumps({"path": str(path)}),
                                    },
                                }
                            ],
                        }
                    }
                ]
            },
        ),
        httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "File contains payload",
                        }
                    }
                ]
            },
        ),
    ]

    settings = Settings()
    result = await run_agent_loop(
        [{"role": "user", "content": "read the note"}],
        settings=settings,
    )
    assert result.get("error") is None
    assert "payload" in (result.get("final_text") or "")
    assert route.call_count == 2


def test_health_endpoint():
    app = Starlette(routes=[Route("/health", health)])
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_chat_completions_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    reset_settings_cache()
    app = Starlette(routes=[Route("/v1/chat/completions", chat_completions, methods=["POST"])])
    client = TestClient(app)
    resp = client.post("/v1/chat/completions", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 503
