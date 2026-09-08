"""Gestione della connessione WebSocket per un singolo device Xiaozhi.

Responsabilità:
- Ciclo di vita della connessione (connect, hello timeout, close, reconnect)
- Parsing e routing dei messaggi JSON
- Routing dei frame audio (grezzi, senza decoding PCM)
- Produzione di eventi astratti verso il runtime
- Cleanup task (nessun task orfano dopo disconnect)
- Duplicate connection policy

Derivato dall'audit in XIAOZHI_PROTOCOL_AUDIT.md e XIAOZHI_STATE_MACHINE.md.
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time
import uuid
from collections.abc import Callable
from typing import Any

from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol

from device.xiaozhi.errors import (
    InvalidStateTransition,
    MalformedMessage,
    ProtocolError,
    ProtocolVersionError,
    UnknownMessageType,
)
from device.xiaozhi.handlers.abort import AbortHandler
from device.xiaozhi.handlers.hello import HelloHandler
from device.xiaozhi.handlers.iot import IoTHandler
from device.xiaozhi.handlers.listen import ListenHandler
from device.xiaozhi.handlers.mcp import MCPHandler
from device.xiaozhi.messages import (
    AudioFrameReceived,
    DeviceDisconnected,
)
from device.xiaozhi.protocol import (
    get_message_type,
    parse_abort,
    parse_hello_device,
    parse_iot,
    parse_listen,
    parse_mcp,
    parse_message,
    serialize_error,
    serialize_hello_server,
    serialize_pong,
)
from device.xiaozhi.state import (
    SessionState,
    is_valid_transition,
)

logger = logging.getLogger("xiaozhi_voicemem.device.xiaozhi.connection")

#: Timeout per l'attesa del messaggio hello dal device (firmware: 10s).
HELLO_TIMEOUT_S = 10.0
#: Timeout idle connessione (nessun messaggio per questo tempo).
IDLE_TIMEOUT_S = 120.0


class DeviceConnection:
    """Gestisce una singola connessione WebSocket con un device Xiaozhi."""

    def __init__(
        self,
        websocket: WebSocketServerProtocol,
        device_id: str,
        client_id: str,
        protocol_version: int = 1,
        *,
        event_callback: Callable[[Any], None] | None = None,
        hello_timeout_s: float = HELLO_TIMEOUT_S,
        idle_timeout_s: float = IDLE_TIMEOUT_S,
    ):
        self.websocket = websocket
        self.device_id = device_id
        self.client_id = client_id
        self.protocol_version = protocol_version
        self.session_id = str(uuid.uuid4())
        self.state = SessionState.CONNECTED
        self._event_callback = event_callback
        self.hello_timeout_s = hello_timeout_s
        self.idle_timeout_s = idle_timeout_s

        # Parametri negoziati (popolati dopo hello)
        self.audio_params: dict[str, Any] = {}
        self.features: dict[str, Any] = {}

        # Task interni
        self._hello_task: asyncio.Task | None = None
        self._idle_task: asyncio.Task | None = None
        self._cleanup_done = asyncio.Event()

        # Handler registry
        self._handlers = {
            "hello": HelloHandler(),
            "listen": ListenHandler(),
            "abort": AbortHandler(),
            "mcp": MCPHandler(),
            "iot": IoTHandler(),
        }

        self._disconnected_emitted = False

        # Metriche
        self._last_message_ts = time.monotonic()
        self._bytes_received = 0
        self._messages_received = 0

    # ── Lifecycle ────────────────────────────────────────────────────────────

    async def run(self) -> None:
        """Avvia la connessione: reader loop con hello timeout e idle check."""
        try:
            self._transition(SessionState.CONNECTED)

            # Avvio hello timeout come task di supervisione
            self._hello_task = asyncio.create_task(self._wait_hello())

            # Avvio idle timeout
            self._idle_task = asyncio.create_task(self._idle_check())

            # Reader loop principale (legge frame finché la connessione è aperta)
            async for raw in self.websocket:
                self._last_message_ts = time.monotonic()

                if isinstance(raw, bytes):
                    await self._handle_binary(raw)
                else:
                    await self._handle_text(raw)

        except ConnectionClosed:
            logger.info("Connection closed: device=%s", self.device_id)
        except asyncio.CancelledError:
            pass
        finally:
            self._emit_disconnect_once("connection_closed")
            await self._cleanup()

    def _emit_disconnect_once(self, reason: str = "disconnected") -> None:
        if not self._disconnected_emitted:
            self._disconnected_emitted = True
            self._emit_event(DeviceDisconnected(
                session_id=self.session_id,
                device_id=self.device_id,
                reason=reason,
            ))

    async def close(self, reason: str = "server_close") -> None:
        """Chiude la connessione in modo controllato."""
        if self.state not in (SessionState.CLOSED, SessionState.DISCONNECTED):
            self._transition(SessionState.CLOSED)
        try:
            await self.websocket.close()
        except Exception:
            pass
        self._emit_disconnect_once(reason)

    # ── Reader loop ─────────────────────────────────────────────────────────

    async def _reader_loop(self) -> None:
        """Legge frame dal WebSocket e li smista."""
        async for raw in self.websocket:
            self._last_message_ts = time.monotonic()

            if isinstance(raw, bytes):
                await self._handle_binary(raw)
            else:
                await self._handle_text(raw)

    async def _handle_text(self, raw: str) -> None:
        """Gestisce un frame text (JSON)."""
        try:
            msg = parse_message(raw)
            msg_type = get_message_type(msg)
            self._messages_received += 1

            if msg_type == "hello":
                await self._handle_hello(msg)
            elif self.state != SessionState.HELLO_DONE:
                raise InvalidStateTransition(
                    self.state.name, SessionState.HELLO_DONE.name, self.session_id
                )
            elif msg_type == "listen":
                self._validate_session_id(msg)
                await self._route_message(msg_type, parse_listen(msg))
            elif msg_type == "abort":
                self._validate_session_id(msg)
                await self._route_message(msg_type, parse_abort(msg))
            elif msg_type == "mcp":
                self._validate_session_id(msg)
                payload = parse_mcp(msg)
                await self._route_message(msg_type, payload)
            elif msg_type == "iot":
                self._validate_session_id(msg)
                descriptors, states = parse_iot(msg)
                await self._route_message(msg_type, {"descriptors": descriptors, "states": states})
            elif msg_type == "ping":
                await self._handle_ping()
            else:
                logger.debug("Ignoring message type: %s", msg_type)

        except UnknownMessageType as e:
            logger.warning("Unknown message type: %s", e)
        except MalformedMessage as e:
            logger.warning("Malformed message: %s", e)
            await self._send_error("MALFORMED", str(e))
        except ProtocolError as e:
            logger.error("Protocol error: %s", e)
            if not e.recoverable:
                await self.close(str(e))

    async def _handle_binary(self, data: bytes) -> None:
        """Gestisce un frame binary (audio Opus).

        In M02 registriamo solo il dato grezzo. Il decoding PCM sarà in M03.
        """
        self._bytes_received += len(data)
        try:
            payload, timestamp = self._decode_audio_frame(data)
        except MalformedMessage as error:
            logger.warning("Malformed binary message: %s", error)
            await self._send_error("MALFORMED_BINARY", str(error))
            return
        self._emit_event(AudioFrameReceived(
            session_id=self.session_id,
            device_id=self.device_id,
            opus_data=payload,
            timestamp=timestamp,
        ))

    def _decode_audio_frame(self, data: bytes) -> tuple[bytes, int | None]:
        if self.protocol_version == 1:
            return data, None
        if self.protocol_version == 2:
            if len(data) < 16:
                raise MalformedMessage("binary", "version 2 header is truncated")
            version, frame_type, _reserved, timestamp, payload_size = struct.unpack(">HHIII", data[:16])
            if version != 2 or frame_type != 0:
                raise MalformedMessage("binary", "invalid version 2 audio header")
            payload = data[16:]
            if len(payload) != payload_size:
                raise MalformedMessage("binary", "version 2 payload size mismatch")
            return payload, timestamp
        if self.protocol_version == 3:
            if len(data) < 4:
                raise MalformedMessage("binary", "version 3 header is truncated")
            frame_type, _reserved, payload_size = struct.unpack(">BBH", data[:4])
            if frame_type != 0:
                raise MalformedMessage("binary", "invalid version 3 audio header")
            payload = data[4:]
            if len(payload) != payload_size:
                raise MalformedMessage("binary", "version 3 payload size mismatch")
            return payload, None
        raise ProtocolVersionError(self.protocol_version, [1, 2, 3])

    async def _handle_hello(self, msg: dict[str, Any]) -> None:
        """Gestisce il primo messaggio hello dal device."""
        if self.state != SessionState.CONNECTED:
            raise InvalidStateTransition(
                self.state.name, SessionState.HELLO_DONE.name, self.session_id
            )

        hello = parse_hello_device(msg)
        if hello.version != self.protocol_version:
            raise ProtocolVersionError(hello.version, [self.protocol_version])
        if hello.transport != "websocket":
            raise MalformedMessage("hello", "WebSocket endpoint requires transport=websocket")
        self.audio_params = {
            "format": hello.audio_params.format,
            "sample_rate": hello.audio_params.sample_rate,
            "channels": hello.audio_params.channels,
            "frame_duration": hello.audio_params.frame_duration,
        }
        self.features = {
            "mcp": hello.features.mcp,
            "aec": hello.features.aec,
            "glyph_push": hello.features.glyph_push,
        }

        # Transizione di stato
        self._transition(SessionState.HELLO_DONE)

        # Invia risposta hello (include transport, richiesto dal firmware)
        response = serialize_hello_server(
            session_id=self.session_id,
            transport="websocket",
        )
        await self.websocket.send(response)

        # Cancella hello timeout (arrivato in tempo)
        if self._hello_task:
            self._hello_task.cancel()
            self._hello_task = None

        # Emetti evento DeviceConnected
        events = await HelloHandler().handle(hello, {
            "session_id": self.session_id,
            "device_id": self.device_id,
            "client_id": self.client_id,
        })
        for evt in events:
            self._emit_event(evt)

        logger.info(
            "Hello done: device=%s session=%s version=%d",
            self.device_id, self.session_id, self.protocol_version,
        )

    async def _handle_ping(self) -> None:
        """Risponde a un ping con pong."""
        await self.websocket.send(serialize_pong())

    def _validate_session_id(self, msg: dict[str, Any]) -> None:
        session_id = msg.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise MalformedMessage("session", "session_id must be a non-empty string")
        if session_id != self.session_id:
            raise MalformedMessage("session", "session_id does not match this connection")

    async def _route_message(self, msg_type: str, parsed: Any) -> None:
        """Inoltra un messaggio all'handler appropriato."""
        handler = self._handlers.get(msg_type)
        if handler is None:
            logger.debug("No handler for %s", msg_type)
            return

        events = await handler.handle(parsed, {
            "session_id": self.session_id,
            "device_id": self.device_id,
        })
        for evt in events:
            self._emit_event(evt)

    # ── Timeout ─────────────────────────────────────────────────────────────

    async def _wait_hello(self) -> None:
        """Attende il messaggio hello con timeout."""
        try:
            await asyncio.sleep(self.hello_timeout_s)
        except asyncio.CancelledError:
            return  # Hello arrivato in tempo

        # Timeout scaduto: hello non ricevuto
        if self.state == SessionState.CONNECTED:
            logger.warning(
                "Hello timeout: device=%s after %.1fs",
                self.device_id, self.hello_timeout_s,
            )
            await self.close("hello_timeout")

    async def _idle_check(self) -> None:
        """Chiude la connessione se non ci sono messaggi per idle_timeout_s."""
        interval = min(30.0, max(0.1, self.idle_timeout_s / 2))
        while True:
            await asyncio.sleep(interval)
            elapsed = time.monotonic() - self._last_message_ts
            if elapsed > self.idle_timeout_s and self.state != SessionState.DISCONNECTED:
                logger.info(
                    "Idle timeout: device=%s session=%s elapsed=%.0fs",
                    self.device_id, self.session_id, elapsed,
                )
                await self.close("idle_timeout")
                break

    # ── Utility ─────────────────────────────────────────────────────────────

    def _transition(self, new_state: SessionState) -> None:
        """Esegue una transizione di stato, validandola."""
        if not is_valid_transition(self.state, new_state):
            raise InvalidStateTransition(
                self.state.name, new_state.name, self.session_id
            )
        old = self.state
        self.state = new_state
        logger.debug("State: %s -> %s (device=%s)", old.name, new_state.name, self.device_id)

    async def _send_error(self, code: str, message: str) -> None:
        """Invia un messaggio di errore al device."""
        try:
            await self.websocket.send(serialize_error(self.session_id, code, message))
        except Exception:
            pass

    def _emit_event(self, event: Any) -> None:
        """Emetti un evento verso il runtime (se callback configurato)."""
        if self._event_callback:
            try:
                self._event_callback(event)
            except Exception as e:
                logger.error("Event callback error: %s", e)

    async def _cleanup(self) -> None:
        """Pulizia risorse: cancella task, chiude socket."""
        self._transition(SessionState.DISCONNECTED)

        current_task = asyncio.current_task()
        for t in [self._hello_task, self._idle_task]:
            if t is current_task:
                continue
            if t and not t.done():
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass

        self._hello_task = None
        self._idle_task = None
        self._cleanup_done.set()

        logger.info("Connection cleaned up: device=%s session=%s", self.device_id, self.session_id)
