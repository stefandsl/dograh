"""Fernet-signed short-TTL token for the Telegram WebApp "Voice Call" button.

ADR-101: when the user taps **🎙️ Voice Call** in the bot, the bot calls
``POST /api/v1/telegram/web-call-link`` which creates a workflow_run
and returns a URL like ``https://<host>/embed/<token>``. The token is
this module's payload, signed with Fernet, TTL 5 minutes by default.

The master key is derived from ``OSS_JWT_SECRET`` — no new env var.
Fernet wants exactly 32 url-safe-base64 bytes, so we hash the secret
with SHA-256 and base64url-encode it.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

from api.constants import OSS_JWT_SECRET


_DEFAULT_TTL_SECONDS = 5 * 60


def _derive_fernet_key(master: str) -> bytes:
    """Turn an arbitrary secret string into a Fernet-compatible key."""
    digest = hashlib.sha256(master.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_FERNET = Fernet(_derive_fernet_key(OSS_JWT_SECRET))


@dataclass(frozen=True)
class WebCallLinkPayload:
    workflow_id: int
    user_id: int
    workflow_run_id: int
    telegram_chat_id: int
    issued_at: int  # unix seconds
    ttl_seconds: int = _DEFAULT_TTL_SECONDS

    def expired(self, now: Optional[int] = None) -> bool:
        return (now or int(time.time())) > self.issued_at + self.ttl_seconds


def sign(
    *,
    workflow_id: int,
    user_id: int,
    workflow_run_id: int,
    telegram_chat_id: int,
    ttl_seconds: int = _DEFAULT_TTL_SECONDS,
) -> str:
    """Encode the payload and return a URL-safe Fernet token."""
    payload = {
        "wf": workflow_id,
        "u": user_id,
        "r": workflow_run_id,
        "c": telegram_chat_id,
        "iat": int(time.time()),
        "ttl": ttl_seconds,
    }
    return _FERNET.encrypt(json.dumps(payload, separators=(",", ":")).encode()).decode()


def verify(token: str) -> WebCallLinkPayload:
    """Decode + validate; raises ValueError on bad/expired/tampered tokens."""
    try:
        raw = _FERNET.decrypt(token.encode())
    except InvalidToken as exc:
        raise ValueError("invalid or tampered web-call link") from exc
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("web-call link payload is not valid JSON") from exc

    payload = WebCallLinkPayload(
        workflow_id=int(body["wf"]),
        user_id=int(body["u"]),
        workflow_run_id=int(body["r"]),
        telegram_chat_id=int(body["c"]),
        issued_at=int(body["iat"]),
        ttl_seconds=int(body.get("ttl", _DEFAULT_TTL_SECONDS)),
    )
    if payload.expired():
        raise ValueError("web-call link expired")
    return payload
