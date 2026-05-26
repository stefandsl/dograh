"""SIP URI parsing helper for the MessageNet provider.

A SIP URI has the shape ``sip:user@host[:port][;params][?headers]`` (or
``sips:`` for TLS). The Python stdlib doesn't have a SIP-aware parser, so
this module provides a small, focused one — just enough to:

* validate that the URI is well-formed at save time
* derive a default ``username`` (the user part) when none is supplied
* hand parts to the SIP gateway when registering or originating
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


class SipUriError(ValueError):
    """Raised when a SIP URI cannot be parsed."""


@dataclass(frozen=True)
class ParsedSipUri:
    scheme: str  # "sip" or "sips"
    user: str
    host: str
    port: Optional[int] = None


def parse_sip_uri(uri: str) -> ParsedSipUri:
    """Parse ``sip:user@host[:port]`` (or ``sips:``) into its parts.

    Trailing ``;params`` and ``?headers`` are ignored — they're valid SIP
    URI components but the MessageNet trunk config doesn't use them.
    """
    if not isinstance(uri, str) or not uri.strip():
        raise SipUriError("SIP URI must be a non-empty string")

    value = uri.strip()
    scheme, sep, rest = value.partition(":")
    if not sep:
        raise SipUriError(f"SIP URI missing scheme separator ':' in {value!r}")
    scheme = scheme.lower()
    if scheme not in {"sip", "sips"}:
        raise SipUriError(f"Unsupported SIP URI scheme {scheme!r}; expected sip or sips")

    # Strip optional ;params and ?headers from the right side.
    for sentinel in (";", "?"):
        idx = rest.find(sentinel)
        if idx != -1:
            rest = rest[:idx]

    if "@" not in rest:
        raise SipUriError(
            f"SIP URI must contain user@host (got {uri!r}); "
            f"example: sip:5000000@sip.messagenet.it"
        )
    user, _, hostport = rest.partition("@")
    if not user:
        raise SipUriError(f"SIP URI user part is empty in {uri!r}")
    if not hostport:
        raise SipUriError(f"SIP URI host part is empty in {uri!r}")

    host = hostport
    port: Optional[int] = None
    if ":" in hostport:
        host, _, port_str = hostport.rpartition(":")
        if not host:
            raise SipUriError(f"SIP URI host part is empty in {uri!r}")
        try:
            port = int(port_str)
        except ValueError as exc:
            raise SipUriError(
                f"SIP URI port must be an integer (got {port_str!r}) in {uri!r}"
            ) from exc
        if not (1 <= port <= 65535):
            raise SipUriError(f"SIP URI port out of range (got {port}) in {uri!r}")

    return ParsedSipUri(scheme=scheme, user=user, host=host, port=port)
