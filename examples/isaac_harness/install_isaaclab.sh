#!/bin/bash
# Установка Isaac Sim 6.0 + IsaacLab 3.0-beta2 (rsl_rl) в .venv engine.
# Запуск: nohup bash examples/isaac_harness/install_isaaclab.sh > ~/isaaclab-install.log 2>&1 &
set -euo pipefail
# shellcheck source=_lib.sh
source "$(cd "$(dirname "$0")" && pwd)/_lib.sh"

cd "$ENGINE_ROOT"
# shellcheck source=/dev/null
source "$VENV/bin/activate"
export OMNI_KIT_ACCEPT_EULA=yes ACCEPT_EULA=Y PRIVACY_CONSENT=Y

echo "=== [1/4] isaacsim pip package ==="
uv pip install "isaacsim[all,extscache]==6.0.0.1" \
  --extra-index-url https://pypi.nvidia.com \
  --index-strategy unsafe-best-match \
  --prerelease=allow

echo "=== [2/4] torch cu128 ==="
uv pip install -U torch==2.10.0 torchvision==0.25.0 \
  --index-url https://download.pytorch.org/whl/cu128

echo "=== [3/4] isaaclab --install rsl_rl ==="
for i in $(seq 1 360); do
  [ -x "$ISAACLAB_DIR/isaaclab.sh" ] && break
  sleep 10
done
[ -x "$ISAACLAB_DIR/isaaclab.sh" ] || { echo "FATAL: IsaacLab submodule missing at $ISAACLAB_DIR"; exit 1; }
cd "$ISAACLAB_DIR"
./isaaclab.sh --install rsl_rl

echo "=== [4/4] verify ==="
python -c "import torch; print('torch', torch.__version__, '| cuda available:', torch.cuda.is_available(), '|', torch.cuda.get_device_name(0))"
echo "=== INSTALL DONE ==="
