#!/usr/bin/env bash
# Foreground chat inbox watcher (AGENT_CHAT_WAKE on agent-chat queue changes).
set -euo pipefail

KOI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$KOI_ROOT/.venv/bin/python"
SCRIPT="$KOI_ROOT/scripts/koi_agent_chat_inbox.py"

if [[ ! -x "$PY" ]]; then
  PY=python3
fi

exec "$PY" "$SCRIPT" watch
