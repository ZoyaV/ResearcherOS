#!/usr/bin/env bash
set -euo pipefail

# Resolve ResearchOS root (directory that contains koi/agent_chat/cli.py).
_koi_root_from_here() {
  local d
  d="$(cd "$(dirname "$0")" && pwd)"
  while [[ "$d" != "/" ]]; do
    if [[ -f "$d/koi/agent_chat/cli.py" ]]; then
      printf '%s\n' "$d"
      return 0
    fi
    d="$(dirname "$d")"
  done
  return 1
}


KOI_ROOT="$(_koi_root_from_here)" || exit 0
PY="$KOI_ROOT/.venv/bin/python"
SCRIPT="$(dirname "$0")/koi-done-research-hook.py"

if [[ ! -x "$PY" ]]; then
  PY=python3
fi

if [[ ! -f "$KOI_ROOT/koi/projects/done_research_cli.py" ]]; then
  cat >/dev/null
  echo '{}'
  exit 0
fi

exec "$PY" "$SCRIPT" stop
