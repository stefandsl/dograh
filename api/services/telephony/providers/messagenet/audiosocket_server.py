"""AudioSocket TCP server + bridge into the existing /ws/ari pipeline.

chan_websocket externalMedia silently 500s in ``andrius/asterisk:21``
(see docs troubleshooting). chan_audiosocket works fine, so we use it
as the audio transport instead.

Architecture
------------

1. Asterisk's externalMedia call uses ``transport=tcp``,
   ``encapsulation=audiosocket``, ``external_host=api:<port>`` and a
   ``data=<uuid>`` field. Asterisk opens a TCP connection here, sends a
   single UUID frame (type=0x01, 16 bytes), then exchanges AUDIO frames
   (type=0x10, slin/PCM16 @ 8 kHz).

2. This module accepts that TCP connection, reads the UUID, looks up
   the routing params (workflow_id / user_id / workflow_run_id) the
   Stasis listener stashed when it placed the externalMedia call, then
   opens a WebSocket loopback to the api's own ``/ws/ari`` endpoint
   carrying those params.

3. From there the existing pipeline runs unchanged — ``AsteriskFrameSerializer``
   handles the µ-law framing on the WebSocket side. We transcode in the
   bridge: AudioSocket PCM16 ↔ µ-law going to/from the WebSocket.

Lifespan-managed by ``api/app.py``: the server starts when
``MESSAGENET_GATEWAY_BACKEND=asterisk-ari`` and stops on shutdown.
"""

from __future__ import annotations

import asyncio
import audioop  # stdlib; deprecated in 3.13 but fine for 3.12
import os
import uuid as uuid_lib
from dataclasses import dataclass, field
from typing import Dict, Optional

import websockets
from loguru import logger

# Frame types — see https://wiki.asterisk.org/wiki/display/AST/AudioSocket
_FRAME_HANGUP = 0x00
_FRAME_UUID = 0x01
_FRAME_DTMF = 0x03
_FRAME_AUDIO = 0x10
_FRAME_ERROR = 0xFF

_AUDIO_BYTES_PER_20MS_PCM16 = 320  # 8000 Hz * 0.020 s * 2 bytes/sample
_AUDIO_BYTES_PER_20MS_ULAW = 160  # 8000 Hz * 0.020 s * 1 byte/sample


@dataclass
class _CallRouting:
    workflow_id: str
    user_id: str
    workflow_run_id: str
    registered_at: float = field(
        default_factory=lambda: asyncio.get_event_loop().time()
    )


