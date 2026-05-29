"""Tests for the Meta webhook signature verifier.

The verifier is pure: bytes in, bool out. Tests cover the happy path
plus every failure mode that should produce ``False`` rather than a
raise (the route returns 403 on any False).
"""

from __future__ import annotations

import hashlib
import hmac

import pytest

from api.services.im.whatsapp.signature import verify_signature


def _sign(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def test_verifies_genuine_signature():
    secret = "test-app-secret-1234"
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    header = _sign(secret, body)
    assert verify_signature(raw_body=body, signature_header=header, app_secret=secret)


def test_rejects_tampered_body():
    secret = "test-app-secret-1234"
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    header = _sign(secret, body)
    tampered = body + b" "
    assert not verify_signature(
        raw_body=tampered, signature_header=header, app_secret=secret
    )


def test_rejects_wrong_secret():
    secret = "test-app-secret-1234"
    body = b'{"object":"whatsapp_business_account"}'
    header = _sign(secret, body)
    assert not verify_signature(
        raw_body=body, signature_header=header, app_secret="different-secret"
    )


@pytest.mark.parametrize(
    "bad_header",
    [
        None,
        "",
        "deadbeef",
        "sha1=" + "0" * 40,
        "sha256=",
        "SHA256=" + "0" * 64,  # case-sensitive prefix
    ],
)
def test_rejects_malformed_header(bad_header):
    body = b"{}"
    assert not verify_signature(
        raw_body=body, signature_header=bad_header, app_secret="secret"
    )


def test_rejects_empty_secret():
    body = b"{}"
    header = _sign("secret", body)
    assert not verify_signature(raw_body=body, signature_header=header, app_secret="")


def test_compare_digest_is_used():
    """Regression guard against switching to ``==`` later — verify that
    a near-miss (one hex digit changed) still rejects.
    """
    secret = "secret"
    body = b'{"object":"whatsapp_business_account"}'
    real = _sign(secret, body)
    # Flip the last hex digit of the digest.
    last = real[-1]
    flipped_char = "0" if last != "0" else "1"
    near_miss = real[:-1] + flipped_char
    assert not verify_signature(
        raw_body=body, signature_header=near_miss, app_secret=secret
    )
