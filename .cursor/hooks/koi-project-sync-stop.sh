#!/usr/bin/env bash
set -euo pipefail

if [[ -f "$(dirname "$0")/.koi-project-sync-paused" ]]; then
  cat >/dev/null
  echo '{}'
  exit 0
fi

KOI_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$KOI_ROOT/.venv/bin/python"
SCRIPT="$(dirname "$0")/koi-project-sync-hook.py"

if [[ ! -x "$PY" ]]; then
  PY=python3
fi

if [[ ! -f "$KOI_ROOT/scripts/koi_project_sync.py" ]]; then
  cat >/dev/null
  echo '{}'
  exit 0
fi

exec "$PY" "$SCRIPT" stop
