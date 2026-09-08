"""WebSocket server per il gateway Xiaozhi (M02).

Endpoint: ws://{host}:{port}/xiaozhi/v1/
Headers richiesti: Authorization, Protocol-Version, Device-Id, Client-Id

Derivato dall'audit in XIAOZHI_PROTOCOL_AUDIT.md.
"""

from __future__ import annotations

import asyncio
import http
import json
import logging
import time
from collections.abc import Callable
from typing import Any
from urllib.parse import parse_qs, urlparse

from aiohttp import web
from websockets.datastructures import Headers
from websockets.legacy.server import WebSocketServer, WebSocketServerProtocol, serve

from device.xiaozhi.connection import DeviceConnection

logger = logging.getLogger("xiaozhi_voicemem.device.xiaozhi.server")

#: Path dell'endpoint WebSocket (atteso dal firmware).
WEBSOCKET_PATH = "/xiaozhi/v1/"
#: Path dell'endpoint bootstrap/OTA (atteso dal firmware).
OTA_PATH = "/xiaozhi/ota/"
#: Versioni del protocollo supportate.
SUPPORTED_VERSIONS = [1, 2, 3]


class XiaozhiWebSocketServer:
    """Server WebSocket per device Xiaozhi ESP32 stock.

    Non contiene logica AI. Produce solo eventi verso il runtime.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8765,
        *,
        ota_port: int | None = None,
        event_callback: Callable[[Any], None] | None = None,
        auth_token: str | None = None,
        hello_timeout_s: float | None = None,
        idle_timeout_s: float | None = None,
    ):
        self.host = host
        self.port = port
        self.ota_port = ota_port if ota_port is not None else 0
        self._event_callback = event_callback
        self._auth_token = auth_token
        self._hello_timeout_s = hello_timeout_s
        self._idle_timeout_s = idle_timeout_s
        self._server: WebSocketServer | None = None
        self._http_runner: web.AppRunner | None = None
        self._http_site: web.TCPSite | None = None
        self._connections: dict[str, DeviceConnection] = {}

    async def start(self) -> None:
        """Avvia il server WebSocket (non bloccante)."""
        self._server = await serve(
            self._handle_connection,
            self.host,
            self.port,
            process_request=self._http_response,
            ping_interval=None,  # Il firmware gestisce il ping a livello protocollo
        )
        app = web.Application()
        app.router.add_route("*", OTA_PATH, self._ota_http_handler)
        self._http_runner = web.AppRunner(app)
        await self._http_runner.setup()
        self._http_site = web.TCPSite(self._http_runner, self.host, self.ota_port)
        await self._http_site.start()
        if self.ota_port == 0 and self._http_site._server is not None:
            socket = self._http_site._server.sockets[0]
            self.ota_port = int(socket.getsockname()[1])
        logger.info(
            "Xiaozhi WebSocket server started on %s:%s (path=%s)",
            self.host, self.port, WEBSOCKET_PATH,
        )
        logger.info("Xiaozhi OTA HTTP server started on %s:%s", self.host, self.ota_port)

    async def serve_forever(self) -> None:
        """Mantiene il server in esecuzione fino a stop()."""
        if self._server is None:
            await self.start()
        await asyncio.Future()  # Run forever

    async def stop(self) -> None:
        """Ferma il server e chiude tutte le connessioni."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if self._http_runner:
            await self._http_runner.cleanup()
            self._http_runner = None
            self._http_site = None

        # Chiudi tutte le connessioni attive
        for conn in list(self._connections.values()):
            await conn.close("server_shutdown")
        self._connections.clear()
        logger.info("Xiaozhi WebSocket server stopped")

    async def _http_response(self, path: str, request_headers: Headers) -> tuple[http.HTTPStatus, Headers, bytes] | None:
        """Intercetta le richieste HTTP per validare il path o servire OTA bootstrap.

        Se il path è /xiaozhi/ota/, restituisce la configurazione per il device stock.
        Se il path non è /xiaozhi/v1/, rifiuta la connessione con 404.
        """
        clean_path = path.split("?")[0].rstrip("/")
        if clean_path == "/xiaozhi/ota":
            host_header = request_headers.get("host")
            host_part = host_header if host_header else f"{self.host}:{self.port}"
            ws_url = f"ws://{host_part}{WEBSOCKET_PATH}"
            response_data = {
                "websocket": {
                    "url": ws_url,
                    "token": self._auth_token or "",
                    "version": 1,
                },
                "server_time": {
                    "timestamp": int(time.time() * 1000),
                    "timezone_offset": 0,
                },
            }
            body = json.dumps(response_data, separators=(",", ":")).encode("utf-8")
            return (
                http.HTTPStatus.OK,
                Headers([
                    ("Content-Type", "application/json"),
                    ("Content-Length", str(len(body))),
                ]),
                body,
            )

        if path != WEBSOCKET_PATH and not path.startswith(WEBSOCKET_PATH):
            return (http.HTTPStatus.NOT_FOUND, Headers([("Content-Type", "text/plain")]), b"Not Found")
        return None  # Prosegui con l'upgrade WebSocket

    async def _ota_http_handler(self, request: web.Request) -> web.Response:
        host_header = request.headers.get("host", self.host)
        host_name = host_header.rsplit(":", 1)[0] if ":" in host_header else host_header
        response_data = {
            "websocket": {
                "url": f"ws://{host_name}:{self.port}{WEBSOCKET_PATH}",
                "token": self._auth_token or "",
                "version": 1,
            },
            "server_time": {
                "timestamp": int(time.time() * 1000),
                "timezone_offset": 0,
            },
        }
        return web.json_response(response_data)

    async def _handle_connection(self, websocket: WebSocketServerProtocol) -> None:
        """Gestisce una nuova connessione WebSocket."""
        # Leggi headers (websockets 11 li imposta su self.request_headers dopo handshake)
        device_id = websocket.request_headers.get("device-id", "")
        client_id = websocket.request_headers.get("client-id", "")
        auth_header = websocket.request_headers.get("authorization", "")
        version_str = websocket.request_headers.get("protocol-version", "")

        # Fallback: query params (solo se device_id non presente negli headers)
        if not device_id:
            query = parse_qs(urlparse(websocket.path).query)
            device_id = query.get("device-id", [""])[0]
            client_id = client_id or query.get("client-id", [""])[0]
            auth_header = auth_header or query.get("authorization", [""])[0]

        # Validazione headers
        if not device_id:
            await websocket.close(4001, "Missing device-id")
            return

        if not client_id:
            await websocket.close(4002, "Missing client-id")
            return

        # Validazione auth
        if self._auth_token:
            if not auth_header.startswith("Bearer "):
                await websocket.close(4004, "Missing or invalid Authorization header")
                return
            token = auth_header[7:]  # Remove "Bearer "
            if token != self._auth_token:
                await websocket.close(4005, "Invalid authorization token")
                return

        # Validazione protocol version
        try:
            protocol_version = int(version_str)
        except (ValueError, TypeError):
            await websocket.close(4003, f"Invalid Protocol-Version: {version_str!r}")
            return

        if protocol_version not in SUPPORTED_VERSIONS:
            await websocket.close(
                4003,
                f"Unsupported Protocol-Version: {protocol_version} (supported: {SUPPORTED_VERSIONS})",
            )
            return

        # Crea la connessione
        conn_kwargs: dict[str, Any] = {
            "websocket": websocket,
            "device_id": device_id,
            "client_id": client_id,
            "protocol_version": protocol_version,
            "event_callback": self._event_callback,
        }
        if self._hello_timeout_s is not None:
            conn_kwargs["hello_timeout_s"] = self._hello_timeout_s
        if self._idle_timeout_s is not None:
            conn_kwargs["idle_timeout_s"] = self._idle_timeout_s

        conn = DeviceConnection(**conn_kwargs)

        # Registra (se già esiste una connessione per questo device, chiudi la vecchia)
        old_conn = self._connections.get(device_id)
        if old_conn is not None:
            logger.info("Duplicate connection: closing old session for device=%s", device_id)
            await old_conn.close("duplicate_connection")

        self._connections[device_id] = conn
        logger.info(
            "New connection: device=%s client=%s version=%d",
            device_id, client_id, protocol_version,
        )

        try:
            await conn.run()
        except Exception as e:
            logger.error("Connection error: device=%s error=%s", device_id, e)
        finally:
            # Rimuovi dalla registry (solo se è ancora la nostra connessione)
            if self._connections.get(device_id) is conn:
                del self._connections[device_id]
            logger.info("Connection closed: device=%s", device_id)
