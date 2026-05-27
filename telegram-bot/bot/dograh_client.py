"""Async HTTP client for the Dograh API.

Auth model is X-API-Key per ADR-102 — one service-account key per IM
channel. Phase 2 reads a single key from env; Phase 4 will load
per-channel keys from the ``im_channels`` secret-bundle endpoint.

Methods cover only what the bot needs through Phase 5. Endpoints are
the ones cataloged in ``docs/internal/merge-cliclaw/dograh-api-map.md``;
add more here, don't sprinkle ad-hoc httpx calls through the handlers.
"""

from __future__ import annotations

from typing import Any, Optional

import httpx
from loguru import logger


class DograhClientError(RuntimeError):
    """Raised when the Dograh API returns a non-2xx response."""

    def __init__(self, status: int, body: str):
        super().__init__(f"Dograh API {status}: {body[:200]}")
        self.status = status
        self.body = body


class DograhClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout: float = 15.0,
    ) -> None:
        if not base_url:
            raise ValueError("DograhClient requires base_url")
        self._base = base_url.rstrip("/")
        self._headers = {
            "X-API-Key": api_key,
            "User-Agent": "dograh-telegram-bot/0.1",
        }
        self._timeout = httpx.Timeout(timeout)
        self._client: Optional[httpx.AsyncClient] = None

    # --- lifecycle ---------------------------------------------------
    async def __aenter__(self) -> "DograhClient":
        self._client = httpx.AsyncClient(
            base_url=self._base,
            headers=self._headers,
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *_: Any) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError(
                "DograhClient must be used as async context manager"
            )
        return self._client

    # --- low level ---------------------------------------------------
    async def _request(
        self, method: str, path: str, **kwargs: Any
    ) -> dict[str, Any]:
        resp = await self._http().request(method, path, **kwargs)
        if resp.status_code >= 400:
            raise DograhClientError(resp.status_code, resp.text)
        if resp.headers.get("content-type", "").startswith("application/json"):
            return resp.json()
        return {"raw": resp.text}

    # --- endpoints (see dograh-api-map.md) ---------------------------
    async def health(self) -> dict[str, Any]:
        """``GET /api/v1/health`` — liveness + deployment-mode probe."""
        return await self._request("GET", "/api/v1/health")

    async def list_workflows_summary(self) -> list[dict[str, Any]]:
        """``GET /api/v1/workflow/summary`` — id+name list for the bot menu."""
        result = await self._request("GET", "/api/v1/workflow/summary")
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "workflows" in result:
            return result["workflows"]
        logger.warning(
            f"[DograhClient] /workflow/summary returned unexpected shape: "
            f"{type(result).__name__}"
        )
        return []

    async def create_workflow_run(
        self,
        workflow_id: int,
        initial_context: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """``POST /api/v1/workflow/{id}/runs`` — start a manual run."""
        body: dict[str, Any] = {"initial_context": initial_context or {}}
        return await self._request(
            "POST",
            f"/api/v1/workflow/{workflow_id}/runs",
            json=body,
        )

    async def get_workflow_run(
        self, workflow_id: int, run_id: int
    ) -> dict[str, Any]:
        """``GET /api/v1/workflow/{id}/runs/{run_id}``."""
        return await self._request(
            "GET", f"/api/v1/workflow/{workflow_id}/runs/{run_id}"
        )

    async def request_web_call_link(
        self, *, workflow_id: int, telegram_chat_id: int
    ) -> dict[str, Any]:
        """``POST /api/v1/telegram/web-call-link`` — see ADR-101.

        Returns ``{ url, workflow_run_id, expires_in_seconds }``.
        The bot sends ``url`` to the user as a Telegram WebApp button.
        """
        return await self._request(
            "POST",
            "/api/v1/telegram/web-call-link",
            json={
                "workflow_id": workflow_id,
                "telegram_chat_id": telegram_chat_id,
            },
        )
