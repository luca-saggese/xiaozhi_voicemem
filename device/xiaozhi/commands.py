"""Comandi server-side, privi di networking."""

from __future__ import annotations

from dataclasses import dataclass

from device.xiaozhi.messages import (
    SendHello,
    SendIoT,
    SendMCP,
    SendTranscript,
    SendTTSStart,
    SendTTSStop,
)


@dataclass(frozen=True)
class SendTTSSentence:
    session_id: str
    device_id: str
    text: str


@dataclass(frozen=True)
class SendLLMState:
    session_id: str
    device_id: str
    emotion: str | None = None
    text: str | None = None


@dataclass(frozen=True)
class SendPong:
    session_id: str
    device_id: str
    timestamp: int


__all__ = [
    "SendHello",
    "SendTranscript",
    "SendTTSStart",
    "SendTTSSentence",
    "SendTTSStop",
    "SendLLMState",
    "SendMCP",
    "SendIoT",
    "SendPong",
]
