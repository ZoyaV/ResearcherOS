"""Send text frames to Yandex API Gateway WebSocket connections."""

from __future__ import annotations

import base64
import json
import os
import time
from typing import Any

import httpx

SEND_URL = (
    "https://apigateway-connections.api.cloud.yandex.net"
    "/apigateways/websocket/v1/connections/{connection_id}:send"
)
METADATA_TOKEN_URL = (
    "http://169.254.169.254/computeMetadata/v1/instance/service-accounts/default/token"
)

_token = ""
_token_exp = 0.0


async def _iam_token() -> str:
    global _token, _token_exp
    override = os.environ.get("YC_IAM_TOKEN", "").strip()
    if override:
        return override
    now = time.time()
    if _token and now < _token_exp - 60:
        return _token
    async with httpx.AsyncClient(timeout=5) as client:
        response = await client.get(
            METADATA_TOKEN_URL,
            headers={"Metadata-Flavor": "Google"},
        )
        response.raise_for_status()
        payload = response.json()
    _token = str(payload.get("access_token") or "")
    _token_exp = now + float(payload.get("expires_in") or 300)
    if not _token:
        raise RuntimeError("empty IAM token from metadata service")
    return _token


async def send_apigw_json(connection_id: str, payload: dict[str, Any]) -> None:
    if not connection_id:
        return
    token = await _iam_token()
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    async with httpx.AsyncClient(timeout=8) as client:
        response = await client.post(
            SEND_URL.format(connection_id=connection_id),
            headers={"Authorization": f"Bearer {token}"},
            json={
                "type": "TEXT",
                "data": base64.b64encode(body.encode("utf-8")).decode("ascii"),
            },
        )
        response.raise_for_status()


class GatewaySocket:
    """Duck-typed sender used by SignalPeer in the API Gateway path."""

    def __init__(self, connection_id: str) -> None:
        self.connection_id = connection_id

    async def send_json(self, payload: dict[str, Any]) -> None:
        await send_apigw_json(self.connection_id, payload)
