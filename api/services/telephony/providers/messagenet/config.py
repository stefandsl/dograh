"""MessageNet SIP trunk telephony configuration schemas.

MessageNet is a SIP-trunking VoIP provider; the trunk is authenticated by a
SIP URI plus a SIP password. The user part of the URI doubles as the SIP
``username`` for digest auth, so we let admins leave ``username`` blank and
default it from the URI at load time.

Per the providers convention, both Request and Response carry
``provider: Literal["messagenet"]`` so Pydantic's discriminated union can
dispatch on it.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .sip_uri import SipUriError, parse_sip_uri


class MessagenetConfigurationRequest(BaseModel):
    """Save-request schema for a MessageNet SIP trunk."""

    provider: Literal["messagenet"] = Field(default="messagenet")
    sip_uri: str = Field(
        ...,
        description="SIP URI of the MessageNet trunk (e.g. sip:5000000@sip.messagenet.it).",
    )
    username: Optional[str] = Field(
        default=None,
        description="SIP auth username. Defaults to the user part of sip_uri if blank.",
    )
    password: str = Field(
        ...,
        min_length=1,
        description="SIP auth password. Sensitive — masked on read.",
    )
    from_numbers: List[str] = Field(
        default_factory=list,
        description="Caller IDs / DIDs allowed for outbound calls (optional).",
    )

    @field_validator("sip_uri")
    @classmethod
    def _validate_sip_uri(cls, value: str) -> str:
        # Surface a helpful 422 at save time rather than letting the gateway
        # complain about it during the first call attempt.
        try:
            parse_sip_uri(value)
        except SipUriError as exc:
            raise ValueError(str(exc)) from exc
        return value.strip()

    @field_validator("username")
    @classmethod
    def _normalize_username(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        stripped = value.strip()
        # Treat empty / whitespace-only as "use the URI default".
        return stripped or None


class MessagenetConfigurationResponse(BaseModel):
    """Read-response schema; ``password`` is masked by the routes layer."""

    provider: Literal["messagenet"] = Field(default="messagenet")
    sip_uri: str
    username: Optional[str] = None
    password: str  # Masked on the way out
    from_numbers: List[str] = Field(default_factory=list)
