#!/usr/bin/env bash
# Cursor sessionStart: start KOI dev stack if not running
set -euo pipefail

cat >/dev/null || true

KOI_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SERVE="$KOI_ROOT/scripts/koi-serve.sh"

if [[ ! -x "$SERVE" ]]; then
  exit 0
fi

if "$SERVE" status >/dev/null 2>&1; then
  exit 0
fi

"$SERVE" start >>"$KOI_ROOT/.run/session-start.log" 2>&1 || true
exit 0
