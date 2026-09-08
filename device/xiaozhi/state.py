"""Stati della sessione protocollo WebSocket (lato server).

Derivati dall'audit firmware `_upstream/xiaozhi-esp32`:
- Stati protocollo WebSocket documentati in XIAOZHI_STATE_MACHINE.md
- Transizioni verificate da `websocket_protocol.cc` e `device_state_machine.cc`

Questi sono gli stati della connessione/sessione lato server, NON gli stati
del device (che sono gestiti dal firmware e ci arrivano via messaggi).
"""

from __future__ import annotations

from enum import Enum, auto


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
