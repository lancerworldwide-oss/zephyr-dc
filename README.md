# Zephyr dev container base image

This project defines a Zephyr RTOS development container based on upstream Zephyr build images. The image includes a **firmware MCP server** (`zephyr-dc-mcp`) that starts with the container and exposes Zephyr tooling (west, Renode, twister, static analysis, coverage, Doxygen) plus an optional in-container OpenAI function-calling agent.

## Build

```bash
docker build -t ghcr.io/lancerworldwide-oss/zephyr-dc:latest .
```

## Run

Publish port `8765` and pass OpenAI settings from the host:

```bash
docker run -it --rm \
  -p 8765:8765 \
  -e OPENAI_API_KEY \
  -e OPENAI_BASE_URL \
  -e OPENAI_MODEL \
  -e ZEPHYR_DC_API_TOKEN \
  -v "${PWD}:/work" -w /work \
  ghcr.io/lancerworldwide-oss/zephyr-dc:latest
```

Environment variables (not baked into the image):

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | Required for the agent and `/v1/chat/completions` |
| `OPENAI_BASE_URL` | OpenAI-compatible base URL (default `https://api.openai.com/v1`) |
| `OPENAI_MODEL` | Model id (default `gpt-4o`) |
| `OPENAI_ORG` | Optional organization header |
| `ZEPHYR_DC_MCP_HOST` | Bind host (default `0.0.0.0`) |
| `ZEPHYR_DC_MCP_PORT` | Port (default `8765`) |
| `ZEPHYR_DC_API_TOKEN` | If set, require `Authorization: Bearer <token>` (except `/health`) |

Without `OPENAI_API_KEY`, MCP firmware tools still work; agent endpoints return an error.

## MCP (Cursor / Claude)

Add a Streamable HTTP MCP server pointing at the container:

```json
{
  "mcpServers": {
    "zephyr-dc": {
      "url": "http://localhost:8765/mcp"
    }
  }
}
```

If `ZEPHYR_DC_API_TOKEN` is set, include the bearer token in the client auth headers.

### Dev Containers

VS Code / Cursor Dev Containers replace the image `ENTRYPOINT` with a keep-alive process, so MCP does **not** start from PID 1. Consumer projects should:

1. Call `/usr/local/bin/zephyr-dc-mcp-start` from `postStartCommand` (see `zephyr-dc-mcp-start`; waits for `GET /health`).
2. Forward port `8765` in `devcontainer.json` (`forwardPorts`).

Do not background `/usr/local/bin/zephyr-dc-entrypoint.sh` from `postStart` — that script chains to an interactive shell and is for `docker run`, not Dev Containers.

After changing MCP install or start scripts in this repo, rebuild and push (or load) `ghcr.io/lancerworldwide-oss/zephyr-dc:latest`, then rebuild the consumer Dev Container.

Useful tools include `west_build_start`, `twister_run_start`, `renode_run_start`, `cppcheck_start`, `semgrep_start`, `coverage_report_start`, `doxygen_run_start`, `job_wait`, and `agent_run`.

## OpenAI-compatible HTTP (n8n / scripts)

```bash
curl -s http://localhost:8765/health

curl -s http://localhost:8765/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${ZEPHYR_DC_API_TOKEN}" \
  -d '{
    "model": "gpt-4o",
    "messages": [{"role": "user", "content": "List boards matching nrf52"}]
  }'
```

The server runs the firmware tool loop internally and returns the final assistant message. The response may include `zephyr_dc_transcript` with tool call steps for logging.

## Hardware debugger MCP

The image still installs `embedded-debugger-mcp` (probe-rs) at `/usr/local/bin/embedded-debugger-mcp`. It is **not** auto-started (stdio transport). Configure it separately in your MCP client if you need hardware debugging.

## Package source

The MCP server lives under [`mcp/`](mcp/) and is installed into `/opt/zephyr-dc-mcp/venv` during the image build. See [`mcp/README.md`](mcp/README.md).
