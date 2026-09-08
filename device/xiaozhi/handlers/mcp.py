"""Handler per il messaggio mcp del device.

Produce MCPMessage.
"""

from __future__ import annotations

from typing import Any

from device.xiaozhi.handlers import MessageHandler
from device.xiaozhi.messages import MCPMessage


class MCPHandler(MessageHandler):
    """Gestisce il messaggio mcp dal device."""

    async def handle(self, msg: dict[str, Any], context: dict[str, Any]) -> list[Any]:
        device_id = context.get("device_id", "unknown")

        return [
            MCPMessage(
                session_id=context.get("session_id", ""),
                device_id=device_id,
                payload=msg,
            ),
        ]
