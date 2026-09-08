"""Handler per il messaggio hello del device.

Produce DeviceConnected quando l'hello è valido.
"""

from __future__ import annotations

from typing import Any

from device.xiaozhi.handlers import MessageHandler
from device.xiaozhi.messages import (
    DeviceConnected,
    HelloDevice,
)


class HelloHandler(MessageHandler):
    """Gestisce il messaggio hello dal device."""

    async def handle(self, msg: HelloDevice, context: dict[str, Any]) -> list[Any]:
        device_id = context.get("device_id", "unknown")
        client_id = context.get("client_id", "unknown")

        return [
            DeviceConnected(
                session_id=context.get("session_id", ""),
                device_id=device_id,
                client_id=client_id,
                protocol_version=msg.version,
                audio_params=msg.audio_params,
                features=msg.features,
            ),
        ]
