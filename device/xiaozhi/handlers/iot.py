"""Handler per il messaggio iot del device.

Produce IoTMessage.
"""

from __future__ import annotations

from typing import Any

from device.xiaozhi.handlers import MessageHandler
from device.xiaozhi.messages import IoTMessage


class IoTHandler(MessageHandler):
    """Gestisce il messaggio iot dal device."""

    async def handle(self, msg: dict[str, Any], context: dict[str, Any]) -> list[Any]:
        device_id = context.get("device_id", "unknown")

        return [
            IoTMessage(
                session_id=context.get("session_id", ""),
                device_id=device_id,
                descriptors=msg.get("descriptors"),
                states=msg.get("states"),
            ),
        ]
