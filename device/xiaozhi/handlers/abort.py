"""Handler per il messaggio abort del device.

Produce AbortRequested.
"""

from __future__ import annotations

from typing import Any

from device.xiaozhi.handlers import MessageHandler
from device.xiaozhi.messages import Abort, AbortRequested


class AbortHandler(MessageHandler):
    """Gestisce il messaggio abort dal device."""

    async def handle(self, msg: Abort, context: dict[str, Any]) -> list[Any]:
        device_id = context.get("device_id", "unknown")

        return [
            AbortRequested(
                session_id=context.get("session_id", ""),
                device_id=device_id,
                reason=msg.reason,
            ),
        ]
