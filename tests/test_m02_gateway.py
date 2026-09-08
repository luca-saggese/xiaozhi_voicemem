"""Test per il package device/xiaozhi — Milestone 2.

Copre:
- Parser messaggi (hello, listen, abort, mcp, iot, ping)
- State machine (transizioni valide/invalide)
- Errori (malformed JSON, unknown type, header mancanti)
- WebSocket integration (con server di test)
- Boundary enforcement (device/xiaozhi non importa AI)
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from device.xiaozhi.errors import (
    MalformedMessage,
    UnknownMessageType,
)
from device.xiaozhi.messages import (
    AbortRequested,
    AudioFrameReceived,
    AudioParams,
    DeviceConnected,
    DeviceDisconnected,
    Features,
    IoTMessage,
    ListenStarted,
    ListenStopped,
    MCPMessage,
)
from device.xiaozhi.protocol import (
    get_message_type,
    parse_abort,
    parse_hello_device,
    parse_listen,
    parse_message,
    serialize_error,
    serialize_hello_server,
    serialize_mcp,
    serialize_pong,
    serialize_stt,
    serialize_tts_start,
    serialize_tts_stop,
)
from device.xiaozhi.state import SessionState, is_valid_transition

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════════════════════════════
# Parser — Hello
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseHello:
    """Parsing del messaggio hello dal device."""

    def test_hello_valid(self):
        """Hello valido con tutti i campi."""
        raw = json.dumps({
            "type": "hello",
            "version": 1,
            "transport": "websocket",
            "features": {"mcp": True, "aec": True},
            "audio_params": {
                "format": "opus",
                "sample_rate": 16000,
                "channels": 1,
                "frame_duration": 60,
            },
        })
        msg = parse_message(raw)
        assert get_message_type(msg) == "hello"
        hello = parse_hello_device(msg)
        assert hello.version == 1
        assert hello.transport == "websocket"
        assert hello.features.mcp is True
        assert hello.features.aec is True
        assert hello.audio_params.format == "opus"
        assert hello.audio_params.sample_rate == 16000

    def test_hello_minimal(self):
        """Hello con soli campi obbligatori."""
        raw = json.dumps({
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
        })
        msg = parse_message(raw)
        hello = parse_hello_device(msg)
        assert hello.features.mcp is True  # default
        assert hello.text_font is None

    def test_hello_missing_version(self):
        """Hello senza version produce errore."""
        raw = json.dumps({
            "type": "hello",
            "transport": "websocket",
            "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
        })
        msg = parse_message(raw)
        with pytest.raises(MalformedMessage):
            parse_hello_device(msg)

    def test_hello_invalid_transport(self):
        """Hello con transport non valido produce errore."""
        raw = json.dumps({
            "type": "hello",
            "version": 1,
            "transport": "mqtt",
            "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
        })
        msg = parse_message(raw)
        with pytest.raises(MalformedMessage):
            parse_hello_device(msg)

    def test_hello_missing_audio_params(self):
        """Hello senza audio_params produce errore."""
        raw = json.dumps({
            "type": "hello",
            "version": 1,
            "transport": "websocket",
        })
        msg = parse_message(raw)
        with pytest.raises(MalformedMessage):
            parse_hello_device(msg)

    def test_hello_with_text_font(self):
        """Hello con text_font opzionale."""
        raw = json.dumps({
            "type": "hello",
            "version": 1,
            "transport": "websocket",
            "features": {"mcp": True, "glyph_push": True},
            "text_font": {"bundle": "noto-v1", "charset": "common", "size": 20, "bpp": 4},
            "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
        })
        msg = parse_message(raw)
        hello = parse_hello_device(msg)
        assert hello.features.glyph_push is True
        assert hello.text_font is not None
        assert hello.text_font.bundle == "noto-v1"

    def test_hello_version_3_mqtt(self):
        """Hello con version 3 (MQTT)."""
        raw = json.dumps({
            "type": "hello",
            "version": 3,
            "transport": "udp",
            "features": {"mcp": True},
            "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
        })
        msg = parse_message(raw)
        hello = parse_hello_device(msg)
        assert hello.version == 3
        assert hello.transport == "udp"


# ═══════════════════════════════════════════════════════════════════════════════
# Parser — Listen
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseListen:
    """Parsing del messaggio listen dal device."""

    def test_listen_start_manual(self):
        """Listen start con mode manual."""
        raw = json.dumps({"session_id": "s1", "type": "listen", "state": "start", "mode": "manual"})
        msg = parse_message(raw)
        listen = parse_listen(msg)
        assert listen.state == "start"
        assert listen.mode == "manual"

    def test_listen_start_auto(self):
        """Listen start con mode auto."""
        raw = json.dumps({"session_id": "s1", "type": "listen", "state": "start", "mode": "auto"})
        msg = parse_message(raw)
        listen = parse_listen(msg)
        assert listen.mode == "auto"

    def test_listen_start_realtime(self):
        """Listen start con mode realtime."""
        raw = json.dumps({"session_id": "s1", "type": "listen", "state": "start", "mode": "realtime"})
        msg = parse_message(raw)
        listen = parse_listen(msg)
        assert listen.mode == "realtime"

    def test_listen_stop(self):
        """Listen stop."""
        raw = json.dumps({"session_id": "s1", "type": "listen", "state": "stop"})
        msg = parse_message(raw)
        listen = parse_listen(msg)
        assert listen.state == "stop"

    def test_listen_detect(self):
        """Listen detect (wake word)."""
        raw = json.dumps({"session_id": "s1", "type": "listen", "state": "detect", "text": "xiaozhi"})
        msg = parse_message(raw)
        listen = parse_listen(msg)
        assert listen.state == "detect"
        assert listen.text == "xiaozhi"

    def test_listen_invalid_state(self):
        """Listen con state non valido produce errore."""
        raw = json.dumps({"session_id": "s1", "type": "listen", "state": "invalid"})
        msg = parse_message(raw)
        with pytest.raises(MalformedMessage):
            parse_listen(msg)

    def test_listen_invalid_mode(self):
        """Listen con mode non valido produce errore."""
        raw = json.dumps({"session_id": "s1", "type": "listen", "state": "start", "mode": "invalid"})
        msg = parse_message(raw)
        with pytest.raises(MalformedMessage):
            parse_listen(msg)


# ═══════════════════════════════════════════════════════════════════════════════
# Parser — Abort
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseAbort:
    """Parsing del messaggio abort dal device."""

    def test_abort_simple(self):
        """Abort senza reason."""
        raw = json.dumps({"session_id": "s1", "type": "abort"})
        msg = parse_message(raw)
        abort = parse_abort(msg)
        assert abort.reason is None

    def test_abort_with_reason(self):
        """Abort con reason wake_word_detected."""
        raw = json.dumps({"session_id": "s1", "type": "abort", "reason": "wake_word_detected"})
        msg = parse_message(raw)
        abort = parse_abort(msg)
        assert abort.reason == "wake_word_detected"


# ═══════════════════════════════════════════════════════════════════════════════
# Parser — Generale
# ═══════════════════════════════════════════════════════════════════════════════


class TestParseGeneral:
    """Parsing generale dei messaggi."""

    def test_malformed_json(self):
        """JSON non valido produce MalformedMessage."""
        with pytest.raises(MalformedMessage):
            parse_message("{invalid json}")

    def test_empty_string(self):
        """Stringa vuota produce errore."""
        with pytest.raises(MalformedMessage):
            parse_message("")

    def test_not_an_object(self):
        """Array JSON non è un oggetto valido."""
        with pytest.raises(MalformedMessage):
            parse_message("[1, 2, 3]")

    def test_unknown_type(self):
        """Type sconosciuto produce UnknownMessageType."""
        raw = json.dumps({"type": "unknown_type"})
        msg = parse_message(raw)
        with pytest.raises(UnknownMessageType):
            get_message_type(msg)

    def test_missing_type(self):
        """Messaggio senza type produce errore."""
        raw = json.dumps({"foo": "bar"})
        msg = parse_message(raw)
        with pytest.raises(MalformedMessage):
            get_message_type(msg)

    def test_ping_message(self):
        """Messaggio ping è riconosciuto."""
        raw = json.dumps({"type": "ping"})
        msg = parse_message(raw)
        assert get_message_type(msg) == "ping"


# ═══════════════════════════════════════════════════════════════════════════════
# Serializzazione (server → device)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSerialize:
    """Serializzazione dei messaggi server → device."""

    def test_hello_server_includes_transport(self):
        """La risposta hello include transport (richiesto dal firmware)."""
        payload = serialize_hello_server("s1")
        data = json.loads(payload)
        assert data["type"] == "hello"
        assert data["transport"] == "websocket"
        assert data["session_id"] == "s1"
        assert data["audio_params"]["sample_rate"] == 24000

    def test_stt(self):
        """Messaggio STT."""
        payload = serialize_stt("s1", "testo")
        data = json.loads(payload)
        assert data["type"] == "stt"
        assert data["text"] == "testo"

    def test_tts_start(self):
        """Messaggio TTS start."""
        payload = serialize_tts_start("s1")
        data = json.loads(payload)
        assert data["type"] == "tts"
        assert data["state"] == "start"

    def test_tts_stop(self):
        """Messaggio TTS stop."""
        payload = serialize_tts_stop("s1")
        data = json.loads(payload)
        assert data["type"] == "tts"
        assert data["state"] == "stop"

    def test_pong(self):
        """Messaggio pong."""
        payload = serialize_pong("ts1")
        data = json.loads(payload)
        assert data["type"] == "pong"
        assert data["timestamp"] == "ts1"

    def test_error(self):
        """Messaggio di errore."""
        payload = serialize_error("s1", "ERR", "test error")
        data = json.loads(payload)
        assert data["type"] == "server"
        assert data["action"] == "error"

    def test_mcp(self):
        """Messaggio MCP."""
        payload = serialize_mcp("s1", {"jsonrpc": "2.0", "method": "tools/list", "id": 1})
        data = json.loads(payload)
        assert data["type"] == "mcp"
        assert data["payload"]["method"] == "tools/list"


# ═══════════════════════════════════════════════════════════════════════════════
# State machine
# ═══════════════════════════════════════════════════════════════════════════════


class TestStateMachine:
    """State machine del protocollo WebSocket."""

    def test_valid_transitions(self):
        """Transizioni valide."""
        assert is_valid_transition(SessionState.DISCONNECTED, SessionState.CONNECTING)
        assert is_valid_transition(SessionState.CONNECTING, SessionState.CONNECTED)
        assert is_valid_transition(SessionState.CONNECTED, SessionState.HELLO_DONE)
        assert is_valid_transition(SessionState.HELLO_DONE, SessionState.CLOSED)
        assert is_valid_transition(SessionState.CLOSED, SessionState.DISCONNECTED)

    def test_invalid_transitions(self):
        """Transizioni non valide."""
        assert not is_valid_transition(SessionState.DISCONNECTED, SessionState.HELLO_DONE)
        assert not is_valid_transition(SessionState.HELLO_DONE, SessionState.CONNECTED)
        assert not is_valid_transition(SessionState.CLOSED, SessionState.HELLO_DONE)
        assert not is_valid_transition(SessionState.CONNECTING, SessionState.HELLO_DONE)

    def test_self_transition(self):
        """Transizione allo stesso stato è valida (no-op)."""
        for state in SessionState:
            assert is_valid_transition(state, state)


# ═══════════════════════════════════════════════════════════════════════════════
# Eventi
# ═══════════════════════════════════════════════════════════════════════════════


class TestEvents:
    """Eventi astratti verso il runtime."""

    def test_device_connected(self):
        """Evento DeviceConnected."""
        evt = DeviceConnected(
            session_id="s1", device_id="d1", client_id="c1",
            protocol_version=1,
            audio_params=AudioParams(),
            features=Features(),
        )
        assert evt.session_id == "s1"
        assert evt.device_id == "d1"

    def test_device_disconnected(self):
        """Evento DeviceDisconnected."""
        evt = DeviceDisconnected(session_id="s1", device_id="d1", reason="test")
        assert evt.reason == "test"

    def test_listen_started(self):
        """Evento ListenStarted."""
        evt = ListenStarted(session_id="s1", device_id="d1", mode="manual")
        assert evt.mode == "manual"

    def test_listen_stopped(self):
        """Evento ListenStopped."""
        evt = ListenStopped(session_id="s1", device_id="d1")
        assert evt is not None

    def test_abort_requested(self):
        """Evento AbortRequested."""
        evt = AbortRequested(session_id="s1", device_id="d1", reason="wake_word_detected")
        assert evt.reason == "wake_word_detected"

    def test_mcp_message(self):
        """Evento MCPMessage."""
        evt = MCPMessage(session_id="s1", device_id="d1", payload={"method": "test"})
        assert evt.payload["method"] == "test"

    def test_iot_message(self):
        """Evento IoTMessage."""
        evt = IoTMessage(session_id="s1", device_id="d1", descriptors=[{"name": "speaker"}])
        assert evt.descriptors is not None

    def test_audio_frame_received(self):
        """Evento AudioFrameReceived."""
        evt = AudioFrameReceived(session_id="s1", device_id="d1", opus_data=b"test")
        assert evt.opus_data == b"test"


# ═══════════════════════════════════════════════════════════════════════════════
# WebSocket integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestWebSocketIntegration:
    """Test di integrazione con WebSocket reale."""

    @pytest.mark.asyncio
    async def test_connect_and_hello(self):
        """Connessione WebSocket + hello valido."""
        events: list[Any] = []

        def on_event(evt: Any) -> None:
            events.append(evt)

        from device.xiaozhi.server import XiaozhiWebSocketServer

        server = XiaozhiWebSocketServer(
            host="127.0.0.1",
            port=18765,
            event_callback=on_event,
        )

        # Avvia server in background
        server_task = asyncio.create_task(server.start())

        # Aspetta che il server sia pronto
        await asyncio.sleep(0.2)

        try:
            import websockets

            async with websockets.connect(
                "ws://127.0.0.1:18765/xiaozhi/v1/",
                extra_headers={
                    "Device-Id": "test-device-001",
                    "Client-Id": "test-client-001",
                    "Protocol-Version": "1",
                },
            ) as ws:
                # Invia hello
                await ws.send(json.dumps({
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
                }))

                # Ricevi risposta hello
                response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(response)
                assert data["type"] == "hello"
                assert data["transport"] == "websocket"
                assert "session_id" in data

                # Verifica evento DeviceConnected
                await asyncio.sleep(0.1)
                assert any(isinstance(e, DeviceConnected) for e in events)

        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_connect_missing_device_id(self):
        """Connessione senza Device-Id viene rifiutata."""
        from device.xiaozhi.server import XiaozhiWebSocketServer

        server = XiaozhiWebSocketServer(host="127.0.0.1", port=18766)
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.2)

        try:
            import websockets

            async with websockets.connect(
                "ws://127.0.0.1:18766/xiaozhi/v1/",
                extra_headers={
                    "Client-Id": "test-client-001",
                    "Protocol-Version": "1",
                },
            ) as ws:
                # Il server dovrebbe chiudere la connessione
                with pytest.raises(websockets.ConnectionClosed):
                    await asyncio.wait_for(ws.recv(), timeout=3.0)
        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_connect_wrong_path(self):
        """Connessione a path sbagliato viene rifiutata (404)."""
        from device.xiaozhi.server import XiaozhiWebSocketServer

        server = XiaozhiWebSocketServer(host="127.0.0.1", port=18767)
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.2)

        try:
            import websockets

            with pytest.raises(websockets.InvalidHandshake):
                async with websockets.connect(
                    "ws://127.0.0.1:18767/wrong-path",
                    extra_headers={
                        "Device-Id": "test-device-001",
                        "Client-Id": "test-client-001",
                        "Protocol-Version": "1",
                    },
                ):
                    pass
        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_hello_timeout(self):
        """Connessione senza hello viene chiusa dopo timeout."""
        events: list[Any] = []

        def on_event(evt: Any) -> None:
            events.append(evt)

        from device.xiaozhi.server import XiaozhiWebSocketServer

        server = XiaozhiWebSocketServer(
            host="127.0.0.1", port=18768,
            event_callback=on_event,
            hello_timeout_s=0.3,
        )
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.2)

        try:
            import websockets

            async with websockets.connect(
                "ws://127.0.0.1:18768/xiaozhi/v1/",
                extra_headers={
                    "Device-Id": "test-device-002",
                    "Client-Id": "test-client-002",
                    "Protocol-Version": "1",
                },
                close_timeout=5,
            ) as ws:
                # Non inviamo hello: aspettiamo che il server chiuda
                with pytest.raises(websockets.ConnectionClosed):
                    await ws.recv()

                await asyncio.sleep(0.1)
                assert any(isinstance(e, DeviceDisconnected) for e in events)

        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_listen_and_abort(self):
        """Sequenza listen + abort via WebSocket."""
        events: list[Any] = []

        def on_event(evt: Any) -> None:
            events.append(evt)

        from device.xiaozhi.server import XiaozhiWebSocketServer

        server = XiaozhiWebSocketServer(
            host="127.0.0.1", port=18769,
            event_callback=on_event,
        )
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.2)

        try:
            import websockets

            async with websockets.connect(
                "ws://127.0.0.1:18769/xiaozhi/v1/",
                extra_headers={
                    "Device-Id": "test-device-003",
                    "Client-Id": "test-client-003",
                    "Protocol-Version": "1",
                },
            ) as ws:
                # Hello
                await ws.send(json.dumps({
                    "type": "hello",
                    "version": 1,
                    "transport": "websocket",
                    "features": {"mcp": True},
                    "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
                }))
                welcome = json.loads(await asyncio.wait_for(ws.recv(), timeout=3.0))
                session_id = welcome["session_id"]

                # Listen start
                await ws.send(json.dumps({
                    "session_id": session_id, "type": "listen", "state": "start", "mode": "manual",
                }))
                await asyncio.sleep(0.1)

                # Abort
                await ws.send(json.dumps({
                    "session_id": session_id, "type": "abort", "reason": "wake_word_detected",
                }))
                await asyncio.sleep(0.1)

                assert any(isinstance(e, ListenStarted) for e in events)
                assert any(isinstance(e, AbortRequested) for e in events)

        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_unknown_message(self):
        """Messaggio con type sconosciuto non causa crash."""
        from device.xiaozhi.server import XiaozhiWebSocketServer

        server = XiaozhiWebSocketServer(host="127.0.0.1", port=18770)
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.2)

        try:
            import websockets

            async with websockets.connect(
                "ws://127.0.0.1:18770/xiaozhi/v1/",
                extra_headers={
                    "Device-Id": "test-device-004",
                    "Client-Id": "test-client-004",
                    "Protocol-Version": "1",
                },
            ) as ws:
                # Hello
                await ws.send(json.dumps({
                    "type": "hello",
                    "version": 1,
                    "transport": "websocket",
                    "features": {"mcp": True},
                    "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
                }))
                await asyncio.wait_for(ws.recv(), timeout=3.0)

                # Unknown type — non deve crashare
                await ws.send(json.dumps({"type": "unknown_type"}))
                await asyncio.sleep(0.1)

                # La connessione deve essere ancora attiva
                await ws.send(json.dumps({"type": "ping"}))
                response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(response)
                assert data["type"] == "pong"

        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_malformed_json_no_crash(self):
        """JSON malformato non causa crash."""
        from device.xiaozhi.server import XiaozhiWebSocketServer

        server = XiaozhiWebSocketServer(host="127.0.0.1", port=18771)
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.2)

        try:
            import websockets

            async with websockets.connect(
                "ws://127.0.0.1:18771/xiaozhi/v1/",
                extra_headers={
                    "Device-Id": "test-device-005",
                    "Client-Id": "test-client-005",
                    "Protocol-Version": "1",
                },
            ) as ws:
                # Hello
                await ws.send(json.dumps({
                    "type": "hello",
                    "version": 1,
                    "transport": "websocket",
                    "features": {"mcp": True},
                    "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
                }))
                await asyncio.wait_for(ws.recv(), timeout=3.0)

                # JSON malformato — non deve crashare
                await ws.send("{invalid json}")
                await asyncio.sleep(0.1)

                # La connessione deve essere ancora attiva
                await ws.send(json.dumps({"type": "ping"}))
                response = await asyncio.wait_for(ws.recv(), timeout=3.0)
                assert response is not None

        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_ota_bootstrap_endpoint(self):
        """Endpoint HTTP /xiaozhi/ota/ restituisce configurazione valida."""
        from device.xiaozhi.server import XiaozhiWebSocketServer

        server = XiaozhiWebSocketServer(host="127.0.0.1", port=18772)
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.2)

        try:
            import urllib.request

            def fetch():
                req = urllib.request.Request("http://127.0.0.1:18772/xiaozhi/ota/")
                with urllib.request.urlopen(req) as resp:
                    return resp.status, resp.read().decode()

            status, body = await asyncio.to_thread(fetch)
            assert status == 200
            data = json.loads(body)
            assert "websocket" in data
            assert data["websocket"]["url"] == "ws://127.0.0.1:18772/xiaozhi/v1/"
            assert "server_time" in data

            def post_firmware():
                req = urllib.request.Request(
                    f"http://127.0.0.1:{server.ota_port}/xiaozhi/ota/",
                    data=b"firmware-metadata",
                    method="POST",
                )
                with urllib.request.urlopen(req) as resp:
                    return resp.status, json.loads(resp.read().decode())

            post_status, post_data = await asyncio.to_thread(post_firmware)
            assert post_status == 200
            assert post_data["websocket"]["url"] == "ws://127.0.0.1:18772/xiaozhi/v1/"
            assert post_data["server_time"]["timestamp"] > 1_000_000_000_000
        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_reconnect_duplicate_device(self):
        """Riconnessione con stesso Device-Id chiude la sessione precedente."""
        from device.xiaozhi.server import XiaozhiWebSocketServer

        server = XiaozhiWebSocketServer(host="127.0.0.1", port=18773)
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.2)

        try:
            import websockets

            headers = {
                "Device-Id": "dup-device",
                "Client-Id": "client-1",
                "Protocol-Version": "1",
            }

            ws1 = await websockets.connect("ws://127.0.0.1:18773/xiaozhi/v1/", extra_headers=headers)
            await ws1.send(json.dumps({
                "type": "hello", "version": 1, "transport": "websocket",
                "features": {"mcp": True},
                "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
            }))
            await ws1.recv()

            ws2 = await websockets.connect("ws://127.0.0.1:18773/xiaozhi/v1/", extra_headers=headers)
            await ws2.send(json.dumps({
                "type": "hello", "version": 1, "transport": "websocket",
                "features": {"mcp": True},
                "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
            }))
            await ws2.recv()

            with pytest.raises(websockets.ConnectionClosed):
                await ws1.recv()

            await ws2.close()
        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_disconnect_during_active_listen(self):
        """Disconnect durante listen attivo emette DeviceDisconnected e pulisce."""
        events: list[Any] = []

        def on_event(evt: Any) -> None:
            events.append(evt)

        from device.xiaozhi.server import XiaozhiWebSocketServer

        server = XiaozhiWebSocketServer(host="127.0.0.1", port=18774, event_callback=on_event)
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.2)

        try:
            import websockets

            async with websockets.connect(
                "ws://127.0.0.1:18774/xiaozhi/v1/",
                extra_headers={"Device-Id": "dev-listen-dc", "Client-Id": "c1", "Protocol-Version": "1"},
            ) as ws:
                await ws.send(json.dumps({
                    "type": "hello", "version": 1, "transport": "websocket",
                    "features": {"mcp": True},
                    "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
                }))
                welcome = json.loads(await ws.recv())
                session_id = welcome["session_id"]

                await ws.send(json.dumps({"session_id": session_id, "type": "listen", "state": "start"}))
                await asyncio.sleep(0.1)

            await asyncio.sleep(0.2)
            assert any(isinstance(e, DeviceDisconnected) for e in events)
        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_protocol_version_unsupported(self):
        """Versione protocollo non supportata viene rifiutata."""
        from device.xiaozhi.server import XiaozhiWebSocketServer

        server = XiaozhiWebSocketServer(host="127.0.0.1", port=18775)
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.2)

        try:
            import websockets

            async with websockets.connect(
                "ws://127.0.0.1:18775/xiaozhi/v1/",
                extra_headers={"Device-Id": "dev-ver", "Client-Id": "c1", "Protocol-Version": "99"},
            ) as ws:
                with pytest.raises(websockets.ConnectionClosed):
                    await ws.recv()
        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_auth_token_required(self):
        """Server con auth_token configurato verifica il Bearer token."""
        from device.xiaozhi.server import XiaozhiWebSocketServer

        server = XiaozhiWebSocketServer(host="127.0.0.1", port=18776, auth_token="secret123")
        server_task = asyncio.create_task(server.start())
        await asyncio.sleep(0.2)

        try:
            import websockets

            # Connessione senza token -> rifiutata
            async with websockets.connect(
                "ws://127.0.0.1:18776/xiaozhi/v1/",
                extra_headers={"Device-Id": "dev-auth", "Client-Id": "c1", "Protocol-Version": "1"},
            ) as ws:
                with pytest.raises(websockets.ConnectionClosed):
                    await ws.recv()

            # Connessione con token errato -> rifiutata
            async with websockets.connect(
                "ws://127.0.0.1:18776/xiaozhi/v1/",
                extra_headers={
                    "Device-Id": "dev-auth", "Client-Id": "c1", "Protocol-Version": "1",
                    "Authorization": "Bearer wrong-token",
                },
            ) as ws:
                with pytest.raises(websockets.ConnectionClosed):
                    await ws.recv()

            # Connessione con token corretto -> accettata
            async with websockets.connect(
                "ws://127.0.0.1:18776/xiaozhi/v1/",
                extra_headers={
                    "Device-Id": "dev-auth", "Client-Id": "c1", "Protocol-Version": "1",
                    "Authorization": "Bearer secret123",
                },
            ) as ws:
                await ws.send(json.dumps({
                    "type": "hello", "version": 1, "transport": "websocket",
                    "features": {"mcp": True},
                    "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60},
                }))
                resp = await asyncio.wait_for(ws.recv(), timeout=3.0)
                data = json.loads(resp)
                assert data["type"] == "hello"
        finally:
            server_task.cancel()
            try:
                await server_task
            except (asyncio.CancelledError, Exception):
                pass


# ═══════════════════════════════════════════════════════════════════════════════
# Validazione Fixture da disco
# ═══════════════════════════════════════════════════════════════════════════════


class TestFixturesValidation:
    """Valida che tutti i file fixture in tests/fixtures/xiaozhi_protocol/ siano parsabili."""

    FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "xiaozhi_protocol"

    def test_fixture_hello_device(self):
        content = (self.FIXTURES_DIR / "hello_device_v1.json").read_text()
        msg = parse_message(content)
        assert get_message_type(msg) == "hello"
        hello = parse_hello_device(msg)
        assert hello.version == 1
        assert hello.transport == "websocket"

    def test_fixture_hello_server(self):
        content = (self.FIXTURES_DIR / "hello_server_v1.json").read_text()
        msg = parse_message(content)
        assert get_message_type(msg) == "hello"
        assert msg["transport"] == "websocket"

    def test_fixture_listen_manual(self):
        content = (self.FIXTURES_DIR / "listen_start_manual.json").read_text()
        msg = parse_message(content)
        listen = parse_listen(msg)
        assert listen.state == "start"
        assert listen.mode == "manual"

    def test_fixture_listen_auto(self):
        content = (self.FIXTURES_DIR / "listen_start_auto.json").read_text()
        msg = parse_message(content)
        listen = parse_listen(msg)
        assert listen.state == "start"
        assert listen.mode == "auto"

    def test_fixture_listen_stop(self):
        content = (self.FIXTURES_DIR / "listen_stop.json").read_text()
        msg = parse_message(content)
        listen = parse_listen(msg)
        assert listen.state == "stop"

    def test_fixture_listen_detect(self):
        content = (self.FIXTURES_DIR / "listen_detect.json").read_text()
        msg = parse_message(content)
        listen = parse_listen(msg)
        assert listen.state == "detect"
        assert listen.text == "xiaozhi"

    def test_fixture_abort_simple(self):
        content = (self.FIXTURES_DIR / "abort_simple.json").read_text()
        msg = parse_message(content)
        abort = parse_abort(msg)
        assert abort.reason is None

    def test_fixture_abort_wake_word(self):
        content = (self.FIXTURES_DIR / "abort_wake_word.json").read_text()
        msg = parse_message(content)
        abort = parse_abort(msg)
        assert abort.reason == "wake_word_detected"

    def test_fixture_mcp_initialize(self):
        content = (self.FIXTURES_DIR / "mcp_initialize.json").read_text()
        msg = parse_message(content)
        assert get_message_type(msg) == "mcp"
        payload = msg["payload"]
        assert payload["method"] == "initialize"

    def test_fixture_ota_response(self):
        content = (self.FIXTURES_DIR / "ota_response.json").read_text()
        data = json.loads(content)
        assert "websocket" in data
        assert "server_time" in data


# ═══════════════════════════════════════════════════════════════════════════════
# Boundary enforcement
# ═══════════════════════════════════════════════════════════════════════════════


class TestBoundaryEnforcement:
    """device/xiaozhi non deve importare moduli AI."""

    def test_device_xiaozhi_does_not_import_voicemem(self):
        """Importare device.xiaozhi non tira su voicemem."""
        code = """
