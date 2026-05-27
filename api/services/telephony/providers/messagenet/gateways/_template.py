"""Template ``MessagenetSipGatewayClient`` — copy when adding a backend.

Copy this file to ``gateways/<your_backend>.py`` and fill in each TODO.
Keep all backend-specific code in this module — never let it leak into
the provider package.

Once implemented, register the backend by adding a branch to
:func:`messagenet.wiring.install_messagenet_gateway`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..sip_gateway import (
    GatewayCallHandle,
    MessagenetGatewayNotConfigured,
    MessagenetTrunkCredentials,
)


@dataclass(frozen=True)
class MyGateway:
    # TODO: minimal connection params for your backend (URL, token, etc.)
    base_url: str
    api_token: str

    @classmethod
    def from_env(cls) -> "MyGateway":
        try:
            return cls(
                base_url=os.environ["MYGW_BASE_URL"].rstrip("/"),
                api_token=os.environ["MYGW_API_TOKEN"],
            )
        except KeyError as exc:
            raise MessagenetGatewayNotConfigured(
                f"Missing env var for MyGateway: {exc.args[0]}"
            ) from exc

    async def register_trunk(self, credentials: MessagenetTrunkCredentials) -> None:
        # TODO: register, or noop if your backend pulls creds from its own config.
        raise NotImplementedError

    async def originate_call(
        self,
        *,
        credentials: MessagenetTrunkCredentials,
        to_number: str,
        from_number: Optional[str],
        workflow_run_id: Optional[int],
    ) -> GatewayCallHandle:
        # TODO: place the outbound leg on the MessageNet trunk and return
        # an opaque call id the backend understands.
        raise NotImplementedError

    async def accept_inbound_call(self, call_id: str) -> None:
        # TODO: answer, or noop if the backend auto-answers.
        raise NotImplementedError

    async def hangup(self, call_id: str) -> None:
        # TODO: terminate the call.
        raise NotImplementedError

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        # TODO: return at minimum {"call_id": ..., "status": ...}.
        raise NotImplementedError
