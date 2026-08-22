"""OpenAI Chat Completions tool-calling agent loop."""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import httpx

from zephyr_dc_mcp.config import Settings, get_settings
from zephyr_dc_mcp.registry import invoke_tool, openai_tools, result_to_text


class AgentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class AgentRun:
    run_id: str
    status: AgentStatus = AgentStatus.PENDING
    prompt: str = ""
    model: str | None = None
    messages: list[dict[str, Any]] = field(default_factory=list)
    final_text: str | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    _cancel: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "status": self.status.value,
            "prompt": self.prompt,
            "model": self.model,
            "messages": self.messages,
            "final_text": self.final_text,
            "error": self.error,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
        }


class AgentManager:
    def __init__(self) -> None:
        self._runs: dict[str, AgentRun] = {}
        self._lock = threading.Lock()

    def get(self, run_id: str) -> AgentRun | None:
        with self._lock:
            return self._runs.get(run_id)

    def cancel(self, run_id: str) -> AgentRun | None:
        run = self.get(run_id)
        if run is None:
            return None
        run._cancel.set()
        if run.status in (AgentStatus.PENDING, AgentStatus.RUNNING):
            run.status = AgentStatus.CANCELLED
            run.finished_at = time.time()
            run.error = "cancelled"
        return run

    def start_background(self, prompt: str, *, system: str | None = None, model: str | None = None) -> AgentRun:
        run = AgentRun(run_id=str(uuid.uuid4()), prompt=prompt, model=model)
        with self._lock:
            self._runs[run.run_id] = run
        thread = threading.Thread(
            target=self._thread_main,
            args=(run, system),
            name=f"agent-{run.run_id[:8]}",
            daemon=True,
        )
        thread.start()
        return run

    def _thread_main(self, run: AgentRun, system: str | None) -> None:
        try:
            import asyncio

            asyncio.run(self._async_run(run, system))
        except Exception as exc:  # noqa: BLE001
            run.status = AgentStatus.FAILED
            run.error = str(exc)
            run.finished_at = time.time()

    async def _async_run(self, run: AgentRun, system: str | None) -> None:
        run.status = AgentStatus.RUNNING
        settings = get_settings()
        try:
            result = await run_agent_loop(
                [{"role": "user", "content": run.prompt}],
                settings=settings,
                system=system,
                model=run.model,
                cancel_event=run._cancel,
                transcript_out=run.messages,
            )
            run.final_text = result.get("final_text")
            run.status = AgentStatus.CANCELLED if run._cancel.is_set() else AgentStatus.SUCCEEDED
            if result.get("error"):
                run.status = AgentStatus.FAILED
                run.error = result["error"]
        except Exception as exc:  # noqa: BLE001
            run.status = AgentStatus.FAILED
            run.error = str(exc)
        finally:
            run.finished_at = time.time()


_AGENT_MANAGER: AgentManager | None = None


def get_agent_manager() -> AgentManager:
    global _AGENT_MANAGER
    if _AGENT_MANAGER is None:
        _AGENT_MANAGER = AgentManager()
    return _AGENT_MANAGER


def reset_agent_manager() -> None:
    global _AGENT_MANAGER
    _AGENT_MANAGER = AgentManager()


DEFAULT_SYSTEM = (
    "You are a Zephyr RTOS firmware engineering agent running inside a container. "
    "Use the provided tools to build with west, run twister/tests/fuzz, emulate with Renode, "
    "run static analysis, generate coverage and Doxygen docs, and read/write project files. "
    "Prefer starting long jobs then polling job_wait/job_status. Be concise and factual."
)


async def run_agent_loop(
    messages: list[dict[str, Any]],
    *,
    settings: Settings | None = None,
    system: str | None = None,
    model: str | None = None,
    tools: list[dict[str, Any]] | None = None,
    max_iterations: int | None = None,
    cancel_event: threading.Event | None = None,
    transcript_out: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    settings = settings or get_settings()
    if not settings.openai_configured:
        return {"error": "OPENAI_API_KEY is not set", "final_text": None, "messages": messages}

    model_name = model or settings.openai_model
    tool_defs = tools if tools is not None else openai_tools()
    iterations = max_iterations or settings.agent_max_iterations

    chat: list[dict[str, Any]] = []
    if system or DEFAULT_SYSTEM:
        chat.append({"role": "system", "content": system or DEFAULT_SYSTEM})
    chat.extend(messages)
    if transcript_out is not None:
        transcript_out.clear()
        transcript_out.extend(chat)

    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }
    if settings.openai_org:
        headers["OpenAI-Organization"] = settings.openai_org

    base = settings.openai_base_url.rstrip("/")
    url = f"{base}/chat/completions"

    async with httpx.AsyncClient(timeout=120.0) as client:
        for _ in range(iterations):
            if cancel_event and cancel_event.is_set():
                return {"error": "cancelled", "final_text": None, "messages": chat}

            payload: dict[str, Any] = {
                "model": model_name,
                "messages": chat,
                "tools": tool_defs,
                "tool_choice": "auto",
            }
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code >= 400:
                return {
                    "error": f"OpenAI HTTP {resp.status_code}: {resp.text}",
                    "final_text": None,
                    "messages": chat,
                }
            data = resp.json()
            choice = (data.get("choices") or [{}])[0]
            message = choice.get("message") or {}
            chat.append(message)
            if transcript_out is not None:
                transcript_out.append(message)

            tool_calls = message.get("tool_calls") or []
            if not tool_calls:
                return {
                    "final_text": message.get("content") or "",
                    "messages": chat,
                    "model": model_name,
                    "raw": data,
                }

            for call in tool_calls:
                if cancel_event and cancel_event.is_set():
                    return {"error": "cancelled", "final_text": None, "messages": chat}
                fn = call.get("function") or {}
                name = fn.get("name") or ""
                raw_args = fn.get("arguments") or "{}"
                try:
                    args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                except json.JSONDecodeError:
                    args = {}
                    tool_result = {"ok": False, "error": f"invalid JSON arguments: {raw_args}"}
                else:
                    try:
                        tool_result = await invoke_tool(name, args)
                    except Exception as exc:  # noqa: BLE001
                        tool_result = {"ok": False, "error": str(exc)}
                tool_msg = {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "content": result_to_text(tool_result),
                }
                chat.append(tool_msg)
                if transcript_out is not None:
                    transcript_out.append(tool_msg)

        return {
            "error": f"exceeded max iterations ({iterations})",
            "final_text": None,
            "messages": chat,
        }
