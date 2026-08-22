# Zephyr DC MCP

Firmware MCP server + in-container OpenAI agent for the zephyr-dc image.

## Install (dev)

```bash
cd mcp
pip install -e ".[dev]"
pytest
```

## Run locally

```bash
export OPENAI_API_KEY=...
export OPENAI_BASE_URL=https://api.openai.com/v1   # optional
export OPENAI_MODEL=gpt-4o                         # optional
zephyr-dc-mcp
```

Endpoints:

- `GET /health`
- MCP Streamable HTTP: `http://127.0.0.1:8765/mcp`
- OpenAI-compatible: `POST /v1/chat/completions`, `GET /v1/models`
