"""Telegram-bot-facing API surface (lives next to other IM channels in
Phase 4).

Endpoints:
- ``POST /api/v1/telegram/web-call-link`` — body
  ``{workflow_id, telegram_chat_id}``. Creates a manual workflow run
  scoped to the caller's org (X-API-Key auth) and returns a signed
  short-TTL URL the bot sends as a Telegram WebApp button.
- ``GET /api/v1/telegram/web-call/{token}`` — the consumer side: opened
  by the Telegram WebApp when the user taps the button. Verifies the
  Fernet token, mints a short-lived embed_session against the existing
  workflow_run, and returns an inline WebRTC client page that connects
  back to ``/api/v1/ws/public/signaling/{session_token}``.
"""

from __future__ import annotations

import html
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from loguru import logger
from pydantic import BaseModel, Field

from api.db import db_client
from api.enums import WorkflowRunMode
from api.services.auth.depends import get_user
from api.services.im.web_call_link import sign, verify


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


@router.get(
    "/web-call/{token}",
    response_class=HTMLResponse,
    summary="Resolve a Telegram WebApp call link and serve the WebRTC client page.",
)
async def open_web_call(token: str, request: Request) -> HTMLResponse:
    """Consumer of the Fernet-signed link minted by ``/web-call-link``.

    ADR-101 specifies a 302 redirect into ``/embed/<session_token>``.
    We deviate by rendering the WebRTC client HTML inline because the
    cloudflared tunnel only points at the api container, so there is no
    separate UI page to redirect to. A one-hop redirect-to-self would add
    nothing observable to the client.
    """
    try:
        payload = verify(token)
    except ValueError as exc:
        logger.info(f"[telegram/web-call] rejected token: {exc}")
        raise HTTPException(status_code=410, detail="link_expired_or_invalid") from exc

    workflow_run = await db_client.get_workflow_run(
        payload.workflow_run_id, user_id=payload.user_id
    )
    if workflow_run is None:
        raise HTTPException(status_code=404, detail="workflow_run_not_found")

    workflow = await db_client.get_workflow_by_id(payload.workflow_id)
    if workflow is None:
        raise HTTPException(status_code=404, detail="workflow_not_found")

    embed_token = await db_client.find_or_create_internal_embed_token(
        workflow_id=workflow.id,
        organization_id=workflow.organization_id,
        created_by=payload.user_id,
        source="telegram-internal",
    )

    session_token = f"emb_session_{secrets.token_urlsafe(24)}"
    embed_session = await db_client.create_embed_session(
        session_token=session_token,
        embed_token_id=embed_token.id,
        workflow_run_id=payload.workflow_run_id,
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        origin="telegram-webapp",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )

    public_base = (
        os.getenv("DOGRAH_PUBLIC_URL")
        or str(request.base_url).rstrip("/")
    ).rstrip("/")
    ws_base = public_base.replace("https://", "wss://").replace("http://", "ws://")
    ws_url = f"{ws_base}/api/v1/ws/public/signaling/{embed_session.session_token}"
    turn_url = f"{public_base}/api/v1/public/embed/turn-credentials/{embed_session.session_token}"

    logger.info(
        f"[telegram/web-call] resolved token: workflow={workflow.id} run="
        f"{workflow_run.id} chat={payload.telegram_chat_id} "
        f"session={embed_session.session_token}"
    )
    return HTMLResponse(
        _TELEGRAM_CALL_HTML.format(
            workflow_name=html.escape(workflow.name or "Voice Call"),
            session_token=html.escape(embed_session.session_token),
            ws_url=html.escape(ws_url),
            turn_url=html.escape(turn_url),
        )
    )


