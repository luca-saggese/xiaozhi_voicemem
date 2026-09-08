"""Handler per il messaggio listen del device.

Produce ListenStarted, ListenStopped a seconda dello stato.
"""

from __future__ import annotations

from typing import Any

from device.xiaozhi.handlers import MessageHandler
from device.xiaozhi.messages import Listen, ListenStarted, ListenStopped


class ListenHandler(MessageHandler):
    """Gestisce il messaggio listen dal device."""

    async def handle(self, msg: Listen, context: dict[str, Any]) -> list[Any]:
        device_id = context.get("device_id", "unknown")

        if msg.state == "start":
            return [
                ListenStarted(
                    session_id=context.get("session_id", ""),
                    device_id=device_id,
                    mode=msg.mode,
                ),
            ]
        elif msg.state == "stop":
            return [
                ListenStopped(
                    session_id=context.get("session_id", ""),
                    device_id=device_id,
                ),
            ]
        elif msg.state == "detect":
            # Wake word detected: trattiamo come start + testo
            return [
                ListenStarted(
                    session_id=context.get("session_id", ""),
                    device_id=device_id,
                    mode="detect",
                ),
            ]

        return []
