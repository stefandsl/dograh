"""3CX Call Control API implementation of ``MessagenetSipGatewayClient``.

3CX acts as the SBC: MessageNet is provisioned as an upstream SIP trunk
inside 3CX, and this client uses the 3CX Call Control API to originate
calls onto that trunk. Audio reaches Dograh via the 3CX media bridge
exposed as a WebSocket externalMedia leg.

Caveat: the Call Control API surface varies by 3CX version/edition. The
endpoint shapes below match the v18 reference; verify against your
deployment's API docs. If your 3CX edition does not expose the Call
Control API, prefer trunk-mode — point 3CX at an Asterisk box and use
:mod:`asterisk_ari` instead.

Wired in at startup by :func:`messagenet.wiring.install_messagenet_gateway`
when ``MESSAGENET_GATEWAY_BACKEND=3cx``.
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
class ThreeCXGateway:
    base_url: str
    api_token: str
    trunk_name: str
    extension: str

    @classmethod
    def from_env(cls) -> "ThreeCXGateway":
        try:
            return cls(
                base_url=os.environ["THREECX_BASE_URL"].rstrip("/"),
                api_token=os.environ["THREECX_API_TOKEN"],
                trunk_name=os.environ["THREECX_MESSAGENET_TRUNK"],
                extension=os.environ["THREECX_DOGRAH_EXTENSION"],
            )
        except KeyError as exc:
            raise MessagenetGatewayNotConfigured(
                f"Missing env var for 3CX gateway: {exc.args[0]}"
            ) from exc

    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}"}

    async def register_trunk(self, credentials: MessagenetTrunkCredentials) -> None:
        # 3CX owns trunk registration via its admin UI; nothing runtime.
        return None

    async def originate_call(
        self,
        *,
        credentials: MessagenetTrunkCredentials,
        to_number: str,
        from_number: Optional[str],
        workflow_run_id: Optional[int],
    ) -> GatewayCallHandle:
        payload = {
            "extension": self.extension,
            "destination": to_number,
            "trunk": self.trunk_name,
            "callerId": from_number or "",
            "tag": f"dograh:wfr={workflow_run_id or ''}",
        }
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.base_url}/callcontrol/calls",
                json=payload,
                headers=self._headers(),
            ) as resp:
                body = await resp.json()
                if resp.status not in (200, 201):
                    raise RuntimeError(
                        f"3CX originate failed: HTTP {resp.status} {body}"
                    )
                return GatewayCallHandle(
                    call_id=str(body["id"]),
                    status=body.get("state", "originated"),
                    raw=body,
                )

    async def accept_inbound_call(self, call_id: str) -> None:
        # 3CX auto-answers calls routed into an API-bound extension when
        # the extension profile is "available". Nothing to do here.
        return None

    async def hangup(self, call_id: str) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{self.base_url}/callcontrol/calls/{call_id}",
                headers=self._headers(),
            ) as resp:
                if resp.status not in (200, 204, 404):
                    raise RuntimeError(
                        f"3CX hangup failed: HTTP {resp.status} {await resp.text()}"
                    )

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{self.base_url}/callcontrol/calls/{call_id}",
                headers=self._headers(),
            ) as resp:
                if resp.status == 404:
                    return {"call_id": call_id, "status": "completed"}
                if resp.status != 200:
                    raise RuntimeError(
                        f"3CX status failed: HTTP {resp.status} {await resp.text()}"
                    )
                return await resp.json()
