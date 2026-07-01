#!/bin/bash
# Один прогон обучения Reach-Franka + парс метрик в bench-results.jsonl
# Использование: bench_run.sh <physics> <num_envs> <seed> <iters> <tag>
set -euo pipefail
# shellcheck source=_lib.sh
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"

PHYSICS="$1"; NUM_ENVS="$2"; SEED="$3"; ITERS="$4"; TAG="$5"
RESULTS="${BENCH_RESULTS:-$HOME/.cockpit-jobs/bench-results.jsonl}"
RUNLOG="${BENCH_RUNLOG:-$HOME/.cockpit-jobs/bench-run-${TAG}.log}"
TMPDIR="${TMPDIR:-$HOME/tmp_isaac}"

cd "$ENGINE_ROOT"
# shellcheck source=/dev/null
source "$VENV/bin/activate"
export OMNI_KIT_ACCEPT_EULA=yes ACCEPT_EULA=Y PRIVACY_CONSENT=Y
mkdir -p "$TMPDIR"

if [[ ! -x "$ISAACLAB_DIR/isaaclab.sh" ]]; then
  echo "FATAL: IsaacLab not found at $ISAACLAB_DIR (init submodule in workspace)" >&2
  exit 1
fi

cd "$ISAACLAB_DIR"
START=$(date +%s)
set +e
./isaaclab.sh train --rl_library rsl_rl --task Isaac-Reach-Franka-v0 --headless \
  --num_envs "$NUM_ENVS" --seed "$SEED" --max_iterations "$ITERS" physics="$PHYSICS" \
  > "$RUNLOG" 2>&1
RC=$?
set -e
END=$(date +%s); WALL=$((END-START))
if [ "$RC" -ne 0 ]; then
  echo "{\"tag\":\"$TAG\",\"physics\":\"$PHYSICS\",\"num_envs\":$NUM_ENVS,\"seed\":$SEED,\"iters\":$ITERS,\"wall_s\":$WALL,\"error\":\"rc=$RC\"}" | tee -a "$RESULTS"
  echo "=== RUN $TAG FAILED rc=$RC (см. $RUNLOG) ==="
  exit 0
fi
python "$HARNESS_DIR/bench_parse.py" "$RUNLOG" "$TAG" "$PHYSICS" "$NUM_ENVS" "$SEED" "$ITERS" "$WALL" | tee -a "$RESULTS"
echo "=== RUN $TAG DONE (wall ${WALL}s) ==="