class AudioSocketServer:
    """asyncio TCP server speaking the AudioSocket protocol.

    The Stasis listener calls :meth:`register_call` before issuing the
    externalMedia ARI call so the UUID Asterisk sends in the first frame
    can be resolved to the workflow run.
    """

    def __init__(
        self,
        *,
        bind_host: str,
        bind_port: int,
        ws_endpoint: str,
        ws_ulaw: bool = True,
    ) -> None:
        self.bind_host = bind_host
        self.bind_port = bind_port
        self.ws_endpoint = ws_endpoint
        self.ws_ulaw = ws_ulaw
        self._server: Optional[asyncio.AbstractServer] = None
        self._routing: Dict[str, _CallRouting] = {}
        self._lock = asyncio.Lock()

    # --- public API ---------------------------------------------------
    async def register_call(
        self,
        *,
        call_uuid: str,
        workflow_id: str,
        user_id: str,
        workflow_run_id: str,
    ) -> None:
        """Pre-register a UUID so we can route the inbound TCP connection."""
        async with self._lock:
            self._routing[call_uuid] = _CallRouting(
                workflow_id=str(workflow_id),
                user_id=str(user_id),
                workflow_run_id=str(workflow_run_id),
            )
        logger.info(
            f"[AudioSocket] registered UUID={call_uuid} "
            f"-> workflow_run_id={workflow_run_id}"
        )

    async def unregister_call(self, call_uuid: str) -> None:
        async with self._lock:
            self._routing.pop(call_uuid, None)

    # --- lifecycle ----------------------------------------------------
    async def start(self) -> None:
        if self._server is not None:
            return
        self._server = await asyncio.start_server(
            self._handle_connection, self.bind_host, self.bind_port
        )
        logger.info(
            f"[AudioSocket] server listening on {self.bind_host}:{self.bind_port}; "
            f"loopback target: {self.ws_endpoint}"
        )

    async def stop(self) -> None:
        if self._server is None:
            return
        self._server.close()
        try:
            await self._server.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        self._server = None
        logger.info("[AudioSocket] server stopped")

    # --- per-connection handler --------------------------------------
    async def _handle_connection(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername")
        logger.info(f"[AudioSocket] new connection from {peer}")

        # Expect the UUID frame first; everything else has to wait until
        # we know which workflow run this is.
        first = await self._read_frame(reader)
        if first is None or first[0] != _FRAME_UUID:
            logger.warning(
                f"[AudioSocket] {peer} did not send UUID first "
                f"(got type={first[0] if first else 'EOF'}); closing"
            )
            writer.close()
            await writer.wait_closed()
            return
        try:
            call_uuid = str(uuid_lib.UUID(bytes=first[1]))
        except ValueError:
            logger.warning(f"[AudioSocket] {peer} sent invalid UUID bytes; closing")
            writer.close()
            await writer.wait_closed()
            return

        async with self._lock:
            routing = self._routing.get(call_uuid)
        if routing is None:
            logger.warning(
                f"[AudioSocket] {peer} sent UUID={call_uuid} but no routing "
                f"is registered; closing. (Was the Stasis listener slow to "
                f"call register_call?)"
            )
            writer.close()
            await writer.wait_closed()
            return

        logger.info(
            f"[AudioSocket] UUID={call_uuid} matched workflow_run_id="
            f"{routing.workflow_run_id}; opening loopback WebSocket"
        )

        ws_url = (
            f"{self.ws_endpoint}?workflow_id={routing.workflow_id}"
            f"&user_id={routing.user_id}"
            f"&workflow_run_id={routing.workflow_run_id}"
        )

        try:
            async with websockets.connect(ws_url, subprotocols=["media"]) as ws:
                await self._bridge(reader, writer, ws, call_uuid)
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                f"[AudioSocket] bridge failed for UUID={call_uuid}: {exc!r}"
            )
        finally:
            await self.unregister_call(call_uuid)
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass

    # --- bridge -------------------------------------------------------
    async def _bridge(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        ws,
        call_uuid: str,
    ) -> None:
        """Run the AudioSocket-TCP ↔ /ws/ari WebSocket pump until either side closes."""

        async def tcp_to_ws() -> None:
            ulaw_state = None  # audioop state for lin2ulaw
            try:
                while True:
                    frame = await self._read_frame(reader)
                    if frame is None:
                        return
                    ftype, body = frame
                    if ftype == _FRAME_HANGUP:
                        return
                    if ftype != _FRAME_AUDIO or not body:
                        continue
                    # Asterisk gives us slin (PCM16 8 kHz). The
                    # /ws/ari endpoint + AsteriskFrameSerializer expect
                    # µ-law on the wire. Transcode here.
                    if self.ws_ulaw:
                        ulaw_payload, ulaw_state = audioop.lin2ulaw(body, 2), ulaw_state
                        await ws.send(ulaw_payload)
                    else:
                        await ws.send(body)
            except (websockets.ConnectionClosed, asyncio.IncompleteReadError):
                return

        async def ws_to_tcp() -> None:
            try:
                async for message in ws:
                    if not isinstance(message, (bytes, bytearray)):
                        # The /ws/ari side may also send JSON control
                        # messages — ignore those, audio-only here.
                        continue
                    if self.ws_ulaw:
                        pcm16 = audioop.ulaw2lin(bytes(message), 2)
                    else:
                        pcm16 = bytes(message)
                    # Send back as AUDIO frames, chunked to the natural
                    # 20 ms / 320-byte PCM16 packet so Asterisk's RTP
                    # writer doesn't have to repacketize.
                    for i in range(0, len(pcm16), _AUDIO_BYTES_PER_20MS_PCM16):
                        chunk = pcm16[i : i + _AUDIO_BYTES_PER_20MS_PCM16]
                        await self._write_frame(writer, _FRAME_AUDIO, chunk)
            except (websockets.ConnectionClosed, ConnectionResetError):
                return

        t1 = asyncio.create_task(tcp_to_ws(), name=f"as-tcp2ws-{call_uuid}")
        t2 = asyncio.create_task(ws_to_tcp(), name=f"as-ws2tcp-{call_uuid}")
        done, pending = await asyncio.wait(
            {t1, t2}, return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
        # Send a HANGUP frame to Asterisk if the pipeline closed first.
        try:
            await self._write_frame(writer, _FRAME_HANGUP, b"")
            await writer.drain()
        except Exception:  # noqa: BLE001
            pass

    # --- frame I/O ----------------------------------------------------
    async def _read_frame(
        self, reader: asyncio.StreamReader
    ) -> Optional[tuple[int, bytes]]:
        try:
            hdr = await reader.readexactly(3)
        except (asyncio.IncompleteReadError, ConnectionResetError):
            return None
        ftype = hdr[0]
        length = int.from_bytes(hdr[1:3], "big")
        body = b""
        if length:
            try:
                body = await reader.readexactly(length)
            except (asyncio.IncompleteReadError, ConnectionResetError):
                return None
        return ftype, body

    async def _write_frame(
        self, writer: asyncio.StreamWriter, ftype: int, body: bytes
    ) -> None:
        writer.write(bytes([ftype]) + len(body).to_bytes(2, "big") + body)
        await writer.drain()


# --- module-level singleton ---------------------------------------------
_server: Optional[AudioSocketServer] = None


def get_audiosocket_server() -> Optional[AudioSocketServer]:
    return _server


def install_messagenet_audiosocket_server() -> Optional[AudioSocketServer]:
    """Build the AudioSocket server from env. None if the backend isn't asterisk-ari.

    Lifespan calls :meth:`AudioSocketServer.start` after this.
    """
    global _server

    backend = (os.getenv("MESSAGENET_GATEWAY_BACKEND") or "stub").lower()
    if backend != "asterisk-ari":
        return None

    bind_host = os.getenv("MESSAGENET_AUDIOSOCKET_HOST", "0.0.0.0")
    bind_port = int(os.getenv("MESSAGENET_AUDIOSOCKET_PORT", "9092"))
    # The WebSocket the bridge connects to. Loopback by default; the
    # backend WS_HOST env lets a remote api point elsewhere.
    ws_host = os.getenv("DOGRAH_WS_HOST", "localhost:8000")
    ws_endpoint = f"ws://{ws_host}/api/v1/telephony/ws/ari"

    server = AudioSocketServer(
        bind_host=bind_host,
        bind_port=bind_port,
        ws_endpoint=ws_endpoint,
    )
    _server = server
    return server
