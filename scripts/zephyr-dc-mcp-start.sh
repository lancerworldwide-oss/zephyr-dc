#!/bin/bash
# Start zephyr-dc-mcp (idempotent). Used by the image entrypoint and Dev Container postStart.
set -eu

MCP_HOST="${ZEPHYR_DC_MCP_HOST:-0.0.0.0}"
MCP_PORT="${ZEPHYR_DC_MCP_PORT:-8765}"
MCP_BIN="${ZEPHYR_DC_MCP_BIN:-/opt/zephyr-dc-mcp/venv/bin/zephyr-dc-mcp}"
MCP_LOG="${ZEPHYR_DC_MCP_LOG:-/tmp/zephyr-dc-mcp.log}"
MCP_PID_FILE="${ZEPHYR_DC_MCP_PID_FILE:-/tmp/zephyr-dc-mcp.pid}"
HEALTH_URL="http://127.0.0.1:${MCP_PORT}/health"
WAIT_SECS="${ZEPHYR_DC_MCP_WAIT_SECS:-30}"

health_ok() {
    curl -fsS "${HEALTH_URL}" >/dev/null 2>&1
}

if health_ok; then
    echo "zephyr-dc-mcp already healthy on ${MCP_HOST}:${MCP_PORT}" >&2
    exit 0
fi

if [ ! -x "${MCP_BIN}" ]; then
    echo "zephyr-dc-mcp binary not found or not executable at ${MCP_BIN}" >&2
    echo "Rebuild/pull ghcr.io/lancerworldwide-oss/zephyr-dc:latest (image must include MCP)." >&2
    exit 1
fi

echo "Starting zephyr-dc-mcp on ${MCP_HOST}:${MCP_PORT}" >&2
nohup "${MCP_BIN}" >>"${MCP_LOG}" 2>&1 &
echo $! >"${MCP_PID_FILE}"

i=0
while [ "${i}" -lt "${WAIT_SECS}" ]; do
    if health_ok; then
        echo "zephyr-dc-mcp is healthy at ${HEALTH_URL}" >&2
        exit 0
    fi
    sleep 1
    i=$((i + 1))
done

echo "zephyr-dc-mcp failed to become healthy within ${WAIT_SECS}s (${HEALTH_URL})" >&2
if [ -f "${MCP_LOG}" ]; then
    echo "--- last 50 lines of ${MCP_LOG} ---" >&2
    tail -n 50 "${MCP_LOG}" >&2 || true
fi
exit 1
