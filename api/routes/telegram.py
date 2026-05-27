"""Telegram-bot-facing API surface (lives next to other IM channels in
Phase 4).

Current endpoints:
- ``POST /api/v1/telegram/web-call-link`` — body
  ``{workflow_id, telegram_chat_id}``. Creates a manual workflow run
  scoped to the caller's org (X-API-Key auth) and returns a signed
  short-TTL URL the bot sends as a Telegram WebApp button.

The redirect/landing endpoint that decodes the token is intentionally
deferred to Phase 5 (where the menu wires the button end-to-end); Phase
3 ships the signer + endpoint so the bot has something to call.
"""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from loguru import logger
from pydantic import BaseModel, Field

from api.db import db_client
from api.enums import WorkflowRunMode
from api.services.auth.depends import get_user
from api.services.im.web_call_link import sign


router = APIRouter(prefix="/telegram", tags=["telegram"])


class WebCallLinkRequest(BaseModel):
    workflow_id: int = Field(..., description="Dograh workflow id to dial into.")
    telegram_chat_id: int = Field(
        ...,
        description="The Telegram chat the bot is conversing in — included "
                    "so the token is bound to one chat and can't be reused "
                    "from a different chat by accident.",
    )


class WebCallLinkResponse(BaseModel):
    url: str
    workflow_run_id: int
    expires_in_seconds: int


@router.post(
    "/web-call-link",
    response_model=WebCallLinkResponse,
    summary="Mint a signed WebApp URL for a Telegram voice-call button.",
)
async def create_web_call_link(
    req: WebCallLinkRequest,
    request: Request,
    user=Depends(get_user),
) -> WebCallLinkResponse:
    # 1. Verify the workflow belongs to the caller's org.
    workflow = await db_client.get_workflow(
        req.workflow_id, organization_id=user.selected_organization_id
    )
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow_not_found")

    # 2. Create a manual workflow run for this chat.
    workflow_run = await db_client.create_workflow_run(
        name=f"Telegram WebApp call {req.telegram_chat_id}",
        workflow_id=req.workflow_id,
        mode=WorkflowRunMode.SMALLWEBRTC.value,
        user_id=workflow.user_id,
        initial_context={
            "telegram_chat_id": req.telegram_chat_id,
            "source": "telegram-webapp",
        },
    )

    # 3. Sign + return.
    ttl = int(os.getenv("TELEGRAM_WEBCALL_TTL_SECONDS", "300"))
    token = sign(
        workflow_id=req.workflow_id,
        user_id=workflow.user_id,
        workflow_run_id=workflow_run.id,
        telegram_chat_id=req.telegram_chat_id,
        ttl_seconds=ttl,
    )
    base = (
        os.getenv("DOGRAH_PUBLIC_URL")
        or str(request.base_url).rstrip("/")
    ).rstrip("/")
    url = f"{base}/api/v1/telegram/web-call/{token}"

    logger.info(
        f"[telegram/web-call-link] minted run {workflow_run.id} for "
        f"workflow {req.workflow_id} chat {req.telegram_chat_id} ttl={ttl}s"
    )
    return WebCallLinkResponse(
        url=url,
        workflow_run_id=workflow_run.id,
        expires_in_seconds=ttl,
    )
