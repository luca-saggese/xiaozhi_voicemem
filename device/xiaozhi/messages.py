"""Messaggi tipizzati del protocollo Xiaozhi.

Ogni messaggio è una dataclass immutabile con validazione dei campi.
Derivati dall'audit in XIAOZHI_MESSAGE_CATALOG.md e XIAOZHI_PROTOCOL_AUDIT.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ── Tipi di messaggio ───────────────────────────────────────────────────────

# Elenco completo dei message type supportati (vedi XIAOZHI_MESSAGE_CATALOG.md)
MSG_HELLO = "hello"
MSG_LISTEN = "listen"
MSG_ABORT = "abort"
MSG_STT = "stt"
MSG_TTS = "tts"
MSG_LLM = "llm"
MSG_MCP = "mcp"
MSG_IOT = "iot"
MSG_PING = "ping"
MSG_PONG = "pong"
MSG_SERVER = "server"
MSG_SYSTEM = "system"
MSG_ALERT = "alert"
MSG_GOODBYE = "goodbye"
MSG_NOTIFY = "notify"
MSG_CUSTOM = "custom"

# Tutti i type conosciuti (per validazione)
KNOWN_TYPES = frozenset({
    MSG_HELLO, MSG_LISTEN, MSG_ABORT, MSG_STT, MSG_TTS, MSG_LLM, MSG_MCP, MSG_IOT,
    MSG_PING, MSG_PONG, MSG_SERVER, MSG_SYSTEM, MSG_ALERT, MSG_GOODBYE,
    MSG_NOTIFY, MSG_CUSTOM,
})


# ── Dataclass messaggi ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class AudioParams:
    """Parametri audio negoziati."""
    format: str = "opus"
    sample_rate: int = 16000
    channels: int = 1
    frame_duration: int = 60


@dataclass(frozen=True)
class TextFont:
    """Capacità text-font (glyph push)."""
    bundle: str = "noto-v1"
    charset: str = "common"
    size: int = 20
    bpp: int = 4


@dataclass(frozen=True)
class Features:
    """Feature flags del device."""
    mcp: bool = True
    aec: bool = False
    glyph_push: bool = False


@dataclass(frozen=True)
class HelloDevice:
    """Messaggio hello inviato dal device al server."""
    type: str = MSG_HELLO
    version: int = 1
    transport: str = "websocket"
    audio_params: AudioParams = field(default_factory=AudioParams)
    features: Features = field(default_factory=Features)
    text_font: TextFont | None = None


@dataclass(frozen=True)
class HelloServer:
    """Messaggio hello inviato dal server al device."""
    type: str = MSG_HELLO
    transport: str = "websocket"
    session_id: str = ""
    audio_params: AudioParams = field(default_factory=lambda: AudioParams(
        format="opus", sample_rate=24000, channels=1, frame_duration=60,
    ))


@dataclass(frozen=True)
class Listen:
    """Messaggio listen dal device."""
    session_id: str
    type: str = MSG_LISTEN
    state: str = "start"  # "start" | "stop" | "detect"
    mode: str | None = None  # "auto" | "manual" | "realtime"
    text: str | None = None  # solo per state="detect" (wake word)


@dataclass(frozen=True)
class Abort:
    """Messaggio abort dal device."""
    session_id: str
    type: str = MSG_ABORT
    reason: str | None = None  # "wake_word_detected"


@dataclass(frozen=True)
class STT:
    """Messaggio stt dal server al device (trascrizione)."""
    session_id: str
    type: str = MSG_STT
    text: str = ""


@dataclass(frozen=True)
class TTS:
    """Messaggio tts dal server al device."""
    session_id: str
    type: str = MSG_TTS
    state: str = "start"  # "start" | "stop" | "sentence_start"
    text: str | None = None


@dataclass(frozen=True)
class LLM:
    """Messaggio llm dal server al device."""
    session_id: str
    type: str = MSG_LLM
    emotion: str | None = None
    text: str | None = None


@dataclass(frozen=True)
class MCP:
    """Messaggio mcp (JSON-RPC 2.0 envelope)."""
    session_id: str
    type: str = MSG_MCP
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IoT:
    """Messaggio iot dal device."""
    session_id: str
    type: str = MSG_IOT
    descriptors: list[dict[str, Any]] | None = None
    states: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class Ping:
    """Messaggio ping dal device."""
    type: str = MSG_PING


@dataclass(frozen=True)
class Pong:
    """Messaggio pong dal server."""
    type: str = MSG_PONG
    timestamp: int | float | str = ""


@dataclass(frozen=True)
class ServerMessage:
    """Messaggio server (update config / restart)."""
    type: str = MSG_SERVER
    action: str = ""  # "update_config" | "restart"
    content: dict[str, Any] | None = None
    status: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class System:
    """Messaggio system (reboot)."""
    type: str = MSG_SYSTEM
    command: str = "reboot"


@dataclass(frozen=True)
class Alert:
    """Messaggio alert."""
    type: str = MSG_ALERT
    status: str | None = None
    message: str | None = None
    emotion: str | None = None


@dataclass(frozen=True)
class Goodbye:
    """Messaggio goodbye (MQTT only)."""
    session_id: str
    type: str = MSG_GOODBYE


@dataclass(frozen=True)
class NotifyMessage:
    """Notifica audio server-side gestita dal firmware stock."""

    audio_url: str
    type: str = MSG_NOTIFY
    subtitles: list[dict[str, Any]] | None = None


# Nomi espliciti del contratto protocollo; gli alias mantengono compatibilità
# con gli handler M02 già esistenti che usano i nomi brevi.
ListenMessage = Listen
AbortMessage = Abort
STTMessage = STT
TTSMessage = TTS
LLMMessage = LLM
PingMessage = Ping
PongMessage = Pong


# ── Eventi interni (device → runtime) ───────────────────────────────────────


@dataclass(frozen=True)
class DeviceConnected:
    """Evento: device connesso e hello completato."""
    session_id: str
    device_id: str
    client_id: str
    protocol_version: int
    audio_params: AudioParams
    features: Features


@dataclass(frozen=True)
class DeviceDisconnected:
    """Evento: device disconnesso."""
    session_id: str
    device_id: str
    reason: str = "unknown"


@dataclass(frozen=True)
class ListenStarted:
    """Evento: device ha iniziato l'ascolto."""
    session_id: str
    device_id: str
    mode: str | None = None


