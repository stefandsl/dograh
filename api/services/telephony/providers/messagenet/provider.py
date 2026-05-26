"""MessageNet SIP-trunk implementation of ``TelephonyProvider``.

MessageNet doesn't offer a REST call-control API — calls are originated
and received over SIP/RTP. This class therefore delegates anything that
would touch SIP signalling to ``MessagenetSipGatewayClient``; the
provider itself stays focused on Dograh-side glue (config validation,
status normalization, the WebSocket bridge to pipecat).

Phase-1 deployments ship with ``StubMessagenetSipGateway`` registered as
the gateway. Every outbound attempt fails fast with HTTP 503 and a clear
operator message — no half-working behavior, no silent drops.
"""

import json
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from fastapi import HTTPException, Response
from loguru import logger

from api.enums import WorkflowRunMode
from api.services.telephony.base import (
    CallInitiationResult,
    NormalizedInboundData,
    TelephonyProvider,
)

from .sip_gateway import (
    MessagenetGatewayNotConfigured,
    MessagenetTrunkCredentials,
    get_sip_gateway,
)
from .sip_uri import SipUriError, parse_sip_uri

if TYPE_CHECKING:
    from fastapi import WebSocket


class MessagenetProvider(TelephonyProvider):
    """SIP-trunk provider for MessageNet."""

    PROVIDER_NAME = WorkflowRunMode.MESSAGENET.value
    WEBHOOK_ENDPOINT = None  # SIP, not HTTP webhooks

    def __init__(self, config: Dict[str, Any]):
        self.sip_uri_raw = (config.get("sip_uri") or "").strip()
        self.username = (config.get("username") or "").strip() or None
        self._password = config.get("password") or ""
        self.from_numbers = config.get("from_numbers") or []
        if isinstance(self.from_numbers, str):
            self.from_numbers = [self.from_numbers]

        # Best-effort parse so derived fields exist; validation happens in
        # validate_config() where we can return False cleanly.
        try:
            self.sip_uri = parse_sip_uri(self.sip_uri_raw) if self.sip_uri_raw else None
        except SipUriError:
            self.sip_uri = None

        # Default username from the URI user part when not supplied.
        if not self.username and self.sip_uri is not None:
            self.username = self.sip_uri.user

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _credentials(self) -> MessagenetTrunkCredentials:
        if self.sip_uri is None:
            raise ValueError("MessageNet provider has no valid SIP URI configured")
        return MessagenetTrunkCredentials(
            sip_uri=self.sip_uri,
            username=self.username or self.sip_uri.user,
            password=self._password,
            from_numbers=list(self.from_numbers),
        )

    # ------------------------------------------------------------------
    # Required: outbound / config / status
    # ------------------------------------------------------------------
    def validate_config(self) -> bool:
        return bool(self.sip_uri_raw and self._password and self.sip_uri is not None)

    async def get_available_phone_numbers(self) -> List[str]:
        return list(self.from_numbers)

    async def initiate_call(
        self,
        to_number: str,
        webhook_url: str,
        workflow_run_id: Optional[int] = None,
        from_number: Optional[str] = None,
        **kwargs: Any,
    ) -> CallInitiationResult:
        if not self.validate_config():
            raise HTTPException(
                status_code=400,
                detail=(
                    "MessageNet provider is not properly configured "
                    "(sip_uri and password are required)."
                ),
            )

        # Note: never log the password, even at DEBUG. ``credentials`` is
        # passed by reference to the gateway, which is responsible for
        # treating it the same way.
        logger.info(
            f"[MessageNet] Initiating outbound call to {to_number} "
            f"via sip:{self.sip_uri.user}@{self.sip_uri.host} "  # type: ignore[union-attr]
            f"workflow_run_id={workflow_run_id}"
        )

        gateway = get_sip_gateway()
        credentials = self._credentials()
        try:
            handle = await gateway.originate_call(
                credentials=credentials,
                to_number=to_number,
                from_number=from_number,
                workflow_run_id=workflow_run_id,
            )
        except MessagenetGatewayNotConfigured as exc:
            # Surface the operator-facing message verbatim — it tells the
            # admin exactly what's missing.
            raise HTTPException(status_code=503, detail=str(exc)) from exc

        return CallInitiationResult(
            call_id=handle.call_id,
            status=handle.status,
            caller_number=from_number,
            provider_metadata={"call_id": handle.call_id},
            raw_response=handle.raw,
        )

    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        gateway = get_sip_gateway()
        try:
            return await gateway.get_call_status(call_id)
        except MessagenetGatewayNotConfigured as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    async def get_call_cost(self, call_id: str) -> Dict[str, Any]:
        # MessageNet doesn't expose a cost API; surface zero/unknown
        # rather than failing — call-record CDR reconciliation is a
        # separate concern.
        return {
            "cost_usd": 0.0,
            "duration": 0,
            "status": "unknown",
            "error": "MessageNet does not expose a call-cost API",
        }

    # ------------------------------------------------------------------
    # Webhook surface: minimal — MessageNet doesn't use HTTP webhooks
    # ------------------------------------------------------------------
    async def verify_webhook_signature(
        self, url: str, params: Dict[str, Any], signature: str
    ) -> bool:
        # No HTTP webhooks → nothing to verify. Returning True mirrors the
        # ARI default: "no verification attempted, not a security gate".
        return True

    async def get_webhook_response(
        self, workflow_id: int, user_id: int, workflow_run_id: int
    ) -> str:
        logger.warning(
            "[MessageNet] get_webhook_response called — MessageNet is SIP-based, "
            "this code path should not be reached."
        )
        return ""

    def parse_status_callback(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Pass-through normalization so the cross-provider status pipeline
        # has a stable shape. Real fields will be populated when the
        # gateway publishes events; until then, the dict is mostly empty.
        return {
            "call_id": data.get("call_id", ""),
            "status": data.get("status", ""),
            "from_number": data.get("from_number"),
            "to_number": data.get("to_number"),
            "duration": data.get("duration"),
            "extra": data,
        }

    async def handle_websocket(
        self,
        websocket: "WebSocket",
        workflow_id: int,
        user_id: int,
        workflow_run_id: int,
    ) -> None:
        from api.db import db_client
        from api.services.pipecat.run_pipeline import run_pipeline_telephony

        workflow_run = await db_client.get_workflow_run(workflow_run_id, user_id)
        call_id = ""
        if workflow_run and workflow_run.gathered_context:
            call_id = workflow_run.gathered_context.get("call_id", "")

        logger.info(
            f"[MessageNet] Starting pipeline for workflow_run {workflow_run_id}, "
            f"call_id={call_id}"
        )

        await run_pipeline_telephony(
            websocket,
            provider_name=self.PROVIDER_NAME,
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            user_id=user_id,
            call_id=call_id,
            transport_kwargs={"call_id": call_id},
        )

    # ------------------------------------------------------------------
    # Inbound surface
    # ------------------------------------------------------------------
    @classmethod
    def can_handle_webhook(
        cls, webhook_data: Dict[str, Any], headers: Dict[str, str]
    ) -> bool:
        # MessageNet inbound arrives over SIP via the gateway, not HTTP.
        return False

    @staticmethod
    def parse_inbound_webhook(webhook_data: Dict[str, Any]) -> NormalizedInboundData:
        return NormalizedInboundData(
            provider=MessagenetProvider.PROVIDER_NAME,
            call_id=str(webhook_data.get("call_id", "")),
            from_number=str(webhook_data.get("from_number", "")),
            to_number=str(webhook_data.get("to_number", "")),
            direction="inbound",
            call_status=str(webhook_data.get("status", "")),
            account_id=None,
            raw_data=webhook_data,
        )

    @staticmethod
    def validate_account_id(config_data: dict, webhook_account_id: str) -> bool:
        # MessageNet inbound matching is done by called number, not by an
        # account-id header. The cross-provider dispatcher should never call
        # this method (account_id_credential_field="" on the SPEC), but we
        # implement it permissively for safety.
        return True

    async def verify_inbound_signature(
        self,
        url: str,
        webhook_data: Dict[str, Any],
        headers: Dict[str, str],
        body: str = "",
    ) -> bool:
        return True

    async def start_inbound_stream(
        self,
        *,
        websocket_url: str,
        workflow_run_id: int,
        normalized_data: NormalizedInboundData,
        backend_endpoint: str,
    ) -> Response:
        # No HTTP response is delivered to MessageNet — the SIP gateway is
        # the integration point. Return 204 so the cross-provider inbound
        # router has a sane Response object to forward.
        return Response(content="", status_code=204)

    @staticmethod
    def generate_error_response(error_type: str, message: str) -> tuple:
        return Response(
            content=json.dumps({"error": error_type, "message": message}),
            media_type="application/json",
        )

    # ------------------------------------------------------------------
    # Transfer surface (deliberately not supported in phase 1)
    # ------------------------------------------------------------------
    def supports_transfers(self) -> bool:
        return False

    async def transfer_call(
        self,
        destination: str,
        transfer_id: str,
        conference_name: str,
        timeout: int = 30,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        raise NotImplementedError(
            "MessageNet call transfer is not implemented in phase 1; "
            "use a re-INVITE / REFER on the SIP gateway side instead."
        )