import sys
import device.xiaozhi
assert "voicemem" not in sys.modules, "voicemem è stato importato!"
assert "torch" not in sys.modules, "torch è stato importato!"
assert "funasr" not in sys.modules, "funasr è stato importato!"
assert "transformers" not in sys.modules, "transformers è stato importato!"
assert "sentence_transformers" not in sys.modules, "sentence_transformers è stato importato!"
print("OK")
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"Fallito: {result.stderr}"

    def test_device_xiaozhi_does_not_import_ai_submodules(self):
        """device.xiaozhi non importa ASR, VAD, LLM, Memory, TTS."""
        code = """
import sys
import device.xiaozhi
ai_modules = {"voicemem", "voicemem.core", "voicemem.stream", "voicemem.reply", "voicemem.tts"}
for mod in ai_modules:
    assert mod not in sys.modules, f"{mod} non dovrebbe essere importato"
print("OK")
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"Fallito: {result.stderr}"

    def test_static_ast_no_ai_imports(self):
        """Analisi statica AST: nessun file in device/xiaozhi importa moduli AI."""
        import ast

        forbidden = (
            "voicemem", "torch", "funasr", "transformers", "sentence_transformers",
            "openai", "mem0", "sherpa_onnx", "onnxruntime",
        )
        device_dir = PROJECT_ROOT / "device" / "xiaozhi"

        for py_file in device_dir.rglob("*.py"):
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for fb in forbidden:
                            assert not alias.name.startswith(fb), (
                                f"{py_file.relative_to(PROJECT_ROOT)} importa {alias.name} (VIETATO)"
                            )
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for fb in forbidden:
                            assert not node.module.startswith(fb), (
                                f"{py_file.relative_to(PROJECT_ROOT)} importa da {node.module} (VIETATO)"
                            )
