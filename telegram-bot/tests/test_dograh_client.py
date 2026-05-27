"""Unit tests for ``DograhClient`` — httpx is mocked via MockTransport."""

import json

import httpx
import pytest

from bot.dograh_client import DograhClient, DograhClientError


def _build(handler):
    """Helper: builds an httpx.AsyncClient with a MockTransport handler.

    The DograhClient creates its own client in ``__aenter__``; for tests
    we patch _http() to return the test client instead.
    """
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


@pytest.fixture
def client(monkeypatch):
    captured = {}

    def make(handler):
        c = _build(handler)
        captured["client"] = c

        async def _aenter(self):
            self._client = c
            return self

        async def _aexit(self, *a):
            await c.aclose()

        monkeypatch.setattr(DograhClient, "__aenter__", _aenter)
        monkeypatch.setattr(DograhClient, "__aexit__", _aexit)
        return DograhClient(base_url="http://test", api_key="k")

    return make


@pytest.mark.asyncio
async def test_health_returns_json(client):
    async def handler(req):
        assert req.url.path == "/api/v1/health"
        return httpx.Response(200, json={"status": "ok"})

    async with client(handler) as c:
        out = await c.health()
        assert out == {"status": "ok"}


@pytest.mark.asyncio
async def test_list_workflows_summary_unwraps_dict(client):
    async def handler(req):
        return httpx.Response(
            200, json={"workflows": [{"id": 1, "name": "Foo"}]}
        )

    async with client(handler) as c:
        out = await c.list_workflows_summary()
        assert out == [{"id": 1, "name": "Foo"}]


@pytest.mark.asyncio
async def test_list_workflows_summary_accepts_list(client):
    async def handler(req):
        return httpx.Response(200, json=[{"id": 2, "name": "Bar"}])

    async with client(handler) as c:
        out = await c.list_workflows_summary()
        assert out[0]["id"] == 2


@pytest.mark.asyncio
async def test_create_workflow_run_posts_json(client):
    captured = {}

    async def handler(req):
        captured["path"] = req.url.path
        captured["body"] = json.loads(req.content)
        return httpx.Response(200, json={"id": 42, "state": "queued"})

    async with client(handler) as c:
        out = await c.create_workflow_run(7, {"caller": "+39..."})
        assert out["id"] == 42
        assert captured["path"] == "/api/v1/workflow/7/runs"
        assert captured["body"] == {"initial_context": {"caller": "+39..."}}


@pytest.mark.asyncio
async def test_error_raises_typed_exception(client):
    async def handler(req):
        return httpx.Response(404, text="not found")

    async with client(handler) as c:
        with pytest.raises(DograhClientError) as ei:
            await c.get_workflow_run(1, 2)
        assert ei.value.status == 404
        assert "not found" in ei.value.body


@pytest.mark.asyncio
async def test_requires_context_manager():
    c = DograhClient(base_url="http://test", api_key="k")
    with pytest.raises(RuntimeError):
        await c.health()