# Inline WebRTC client page. Kept here for locality with the route that
# serves it. Jinja2 is not installed in the api image and the template
# has no inheritance/partials, so f-string substitution is sufficient.
# Curly braces in CSS/JS are doubled to escape the .format() pass.
_TELEGRAM_CALL_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <title>{workflow_name}</title>
  <script src="https://telegram.org/js/telegram-web-app.js?56"></script>
  <style>
    :root {{
      --bg: var(--tg-theme-bg-color, #17212b);
      --text: var(--tg-theme-text-color, #f5f5f5);
      --button: var(--tg-theme-button-color, #5288c1);
      --button-text: var(--tg-theme-button-text-color, #ffffff);
      --hint: var(--tg-theme-hint-color, #708499);
      --danger: #e0524b;
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin: 0; height: 100%; }}
    body {{
      background: var(--bg); color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      display: flex; align-items: center; justify-content: center;
      padding: 24px;
    }}
    main {{
      width: 100%; max-width: 360px; text-align: center;
    }}
    h1 {{
      font-size: 18px; font-weight: 600; margin: 0 0 24px;
    }}
    .status {{
      font-size: 15px; color: var(--hint); margin-bottom: 32px;
      min-height: 22px;
    }}
    .mic {{
      width: 96px; height: 96px; border-radius: 50%;
      background: var(--button); color: var(--button-text);
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 24px; font-size: 42px;
      transition: transform .25s ease;
    }}
    .mic.pulse {{ animation: pulse 1.6s ease-in-out infinite; }}
    @keyframes pulse {{
      0%, 100% {{ transform: scale(1); box-shadow: 0 0 0 0 rgba(82,136,193,.5); }}
      50% {{ transform: scale(1.06); box-shadow: 0 0 0 18px rgba(82,136,193,0); }}
    }}
    .timer {{
      font-variant-numeric: tabular-nums; font-size: 28px;
      margin: 0 0 24px;
    }}
    .hint {{
      color: var(--hint); font-size: 13px; line-height: 1.4;
      margin: 16px 0 24px; padding: 0 8px;
    }}
    button {{
      appearance: none; border: 0; cursor: pointer;
      padding: 14px 32px; border-radius: 10px;
      font-size: 16px; font-weight: 600;
      background: var(--danger); color: #fff;
    }}
    button.primary {{ background: var(--button); color: var(--button-text); }}
    button:active {{ transform: translateY(1px); }}
    button + button {{ margin-top: 12px; }}
    .hidden {{ display: none; }}
  </style>
</head>
<body>
  <main>
    <h1>{workflow_name}</h1>
    <div class="mic" id="mic">🎙️</div>
    <div class="status" id="status">Connecting…</div>
    <div class="hint hidden" id="hint"></div>
    <div class="timer hidden" id="timer">00:00</div>
    <button id="retry" class="primary hidden">Try Again</button>
    <button id="end" class="hidden">End Call</button>
    <audio id="remote" autoplay playsinline></audio>
  </main>
  <script>
  (function() {{
    const WS_URL = "{ws_url}";
    const TURN_URL = "{turn_url}";
    const PC_ID = "tg-" + Math.random().toString(36).slice(2, 10);

    const tg = window.Telegram && window.Telegram.WebApp;
    if (tg) {{ tg.ready(); tg.expand(); }}

    const $status = document.getElementById("status");
    const $hint = document.getElementById("hint");
    const $mic = document.getElementById("mic");
    const $timer = document.getElementById("timer");
    const $end = document.getElementById("end");
    const $retry = document.getElementById("retry");
    const $remote = document.getElementById("remote");

    let pc = null, ws = null, micStream = null, startedAt = 0, timerHandle = 0;
    let inCall = false;

    function setStatus(msg) {{ $status.textContent = msg; }}
    function setHint(msg) {{
      if (msg) {{ $hint.textContent = msg; $hint.classList.remove("hidden"); }}
      else {{ $hint.classList.add("hidden"); $hint.textContent = ""; }}
    }}
    function fmt(s) {{
      const m = Math.floor(s / 60).toString().padStart(2, "0");
      const ss = Math.floor(s % 60).toString().padStart(2, "0");
      return m + ":" + ss;
    }}
    function showInCall() {{
      inCall = true;
      setStatus("In call");
      setHint("");
      $mic.classList.add("pulse");
      $timer.classList.remove("hidden");
      $end.classList.remove("hidden");
      $retry.classList.add("hidden");
      startedAt = Date.now();
      timerHandle = setInterval(() => {{
        $timer.textContent = fmt((Date.now() - startedAt) / 1000);
      }}, 250);
    }}
    function showEnded(reason, opts) {{
      opts = opts || {{}};
      $mic.classList.remove("pulse");
      $timer.classList.add("hidden");
      $end.classList.add("hidden");
      setStatus(reason || "Call ended");
      setHint(opts.hint || "");
      clearInterval(timerHandle);
      if (opts.allowRetry) {{
        $retry.classList.remove("hidden");
      }} else {{
        $retry.classList.add("hidden");
        setTimeout(() => {{ if (tg) tg.close(); }}, 2000);
      }}
    }}
    function teardown(reason, opts) {{
      try {{ if (pc) pc.close(); }} catch (e) {{}}
      try {{ if (ws && ws.readyState <= 1) ws.close(); }} catch (e) {{}}
      try {{ if (micStream) micStream.getTracks().forEach(t => t.stop()); }} catch (e) {{}}
      pc = null; ws = null; micStream = null; inCall = false;
      showEnded(reason, opts);
    }}
    $end.addEventListener("click", () => teardown("Call ended"));
    $retry.addEventListener("click", () => {{
      $retry.classList.add("hidden");
      setStatus("Connecting…");
      setHint("");
      start();
    }});

    async function start() {{
      try {{
        setStatus("Requesting microphone…");
        // Explicit audio constraints help WebRTC pick reasonable defaults across
        // browsers; the booleans are nominally browser defaults but several
        // mobile WebViews disable echoCancellation unless asked.
        micStream = await navigator.mediaDevices.getUserMedia({{
          audio: {{
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          }},
          video: false,
        }});
      }} catch (e) {{
        const denied = e && (e.name === "NotAllowedError" || e.name === "SecurityError");
        teardown(
          denied ? "Microphone access denied" : "Microphone unavailable",
          {{
            allowRetry: true,
            hint: denied
              ? "Allow microphone access for Telegram in your device settings, then tap Try Again."
              : "No microphone was found. Check your audio device and try again.",
          }}
        );
        return;
      }}

      setStatus("Fetching network config…");
      let iceServers = [{{ urls: "stun:stun.l.google.com:19302" }}];
      try {{
        const r = await fetch(TURN_URL);
        if (r.ok) {{
          const data = await r.json();
          if (Array.isArray(data.ice_servers) && data.ice_servers.length) {{
            iceServers = data.ice_servers;
          }}
        }}
      }} catch (e) {{ /* fall back to STUN */ }}

      setStatus("Connecting…");
      pc = new RTCPeerConnection({{ iceServers }});
      micStream.getAudioTracks().forEach(t => pc.addTrack(t, micStream));

      // Pipecat's SmallWebRTC transport uses a data channel for the control
      // plane (heartbeats, jitter/state feedback). Without it the server logs
      // "Data channel not established within 10s" and audio quality drops.
      // The channel must exist on the offer before we createOffer().
      pc.createDataChannel("pipecat-control");

      pc.ontrack = (ev) => {{
        if (ev.streams && ev.streams[0]) $remote.srcObject = ev.streams[0];
      }};
      pc.onconnectionstatechange = () => {{
        if (!pc) return;
        if (pc.connectionState === "failed") {{
          teardown("Connection lost", {{ allowRetry: true, hint: "Network may be unstable. Tap Try Again." }});
        }} else if (["closed", "disconnected"].includes(pc.connectionState) && inCall) {{
          teardown("Call ended");
        }}
      }};
      pc.onicecandidate = (ev) => {{
        if (ev.candidate && ws && ws.readyState === 1) {{
          ws.send(JSON.stringify({{
            type: "ice-candidate",
            payload: {{
              pc_id: PC_ID,
              candidate: {{
                candidate: ev.candidate.candidate,
                sdpMid: ev.candidate.sdpMid,
                sdpMLineIndex: ev.candidate.sdpMLineIndex,
              }},
            }},
          }}));
        }}
      }};

      ws = new WebSocket(WS_URL);
      ws.onopen = async () => {{
        try {{
          const offer = await pc.createOffer({{ offerToReceiveAudio: true }});
          await pc.setLocalDescription(offer);
          ws.send(JSON.stringify({{
            type: "offer",
            payload: {{
              type: "offer",
              sdp: offer.sdp,
              pc_id: PC_ID,
              call_context_vars: {{}},
            }},
          }}));
        }} catch (e) {{
          teardown("Failed to start call", {{ allowRetry: true }});
        }}
      }};
      ws.onmessage = async (ev) => {{
        let msg;
        try {{ msg = JSON.parse(ev.data); }} catch (e) {{ return; }}
        const p = msg.payload || msg;
        if (msg.type === "answer" && p.sdp) {{
          await pc.setRemoteDescription({{ type: "answer", sdp: p.sdp }});
          showInCall();
        }} else if (msg.type === "ice-candidate" && p.candidate) {{
          try {{
            const c = (typeof p.candidate === "string")
              ? {{ candidate: p.candidate, sdpMid: p.sdpMid, sdpMLineIndex: p.sdpMLineIndex }}
              : p.candidate;
            await pc.addIceCandidate(c);
          }} catch (e) {{}}
        }} else if (msg.type === "error") {{
          const detail = (p && (p.message || p.error_type)) || msg.detail || "Call error";
          teardown(detail, {{ allowRetry: true }});
        }}
      }};
      ws.onerror = () => {{
        if (!inCall) teardown("Signaling error", {{ allowRetry: true }});
      }};
      ws.onclose = () => {{
        if (!inCall) teardown("Could not connect", {{ allowRetry: true }});
      }};
    }}

    start();
  }})();
  </script>
</body>
</html>"""
