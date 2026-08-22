#!/bin/bash
# Start zephyr-dc-mcp then chain to the upstream zephyr-build entrypoint.
set -eu

MCP_START="${ZEPHYR_DC_MCP_START:-/usr/local/bin/zephyr-dc-mcp-start}"

start_mcp() {
    if [ -x "${MCP_START}" ]; then
        "${MCP_START}" || {
            echo "zephyr-dc-mcp-start failed; continuing without MCP" >&2
            return 0
        }
        return 0
    fi
    # Fallback if helper was not installed in an older image layer.
    MCP_BIN="${ZEPHYR_DC_MCP_BIN:-/opt/zephyr-dc-mcp/venv/bin/zephyr-dc-mcp}"
    MCP_LOG="${ZEPHYR_DC_MCP_LOG:-/tmp/zephyr-dc-mcp.log}"
    MCP_HOST="${ZEPHYR_DC_MCP_HOST:-0.0.0.0}"
    MCP_PORT="${ZEPHYR_DC_MCP_PORT:-8765}"
    if [ ! -x "${MCP_BIN}" ]; then
        echo "zephyr-dc-mcp binary not found at ${MCP_BIN}; skipping MCP startup" >&2
        return 0
    fi
    echo "Starting zephyr-dc-mcp on ${MCP_HOST}:${MCP_PORT} (legacy fallback)" >&2
    nohup "${MCP_BIN}" >>"${MCP_LOG}" 2>&1 &
    echo $! > /tmp/zephyr-dc-mcp.pid
}

start_mcp

# Prefer upstream entrypoint if present (zephyr-build base image).
UPSTREAM_ENTRYPOINTS=(
    /usr/local/bin/entrypoint.sh
    /entrypoint.sh
    /usr/bin/entrypoint.sh
)

for ep in "${UPSTREAM_ENTRYPOINTS[@]}"; do
    if [ -x "${ep}" ]; then
        exec "${ep}" "$@"
    fi
done

# Fallback: run the user command or an interactive shell.
if [ "$#" -gt 0 ]; then
    exec "$@"
fi
exec bash -l
