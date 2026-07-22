#!/usr/bin/env bash
# Cursor sessionStart: start KOI dev stack if not running
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


cat >/dev/null || true

KOI_ROOT="$(_koi_root_from_here)" || exit 0
SERVE="$KOI_ROOT/scripts/koi-serve.sh"

if [[ ! -x "$SERVE" ]]; then
  exit 0
fi

if "$SERVE" status >/dev/null 2>&1; then
  exit 0
fi

"$SERVE" start >>"$KOI_ROOT/.run/session-start.log" 2>&1 || true
exit 0
