"""Interfacce minime di confine tra device, runtime e VoiceMem (M01, passo 4).

Queste classi definiscono il contratto architetturale tra i tre livelli:

    device/xiaozhi  = protocollo e transport (DeviceSession)
    runtime         = orchestrazione device ↔ VoiceMem (AssistantSession)
    voicemem        = AI/memory/audio cognition (non conosce WebSocket/MQTT)

In M01 non implementano ancora logica completa: sono solo i boundary da cui
partiranno le milestone successive (M02+).
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any

# ── Event model interno (device → runtime) ──────────────────────────────────


@dataclass
class DeviceEvent:
    """Evento generato dal gateway Xiaozhi e consumato dal runtime.

    In M01 è solo il tipo base: le sottoclassi concrete (DeviceConnected,
    ListenStarted, AudioFrameReceived, ...) arriveranno con M02.
    """

    session_id: str
    device_id: str
    #: timestamp epoch (secondi) di generazione dell'evento.
    ts: float = field(default_factory=lambda: __import__("time").time())
    #: payload opzionale specifico del tipo di evento.
    payload: Any = None


# ── Command model interno (runtime → device) ────────────────────────────────


@dataclass
class DeviceCommand:
    """Comando inviato dal runtime al gateway Xiaozhi.

    In M01 è solo il tipo base: le sottoclassi concrete (SendHello,
    SendTranscript, SendTTSStart, SendAudioFrame, ...) arriveranno con M02.
    """

    session_id: str
    device_id: str
    #: payload opzionale specifico del tipo di comando.
    payload: Any = None


# ── Sessioni ────────────────────────────────────────────────────────────────


class DeviceSession(abc.ABC):
    """Sessione verso un device ESP32 stock (lato gateway Xiaozhi).

    Responsabilità (M02+): handshake, state machine, invio/ricezione messaggi,
    reconnect. Nessuna logica AI.
    """

    @abc.abstractmethod
    async def run(self) -> None:
        """Avvia e mantiene la sessione fino a chiusura o errore."""
        raise NotImplementedError

    @abc.abstractmethod
    async def send(self, command: DeviceCommand) -> None:
        """Invia un comando al device."""
        raise NotImplementedError


class AssistantSession(abc.ABC):
    """Sessione assistente lato runtime: collega device ↔ VoiceMem.

    Responsabilità (M04+): possedere il riferimento DeviceSession, gestire
    VoiceStream, assegnare turn_id, ricevere eventi device. Non duplica le
    capability VoiceMem.
    """

    @abc.abstractmethod
    async def handle(self, event: DeviceEvent) -> None:
        """Gestisce un evento proveniente dal device."""
        raise NotImplementedError
