#!/usr/bin/env bash
# Lint KOI web/ UI changes. By default checks only added lines in git diff.
# Usage: lint-ui-css.sh [files...]   |   lint-ui-css.sh --all [files...]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
WEB="$ROOT/web"
SCAN_ALL=0

if [[ "${1:-}" == "--all" ]]; then
  SCAN_ALL=1
  shift
fi

if [[ $# -eq 0 ]]; then
  mapfile -t FILES < <(find "$WEB" -maxdepth 1 -type f \( -name '*.css' -o -name '*.js' -o -name '*.html' \) | sort)
else
  FILES=("$@")
fi

BLOCK=0
WARN=0
CHECKED=0

block() { echo "BLOCK: $*"; BLOCK=$((BLOCK + 1)); }
warn()  { echo "WARN:  $*"; WARN=$((WARN + 1)); }

check_line() {
  local f=$1 lineno=$2 content=$3 ext=$4
  CHECKED=$((CHECKED + 1))

  if [[ "$ext" == "css" ]]; then
    if [[ "$content" =~ \#[0-9a-fA-F]{3,8} ]] && [[ ! "$content" =~ --[a-zA-Z0-9_-]+: ]]; then
      if [[ "$content" =~ (color|background|border|box-shadow|fill|stroke)[[:space:]:] ]]; then
        block "$f:$lineno: hardcoded color — use var(--token)"
      fi
    fi
    if [[ "$content" =~ font-family: ]] && [[ ! "$content" =~ (Outfit|Syne|system-ui|sans-serif|inherit|monospace|ui-monospace) ]]; then
      block "$f:$lineno: unexpected font-family — use Outfit / Syne (monospace ok for code)"
    fi
    if [[ "$content" =~ outline:[[:space:]]*none ]] && [[ ! "$content" =~ focus ]]; then
      warn "$f:$lineno: outline:none — add :focus-visible style"
    fi
  fi

  if [[ "$ext" == "html" || "$ext" == "js" ]]; then
    if [[ "$content" =~ style=\" ]]; then
      block "$f:$lineno: inline style attribute — use CSS classes"
    fi
    if [[ "$content" =~ \<button ]] && [[ ! "$content" =~ type= ]]; then
      warn "$f:$lineno: <button> without explicit type="
    fi
    if [[ "$content" =~ class=\"modal[[:space:]]hidden\" ]] && [[ ! "$content" =~ role=\"dialog\" ]]; then
      warn "$f:$lineno: modal root missing role=\"dialog\""
    fi
    if echo "$content" | grep -qE '<button[^>]*>[^<]*<svg' && [[ ! "$content" =~ aria-label= ]]; then
      warn "$f:$lineno: icon button — add aria-label"
    fi
    if [[ "$ext" == "js" ]] && [[ "$content" =~ \#[0-9a-fA-F]{3,8} ]]; then
      if echo "$content" | grep -qE 'stop-color|fill=|stroke=|(color|background)'; then
        warn "$f:$lineno: hardcoded color in JS — prefer CSS / tokens if adding new UI"
      fi
    fi
  fi
}

for f in "${FILES[@]}"; do
  [[ -f "$f" ]] || { warn "$f: file not found"; continue; }
  ext="${f##*.}"

  if [[ "$SCAN_ALL" -eq 1 ]]; then
    while IFS= read -r entry; do
      lineno="${entry%%:*}"
      content="${entry#*:}"
      check_line "$f" "$lineno" "$content" "$ext"
    done < <(grep -n '.' "$f" || true)
  else
    rel="${f#"$ROOT"/}"
    mapfile -t ADDED < <(
      git -C "$ROOT" diff -U0 -- "$rel" 2>/dev/null | grep -E '^\+[^+]' | sed 's/^+//' || true
      git -C "$ROOT" diff -U0 --cached -- "$rel" 2>/dev/null | grep -E '^\+[^+]' | sed 's/^+//' || true
    )
    if [[ ${#ADDED[@]} -eq 0 ]]; then
      continue
    fi
    lineno=0
    for content in "${ADDED[@]}"; do
      [[ -z "$content" ]] && continue
      lineno=$((lineno + 1))
      check_line "$f" "added:$lineno" "$content" "$ext"
    done
  fi
done

echo "---"
if [[ "$CHECKED" -eq 0 ]]; then
  echo "no added lines to check (use --all for full scan)"
fi
echo "lines checked: $CHECKED  blocking: $BLOCK  warnings: $WARN"
[[ "$BLOCK" -eq 0 ]]
