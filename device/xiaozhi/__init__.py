"""Package `device.xiaozhi` — protocollo e transport verso il device ESP32 stock.

Vincolo architetturale non negoziabile:
- Questo package contiene **solo** protocollo, transport, framing/codec e semantica
  device/server.
- **NON** deve contenere logica ASR, VAD, LLM, Memory o TTS.
- **NON** deve importare moduli AI (voicemem o simili).
- Il firmware ESP32 resta stock: nessuna modifica lato device.
"""

from __future__ import annotations

from device.xiaozhi.connection import DeviceConnection
from device.xiaozhi.errors import (
    AuthenticationError,
    HelloTimeout,
    InvalidStateTransition,
    MalformedMessage,
    ProtocolError,
    ProtocolVersionError,
    UnknownMessageType,
)
from device.xiaozhi.protocol import get_message_type, parse_message
from device.xiaozhi.server import XiaozhiWebSocketServer
from device.xiaozhi.state import DeviceProtocolState, SessionState

__all__ = [
    "__version__",
    "XiaozhiWebSocketServer",
    "DeviceConnection",
    "parse_message",
    "get_message_type",
    "SessionState",
    "DeviceProtocolState",
    "ProtocolError",
    "MalformedMessage",
    "UnknownMessageType",
    "InvalidStateTransition",
    "HelloTimeout",
    "AuthenticationError",
    "ProtocolVersionError",
]

__version__ = "0.2.0"
