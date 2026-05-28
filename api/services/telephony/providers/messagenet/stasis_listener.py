"""Deployment-level Stasis event listener for the MessageNet ARI app.

Why this is separate from ``ari_manager.py``:

``ari_manager.py`` is org-scoped — it walks ``telephony_configurations``
rows where ``provider='ari'`` and opens one WebSocket per org. MessageNet
calls go through a **single deployment-level** Asterisk instance whose
ARI endpoint is configured via env (``ARI_BASE_URL`` etc.), not per-org
DB rows, so the org-driven loop doesn't see it. This listener is the
minimum viable counterpart: one WebSocket subscribed to one Stasis app,
handling the outbound bridge dance the messagenet provider depends on.

Phase 1 handles **outbound only** — channels originated by
``MessagenetProvider.initiate_call`` that land in the Stasis app with a
``workflow_run_id`` appArg. Inbound (PSTN → MessageNet → Asterisk →
Stasis) is logged but not bridged here; DID-to-workflow resolution is a
follow-up that needs to read ``telephony_phone_numbers`` and create a
workflow_run, mirroring the inbound path in ari_manager.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, Optional

import aiohttp
import websockets
from loguru import logger

_STASIS_APP_DEFAULT = "dograh-messagenet"


class MessagenetStasisListener:
    """Single-connection ARI event listener for the messagenet Stasis app."""

    def __init__(
        self,
        *,
        ari_base_url: str,
        ari_user: str,
        ari_password: str,
        app_name: str,
        ws_client_name: str,
        audiosocket_target: str = "api:9092",
    ) -> None:
        self.ari_base_url = ari_base_url.rstrip("/")
        self.ari_user = ari_user
        self.ari_password = ari_password
        self.app_name = app_name
        self.ws_client_name = ws_client_name
        # host:port asterisk uses to reach the api's AudioSocket server.
        # asterisk and api share root_app-network so the bridge hostname
        # "api" resolves; in other deployments this can be overridden.
        self.audiosocket_target = audiosocket_target
        self._task: Optional[asyncio.Task[None]] = None
        self._stop = asyncio.Event()

    # --- Lifecycle ----------------------------------------------------
    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="messagenet-stasis-listener")
        logger.info(
            f"[MessageNet/Stasis] Listener started for app={self.app_name} "
            f"at {self.ari_base_url}"
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        self._task.cancel()
        try:
            await self._task
        except (asyncio.CancelledError, Exception):
            pass
        self._task = None
        logger.info("[MessageNet/Stasis] Listener stopped")

    # --- WS connect loop ---------------------------------------------
    async def _run(self) -> None:
        # Convert http(s):// → ws(s):// for the ARI WebSocket events URL.
        if self.ari_base_url.startswith("https://"):
            ws_scheme = "wss://"
            host_path = self.ari_base_url[len("https://") :]
        elif self.ari_base_url.startswith("http://"):
            ws_scheme = "ws://"
            host_path = self.ari_base_url[len("http://") :]
        else:
            raise RuntimeError(
                f"ARI_BASE_URL must start with http:// or https:// "
                f"(got {self.ari_base_url!r})"
            )
        events_url = (
            f"{ws_scheme}{host_path}/ari/events"
            f"?api_key={self.ari_user}:{self.ari_password}"
            f"&app={self.app_name}&subscribeAll=true"
        )

        backoff = 1.0
        while not self._stop.is_set():
            try:
                async with websockets.connect(events_url) as ws:
                    logger.info(
                        f"[MessageNet/Stasis] Connected to ARI events "
                        f"for app={self.app_name}"
                    )
                    backoff = 1.0
                    async for raw in ws:
                        if self._stop.is_set():
                            break
                        await self._handle_event(raw)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # Reconnect with exponential backoff capped at 30s.
                logger.warning(
                    f"[MessageNet/Stasis] WS error ({exc!r}); "
                    f"reconnecting in {backoff:.1f}s"
                )
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                except asyncio.TimeoutError:
                    pass
                backoff = min(backoff * 2, 30.0)

    # --- Event handlers ----------------------------------------------
    async def _handle_event(self, raw: Any) -> None:
        try:
            event = json.loads(raw)
        except Exception:
            logger.warning(f"[MessageNet/Stasis] Non-JSON event: {raw!r}")
            return

        event_type = event.get("type", "")
        if event_type == "StasisStart":
            await self._on_stasis_start(event)
        elif event_type == "StasisEnd":
            await self._on_stasis_end(event)
        # Other events (ChannelStateChange, BridgeCreated, etc.) are
        # ignored here — the audio bridge is enough for phase 1.

    async def _on_stasis_start(self, event: Dict[str, Any]) -> None:
        channel = event.get("channel", {}) or {}
        channel_id = channel.get("id", "")
        channel_name = channel.get("name", "")
        args = event.get("args", []) or []
        kv = _parse_appargs(args)

        # externalMedia channels enter Stasis with no useful appArgs
        # (chan_websocket / UnicastRTP / chan_audiosocket variants). The
        # listener already wired the bridge before we see this event,
        # so just ignore the StasisStart — hanging up here would tear
        # down the bridge we just made.
        if (
            channel_name.startswith("UnicastRTP/")
            or channel_name.startswith("AudioSocket/")
            or channel_name.startswith("WebSocket/")
        ):
            logger.debug(
                f"[MessageNet/Stasis] externalMedia StasisStart "
                f"channel={channel_id} name={channel_name} — "
                f"gateway-managed, ignoring"
            )
            return

        workflow_run_id = kv.get("workflow_run_id")
        direction = kv.get("direction", "outbound" if workflow_run_id else "")

        if direction == "inbound" and not workflow_run_id:
            await self._on_inbound_stasis_start(event, kv)
            return

        if not workflow_run_id:
            logger.warning(
                f"[MessageNet/Stasis] StasisStart missing workflow_run_id "
                f"(channel={channel_id}, name={channel_name}, args={args}); hanging up"
            )
            await self._hangup(channel_id)
            return

        # Gateway uses the simple originate pattern. On StasisStart we
        # answer, spawn externalMedia, and bridge.
        logger.info(
            f"[MessageNet/Stasis] Outbound trunk StasisStart "
            f"channel={channel_id} name={channel_name} "
            f"workflow_run_id={workflow_run_id}"
        )
        if not await self._answer(channel_id):
            return
        ext_id = await self._create_external_media(
            workflow_run_id=workflow_run_id,
            workflow_id=kv.get("workflow_id", ""),
            user_id=kv.get("user_id", ""),
        )
        if not ext_id:
            await self._hangup(channel_id)
            return
        bridge_id = await self._bridge([channel_id, ext_id])
        if not bridge_id:
            await self._hangup(channel_id)
            await self._hangup(ext_id)
            return
        logger.info(
            f"[MessageNet/Stasis] Bridge {bridge_id} live: "
            f"trunk={channel_id} ext={ext_id}"
        )

    async def _on_inbound_stasis_start(
        self, event: Dict[str, Any], kv: Dict[str, str]
    ) -> None:
        """Resolve called DID → workflow → create workflow_run → bridge audio.

        Mirrors ``ari_manager._handle_inbound_stasis_start`` but for the
        deployment-level messagenet listener: there's no org context to start
        from, so we look up the phone number across orgs using
        ``find_phone_number_for_provider_address``.
        """
        from api.db import db_client
        from api.enums import CallType, WorkflowRunMode
        from api.services.quota_service import check_dograh_quota_by_user_id

        channel = event.get("channel", {}) or {}
        channel_id = channel.get("id", "")
        to_number = kv.get("to") or channel.get("dialplan", {}).get("exten", "")
        from_number = kv.get("from") or channel.get("caller", {}).get("number", "")

        if not to_number:
            logger.warning(
                f"[MessageNet/Stasis] Inbound StasisStart channel={channel_id} "
                f"has no 'to' / dialplan.exten — hanging up"
            )
            await self._hangup(channel_id)
            return

        try:
            # MessageNet is an Italian carrier; their inbound INVITEs put the
            # dialled DID in the To header in national format (e.g.
            # 0418878808). normalize_telephony_address needs a country hint
            # to turn that into the canonical E.164 form (+390418878808)
            # the DB stores. Override via MESSAGENET_COUNTRY for non-IT
            # deployments.
            country_hint = os.getenv("MESSAGENET_COUNTRY", "IT")
            row = await db_client.find_phone_number_for_provider_address(
                provider="messagenet",
                address=to_number,
                country_hint=country_hint,
            )
            if row is None:
                logger.warning(
                    f"[MessageNet/Stasis] Inbound call to {to_number} from "
                    f"{from_number}: no active phone number registered in any "
                    f"messagenet config — hanging up"
                )
                await self._hangup(channel_id)
                return
            config, phone = row

            if not phone.inbound_workflow_id:
                logger.warning(
                    f"[MessageNet/Stasis] Inbound call to {to_number}: phone "
                    f"number row id={phone.id} has no inbound_workflow_id "
                    f"assigned — hanging up"
                )
                await self._hangup(channel_id)
                return

            workflow = await db_client.get_workflow(
                phone.inbound_workflow_id,
                organization_id=phone.organization_id,
            )
            if not workflow:
                logger.warning(
                    f"[MessageNet/Stasis] inbound_workflow_id={phone.inbound_workflow_id} "
                    f"not found in org {phone.organization_id} — hanging up"
                )
                await self._hangup(channel_id)
                return

            user_id = workflow.user_id
            quota = await check_dograh_quota_by_user_id(
                user_id, workflow_id=phone.inbound_workflow_id
            )
            if not quota.has_quota:
                logger.warning(
                    f"[MessageNet/Stasis] Quota exceeded for user {user_id} — "
                    f"hanging up inbound call to {to_number}"
                )
                await self._hangup(channel_id)
                return

            workflow_run = await db_client.create_workflow_run(
                name=f"MessageNet Inbound {from_number or 'unknown'}",
                workflow_id=phone.inbound_workflow_id,
                mode=WorkflowRunMode.MESSAGENET.value,
                user_id=user_id,
                call_type=CallType.INBOUND,
                initial_context={
                    "caller_number": from_number,
                    "called_number": to_number,
                    "direction": "inbound",
                    "provider": "messagenet",
                    "telephony_configuration_id": config.id,
                },
                gathered_context={"call_id": channel_id},
            )

            logger.info(
                f"[MessageNet/Stasis] Inbound workflow_run {workflow_run.id} "
                f"created for channel={channel_id} (caller={from_number}, "
                f"called={to_number}, workflow_id={phone.inbound_workflow_id})"
            )

            # Same bridge sequence as outbound StasisStart: the trunk
            # channel is already Up (the inbound dialplan does Answer()),
            # so just spawn the externalMedia leg and bridge.
            ext_id = await self._create_external_media(
                workflow_run_id=str(workflow_run.id),
                workflow_id=str(phone.inbound_workflow_id),
                user_id=str(user_id),
            )
            if not ext_id:
                await self._hangup(channel_id)
                return
            bridge_id = await self._bridge([channel_id, ext_id])
            if not bridge_id:
                await self._hangup(channel_id)
                await self._hangup(ext_id)
                return
            logger.info(
                f"[MessageNet/Stasis] Inbound bridge {bridge_id} live: "
                f"trunk={channel_id} ext={ext_id}"
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                f"[MessageNet/Stasis] Error handling inbound StasisStart "
                f"channel={channel_id}: {exc!r}"
            )
            try:
                await self._hangup(channel_id)
            except Exception:  # noqa: BLE001
                pass

    async def _on_stasis_end(self, event: Dict[str, Any]) -> None:
        channel = event.get("channel", {}) or {}
        channel_id = channel.get("id", "")
        logger.info(f"[MessageNet/Stasis] StasisEnd channel={channel_id}")
        # Asterisk tears down the bridge automatically when both legs leave.

    # --- ARI helpers --------------------------------------------------
    def _auth(self) -> aiohttp.BasicAuth:
        return aiohttp.BasicAuth(self.ari_user, self.ari_password)

    async def _ari(
        self, method: str, path: str, **kwargs: Any
    ) -> Optional[Dict[str, Any]]:
        url = f"{self.ari_base_url}/ari{path}"
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method, url, auth=self._auth(), **kwargs
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    logger.error(
                        f"[MessageNet/Stasis] ARI {method} {path} "
                        f"failed: HTTP {resp.status} {text}"
                    )
                    return None
                if not text:
                    return {}
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return {"raw": text}

    async def _answer(self, channel_id: str) -> bool:
        res = await self._ari("POST", f"/channels/{channel_id}/answer")
        return res is not None

    async def _hangup(self, channel_id: str) -> None:
        await self._ari("DELETE", f"/channels/{channel_id}")

    async def _create_external_media(
        self, *, workflow_run_id: str, workflow_id: str, user_id: str
    ) -> str:
        # AudioSocket over TCP — chan_websocket externalMedia silently
        # 500s in andrius/asterisk:21, see docs troubleshooting. We
        # pre-register a UUID with the AudioSocket server so the
        # inbound TCP connection can be routed back to this workflow run.
        import uuid as uuid_lib

        from .audiosocket_server import get_audiosocket_server

        srv = get_audiosocket_server()
        if srv is None:
            logger.error(
                "[MessageNet/Stasis] AudioSocket server not running; "
                "cannot create externalMedia leg"
            )
            return ""

        call_uuid = str(uuid_lib.uuid4())
        await srv.register_call(
            call_uuid=call_uuid,
            workflow_id=workflow_id,
            user_id=user_id,
            workflow_run_id=workflow_run_id,
        )
        params = {
            "app": self.app_name,
            "external_host": f"{self.audiosocket_target}",
            "format": "slin",
            "transport": "tcp",
            "encapsulation": "audiosocket",
            "direction": "both",
            "data": call_uuid,
        }
        res = await self._ari("POST", "/channels/externalMedia", params=params)
        ext_id = (res or {}).get("id", "")
        if not ext_id:
            # Clean up the registration if the ARI call failed.
            await srv.unregister_call(call_uuid)
        return ext_id

    async def _bridge(self, channel_ids: list[str]) -> str:
        res = await self._ari(
            "POST",
            "/bridges",
            params={"type": "mixing", "name": f"mn-{channel_ids[0]}"},
        )
        bridge_id = (res or {}).get("id", "")
        if not bridge_id:
            return ""
        ok = await self._ari(
            "POST",
            f"/bridges/{bridge_id}/addChannel",
            params={"channel": ",".join(channel_ids)},
        )
        return bridge_id if ok is not None else ""


def _parse_appargs(args: list[str]) -> Dict[str, str]:
    """Parse ``["key=value", "k2=v2"]`` into ``{"key": "value", ...}``.

    Asterisk passes Stasis() appArgs as a list of strings split on commas
    in the dialplan and as positional args from ARI originate. We accept
    both shapes — anything without ``=`` is ignored.
    """
    out: Dict[str, str] = {}
    for item in args:
        if not isinstance(item, str) or "=" not in item:
            continue
        k, _, v = item.partition("=")
        out[k.strip()] = v.strip()
    return out


_listener_singleton: Optional[MessagenetStasisListener] = None


def get_listener() -> Optional[MessagenetStasisListener]:
    return _listener_singleton


def install_messagenet_stasis_listener() -> Optional[MessagenetStasisListener]:
    """Build the listener from env. Returns None if the backend isn't asterisk-ari.

    Called from the FastAPI lifespan; the caller is responsible for
    invoking ``listener.start()`` and ``listener.stop()``.
    """
    global _listener_singleton

    backend = (os.getenv("MESSAGENET_GATEWAY_BACKEND") or "stub").lower()
    if backend != "asterisk-ari":
        logger.info(
            f"[MessageNet/Stasis] Backend={backend} — Stasis listener not started"
        )
        return None

    try:
        # ``api`` is the docker service name reachable from the asterisk
        # container; override via env in non-bridge-network deployments.
        as_host = os.getenv("MESSAGENET_AUDIOSOCKET_TARGET_HOST", "api")
        as_port = os.getenv("MESSAGENET_AUDIOSOCKET_PORT", "9092")
        listener = MessagenetStasisListener(
            ari_base_url=os.environ["ARI_BASE_URL"],
            ari_user=os.environ["ARI_USER"],
            ari_password=os.environ["ARI_PASSWORD"],
            app_name=os.getenv("ARI_APP_NAME", _STASIS_APP_DEFAULT),
            ws_client_name=os.getenv("MESSAGENET_WS_CLIENT_NAME", "dograh-ws"),
            audiosocket_target=f"{as_host}:{as_port}",
        )
    except KeyError as exc:
        raise RuntimeError(
            f"Missing env var for MessageNet Stasis listener: {exc.args[0]}"
        ) from exc

    _listener_singleton = listener
    return listener
