#!/bin/bash
# Матрица прогонов H1/H2/H3. Один GPU → строго последовательно.
set -uo pipefail
# shellcheck source=_lib.sh
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"

RESULTS="${BENCH_RESULTS:-$HOME/.cockpit-jobs/bench-results.jsonl}"
[ -f "$RESULTS" ] && cp "$RESULTS" "${RESULTS}.bak.$(date +%Y%m%d-%H%M%S)"
: > "$RESULTS"

run() { echo ">>> $(date +%H:%M:%S) RUN $5"; bash "$HARNESS_DIR/bench_run.sh" "$@"; }

echo "===== BENCH MATRIX START $(date +%F_%T) ====="

run newton_mjwarp 4096 42 300 h1-newton
run physx         4096 42 300 h1-physx

run newton_mjwarp  128 42 200 h2-n128
run newton_mjwarp  512 42 200 h2-n512
run newton_mjwarp 2048 42 200 h2-n2048
run newton_mjwarp 4096 42 200 h2-n4096

run newton_mjwarp 4096 0 150 h3-s0
run newton_mjwarp 4096 1 150 h3-s1
run newton_mjwarp 4096 2 150 h3-s2
run newton_mjwarp 4096 3 150 h3-s3
run newton_mjwarp 4096 4 150 h3-s4

echo "===== BENCH MATRIX DONE $(date +%F_%T) ====="
