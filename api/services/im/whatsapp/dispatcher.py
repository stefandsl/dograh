"""Inbound WhatsApp message dispatcher.

Triggered from the webhook POST handler with a verified, parsed
``ParsedWebhook``. For each ``InboundMessage`` we:

1. Look up the owning channel (matched on ``phone_number_id``).
2. Ensure a session row exists for (org, channel, wa_id).
3. Dedupe by Meta message id — Meta retries for ~7 days on non-2xx /
   timeout responses, so the same message can land many times.
4. Ensure a workflow_run exists for the conversation. If the session has
   no active workflow set, we use the org's *first* active workflow as a
   safe default; admins can change the active workflow per conversation
   via a future ``/im/channels/whatsapp/.../set-workflow`` endpoint.
5. Append the user message to the text-chat session, run the pending
   assistant turn, pluck the reply text, and send it via the outbound
   Meta client. Errors at any step are logged and either reply with a
   safe fallback message or silently ack (Meta will not retry on 200).

Only ``text`` inbound is converted to a workflow turn for the MVP. Media
inbound (image, audio, etc.) is acked and the channel replies with a
"text only for now" hint — fully wiring audio in requires the STT/Whisper
plumbing the Telegram bot already has, which we'll port over in a
follow-up. Statuses (sent/delivered/read/failed) are logged for audit
but otherwise ignored.
"""

from __future__ import annotations

from typing import Any, Optional

from loguru import logger
from sqlalchemy import select

from api.db import db_client
from api.db.models import WorkflowModel
from api.enums import WorkflowRunMode
from api.services.im import channel_service
from api.services.im.whatsapp import meta_client, sessions
from api.services.im.whatsapp.inbound_parser import (
    DeliveryStatus,
    InboundMessage,
    ParsedWebhook,
)
from api.services.workflow.text_chat_session_service import (
    TextChatSessionExecutionError,
    append_text_chat_user_message,
    default_text_chat_checkpoint,
    default_text_chat_session_data,
    execute_pending_text_chat_turn,
    initialize_text_chat_session,
    normalize_text_chat_session_data,
)

_FALLBACK_REPLY = "Sorry, I had trouble answering that. Please try again in a moment."
_UNSUPPORTED_MEDIA_REPLY = (
    "I can only handle text messages right now. Could you type your question?"
)


async def dispatch(
    parsed: ParsedWebhook, *, channel_phone_number_id: Optional[str] = None
) -> None:
    """Top-level entry called from the webhook POST handler."""
    # Log statuses for audit — no action.
    for status in parsed.statuses:
        _log_status(status)

    # Group messages by phone_number_id to minimise channel lookups
    # within a single Meta delivery.
    by_pnid: dict[str, list[InboundMessage]] = {}
    for msg in parsed.messages:
        pnid = msg.channel_phone_number_id or (channel_phone_number_id or "")
        if not pnid:
            logger.warning("[whatsapp/dispatch] inbound has no channel pnid; skipping")
            continue
        by_pnid.setdefault(pnid, []).append(msg)

    for pnid, batch in by_pnid.items():
        channel = await channel_service.get_whatsapp_channel_by_phone_number_id(pnid)
        if channel is None:
            logger.warning(
                "[whatsapp/dispatch] no enabled channel for phone_number_id={pnid}; "
                "ignoring {n} messages",
                pnid=pnid,
                n=len(batch),
            )
            continue
        for msg in batch:
            try:
                await _dispatch_one(channel, msg)
            except Exception as exc:  # noqa: BLE001
                # Log but never re-raise — the webhook must ack 200 or
                # Meta will replay the entire delivery.
                logger.exception(
                    "[whatsapp/dispatch] failure on message_id={mid}: {exc!r}",
                    mid=msg.message_id,
                    exc=exc,
                )


