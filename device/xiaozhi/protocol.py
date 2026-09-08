"""Parser del protocollo Xiaozhi: JSON ↔ dataclass tipizzate.

Responsabilità:
- Parsing dei messaggi JSON in arrivo dal device in dataclass tipizzate
- Serializzazione dei messaggi in uscita verso il device in JSON
- Validazione esplicita dei campi obbligatori
- Gestione deterministica degli errori (nessun crash su payload malformato)
- Preservazione dati protocollo per versioni differenti

Derivato dall'audit in XIAOZHI_PROTOCOL_AUDIT.md e XIAOZHI_MESSAGE_CATALOG.md.
"""

from __future__ import annotations

import json
import time
from typing import Any

from device.xiaozhi.errors import MalformedMessage, UnknownMessageType
from device.xiaozhi.messages import (
    KNOWN_TYPES,
    Abort,
    AudioParams,
    Features,
    HelloDevice,
    Listen,
    TextFont,
)


def parse_message(raw: str) -> dict[str, Any]:
    """Parsa un messaggio JSON dal device.

    Args:
        raw: Stringa JSON grezza dal WebSocket.

    Returns:
        Dict con i campi parsati.

    Raises:
        MalformedMessage: se il JSON non è valido.
    """
    try:
        msg = json.loads(raw)
    except json.JSONDecodeError as e:
        raise MalformedMessage("Invalid JSON", str(e)) from e

    if not isinstance(msg, dict):
        raise MalformedMessage("Payload must be a JSON object")

    return msg


def get_message_type(msg: dict[str, Any]) -> str:
    """Estrae e valida il campo `type` da un messaggio.

    Raises:
        MalformedMessage: se `type` è mancante o non è una stringa.
        UnknownMessageType: se `type` non è tra quelli conosciuti.
    """
    msg_type = msg.get("type")
    if not isinstance(msg_type, str) or not msg_type:
        raise MalformedMessage("Missing or invalid 'type' field")
    if msg_type not in KNOWN_TYPES:
        raise UnknownMessageType(msg_type)
    return msg_type


