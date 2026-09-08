"""Test end-to-end del gateway WebSocket M02 senza VoiceMem o Opus."""

from __future__ import annotations

import asyncio
import json
import sys

import pytest
import websockets

from device.xiaozhi.codec import encode_frame
from device.xiaozhi.commands import (
    SendIoT,
    SendLLMState,
    SendMCP,
    SendPong,
    SendTranscript,
    SendTTSSentence,
    SendTTSStart,
    SendTTSStop,
)
from device.xiaozhi.events import AudioFrameReceived, DeviceConnected, DeviceDisconnected
from device.xiaozhi.messages import AbortRequested, ListenStarted, MCPMessage
from device.xiaozhi.server import XiaozhiWebSocketServer

HELLO = {
    "type": "hello",
    "version": 1,
    "transport": "websocket",
    "features": {"mcp": True},
    "audio_params": {
        "format": "opus",
        "sample_rate": 16000,
        "channels": 1,
        "frame_duration": 60,
    },
}


def headers(device_id: str = "device-1", client_id: str = "client-1") -> dict[str, str]:
    return {
        "Authorization": "Bearer test-token",
        "Protocol-Version": "1",
        "Device-Id": device_id,
        "Client-Id": client_id,
    }


async def connect_and_hello(server: XiaozhiWebSocketServer, **kwargs):
    websocket = await websockets.connect(
        f"ws://127.0.0.1:{server.port}/xiaozhi/v1/",
        extra_headers=headers(**kwargs),
    )
    await websocket.send(json.dumps(HELLO))
    welcome = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))
    return websocket, welcome


@pytest.mark.asyncio
async def test_gateway_dispatch_audio_events_and_server_commands() -> None:
    events: list[object] = []
    server = XiaozhiWebSocketServer(
        host="127.0.0.1",
        port=0,
        auth_token="test-token",
        event_callback=events.append,
    )
    await server.start()
    try:
        websocket, welcome = await connect_and_hello(server)
        try:
            session_id = welcome["session_id"]
            assert welcome == {
                "type": "hello",
                "transport": "websocket",
                "session_id": session_id,
                "audio_params": {
                    "format": "opus",
                    "sample_rate": 24000,
                    "channels": 1,
                    "frame_duration": 60,
                },
            }
            connection = server._connections["device-1"]
            assert connection.headers.authorization == "Bearer test-token"
            assert connection.headers.protocol_version == "1"
            assert connection.device_id == "device-1"
            assert connection.client_id == "client-1"
            assert isinstance(events[0], DeviceConnected)

            await websocket.send(json.dumps({
                "type": "listen", "session_id": session_id, "state": "start", "mode": "manual",
            }))
            await websocket.send(encode_frame(b"opaque-opus", 1))
            await websocket.send(json.dumps({
                "type": "abort", "session_id": session_id, "reason": "wake_word_detected",
            }))
            await websocket.send(json.dumps({
                "type": "mcp", "session_id": session_id,
                "payload": {"jsonrpc": "2.0", "method": "notifications/state_changed"},
            }))
            await websocket.send(json.dumps({
                "type": "iot", "session_id": session_id, "descriptors": [], "states": [],
            }))
            await websocket.send(json.dumps({"type": "ping"}))
            assert json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))["type"] == "pong"

            await asyncio.sleep(0.05)
            assert any(isinstance(event, ListenStarted) for event in events)
            assert any(isinstance(event, AudioFrameReceived) and event.opus_data == b"opaque-opus" for event in events)
            assert any(isinstance(event, AbortRequested) for event in events)
            assert any(isinstance(event, MCPMessage) for event in events)

            commands = [
                SendTranscript(session_id, "device-1", "ciao"),
                SendTTSStart(session_id, "device-1"),
                SendTTSSentence(session_id, "device-1", "come stai"),
                SendTTSStop(session_id, "device-1"),
                SendLLMState(session_id, "device-1", emotion="happy", text="bene"),
                SendMCP(session_id, "device-1", {"jsonrpc": "2.0", "method": "tools/list"}),
                SendIoT(session_id, "device-1", {"states": []}),
                SendPong(session_id, "device-1", 123),
            ]
            for command in commands:
                await connection.send(command)
            sent_types = [json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))["type"] for _ in commands]
            assert sent_types == ["stt", "tts", "tts", "tts", "llm", "mcp", "iot", "pong"]
        finally:
            await websocket.close()
        await asyncio.sleep(0.05)
        assert any(isinstance(event, DeviceDisconnected) for event in events)
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_gateway_rejects_protocol_errors_without_dropping_connection() -> None:
    server = XiaozhiWebSocketServer(host="127.0.0.1", port=0, auth_token="test-token")
    await server.start()
    try:
        websocket = await websockets.connect(
            f"ws://127.0.0.1:{server.port}/xiaozhi/v1/",
            extra_headers=headers(),
        )
        try:
            await websocket.send(json.dumps({"type": "ping"}))
            before_hello = json.loads(await websocket.recv())
            assert before_hello["type"] == "server"
            assert "INVALID_STATE_TRANSITION" in before_hello["message"]

            await websocket.send("{")
            malformed = json.loads(await websocket.recv())
            assert "[MALFORMED]" in malformed["message"]

            await websocket.send(json.dumps(HELLO))
            await websocket.recv()
            await websocket.send(json.dumps({"type": "listen", "session_id": "wrong", "state": "start"}))
            mismatch = json.loads(await websocket.recv())
            assert "SESSION_ID_MISMATCH" in mismatch["message"]

            await websocket.send(json.dumps({"type": "ping"}))
            assert json.loads(await websocket.recv())["type"] == "pong"
        finally:
            await websocket.close()
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_gateway_hello_timeout_and_exact_path() -> None:
    server = XiaozhiWebSocketServer(host="127.0.0.1", port=0, auth_token="test-token", hello_timeout_s=0.05)
    await server.start()
    try:
        websocket = await websockets.connect(
            f"ws://127.0.0.1:{server.port}/xiaozhi/v1/",
            extra_headers=headers(),
        )
        try:
            with pytest.raises(websockets.ConnectionClosed):
                await asyncio.wait_for(websocket.recv(), timeout=1)
        finally:
            await websocket.close()

        with pytest.raises(websockets.InvalidHandshake):
            await websockets.connect(
                f"ws://127.0.0.1:{server.port}/xiaozhi/v1/extra",
                extra_headers=headers(),
            )
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_gateway_reconnect_creates_new_session_ids() -> None:
    server = XiaozhiWebSocketServer(host="127.0.0.1", port=0, auth_token="test-token")
    await server.start()
    session_ids: set[str] = set()
    try:
        for index in range(100):
            websocket, welcome = await connect_and_hello(
                server,
                device_id="stress-device",
                client_id=f"stress-client-{index}",
            )
            session_ids.add(welcome["session_id"])
            await websocket.close()
        assert len(session_ids) == 100
    finally:
        await server.stop()


def test_xiaozhi_boundary_in_clean_process() -> None:
    result = __import__("subprocess").run(
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