async def _dispatch_one(channel, msg: InboundMessage) -> None:
    session = await sessions.get_or_create(
        organization_id=channel.organization_id,
        channel_id=channel.id,
        wa_id=msg.wa_id,
    )

    # 1. Dedupe.
    is_new = await sessions.mark_inbound_seen(
        organization_id=channel.organization_id,
        channel_id=channel.id,
        wa_id=msg.wa_id,
        message_id=msg.message_id,
    )
    if not is_new:
        logger.info(
            "[whatsapp/dispatch] duplicate message_id={mid} for wa_id={wa}; acking",
            mid=msg.message_id,
            wa=msg.wa_id,
        )
        return

    # 2. Non-text → quick "text only" reply and return.
    if msg.message_type != "text" or not msg.text:
        await _safe_send(channel, msg.wa_id, _UNSUPPORTED_MEDIA_REPLY)
        return

    # 3. Resolve / open the workflow run.
    workflow_id = session.get("workflow_id")
    if workflow_id is None:
        workflow_id = await _pick_default_workflow_id(channel.organization_id)
        if workflow_id is None:
            logger.warning(
                "[whatsapp/dispatch] no active workflow for org={org}; "
                "cannot dispatch message_id={mid}",
                org=channel.organization_id,
                mid=msg.message_id,
            )
            await _safe_send(channel, msg.wa_id, _FALLBACK_REPLY)
            return
        await sessions.set_active_workflow(
            organization_id=channel.organization_id,
            channel_id=channel.id,
            wa_id=msg.wa_id,
            workflow_id=workflow_id,
        )

    run_id = session.get("workflow_run_id")
    if run_id is None:
        workflow_run = await db_client.create_workflow_run(
            name=f"WhatsApp {msg.wa_id}",
            workflow_id=workflow_id,
            mode=WorkflowRunMode.TEXTCHAT.value,
            user_id=None,
            initial_context={
                "channel": "whatsapp",
                "wa_id": msg.wa_id,
                "channel_id": channel.id,
                "profile_name": msg.profile_name,
            },
            organization_id=channel.organization_id,
        )
        run_id = workflow_run.id
        await sessions.set_workflow_run(
            organization_id=channel.organization_id,
            channel_id=channel.id,
            wa_id=msg.wa_id,
            workflow_run_id=run_id,
        )
        # Brand new run — initialize the text session before the user
        # message goes in (mirrors workflow_text_chat.create_session).
        text_session = await db_client.ensure_workflow_run_text_session(
            run_id,
            session_data=default_text_chat_session_data(),
            checkpoint=default_text_chat_checkpoint(),
        )
        text_session = await initialize_text_chat_session(
            run_id=run_id, text_session=text_session
        )
    else:
        text_session = await db_client.get_workflow_run_text_session(
            run_id, organization_id=channel.organization_id
        )

    if text_session is None:
        await _safe_send(channel, msg.wa_id, _FALLBACK_REPLY)
        return

    # 4. Append + execute.
    text_session = await append_text_chat_user_message(
        run_id=run_id,
        text_session=text_session,
        user_text=msg.text,
        expected_revision=text_session.revision,
    )
    try:
        text_session = await execute_pending_text_chat_turn(
            workflow_id=workflow_id,
            run_id=run_id,
            text_session=text_session,
        )
    except TextChatSessionExecutionError as exc:
        logger.exception(
            "[whatsapp/dispatch] execution failed for run={run}: {exc}",
            run=run_id,
            exc=exc,
        )
        await _safe_send(channel, msg.wa_id, _FALLBACK_REPLY)
        return

    reply_text = _extract_latest_assistant_text(text_session.session_data)
    if not reply_text:
        await _safe_send(channel, msg.wa_id, _FALLBACK_REPLY)
        return
    await _safe_send(channel, msg.wa_id, reply_text)


async def _pick_default_workflow_id(organization_id: int) -> Optional[int]:
    """First active workflow in the org, picked alphabetically by name.

    Stable across calls so different conversations land on the same
    workflow by default. When per-conversation workflow selection is
    added (a UI button / a /workflows command), it overrides this.
    """
    async with db_client.async_session() as s:
        result = await s.execute(
            select(WorkflowModel)
            .where(
                WorkflowModel.organization_id == organization_id,
                WorkflowModel.status == "active",
            )
            .order_by(WorkflowModel.name.asc())
            .limit(1)
        )
        row = result.scalars().first()
    return row.id if row else None


def _extract_latest_assistant_text(session_data: Any) -> Optional[str]:
    data = normalize_text_chat_session_data(session_data)
    turns = data.get("turns") or []
    if not turns:
        return None
    last = turns[-1]
    assistant = last.get("assistant_message") or {}
    text = assistant.get("text")
    return text if isinstance(text, str) and text.strip() else None


async def _safe_send(channel, wa_id: str, text: str) -> None:
    try:
        await meta_client.send_text(
            config=channel.config,
            to=wa_id,
            text=text[:4096],
        )
    except meta_client.MetaClientError as exc:
        logger.warning(
            "[whatsapp/dispatch] outbound send failed status={status} meta_error={err}",
            status=exc.status_code,
            err=exc.meta_error,
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            "[whatsapp/dispatch] outbound send unexpected error: {exc!r}",
            exc=exc,
        )


def _log_status(status: DeliveryStatus) -> None:
    logger.info(
        "[whatsapp/status] message_id={mid} status={st} recipient={rcpt} errors={errs}",
        mid=status.message_id,
        st=status.status,
        rcpt=status.recipient_id,
        errs=status.errors,
    )
