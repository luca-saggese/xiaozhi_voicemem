"""Gate finali M02: bootstrap stock, failure modes e isolamento multi-device."""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest
import websockets

from device.xiaozhi.codec import encode_frame
from device.xiaozhi.commands import SendTranscript
from device.xiaozhi.errors import InvalidStateTransition
from device.xiaozhi.events import AudioFrameReceived, DeviceConnected
from device.xiaozhi.messages import ListenStarted
from device.xiaozhi.server import XiaozhiWebSocketServer

ROOT = Path(__file__).resolve().parent
FIXTURES = ROOT / "fixtures" / "xiaozhi_protocol"

HELLO = {
    "type": "hello",
    "version": 1,
    "transport": "websocket",
    "features": {"mcp": True},
    "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
}


def ws_headers(device_id: str, client_id: str, protocol_version: int = 1) -> dict[str, str]:
    return {
        "Authorization": "Bearer token",
        "Protocol-Version": str(protocol_version),
        "Device-Id": device_id,
        "Client-Id": client_id,
    }


async def hello(
    server: XiaozhiWebSocketServer,
    device_id: str,
    client_id: str,
    protocol_version: int = 1,
):
    websocket = await websockets.connect(
        f"ws://127.0.0.1:{server.port}/xiaozhi/v1/",
        extra_headers=ws_headers(device_id, client_id, protocol_version),
    )
    hello_message = {**HELLO, "version": protocol_version}
    await websocket.send(json.dumps(hello_message))
    welcome = json.loads(await asyncio.wait_for(websocket.recv(), timeout=2))
    return websocket, welcome


def post_bootstrap(port: int, request_headers: dict[str, str], body: bytes = b"{}") -> tuple[int, dict]:
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/xiaozhi/ota/",
        data=body,
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode())


@pytest.mark.asyncio
async def test_stock_bootstrap_post_fixture_is_parser_compatible() -> None:
    request_headers = json.loads((FIXTURES / "ota_request_headers.json").read_text())
    server = XiaozhiWebSocketServer(host="127.0.0.1", port=0, ota_port=0, auth_token="token")
    await server.start()
    try:
        status, response = await asyncio.to_thread(post_bootstrap, server.ota_port, request_headers)
        assert status == 200
        assert response["websocket"]["url"] == f"ws://127.0.0.1:{server.port}/xiaozhi/v1/"
        assert response["websocket"] == {
            "url": f"ws://127.0.0.1:{server.port}/xiaozhi/v1/",
            "token": "token",
            "version": 1,
        }
        assert response["firmware"] == {"version": "0.0.0", "url": ""}
        assert isinstance(response["server_time"]["timestamp"], int)
        assert response["server_time"]["timezone_offset"] == 0

        missing_status, missing_body = await asyncio.to_thread(
            post_bootstrap,
            server.ota_port,
            {"Activation-Version": "1", "Content-Type": "application/json"},
        )
        assert missing_status == 400
        assert "Device-Id" in missing_body["error"]

        bad_auth_headers = {**request_headers, "Authorization": "Bearer wrong"}
        auth_status, auth_body = await asyncio.to_thread(post_bootstrap, server.ota_port, bad_auth_headers)
        assert auth_status == 401
        assert auth_body["error"] == "Invalid authorization token"
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_invalid_binary_duplicate_hello_and_close_during_send() -> None:
    events: list[object] = []
    server = XiaozhiWebSocketServer(host="127.0.0.1", port=0, event_callback=events.append)
    await server.start()
    try:
        websocket, welcome = await hello(server, "failure-device", "failure-client", protocol_version=2)
        connection = server._connections["failure-device"]
        session_id = welcome["session_id"]
        try:
            await websocket.send(json.dumps(HELLO))
            duplicate = json.loads(await websocket.recv())
            assert "INVALID_STATE_TRANSITION" in duplicate["message"]

            await websocket.send(b"\x00")
            malformed = json.loads(await websocket.recv())
            assert "MALFORMED_BINARY" in malformed["message"]

            await websocket.send(encode_frame(b"not-audio", 2, frame_type=1))
            wrong_type = json.loads(await websocket.recv())
            assert "MALFORMED_BINARY" in wrong_type["message"]

            await websocket.send(json.dumps({"type": "listen", "session_id": session_id, "state": "start"}))
            await asyncio.sleep(0.02)
            assert any(isinstance(event, ListenStarted) for event in events)
        finally:
            await websocket.close()
        await asyncio.wait_for(connection._cleanup_done.wait(), timeout=2)
        with pytest.raises(InvalidStateTransition):
            await connection.send(SendTranscript(session_id, "failure-device", "late"))
    finally:
        await server.stop()


@pytest.mark.asyncio
async def test_concurrent_devices_keep_sessions_and_events_isolated() -> None:
    events: list[object] = []
    server = XiaozhiWebSocketServer(host="127.0.0.1", port=0, event_callback=events.append)
    await server.start()
    try:
        first, second = await asyncio.gather(
            hello(server, "device-a", "client-a"),
            hello(server, "device-b", "client-b"),
        )
        websocket_a, welcome_a = first
        websocket_b, welcome_b = second
        try:
            assert welcome_a["session_id"] != welcome_b["session_id"]
            assert server._connections["device-a"].client_id == "client-a"
            assert server._connections["device-b"].client_id == "client-b"
            await asyncio.gather(
                websocket_a.send(json.dumps({
                    "type": "listen", "session_id": welcome_a["session_id"], "state": "start",
                })),
                websocket_b.send(encode_frame(b"device-b-opus", 1)),
            )
            await asyncio.sleep(0.05)
            assert any(isinstance(event, DeviceConnected) and event.device_id == "device-a" for event in events)
            assert any(isinstance(event, DeviceConnected) and event.device_id == "device-b" for event in events)
            assert any(isinstance(event, ListenStarted) and event.device_id == "device-a" for event in events)
            assert any(isinstance(event, AudioFrameReceived) and event.device_id == "device-b" and event.opus_data == b"device-b-opus" for event in events)
        finally:
            await asyncio.gather(websocket_a.close(), websocket_b.close())
    finally:
        await server.stop()


def test_xiaozhi_import_boundary_excludes_ai_dependencies() -> None:
    result = __import__("subprocess").run(
        [
            sys.executable,
            "-c",
            "import sys; import device.xiaozhi; forbidden=('voicemem','torch','funasr'); assert not any(name == root or name.startswith(root + '.') for name in sys.modules for root in forbidden)",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
