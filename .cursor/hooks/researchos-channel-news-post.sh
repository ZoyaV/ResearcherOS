#!/usr/bin/env bash
set -euo pipefail

KOI_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$KOI_ROOT/.venv/bin/python"
SCRIPT="$(dirname "$0")/researchos-channel-news-hook.py"

if [[ ! -x "$PY" ]]; then
  PY=python3
fi

exec "$PY" "$SCRIPT"