@dataclass(frozen=True)
class ListenStopped:
    """Evento: device ha fermato l'ascolto."""
    session_id: str
    device_id: str


@dataclass(frozen=True)
class AbortRequested:
    """Evento: device ha richiesto abort."""
    session_id: str
    device_id: str
    reason: str | None = None


@dataclass(frozen=True)
class MCPMessage:
    """Evento: messaggio MCP dal device."""
    session_id: str
    device_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class IoTMessage:
    """Evento: messaggio IoT dal device."""
    session_id: str
    device_id: str
    descriptors: list[dict[str, Any]] | None = None
    states: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class AudioFrameReceived:
    """Evento: frame audio Opus ricevuto dal device.

    L'implementazione codec/framing completa appartiene a M03.
    In M02 registriamo solo il dato grezzo.
    """
    session_id: str
    device_id: str
    #: Dato Opus grezzo (bytes). Il decoding in PCM sarà in M03.
    opus_data: bytes
    #: Timestamp opzionale (solo binary protocol v2).
    timestamp: int | None = None


# ── Comandi interni (runtime → device) ──────────────────────────────────────


@dataclass(frozen=True)
class SendHello:
    """Comando: invia hello al device (usato in reconnect)."""
    session_id: str
    device_id: str


@dataclass(frozen=True)
class SendTranscript:
    """Comando: invia trascrizione STT al device."""
    session_id: str
    device_id: str
    text: str


@dataclass(frozen=True)
class SendTTSStart:
    """Comando: avvia TTS sul device."""
    session_id: str
    device_id: str


@dataclass(frozen=True)
class SendTTSStop:
    """Comando: ferma TTS sul device."""
    session_id: str
    device_id: str


@dataclass(frozen=True)
class SendMCP:
    """Comando: invia messaggio MCP al device."""
    session_id: str
    device_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class SendIoT:
    """Comando: invia messaggio IoT al device."""
    session_id: str
    device_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class SendError:
    """Comando: invia errore al device."""
    session_id: str
    device_id: str
    code: str
    message: str
