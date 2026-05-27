"""Startup-time selection of the MessageNet SIP gateway backend.

Reads ``MESSAGENET_GATEWAY_BACKEND`` and installs the matching
implementation via :func:`sip_gateway.set_sip_gateway`. Unset (or
``stub``) keeps the default ``StubMessagenetSipGateway`` — outbound
calls then fail safely with HTTP 503 until a real backend is wired in.

Call :func:`install_messagenet_gateway` once during app startup
(FastAPI lifespan). Unknown backend names raise at startup so a typo
fails the deploy instead of silently falling back to stub.
"""

from __future__ import annotations

import os

from loguru import logger

from .sip_gateway import (
    MessagenetSipGatewayClient,
    StubMessagenetSipGateway,
    set_sip_gateway,
)


def install_messagenet_gateway() -> None:
    backend = (os.getenv("MESSAGENET_GATEWAY_BACKEND") or "stub").lower()

    client: MessagenetSipGatewayClient
    if backend == "asterisk-ari":
        from .gateways.asterisk_ari import AsteriskARIGateway

        client = AsteriskARIGateway.from_env()
    elif backend == "3cx":
        from .gateways.three_cx import ThreeCXGateway

        client = ThreeCXGateway.from_env()
    elif backend == "stub":
        client = StubMessagenetSipGateway()
    else:
        raise RuntimeError(
            f"Unknown MESSAGENET_GATEWAY_BACKEND={backend!r}; "
            f"expected one of: asterisk-ari, 3cx, stub"
        )

    set_sip_gateway(client)
    logger.info(f"[MessageNet] SIP gateway backend installed: {backend}")
