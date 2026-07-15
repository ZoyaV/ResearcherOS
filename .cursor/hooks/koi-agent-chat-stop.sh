#!/usr/bin/env bash
set -euo pipefail

KOI_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$KOI_ROOT/.venv/bin/python"
SCRIPT="$(dirname "$0")/koi-agent-chat-hook.py"

if [[ ! -x "$PY" ]]; then
  PY=python3
fi

if [[ ! -f "$KOI_ROOT/koi/agent_chat/cli.py" ]]; then
  cat >/dev/null
  echo '{}'
  exit 0
fi

exec "$PY" "$SCRIPT" stop
