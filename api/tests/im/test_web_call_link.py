"""Tests for the Fernet-signed web-call-link tokens.

Covers: round-trip, TTL boundary, tamper detection. The master key is
``OSS_JWT_SECRET`` so we monkey-patch it (and re-derive the singleton
Fernet) for deterministic test behaviour.
"""

import importlib
import time

import pytest


@pytest.fixture
def fresh_module(monkeypatch):
    """Reload the module so its Fernet key is rebuilt from a known secret."""
    monkeypatch.setenv("OSS_JWT_SECRET", "test-secret-12345")
    import api.constants
    importlib.reload(api.constants)
    import api.services.im.web_call_link as mod
    importlib.reload(mod)
    return mod


def test_sign_and_verify_roundtrip(fresh_module):
    mod = fresh_module
    token = mod.sign(
        workflow_id=42,
        user_id=7,
        workflow_run_id=99,
        telegram_chat_id=12345,
        ttl_seconds=300,
    )
    payload = mod.verify(token)
    assert payload.workflow_id == 42
    assert payload.user_id == 7
    assert payload.workflow_run_id == 99
    assert payload.telegram_chat_id == 12345
    assert not payload.expired()


def test_expired_token_rejected(fresh_module, monkeypatch):
    mod = fresh_module
    # Sign a token, then jump time forward past TTL.
    token = mod.sign(
        workflow_id=1,
        user_id=1,
        workflow_run_id=1,
        telegram_chat_id=1,
        ttl_seconds=1,
    )
    real_time = time.time

    def fake_time():
        return real_time() + 10

    monkeypatch.setattr(time, "time", fake_time)
    with pytest.raises(ValueError, match="expired"):
        mod.verify(token)


def test_tampered_token_rejected(fresh_module):
    mod = fresh_module
    token = mod.sign(
        workflow_id=1,
        user_id=1,
        workflow_run_id=1,
        telegram_chat_id=1,
    )
    # Flip a character in the middle of the token.
    tampered = token[:-2] + ("aa" if token[-2:] != "aa" else "bb")
    with pytest.raises(ValueError, match="invalid or tampered"):
        mod.verify(tampered)


def test_garbage_token_rejected(fresh_module):
    mod = fresh_module
    with pytest.raises(ValueError):
        mod.verify("not-a-real-token")
