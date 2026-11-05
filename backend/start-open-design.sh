#!/bin/sh
set -eu
export HOME=/home/open-design
export CODEX_HOME=/home/open-design/.codex

node /app/apps/daemon/dist/cli.js --no-open &
daemon_pid=$!
trap 'kill "$daemon_pid" 2>/dev/null || true' EXIT

for _ in $(seq 1 60); do
    if node -e "fetch('http://127.0.0.1:7456/api/health').then(r => { if (!r.ok) process.exit(1) }).catch(() => process.exit(1))"; then
        break
    fi
    sleep 1
done

mkdir -p "$CODEX_HOME"
model=${CODEX_MODEL:-gpt-5.6-luna}
cat > "$CODEX_HOME/config.toml" <<EOF
model = "$model"
cli_auth_credentials_store = "file"

[mcp_servers.open_design]
command = "/usr/local/bin/node"
args = ["/app/apps/daemon/dist/cli.js", "mcp", "--daemon-url", "http://127.0.0.1:7456"]
EOF

if command -v codex >/dev/null 2>&1; then
    codex mcp remove open_design >/dev/null 2>&1 || true
    codex mcp add open_design -- /usr/local/bin/node /app/apps/daemon/dist/cli.js mcp --daemon-url http://127.0.0.1:7456 >/dev/null
fi

wait "$daemon_pid"
