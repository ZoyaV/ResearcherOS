#!/bin/bash
set -euo pipefail
# shellcheck source=_lib.sh
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"

TMPDIR="${TMPDIR:-$HOME/tmp_isaac}"
cd "$ENGINE_ROOT"
# shellcheck source=/dev/null
source "$VENV/bin/activate"
export OMNI_KIT_ACCEPT_EULA=yes ACCEPT_EULA=Y PRIVACY_CONSENT=Y
mkdir -p "$TMPDIR"
cd "$ISAACLAB_DIR"
./isaaclab.sh train --rl_library rsl_rl --task Isaac-Reach-Franka-v0 --headless --max_iterations 10 physics=newton_mjwarp
echo "=== SMOKE DONE ==="
