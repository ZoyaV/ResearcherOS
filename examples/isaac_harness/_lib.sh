# Shared paths for IsaacLab harness scripts (source from bash, do not execute).
HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_ROOT="$(cd "$HARNESS_DIR/../.." && pwd)"
KOI_WORKSPACE="${KOI_WORKSPACE:-$ENGINE_ROOT/../koi-workspace}"
ISAACLAB_DIR="$KOI_WORKSPACE/projects/IsaacLab_release_3_0"
VENV="$ENGINE_ROOT/.venv"