def _required_string(payload: dict[str, Any], field: str, message_type: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise MalformedMessage(message_type, f"{field} must be a non-empty string")
    return value


def _required_int(payload: dict[str, Any], field: str, message_type: str) -> int:
    value = payload.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise MalformedMessage(message_type, f"{field} must be an integer")
    return value


def _required_bool(payload: dict[str, Any], field: str, message_type: str) -> bool:
    value = payload.get(field)
    if not isinstance(value, bool):
        raise MalformedMessage(message_type, f"{field} must be a boolean")
    return value


def parse_hello_device(msg: dict[str, Any]) -> HelloDevice:
    """Parsa un messaggio hello dal device.

    Campi obbligatori: type, version, transport, features.mcp,
    audio_params{format,sample_rate,channels,frame_duration}
    Campi opzionali: features{aec,glyph_push}, text_font
    """
    version = _required_int(msg, "version", "hello")

    transport = msg.get("transport")
    if transport not in ("websocket", "udp"):
        raise MalformedMessage("hello", f"invalid transport: {transport!r}")

    # audio_params
    ap = msg.get("audio_params")
    if not isinstance(ap, dict):
        raise MalformedMessage("hello", "audio_params is required")
    audio_format = _required_string(ap, "format", "hello.audio_params")
    if audio_format != "opus":
        raise MalformedMessage("hello.audio_params", f"unsupported format: {audio_format!r}")
    sample_rate = _required_int(ap, "sample_rate", "hello.audio_params")
    channels = _required_int(ap, "channels", "hello.audio_params")
    frame_duration = _required_int(ap, "frame_duration", "hello.audio_params")
    if sample_rate <= 0 or channels <= 0 or frame_duration <= 0:
        raise MalformedMessage("hello.audio_params", "audio values must be positive")
    audio_params = AudioParams(
        format=audio_format,
        sample_rate=sample_rate,
        channels=channels,
        frame_duration=frame_duration,
    )

    # features
    feat = msg.get("features")
    if not isinstance(feat, dict):
        raise MalformedMessage("hello", "features is required")
    features = Features(
        mcp=_required_bool(feat, "mcp", "hello.features"),
        aec=feat.get("aec", False),
        glyph_push=feat.get("glyph_push", False),
    )
    if not isinstance(features.aec, bool) or not isinstance(features.glyph_push, bool):
        raise MalformedMessage("hello.features", "optional feature flags must be booleans")

    # text_font (opzionale)
    tf = msg.get("text_font")
    text_font = None
    if isinstance(tf, dict):
        text_font = TextFont(
            bundle=_required_string(tf, "bundle", "hello.text_font"),
            charset=_required_string(tf, "charset", "hello.text_font"),
            size=_required_int(tf, "size", "hello.text_font"),
            bpp=_required_int(tf, "bpp", "hello.text_font"),
        )
    elif tf is not None:
        raise MalformedMessage("hello", "text_font must be an object")

    return HelloDevice(
        version=version,
        transport=transport,
        audio_params=audio_params,
        features=features,
        text_font=text_font,
    )


def parse_listen(msg: dict[str, Any]) -> Listen:
    """Parsa un messaggio listen dal device.

    Campi obbligatori: session_id, type, state
    Campi opzionali: mode, text
    """
    session_id = _required_string(msg, "session_id", "listen")
    state = _required_string(msg, "state", "listen")
    if state not in ("start", "stop", "detect"):
        raise MalformedMessage("listen", f"invalid state: {state!r}")

    mode = msg.get("mode")
    if mode is not None and mode not in ("auto", "manual", "realtime"):
        raise MalformedMessage("listen", f"invalid mode: {mode!r}")

    text = msg.get("text") if state == "detect" else None
    if state == "detect" and (not isinstance(text, str) or not text):
        raise MalformedMessage("listen", "text is required for state=detect")
    if text is not None and not isinstance(text, str):
        raise MalformedMessage("listen", "text must be a string")

    return Listen(
        session_id=session_id,
        state=state,
        mode=mode,
        text=text,
    )


def parse_abort(msg: dict[str, Any]) -> Abort:
    """Parsa un messaggio abort dal device.

    Campi obbligatori: session_id, type
    Campi opzionali: reason
    """
    session_id = _required_string(msg, "session_id", "abort")
    reason = msg.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise MalformedMessage("abort", "reason must be a string")
    return Abort(session_id=session_id, reason=reason)


def parse_mcp(msg: dict[str, Any]) -> dict[str, Any]:
    """Parsa un messaggio mcp dal device.

    Restituisce il payload JSON-RPC 2.0.
    """
    _required_string(msg, "session_id", "mcp")
    payload = msg.get("payload")
    if not isinstance(payload, dict):
        raise MalformedMessage("mcp", "payload must be a JSON object")
    if payload.get("jsonrpc") != "2.0":
        raise MalformedMessage("mcp", "payload.jsonrpc must be '2.0'")
    if not any(key in payload for key in ("method", "result", "error")):
        raise MalformedMessage("mcp", "payload must contain method, result, or error")
    return payload


def parse_iot(msg: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, list[dict[str, Any]] | None]:
    """Parsa un messaggio iot dal device.

    Restituisce (descriptors, states).
    """
    _required_string(msg, "session_id", "iot")
    descriptors = msg.get("descriptors")
    states = msg.get("states")
    if descriptors is not None and not isinstance(descriptors, list):
        raise MalformedMessage("iot", "descriptors must be an array")
    if states is not None and not isinstance(states, list):
        raise MalformedMessage("iot", "states must be an array")
    if descriptors is not None and any(not isinstance(item, dict) for item in descriptors):
        raise MalformedMessage("iot", "descriptors items must be objects")
    if states is not None and any(not isinstance(item, dict) for item in states):
        raise MalformedMessage("iot", "states items must be objects")
    return descriptors, states


# ── Serializzazione (server → device) ────────────────────────────────────────


def serialize_hello_server(
    session_id: str,
    audio_params: AudioParams | None = None,
    transport: str = "websocket",
) -> str:
    """Serializza un messaggio hello server → device.

    Include `transport` (richiesto dal firmware: websocket_protocol.cc:228).
    """
    ap = audio_params or AudioParams(format="opus", sample_rate=24000, channels=1, frame_duration=60)
    msg = {
        "type": "hello",
        "transport": transport,
        "session_id": session_id,
        "audio_params": {
            "format": ap.format,
            "sample_rate": ap.sample_rate,
            "channels": ap.channels,
            "frame_duration": ap.frame_duration,
        },
    }
    return json.dumps(msg, ensure_ascii=False)


def serialize_stt(session_id: str, text: str) -> str:
    return json.dumps({
        "session_id": session_id,
        "type": "stt",
        "text": text,
    }, ensure_ascii=False)


def serialize_tts_start(session_id: str) -> str:
    return json.dumps({
        "session_id": session_id,
        "type": "tts",
        "state": "start",
    })


def serialize_tts_sentence(session_id: str, text: str) -> str:
    return json.dumps({
        "session_id": session_id,
        "type": "tts",
        "state": "sentence_start",
        "text": text,
    }, ensure_ascii=False)


def serialize_tts_stop(session_id: str) -> str:
    return json.dumps({
        "session_id": session_id,
        "type": "tts",
        "state": "stop",
    })


def serialize_llm(session_id: str, text: str = "", emotion: str = "") -> str:
    msg: dict[str, Any] = {"session_id": session_id, "type": "llm"}
    if emotion:
        msg["emotion"] = emotion
    if text:
        msg["text"] = text
    return json.dumps(msg, ensure_ascii=False)


def serialize_mcp(session_id: str, payload: dict[str, Any]) -> str:
    return json.dumps({
        "session_id": session_id,
        "type": "mcp",
        "payload": payload,
    }, ensure_ascii=False)


def serialize_iot(session_id: str, payload: dict[str, Any]) -> str:
    return json.dumps({
        "session_id": session_id,
        "type": "iot",
        **payload,
    }, ensure_ascii=False)


def serialize_pong(timestamp: str = "") -> str:
    return json.dumps({
        "type": "pong",
        "timestamp": timestamp or time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
    })


def serialize_error(session_id: str, code: str, message: str) -> str:
    return json.dumps({
        "session_id": session_id,
        "type": "server",
        "action": "error",
        "status": "error",
        "message": f"[{code}] {message}",
    }, ensure_ascii=False)


def serialize_system(session_id: str, command: str = "reboot") -> str:
    return json.dumps({
        "session_id": session_id,
        "type": "system",
        "command": command,
    })


def serialize_alert(session_id: str, status: str = "", message: str = "", emotion: str = "") -> str:
    msg: dict[str, Any] = {"session_id": session_id, "type": "alert"}
    if status:
        msg["status"] = status
    if message:
        msg["message"] = message
    if emotion:
        msg["emotion"] = emotion
    return json.dumps(msg, ensure_ascii=False)
