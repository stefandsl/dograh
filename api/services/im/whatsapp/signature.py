"""Meta webhook signature verification.

Meta signs every webhook payload with HMAC-SHA256(app_secret, raw_body)
and sends the hex digest in the ``X-Hub-Signature-256`` header as
``"sha256=<hexdigest>"``. We verify against the *raw* body bytes — any
JSON-decode-then-re-encode round trip would invalidate the signature
because Meta's encoder ordering and whitespace are not guaranteed to
match Python's.

Use ``hmac.compare_digest`` for constant-time comparison so a hostile
attacker can't probe the signature byte-by-byte via timing.
"""

from __future__ import annotations

import hashlib
import hmac


def verify_signature(
    *, raw_body: bytes, signature_header: str | None, app_secret: str
) -> bool:
    """Return True iff ``signature_header`` matches HMAC-SHA256(app_secret, raw_body).

    Args:
        raw_body: The exact body bytes received from Meta. Must not be the
            decoded/re-encoded JSON.
        signature_header: The value of the ``X-Hub-Signature-256`` header
            verbatim. May be ``None`` (rejected).
        app_secret: The per-channel Meta App Secret stored in the
            ``im_channels`` encrypted config blob.

    Returns:
        ``True`` if the signature is present, well-formed, and matches.
        ``False`` for any failure mode — caller should treat False as
        "reject the request" and not retry.
    """
    if not signature_header or not app_secret:
        return False
    if not signature_header.startswith("sha256="):
        return False

    received = signature_header.removeprefix("sha256=").strip().lower()
    if not received:
        return False

    expected = hmac.new(
        app_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, received)
