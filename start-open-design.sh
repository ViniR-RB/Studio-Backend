#!/bin/sh
set -eu

if [ "${OPEN_DESIGN_AS_USER:-}" != "1" ]; then
    mkdir -p "${CODEX_HOME:-/app/.codex}"
    chown -R open-design:open-design "${CODEX_HOME:-/app/.codex}" /app/.od
    export OPEN_DESIGN_AS_USER=1
    exec su-exec open-design /usr/local/bin/start-open-design
fi

node /app/apps/daemon/dist/cli.js --no-open &
daemon_pid=$!
trap 'kill "$daemon_pid" 2>/dev/null || true' EXIT

for _ in $(seq 1 60); do
    if node -e "fetch('http://127.0.0.1:7456/api/health').then(r => { if (!r.ok) process.exit(1) }).catch(() => process.exit(1))"; then
        break
    fi
    sleep 1
done

node /app/apps/daemon/bin/od.mjs mcp install codex --daemon-url http://127.0.0.1:7456
wait "$daemon_pid"
