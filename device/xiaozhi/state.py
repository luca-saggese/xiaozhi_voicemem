"""Stati della sessione protocollo WebSocket (lato server).

Derivati dall'audit firmware `_upstream/xiaozhi-esp32`:
- Stati protocollo WebSocket documentati in XIAOZHI_STATE_MACHINE.md
- Transizioni verificate da `websocket_protocol.cc` e `device_state_machine.cc`

Questi sono gli stati della connessione/sessione lato server, NON gli stati
del device (che sono gestiti dal firmware e ci arrivano via messaggi).
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Any

from device.xiaozhi.codec import BinaryFramingVersion, decode_frame
from device.xiaozhi.errors import InvalidStateTransition, SessionIdMismatch
from device.xiaozhi.events import (
    AbortRequested,
    AudioFrameReceived,
    DeviceConnected,
    IoTReceived,
    ListenStarted,
    ListenStopped,
    MCPReceived,
    WakeWordDetected,
)
from device.xiaozhi.protocol import (
    get_message_type,
    parse_abort,
    parse_hello_device,
    parse_iot,
    parse_listen,
    parse_mcp,
)


class SessionState(Enum):
    """Stati della sessione protocollo WebSocket lato server."""

    DISCONNECTED = auto()
    """Socket chiuso, nessuna connessione attiva."""

    CONNECTING = auto()
    """Handshake WebSocket in corso."""

    CONNECTED = auto()
    """Socket aperto, hello non ancora ricevuto dal device."""

    HELLO_DONE = auto()
    """Hello ricevuto e risposto, sessione attiva e pronta."""

    CLOSED = auto()
    """Sessione terminata (clean close)."""


# Transizioni valide per SessionState
# Include self-transitions (no-op, come da firmware device_state_machine.cc)
_VALID_TRANSITIONS: dict[SessionState, set[SessionState]] = {
    SessionState.DISCONNECTED: {SessionState.DISCONNECTED, SessionState.CONNECTING},
    SessionState.CONNECTING: {SessionState.CONNECTING, SessionState.CONNECTED, SessionState.DISCONNECTED},
    SessionState.CONNECTED: {SessionState.CONNECTED, SessionState.HELLO_DONE, SessionState.DISCONNECTED, SessionState.CLOSED},
    SessionState.HELLO_DONE: {SessionState.HELLO_DONE, SessionState.CLOSED, SessionState.DISCONNECTED},
    SessionState.CLOSED: {SessionState.CLOSED, SessionState.DISCONNECTED},
}


def is_valid_transition(from_state: SessionState, to_state: SessionState) -> bool:
    """Verifica se una transizione è valida secondo la state machine del protocollo."""
    allowed = _VALID_TRANSITIONS.get(from_state, set())
    return to_state in allowed


class ProtocolSession:
    """State machine server-side per messaggi già separati dal transport."""

    def __init__(self, session_id: str, device_id: str, protocol_version: int = 1):
        self.session_id = session_id
        self.device_id = device_id
        self.protocol_version = protocol_version
        self.state = SessionState.CONNECTED
        self._hello: Any = None

    def receive(self, message: dict[str, Any]) -> Any:
        """Valida e converte un messaggio JSON in un evento interno."""

        if self.state in (SessionState.CLOSED, SessionState.DISCONNECTED):
            raise InvalidStateTransition(self.state.name, "RECEIVE", self.session_id)
        message_type = get_message_type(message)
        if message_type == "hello":
            if self.state is not SessionState.CONNECTED:
                raise InvalidStateTransition(self.state.name, "HELLO", self.session_id)
            hello = parse_hello_device(message)
            self._hello = hello
            self._transition(SessionState.HELLO_DONE)
            return DeviceConnected(
                session_id=self.session_id,
                device_id=self.device_id,
                client_id="",
                protocol_version=hello.version,
                audio_params=hello.audio_params,
                features=hello.features,
            )

        if self.state is not SessionState.HELLO_DONE:
            raise InvalidStateTransition(self.state.name, message_type, self.session_id)
        if message_type != "ping":
            actual_session = message.get("session_id")
            if actual_session != self.session_id:
                raise SessionIdMismatch(self.session_id, str(actual_session))

        if message_type == "listen":
            listen_message = parse_listen(message)
            if listen_message.state == "start":
                return ListenStarted(self.session_id, self.device_id, listen_message.mode)
            if listen_message.state == "stop":
                return ListenStopped(self.session_id, self.device_id)
            return WakeWordDetected(self.session_id, self.device_id, listen_message.text or "")
        if message_type == "abort":
            abort_message = parse_abort(message)
            return AbortRequested(self.session_id, self.device_id, abort_message.reason)
        if message_type == "mcp":
            return MCPReceived(self.session_id, self.device_id, parse_mcp(message))
        if message_type == "iot":
            descriptors, states = parse_iot(message)
            return IoTReceived(self.session_id, self.device_id, descriptors, states)
        return None

    def receive_binary(self, data: bytes) -> AudioFrameReceived:
        if self.state is not SessionState.HELLO_DONE:
            raise InvalidStateTransition(self.state.name, "AUDIO", self.session_id)
        frame = decode_frame(data, BinaryFramingVersion(self.protocol_version))
        return AudioFrameReceived(
            session_id=self.session_id,
            device_id=self.device_id,
            opus_data=frame.payload,
            timestamp=frame.timestamp or None,
        )

    def close(self) -> None:
        if self.state is SessionState.CLOSED:
            return
        self._transition(SessionState.CLOSED)

    def _transition(self, new_state: SessionState) -> None:
        if not is_valid_transition(self.state, new_state):
            raise InvalidStateTransition(self.state.name, new_state.name, self.session_id)
        self.state = new_state


class DeviceListenState(Enum):
    """Stato di ascolto del device (tracking lato server)."""

    IDLE = auto()
    """Nessun ascolto in corso."""
    LISTENING = auto()
    """Device in ascolto, audio in arrivo."""
    SPEAKING = auto()
    """Server in riproduzione TTS verso device."""
    WAITING = auto()
    """In attesa di elaborazione (ASR/LLM)."""


class DeviceProtocolState(Enum):
    """Stati device come definiti dal firmware (device_state.h).

    Usati per tracciare lo stato dichiarato dal device via messaggi.
    Non tutti sono rilevanti lato server; includiamo quelli che il
    protocollo ci notifica.
    """

    UNKNOWN = 0
    IDLE = 3
    CONNECTING = 4
    LISTENING = 5
    SPEAKING = 6
    UPGRADING = 8
    FATAL_ERROR = 11
