"""Handler per messaggi di protocollo Xiaozhi.

Ogni handler riceve il messaggio parsato e il contesto della connessione,
e produce eventi astratti verso il runtime.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MessageHandler(ABC):
    """Base per gli handler di messaggi protocollo."""

    @abstractmethod
    async def handle(self, msg: Any, context: dict[str, Any]) -> list[Any]:
        """Gestisce un messaggio e restituisce una lista di eventi.

        Args:
            msg: Il messaggio parsato (dataclass tipizzata).
            context: Contesto della connessione (session_id, device_id, ...).

        Returns:
            Lista di eventi astratti da inviare al runtime.
        """
        raise NotImplementedError
