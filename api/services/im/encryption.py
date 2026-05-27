"""Shared Fernet key derivation for IM channel services.

Both ``web_call_link`` (Phase 3) and ``channel_service`` (Phase 4) need
to symmetrically encrypt small payloads. The master key is derived from
``OSS_JWT_SECRET`` so deployments don't have to manage a second secret.

Fernet wants exactly 32 url-safe-base64 bytes; SHA-256(secret) →
base64url gives us that.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from api.constants import OSS_JWT_SECRET


def _derive_fernet_key(master: str) -> bytes:
    digest = hashlib.sha256(master.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


# Module-level singleton. Tests that need a different key reload this
# module after patching OSS_JWT_SECRET (see api/tests/im/...).
fernet = Fernet(_derive_fernet_key(OSS_JWT_SECRET))
