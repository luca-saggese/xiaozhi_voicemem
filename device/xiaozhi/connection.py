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
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from websockets.exceptions import ConnectionClosed
from websockets.legacy.server import WebSocketServerProtocol

from device.xiaozhi.codec import BinaryFramingVersion, MalformedFrame, decode_frame
from device.xiaozhi.commands import (
    SendHello,
    SendIoT,
    SendLLMState,
    SendMCP,
    SendPong,
    SendTranscript,
    SendTTSSentence,
    SendTTSStart,
    SendTTSStop,
)
from device.xiaozhi.errors import (
    InvalidStateTransition,
    MalformedMessage,
    ProtocolError,
    ProtocolVersionError,
    SessionIdMismatch,
    UnknownMessageType,
)
from device.xiaozhi.handlers.abort import AbortHandler
from device.xiaozhi.handlers.hello import HelloHandler
from device.xiaozhi.handlers.iot import IoTHandler
from device.xiaozhi.handlers.listen import ListenHandler
from device.xiaozhi.handlers.mcp import MCPHandler
from device.xiaozhi.messages import (
    AudioFrameReceived,
    AudioParams,
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
    serialize_iot,
    serialize_llm,
    serialize_mcp,
    serialize_pong,
    serialize_stt,
    serialize_tts_sentence,
    serialize_tts_start,
    serialize_tts_stop,
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
_EVENT_END = object()


@dataclass(frozen=True)
class SessionHeaders:
    """Header WebSocket conservati per la durata della sessione."""

    authorization: str
    protocol_version: str
    device_id: str
    client_id: str


class DeviceConnection:
    """Sessione WebSocket Xiaozhi e bridge tra transport ed eventi runtime."""

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
        authorization: str = "",
        server_audio_params: dict[str, Any] | None = None,
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
        self.headers = SessionHeaders(
            authorization=authorization,
            protocol_version=str(protocol_version),
            device_id=device_id,
            client_id=client_id,
        )
        self.auth_info = {"authorization": authorization}
        self.server_audio_params = server_audio_params or {
            "format": "opus",
            "sample_rate": 24000,
            "channels": 1,
            "frame_duration": 60,
        }
        self.connected_at = time.time()
        self.last_activity_at = self.connected_at
        self._events: asyncio.Queue[Any] = asyncio.Queue()
        self._send_lock = asyncio.Lock()

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
                self.last_activity_at = time.time()

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
            if e.recoverable:
                await self._send_error(e.code, str(e))
            else:
                await self.close(str(e))

    async def _handle_binary(self, data: bytes) -> None:
        """Gestisce un frame binary (audio Opus).

        In M02 registriamo solo il dato grezzo. Il decoding PCM sarà in M03.
        """
        if self.state is not SessionState.HELLO_DONE:
            raise InvalidStateTransition(self.state.name, "AUDIO", self.session_id)
        self._bytes_received += len(data)
        try:
            frame = decode_frame(data, BinaryFramingVersion(self.protocol_version))
            if frame.frame_type != 0:
                raise MalformedFrame("binary frame type is not Opus audio")
        except (MalformedFrame, ValueError) as error:
            logger.warning("Malformed binary message: %s", error)
            await self._send_error("MALFORMED_BINARY", str(error))
            return
        self._emit_event(AudioFrameReceived(
            session_id=self.session_id,
            device_id=self.device_id,
            opus_data=frame.payload,
            timestamp=frame.timestamp or None,
        ))

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
            audio_params=self._audio_params_model(self.server_audio_params),
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
            raise SessionIdMismatch(self.session_id, session_id)

    async def send(self, command: Any) -> None:
        """Serializza e invia un comando server-side sul WebSocket."""

        if self.state is not SessionState.HELLO_DONE and not isinstance(command, SendHello):
            raise InvalidStateTransition(self.state.name, "SEND", self.session_id)
        command_session_id = getattr(command, "session_id", self.session_id)
        if command_session_id != self.session_id:
            raise SessionIdMismatch(self.session_id, str(command_session_id))

        if isinstance(command, SendHello):
            payload = serialize_hello_server(
                self.session_id,
                transport="websocket",
                audio_params=self._audio_params_model(self.server_audio_params),
            )
        elif isinstance(command, SendTranscript):
            payload = serialize_stt(self.session_id, command.text)
        elif isinstance(command, SendTTSStart):
            payload = serialize_tts_start(self.session_id)
        elif isinstance(command, SendTTSSentence):
            payload = serialize_tts_sentence(self.session_id, command.text)
        elif isinstance(command, SendTTSStop):
            payload = serialize_tts_stop(self.session_id)
        elif isinstance(command, SendLLMState):
            payload = serialize_llm(self.session_id, command.text or "", command.emotion or "")
        elif isinstance(command, SendMCP):
            payload = serialize_mcp(self.session_id, command.payload)
        elif isinstance(command, SendIoT):
            payload = serialize_iot(self.session_id, command.payload)
        elif isinstance(command, SendPong):
            payload = serialize_pong(str(command.timestamp))
        else:
            raise TypeError(f"unsupported Xiaozhi command: {type(command).__name__}")

        async with self._send_lock:
            await self.websocket.send(payload)

    @staticmethod
    def _audio_params_model(params: dict[str, Any]) -> AudioParams:
        return AudioParams(
            format=str(params.get("format", "opus")),
            sample_rate=int(params.get("sample_rate", 24000)),
            channels=int(params.get("channels", 1)),
            frame_duration=int(params.get("frame_duration", 60)),
        )

    async def events(self):
        """Itera sugli eventi fino alla disconnessione della sessione."""

        while True:
            event = await self._events.get()
            if event is _EVENT_END:
                return
            yield event

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
        self._events.put_nowait(event)
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
        self._events.put_nowait(_EVENT_END)
        self._cleanup_done.set()

        logger.info("Connection cleaned up: device=%s session=%s", self.device_id, self.session_id)

# Nome semantico del contratto runtime; DeviceConnection resta l'API legacy.
DeviceSession = DeviceConnection
