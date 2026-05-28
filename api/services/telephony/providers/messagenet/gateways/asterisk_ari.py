"""Asterisk ARI implementation of ``MessagenetSipGatewayClient``.

Outbound flow:

1. ``originate_call`` does a single ``POST /channels`` with
   ``app=dograh-messagenet`` and the PJSIP endpoint, so the channel
   enters Stasis as soon as MessageNet answers. The outbound INVITE
   carries a proper SDP (``m=audio``) — this depends on Asterisk
   having ``res_pjsip_sdp_rtp.so`` loaded (see ``asterisk/modules.conf``).
2. The listener (:mod:`stasis_listener`) handles the StasisStart event:
   answer the channel, create the externalMedia leg, bridge the two.

Trunk registration is owned by Asterisk's PJSIP config (see the
deployment guide for the ``[messagenet]`` registration/auth/aor/endpoint
blocks); we only orchestrate channels here.

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
    ws_client_name: str = "dograh-ws"

    @classmethod
    def from_env(cls) -> "AsteriskARIGateway":
        try:
            return cls(
                base_url=os.environ["ARI_BASE_URL"].rstrip("/"),
                app_name=os.environ["ARI_APP_NAME"],
                ari_user=os.environ["ARI_USER"],
                ari_password=os.environ["ARI_PASSWORD"],
                pjsip_endpoint=os.getenv("MESSAGENET_PJSIP_ENDPOINT", "messagenet"),
                ws_client_name=os.getenv("MESSAGENET_WS_CLIENT_NAME", "dograh-ws"),
            )
        except KeyError as exc:
            raise MessagenetGatewayNotConfigured(
                f"Missing env var for Asterisk ARI gateway: {exc.args[0]}"
            ) from exc

    def _auth(self) -> aiohttp.BasicAuth:
        return aiohttp.BasicAuth(self.ari_user, self.ari_password)

    async def _ari(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/ari{path}"
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, params=params, auth=self._auth()
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise RuntimeError(
                        f"ARI {method} {path} failed: HTTP {resp.status} {text}"
                    )
                if not text:
                    return {}
                try:
                    import json

                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw": text}

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
        workflow_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> GatewayCallHandle:
        # Simple originate-into-Stasis pattern. With res_pjsip_sdp_rtp.so
        # loaded, chan_pjsip allocates the audio stream up front and the
        # outbound INVITE carries a proper SDP with m=audio. Listener
        # handles externalMedia + bridge on StasisStart.
        endpoint = f"PJSIP/{to_number}@{self.pjsip_endpoint}"
        # ARI defaults originate timeout to 30s, which is too tight for
        # international PSTN — 183 Session Progress arrives, the destination
        # rings for a few seconds, the phone is in a pocket / on silent,
        # and we CANCEL before anyone can pick up. 60s is a more humane
        # ring-out window; override via MESSAGENET_ORIGINATE_TIMEOUT.
        timeout = int(os.getenv("MESSAGENET_ORIGINATE_TIMEOUT", "60"))
        params: Dict[str, Any] = {
            "endpoint": endpoint,
            "app": self.app_name,
            "appArgs": (
                f"workflow_run_id={workflow_run_id or ''},"
                f"workflow_id={workflow_id or ''},"
                f"user_id={user_id or ''}"
            ),
            "timeout": timeout,
        }
        if from_number:
            params["callerId"] = from_number
        body = await self._ari("POST", "/channels", params=params)
        return GatewayCallHandle(
            call_id=body["id"],
            status=body.get("state", "originated"),
            raw=body,
        )

    async def accept_inbound_call(self, call_id: str) -> None:
        await self._ari("POST", f"/channels/{call_id}/answer")

    async def hangup(self, call_id: str) -> None:
        try:
            await self._ari("DELETE", f"/channels/{call_id}")
        except RuntimeError as exc:
            # 404 means the channel is already gone — treat as success.
            if "HTTP 404" not in str(exc):
                raise

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        try:
            data = await self._ari("GET", f"/channels/{call_id}")
        except RuntimeError as exc:
            if "HTTP 404" in str(exc):
                return {"call_id": call_id, "status": "completed"}
            raise
        return {
            "call_id": data["id"],
            "status": data.get("state", "unknown"),
            "raw": data,
        }
