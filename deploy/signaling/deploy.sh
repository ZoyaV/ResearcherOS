#!/usr/bin/env bash
# Deploy paper-collab signaling to Yandex Serverless Container + API Gateway WebSocket.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DEPLOY="$ROOT/deploy/signaling"

FOLDER_ID="${YC_FOLDER_ID:-b1gd4tuo1s1lu2b87fmf}"
CONTAINER_NAME="${COLLAB_CONTAINER_NAME:-researchos-collab-signal}"
REGISTRY_NAME="${COLLAB_REGISTRY_NAME:-researchos-collab-cr}"
GATEWAY_NAME="${COLLAB_GATEWAY_NAME:-researchos-collab-gw}"
SA_NAME="${COLLAB_SA_NAME:-researchos-collab-sa}"
IMAGE_TAG="${COLLAB_IMAGE_TAG:-latest}"

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$ROOT/.env"
  set +a
fi

: "${KOI_COLLAB_TOKEN_SECRET:?Set KOI_COLLAB_TOKEN_SECRET in ReseachOS/.env}"

echo "==> Ensure container registry"
REGISTRY_ID=""
if REGISTRY_JSON="$(yc container registry get --name "$REGISTRY_NAME" --folder-id "$FOLDER_ID" --format json 2>/dev/null)"; then
  REGISTRY_ID="$(echo "$REGISTRY_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
fi
if [[ -z "$REGISTRY_ID" ]]; then
  yc container registry create --name "$REGISTRY_NAME" --folder-id "$FOLDER_ID"
  REGISTRY_ID="$(yc container registry get --name "$REGISTRY_NAME" --folder-id "$FOLDER_ID" --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
fi
REGISTRY_URI="cr.yandex/${REGISTRY_ID}/${CONTAINER_NAME}:${IMAGE_TAG}"

echo "==> Build & push ${REGISTRY_URI} (linux/amd64)"
cd "$ROOT"
docker build --platform linux/amd64 -f deploy/signaling/Dockerfile -t "$REGISTRY_URI" .
yc container registry configure-docker
docker push "$REGISTRY_URI"

echo "==> Ensure service account"
SA_ID=""
if SA_JSON="$(yc iam service-account get --name "$SA_NAME" --folder-id "$FOLDER_ID" --format json 2>/dev/null)"; then
  SA_ID="$(echo "$SA_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
fi
if [[ -z "$SA_ID" ]]; then
  yc iam service-account create --name "$SA_NAME" --folder-id "$FOLDER_ID"
  SA_ID="$(yc iam service-account get --name "$SA_NAME" --folder-id "$FOLDER_ID" --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
fi

yc resource-manager folder add-access-binding "$FOLDER_ID" \
  --role serverless-containers.containerInvoker \
  --service-account-id "$SA_ID" >/dev/null
yc resource-manager folder add-access-binding "$FOLDER_ID" \
  --role container-registry.images.puller \
  --service-account-id "$SA_ID" >/dev/null
yc resource-manager folder add-access-binding "$FOLDER_ID" \
  --role api-gateway.websocketBroadcaster \
  --service-account-id "$SA_ID" >/dev/null || true

echo "==> Ensure serverless container"
CONTAINER_ID=""
if CONTAINER_JSON="$(yc serverless container get --name "$CONTAINER_NAME" --folder-id "$FOLDER_ID" --format json 2>/dev/null)"; then
  CONTAINER_ID="$(echo "$CONTAINER_JSON" | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
fi
if [[ -z "$CONTAINER_ID" ]]; then
  yc serverless container create --name "$CONTAINER_NAME" --folder-id "$FOLDER_ID"
  CONTAINER_ID="$(yc serverless container get --name "$CONTAINER_NAME" --folder-id "$FOLDER_ID" --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])')"
fi

echo "==> Deploy revision (one warm replica, in-memory rooms)"
yc serverless container revision deploy \
  --container-id "$CONTAINER_ID" \
  --image "$REGISTRY_URI" \
  --cores 1 \
  --memory 512MB \
  --execution-timeout 30s \
  --concurrency 8 \
  --min-instances 1 \
  --service-account-id "$SA_ID" \
  --environment "KOI_COLLAB_TOKEN_SECRET=${KOI_COLLAB_TOKEN_SECRET}"

python3 - "$DEPLOY/api-gateway.yaml" "$CONTAINER_ID" "$SA_ID" <<'PY'
import sys
from pathlib import Path
spec = Path(sys.argv[1]).read_text()
spec = spec.replace("__CONTAINER_ID__", sys.argv[2])
spec = spec.replace("__SERVICE_ACCOUNT_ID__", sys.argv[3])
Path(sys.argv[1] + ".rendered").write_text(spec)
PY

yc serverless api-gateway create --name "$GATEWAY_NAME" --folder-id "$FOLDER_ID" --spec "$DEPLOY/api-gateway.yaml.rendered" 2>/dev/null || \
  yc serverless api-gateway update --name "$GATEWAY_NAME" --folder-id "$FOLDER_ID" --spec "$DEPLOY/api-gateway.yaml.rendered"

GW_DOMAIN="$(yc serverless api-gateway get --name "$GATEWAY_NAME" --folder-id "$FOLDER_ID" --format json | python3 -c 'import json,sys; print(json.load(sys.stdin)["domain"])')"
echo
echo "Deployed signaling."
echo "Health:  https://${GW_DOMAIN}/health"
echo "Set both ResearcherOS machines to:"
echo "  KOI_COLLAB_SIGNALING_URL=wss://${GW_DOMAIN}/signal"
echo "  KOI_COLLAB_TOKEN_SECRET=<same secret used for this deploy>"
echo "Then restart KOI on both machines. Leave local LAN signaling off."
