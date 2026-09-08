"""Eventi interni del protocollo, indipendenti dal transport."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from device.xiaozhi.messages import (
    AbortRequested,
    AudioFrameReceived,
    DeviceConnected,
    DeviceDisconnected,
    IoTMessage,
    ListenStarted,
    ListenStopped,
    MCPMessage,
)


@dataclass(frozen=True)
class WakeWordDetected:
    session_id: str
    device_id: str
    text: str


@dataclass(frozen=True)
class MCPReceived:
    session_id: str
    device_id: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class IoTReceived:
    session_id: str
    device_id: str
    descriptors: list[dict[str, Any]] | None = None
    states: list[dict[str, Any]] | None = None


__all__ = [
    "AbortRequested",
    "AudioFrameReceived",
    "DeviceConnected",
    "DeviceDisconnected",
    "IoTMessage",
    "IoTReceived",
    "ListenStarted",
    "ListenStopped",
    "MCPMessage",
    "MCPReceived",
    "WakeWordDetected",
]
