"""Tests for the Meta Cloud API outbound client.

HTTP is mocked via ``httpx.MockTransport`` so no new test dep is needed.
We monkeypatch ``httpx.AsyncClient`` so the client used inside
``meta_client._post`` routes through our mock handler.
"""

from __future__ import annotations

import json
from typing import Any, Callable

import httpx
import pytest

from api.services.im.whatsapp import meta_client

_CFG = {
    "phone_number_id": "PNID-123",
    "access_token": "test-access-token",
    "graph_version": "v20.0",
}


def _patch_async_client(
    monkeypatch, handler: Callable[[httpx.Request], httpx.Response]
):
    """Replace ``httpx.AsyncClient`` with one wired to ``MockTransport(handler)``.

    Calls to ``AsyncClient(...)`` inside ``meta_client._post`` pick up
    ``transport=MockTransport(handler)`` and never hit the network.
    """
    original = httpx.AsyncClient

    def _factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", _factory)


@pytest.mark.asyncio
async def test_send_text_posts_correct_body_and_url(monkeypatch):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"messages": [{"id": "wamid.outbound.1"}]})

    _patch_async_client(monkeypatch, handler)

    result = await meta_client.send_text(config=_CFG, to="393450000000", text="Ciao!")

    assert result == {"messages": [{"id": "wamid.outbound.1"}]}
    assert captured["url"] == "https://graph.facebook.com/v20.0/PNID-123/messages"
    assert captured["headers"]["authorization"] == "Bearer test-access-token"
    assert captured["body"]["messaging_product"] == "whatsapp"
    assert captured["body"]["to"] == "393450000000"
    assert captured["body"]["type"] == "text"
    assert captured["body"]["text"] == {"body": "Ciao!", "preview_url": False}


@pytest.mark.asyncio
async def test_send_text_raises_meta_client_error_on_non_2xx(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"error": {"message": "outside customer window", "code": 131047}},
        )

    _patch_async_client(monkeypatch, handler)

    with pytest.raises(meta_client.MetaClientError) as exc_info:
        await meta_client.send_text(config=_CFG, to="393450000000", text="hi")

    assert exc_info.value.status_code == 400
    assert exc_info.value.meta_error == {
        "message": "outside customer window",
        "code": 131047,
    }


@pytest.mark.asyncio
async def test_send_template_includes_components_when_variables_given(monkeypatch):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={})

    _patch_async_client(monkeypatch, handler)

    await meta_client.send_template(
        config=_CFG,
        to="393450000000",
        template_name="appointment_reminder",
        language="it",
        variables=["Mario", "tomorrow at 10am"],
    )

    body = captured["body"]
    assert body["type"] == "template"
    assert body["template"]["name"] == "appointment_reminder"
    assert body["template"]["language"] == {"code": "it"}
    assert body["template"]["components"] == [
        {
            "type": "body",
            "parameters": [
                {"type": "text", "text": "Mario"},
                {"type": "text", "text": "tomorrow at 10am"},
            ],
        }
    ]


@pytest.mark.asyncio
async def test_send_template_omits_components_when_no_variables(monkeypatch):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={})

    _patch_async_client(monkeypatch, handler)

    await meta_client.send_template(
        config=_CFG,
        to="393450000000",
        template_name="hello_world",
        language="en_US",
        variables=None,
    )

    assert captured["body"]["template"]["components"] == []


@pytest.mark.asyncio
async def test_send_media_rejects_both_id_and_url():
    with pytest.raises(ValueError):
        await meta_client.send_media(
            config=_CFG,
            to="393450000000",
            media_type="image",
            media_id="MID",
            media_url="https://example.com/x.png",
        )


@pytest.mark.asyncio
async def test_send_media_rejects_neither_id_nor_url():
    with pytest.raises(ValueError):
        await meta_client.send_media(
            config=_CFG,
            to="393450000000",
            media_type="image",
        )


@pytest.mark.asyncio
async def test_send_media_audio_drops_caption(monkeypatch):
    """Audio doesn't accept a caption per Meta's spec."""
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={})

    _patch_async_client(monkeypatch, handler)

    await meta_client.send_media(
        config=_CFG,
        to="393450000000",
        media_type="audio",
        media_url="https://example.com/x.ogg",
        caption="I should be dropped",
    )

    body = captured["body"]
    assert body["audio"] == {"link": "https://example.com/x.ogg"}
    assert "caption" not in body["audio"]


@pytest.mark.asyncio
async def test_graph_version_overrides_default(monkeypatch):
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        return httpx.Response(200, json={})

    _patch_async_client(monkeypatch, handler)

    cfg = {**_CFG, "graph_version": "v21.0"}
    await meta_client.send_text(config=cfg, to="393450000000", text="hi")

    assert captured["url"] == "https://graph.facebook.com/v21.0/PNID-123/messages"
