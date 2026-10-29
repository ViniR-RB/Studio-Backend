#!/bin/sh
set -eu

node /app/apps/daemon/dist/cli.js --no-open &
daemon_pid=$!
trap 'kill "$daemon_pid" 2>/dev/null || true' EXIT

for _ in $(seq 1 60); do
    if node -e "fetch('http://127.0.0.1:7456/api/health').then(r => { if (!r.ok) process.exit(1) }).catch(() => process.exit(1))"; then
        break
    fi
    sleep 1
done

node /app/apps/daemon/bin/od.mjs mcp install opencode --daemon-url http://127.0.0.1:7456
node -e "const fs=require('fs'); const path=require('path'); const file=path.join(process.env.HOME, '.config/opencode/opencode.json'); let config={}; try { config=JSON.parse(fs.readFileSync(file, 'utf8')); } catch {} config.model=process.env.OPENCODE_MODEL || 'opencode/nemotron-3.5-lightning-free'; config.mcp=config.mcp || {}; config.mcp['open-design']={type:'local',command:['/usr/local/bin/node','/app/apps/daemon/dist/cli.js','mcp','--daemon-url','http://127.0.0.1:7456'],enabled:true,environment:{OD_DATA_DIR:'/app/.od'}}; fs.mkdirSync(path.dirname(file), { recursive: true }); fs.writeFileSync(file, JSON.stringify(config, null, 2) + '\\n');"
wait "$daemon_pid"
