"""Tests for the IM channel encryption + masking helpers.

DB-side operations (create/update/delete/rotate) are covered by the
api's existing integration test rig (Phase 8 wires them into the
e2e workflow); here we cover the pure functions to keep the unit suite
fast and DB-free.
"""

import importlib

import pytest


@pytest.fixture
def fresh_module(monkeypatch):
    monkeypatch.setenv("OSS_JWT_SECRET", "test-secret-12345")
    import api.constants
    importlib.reload(api.constants)
    import api.services.im.encryption as enc
    importlib.reload(enc)
    import api.services.im.channel_service as svc
    importlib.reload(svc)
    return svc


def test_encrypt_then_decrypt_roundtrip(fresh_module):
    svc = fresh_module
    payload = {
        "bot_token": "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ",
        "allowed_user_ids": [111, 222],
        "api_key": "sk-test-deadbeef",
    }
    cipher = svc.encrypt_config(payload)
    assert isinstance(cipher, str)
    assert "bot_token" not in cipher  # not plaintext
    assert svc.decrypt_config(cipher) == payload


def test_decrypt_rejects_garbage(fresh_module):
    svc = fresh_module
    with pytest.raises(Exception):
        svc.decrypt_config("not-a-real-fernet-token")


def test_record_to_public_dict_masks_token(fresh_module):
    svc = fresh_module
    record = svc.ImChannelRecord(
        id=7,
        organization_id=3,
        type="telegram",
        name="bot1",
        enabled=True,
        api_key_id=42,
        config={
            "bot_token": "1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ",
            "allowed_user_ids": [111],
            "api_key": "sk-test-deadbeef",
        },
    )
    pub = record.to_public_dict()
    assert pub["config"]["bot_token"].startswith("***")
    # Last 6 chars preserved for visual id, not the whole thing.
    assert pub["config"]["bot_token"].endswith("vwxYZ"[-3:])
    # api_key is intentionally still in the public dict here — the route
    # layer maps to TelegramChannelResponse which doesn't expose it.
    assert pub["config"]["allowed_user_ids"] == [111]


def test_record_masking_handles_empty_token(fresh_module):
    svc = fresh_module
    record = svc.ImChannelRecord(
        id=1,
        organization_id=1,
        type="telegram",
        name="empty",
        enabled=False,
        api_key_id=None,
        config={"bot_token": "", "allowed_user_ids": []},
    )
    pub = record.to_public_dict()
    # Empty token shouldn't crash and shouldn't be masked into "***".
    assert pub["config"]["bot_token"] == ""
