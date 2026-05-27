"""Asterisk ARI implementation of ``MessagenetSipGatewayClient``.

Originates calls into a Stasis app via the ARI REST surface; trunk
registration is owned by Asterisk's PJSIP config (see the deployment
guide for the ``[messagenet]`` registration/auth/aor/endpoint blocks).
The Stasis app pipes answered audio into ``chan_websocket`` pointed at
the Dograh MessageNet WebSocket endpoint, where ``AsteriskFrameSerializer``
takes over.

Wired in at startup by :func:`messagenet.wiring.install_messagenet_gateway`
when ``MESSAGENET_GATEWAY_BACKEND=asterisk-ari``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

import aiohttp

from ..sip_gateway import (
    GatewayCallHandle,
    MessagenetGatewayNotConfigured,
    MessagenetTrunkCredentials,
)


@dataclass(frozen=True)
class AsteriskARIGateway:
    base_url: str
    app_name: str
    ari_user: str
    ari_password: str
    pjsip_endpoint: str

    @classmethod
    def from_env(cls) -> "AsteriskARIGateway":
        try:
            return cls(
                base_url=os.environ["ARI_BASE_URL"].rstrip("/"),
                app_name=os.environ["ARI_APP_NAME"],
                ari_user=os.environ["ARI_USER"],
                ari_password=os.environ["ARI_PASSWORD"],
                pjsip_endpoint=os.getenv("MESSAGENET_PJSIP_ENDPOINT", "messagenet"),
            )
        except KeyError as exc:
            raise MessagenetGatewayNotConfigured(
                f"Missing env var for Asterisk ARI gateway: {exc.args[0]}"
            ) from exc

    def _auth(self) -> aiohttp.BasicAuth:
        return aiohttp.BasicAuth(self.ari_user, self.ari_password)

    async def register_trunk(self, credentials: MessagenetTrunkCredentials) -> None:
        # Registration is owned by Asterisk PJSIP config; nothing to do
        # at runtime. See docs for the ``[messagenet]`` PJSIP blocks.
        return None

    async def originate_call(
        self,
        *,
        credentials: MessagenetTrunkCredentials,
        to_number: str,
        from_number: Optional[str],
        workflow_run_id: Optional[int],
    ) -> GatewayCallHandle:
        # SIP URI form so we don't depend on a dialplan rewrite for the
        # destination; the registered PJSIP endpoint anchors the trunk.
        endpoint = (
            f"PJSIP/sip:{to_number}@{credentials.sip_uri.host}"
            f"/{self.pjsip_endpoint}"
        )
        params = {
            "endpoint": endpoint,
            "app": self.app_name,
            "appArgs": f"workflow_run_id={workflow_run_id or ''}",
        }
        if from_number:
            params["callerId"] = from_number

        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/ari/channels",
                params=params,
                auth=self._auth(),
            ) as resp:
                body = await resp.json()
                if resp.status != 200:
                    raise RuntimeError(
                        f"ARI originate failed: HTTP {resp.status} {body}"
                    )
                return GatewayCallHandle(
                    call_id=body["id"],
                    status=body.get("state", "originated"),
                    raw=body,
                )

    async def accept_inbound_call(self, call_id: str) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/ari/channels/{call_id}/answer",
                auth=self._auth(),
            ) as resp:
                if resp.status not in (200, 204):
                    raise RuntimeError(
                        f"ARI answer failed: HTTP {resp.status} "
                        f"{await resp.text()}"
                    )

    async def hangup(self, call_id: str) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{self.base_url}/ari/channels/{call_id}",
                auth=self._auth(),
            ) as resp:
                # 404 means the channel is already gone — treat as success.
                if resp.status not in (204, 404):
                    raise RuntimeError(
                        f"ARI hangup failed: HTTP {resp.status} "
                        f"{await resp.text()}"
                    )

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/ari/channels/{call_id}",
                auth=self._auth(),
            ) as resp:
                if resp.status == 404:
                    return {"call_id": call_id, "status": "completed"}
                if resp.status != 200:
                    raise RuntimeError(
                        f"ARI status failed: HTTP {resp.status} "
                        f"{await resp.text()}"
                    )
                data = await resp.json()
                return {
                    "call_id": data["id"],
                    "status": data.get("state", "unknown"),
                    "raw": data,
                }
