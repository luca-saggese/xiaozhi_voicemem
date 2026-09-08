"""Binary framing Xiaozhi, senza dipendenze audio.

Il codec tratta il payload come bytes opachi. La decodifica Opus appartiene a
M03 e non deve essere introdotta qui.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum

from device.xiaozhi.errors import ProtocolError


class BinaryFramingVersion(IntEnum):
    """Versione del formato del binary frame, distinta da hello e dagli header HTTP."""

    V1 = 1
    V2 = 2
    V3 = 3


@dataclass(frozen=True)
class BinaryFrame:
    """Frame binario decodificato, con payload ancora opaco."""

    version: BinaryFramingVersion
    payload: bytes
    frame_type: int = 0
    timestamp: int = 0


class MalformedFrame(ProtocolError):
    """Frame binario troncato, incoerente o con dimensione non valida."""

    def __init__(self, message: str):
        super().__init__(message, code="MALFORMED_FRAME", recoverable=True)


_V2_HEADER = struct.Struct("!HHIII")
_V3_HEADER = struct.Struct("!BBH")


def encode_frame(
    payload: bytes,
    version: BinaryFramingVersion | int,
    *,
    frame_type: int = 0,
    timestamp: int = 0,
) -> bytes:
    """Serializza un frame v1, v2 o v3 usando network byte order."""

    framing_version = _version(version)
    if not isinstance(payload, bytes):
        raise MalformedFrame("payload must be bytes")
    if not 0 <= frame_type <= 0xFFFF:
        raise MalformedFrame("frame_type is outside the supported range")
    if not 0 <= timestamp <= 0xFFFFFFFF:
        raise MalformedFrame("timestamp is outside the supported range")

    if framing_version is BinaryFramingVersion.V1:
        return payload
    if framing_version is BinaryFramingVersion.V2:
        if len(payload) > 0xFFFFFFFF:
            raise MalformedFrame("payload is too large for binary v2")
        if frame_type > 0xFFFF:
            raise MalformedFrame("frame_type is too large for binary v2")
        return _V2_HEADER.pack(2, frame_type, 0, timestamp, len(payload)) + payload
    if frame_type > 0xFF:
        raise MalformedFrame("frame_type is too large for binary v3")
    if len(payload) > 0xFFFF:
        raise MalformedFrame("payload is too large for binary v3")
    return _V3_HEADER.pack(frame_type, 0, len(payload)) + payload


def decode_frame(
    data: bytes,
    version: BinaryFramingVersion | int,
) -> BinaryFrame:
    """Decodifica un frame e rifiuta header o payload troncati."""

    framing_version = _version(version)
    if not isinstance(data, bytes):
        raise MalformedFrame("frame must be bytes")

    if framing_version is BinaryFramingVersion.V1:
        return BinaryFrame(framing_version, data)

    if framing_version is BinaryFramingVersion.V2:
        if len(data) < _V2_HEADER.size:
            raise MalformedFrame("binary v2 header is truncated")
        header_version, frame_type, _reserved, timestamp, payload_size = _V2_HEADER.unpack_from(data)
        if header_version != 2:
            raise MalformedFrame(f"binary v2 header has version {header_version}")
    else:
        if len(data) < _V3_HEADER.size:
            raise MalformedFrame("binary v3 header is truncated")
        frame_type, _reserved, payload_size = _V3_HEADER.unpack_from(data)
        timestamp = 0

    header_size = _V2_HEADER.size if framing_version is BinaryFramingVersion.V2 else _V3_HEADER.size
    actual_size = len(data) - header_size
    if payload_size != actual_size:
        raise MalformedFrame(
            f"payload_size={payload_size} does not match actual size={actual_size}"
        )
    return BinaryFrame(framing_version, data[header_size:], frame_type, timestamp)


def _version(version: BinaryFramingVersion | int) -> BinaryFramingVersion:
    try:
        return BinaryFramingVersion(version)
    except (TypeError, ValueError) as exc:
        raise MalformedFrame(f"unsupported binary framing version: {version!r}") from exc
