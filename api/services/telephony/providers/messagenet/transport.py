"""Transport factory for MessageNet calls.

MessageNet SIP/RTP is bridged into Dograh by a SIP/media gateway (see
``sip_gateway.py``); the WebSocket leg between Dograh and that gateway
carries audio in the same chan_websocket framing ARI uses. This factory
loads the org's trunk credentials lazily and wires up a
``FastAPIWebsocketTransport`` around the gateway's audio stream.

Phase-1 caveat: when no real gateway is wired up, the provider rejects
``initiate_call`` at HTTP time (HTTP 503) so we should never actually
reach the WebSocket layer in production. The transport is here so the
provider satisfies the registry contract and is ready for the gateway
swap-in.
"""

import os
from typing import Optional

from fastapi import WebSocket
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

from api.services.pipecat.audio_config import AudioConfig
from api.services.pipecat.audio_mixer import build_audio_out_mixer
from api.services.pipecat.transport_params import realtime_param_overrides
from api.services.telephony.factory import load_credentials_for_transport

from .serializers import AsteriskFrameSerializer
from .sip_uri import parse_sip_uri


async def create_transport(
    websocket: WebSocket,
    workflow_run_id: int,
    audio_config: AudioConfig,
    organization_id: int,
    *,
    ambient_noise_config: Optional[dict] = None,
    telephony_configuration_id: Optional[int] = None,
    is_realtime: bool = False,
    call_id: str = "",
):
    """Create a transport for an active MessageNet call.

    Credentials are loaded *lazily* via
    ``load_credentials_for_transport`` — the workflow run carries
    ``telephony_configuration_id`` in its initial context so multi-trunk
    orgs land on the right row.
    """
    config = await load_credentials_for_transport(
        organization_id,
        telephony_configuration_id,
        expected_provider="messagenet",
    )

    sip_uri = config.get("sip_uri")
    password = config.get("password")
    if not sip_uri or not password:
        raise ValueError(
            f"Incomplete MessageNet configuration for organization {organization_id}. "
            f"Required: sip_uri, password"
        )

    # Validate at transport-build time too — defends against stored rows
    # that were created before the validator existed.
    parse_sip_uri(sip_uri)

    # AsteriskFrameSerializer needs ARI creds so its transfer/hangup
    # strategies can call back into Asterisk. For messagenet the ARI
    # endpoint is deployment-level (configured via env, not per-org),
    # so pull straight from os.environ here. Empty strings are fine if
    # transfer/hangup never gets used.
    serializer = AsteriskFrameSerializer(
        channel_id=call_id,
        ari_endpoint=os.getenv("ARI_BASE_URL", ""),
        app_name=os.getenv("ARI_APP_NAME", "dograh-messagenet"),
        app_password=os.getenv("ARI_PASSWORD", ""),
        params=AsteriskFrameSerializer.InputParams(
            asterisk_sample_rate=audio_config.transport_in_sample_rate,
            sample_rate=audio_config.pipeline_sample_rate,
        ),
    )

    mixer = await build_audio_out_mixer(
        audio_config.transport_out_sample_rate, ambient_noise_config
    )

    return FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=audio_config.transport_in_sample_rate,
            audio_out_sample_rate=audio_config.transport_out_sample_rate,
            audio_out_mixer=mixer,
            serializer=serializer,
            **realtime_param_overrides(is_realtime),
        ),
    )
