"""Test offline del protocol core M02, senza WebSocket o audio codec."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

from device.xiaozhi.codec import BinaryFramingVersion, MalformedFrame, decode_frame, encode_frame
from device.xiaozhi.errors import InvalidStateTransition, MalformedMessage, SessionIdMismatch
from device.xiaozhi.events import IoTReceived, MCPReceived, WakeWordDetected
from device.xiaozhi.protocol import (
    parse_abort,
    parse_hello_device,
    parse_hello_server,
    parse_iot,
    parse_listen,
    parse_llm,
    parse_mcp,
    parse_ping,
    parse_pong,
    parse_stt,
    parse_tts,
)
from device.xiaozhi.state import ProtocolSession, SessionState

HELLO_DEVICE = {
    "type": "hello",
    "version": 1,
    "features": {"mcp": True},
    "transport": "websocket",
    "audio_params": {
        "format": "opus",
        "sample_rate": 16000,
        "channels": 1,
        "frame_duration": 60,
    },
}


def test_hello_models_and_invalid_required_fields() -> None:
    assert parse_hello_device(HELLO_DEVICE).version == 1
    server = {
        "type": "hello",
        "transport": "websocket",
        "session_id": "s1",
        "audio_params": {"format": "opus", "sample_rate": 24000, "channels": 1, "frame_duration": 60},
    }
    assert parse_hello_server(server).session_id == "s1"
    with pytest.raises(MalformedMessage):
        parse_hello_device({**HELLO_DEVICE, "version": True})
    with pytest.raises(MalformedMessage):
        parse_hello_server({**server, "transport": "mqtt"})


@pytest.mark.parametrize(
    ("state", "extra"),
    [("start", {}), ("stop", {}), ("detect", {"text": "xiaozhi"})],
)
def test_listen_states_and_optional_mode(state: str, extra: dict[str, str]) -> None:
    message = {"type": "listen", "session_id": "s1", "state": state, **extra}
    assert parse_listen(message).state == state
    assert parse_listen({**message, "mode": "realtime"}).mode == "realtime"
    with pytest.raises(MalformedMessage):
        parse_listen({**message, "state": "invalid"})


def test_abort_and_server_models() -> None:
    assert parse_abort({"type": "abort", "session_id": "s1", "reason": "wake_word_detected"}).reason == "wake_word_detected"
    assert parse_stt({"type": "stt", "session_id": "s1", "text": "ciao"}).text == "ciao"
    assert parse_tts({"type": "tts", "session_id": "s1", "state": "start"}).state == "start"
    assert parse_llm({"type": "llm", "session_id": "s1", "emotion": "happy"}).emotion == "happy"
    assert parse_ping({"type": "ping"}).type == "ping"
    assert parse_pong({"type": "pong", "timestamp": 1788888000000}).timestamp == 1788888000000


def test_mcp_request_response_notification() -> None:
    request = {"type": "mcp", "session_id": "s1", "payload": {"jsonrpc": "2.0", "method": "tools/list", "id": 1}}
    response = {"type": "mcp", "session_id": "s1", "payload": {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}}
    notification = {"type": "mcp", "session_id": "s1", "payload": {"jsonrpc": "2.0", "method": "notifications/state_changed"}}
    assert parse_mcp(request)["method"] == "tools/list"
    assert parse_mcp(response)["result"] == {"tools": []}
    assert "id" not in parse_mcp(notification)
    with pytest.raises(MalformedMessage):
        parse_mcp({**request, "payload": {"jsonrpc": "2.0", "method": "tools/list"}})


def test_iot_preserves_conservative_raw_items() -> None:
    descriptors = [{"name": "speaker", "properties": {"volume": {"type": "integer"}}}]
    states = [{"name": "speaker", "state": {"volume": 50}}]
    parsed = parse_iot({"type": "iot", "session_id": "s1", "descriptors": descriptors, "states": states})
    assert parsed == (descriptors, states)
    with pytest.raises(MalformedMessage):
        parse_iot({"type": "iot", "session_id": "s1", "states": ["not-an-object"]})


def test_protocol_session_rules_and_events() -> None:
    session = ProtocolSession("s1", "d1")
    connected = session.receive(HELLO_DEVICE)
    assert connected.session_id == "s1"
    assert isinstance(session.receive({"type": "mcp", "session_id": "s1", "payload": {"jsonrpc": "2.0", "method": "notifications/state_changed"}}), MCPReceived)
    assert isinstance(session.receive({"type": "iot", "session_id": "s1", "descriptors": []}), IoTReceived)
    assert isinstance(session.receive({"type": "listen", "session_id": "s1", "state": "detect", "text": "xiaozhi"}), WakeWordDetected)
    with pytest.raises(SessionIdMismatch):
        session.receive({"type": "abort", "session_id": "other"})
    with pytest.raises(InvalidStateTransition):
        session.receive({"type": "hello", **HELLO_DEVICE})
    session.close()
    assert session.state is SessionState.CLOSED
    with pytest.raises(InvalidStateTransition):
        session.receive({"type": "ping"})


@pytest.mark.parametrize("version", list(BinaryFramingVersion))
def test_binary_framing_round_trip(version: BinaryFramingVersion) -> None:
    frame = encode_frame(b"opaque-opus", version, frame_type=0, timestamp=123)
    decoded = decode_frame(frame, version)
    assert decoded.payload == b"opaque-opus"
    assert decoded.version is version
    if version is BinaryFramingVersion.V2:
        assert decoded.timestamp == 123


def test_binary_framing_rejects_truncated_and_bad_sizes() -> None:
    with pytest.raises(MalformedFrame):
        decode_frame(b"\x00\x01", BinaryFramingVersion.V3)
    frame = encode_frame(b"payload", BinaryFramingVersion.V2)
    with pytest.raises(MalformedFrame):
        decode_frame(frame[:-1], BinaryFramingVersion.V2)


def test_malformed_json_and_unknown_type() -> None:
    from device.xiaozhi.errors import UnknownMessageType
    from device.xiaozhi.protocol import get_message_type, parse_message

    with pytest.raises(MalformedMessage):
        parse_message("{")
    with pytest.raises(UnknownMessageType):
        get_message_type(json.loads('{"type":"unknown"}'))


def test_import_boundary() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import device.xiaozhi; assert not any(name == 'voicemem' or name.startswith('voicemem.') for name in sys.modules)",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
