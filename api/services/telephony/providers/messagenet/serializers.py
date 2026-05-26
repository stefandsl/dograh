"""Pipecat serializer re-export for the MessageNet transport.

MessageNet itself is a SIP trunk; Dograh reaches it through a SIP/media
gateway (Asterisk/PJSIP by default — see ``sip_gateway.py``). The wire
format on the WebSocket leg between Dograh and that gateway is the same
Asterisk ``chan_websocket`` audio frame format ARI uses, so we re-export
pipecat's ``AsteriskFrameSerializer`` here for the transport to consume.

Re-exporting from pipecat (not from another provider package) keeps the
"don't import another provider" rule intact — when a future deployment
swaps the gateway to something with a different on-the-wire format, only
this module changes.
"""

from pipecat.serializers.asterisk import AsteriskFrameSerializer

__all__ = ["AsteriskFrameSerializer"]
