"""Errori e eccezioni del protocollo Xiaozhi (lato gateway).

Gerarchia:
- ProtocolError (base)
  - MalformedMessage: JSON non valido o campi mancanti
  - UnknownMessageType: type sconosciuto
  - InvalidStateTransition: transizione di stato non valida
  - HelloTimeout: timeout attesa hello dal device
  - AuthenticationError: header mancanti o token non valido
  - ProtocolVersionError: versione protocollo non supportata
"""

from __future__ import annotations


class ProtocolError(Exception):
    """Errore base del protocollo Xiaozhi."""

    def __init__(self, message: str, *, code: str = "PROTOCOL_ERROR", recoverable: bool = False):
        self.code = code
        self.recoverable = recoverable
        super().__init__(message)


class MalformedMessage(ProtocolError):
    """Messaggio JSON malformato o con campi obbligatori mancanti."""

    def __init__(self, message: str, detail: str = ""):
        super().__init__(
            f"Malformed message: {message}" + (f" ({detail})" if detail else ""),
            code="MALFORMED_MESSAGE",
            recoverable=True,
        )


class UnknownMessageType(ProtocolError):
    """Type sconosciuto nel messaggio."""

    def __init__(self, msg_type: str):
        super().__init__(
            f"Unknown message type: {msg_type!r}",
            code="UNKNOWN_MESSAGE_TYPE",
            recoverable=True,
        )


class InvalidStateTransition(ProtocolError):
    """Transizione di stato non valida per la sessione."""

    def __init__(self, from_state: str, to_state: str, session_id: str = ""):
        msg = f"Invalid state transition: {from_state} -> {to_state}"
        if session_id:
            msg += f" (session={session_id})"
        super().__init__(msg, code="INVALID_STATE_TRANSITION", recoverable=True)


class HelloTimeout(ProtocolError):
    """Timeout nell'attesa del messaggio hello dal device."""

    def __init__(self, timeout_s: float):
        super().__init__(
            f"Hello timeout after {timeout_s}s",
            code="HELLO_TIMEOUT",
            recoverable=False,
        )


class AuthenticationError(ProtocolError):
    """Header di autenticazione mancanti o token non valido."""

    def __init__(self, reason: str):
        super().__init__(
            f"Authentication failed: {reason}",
            code="AUTH_ERROR",
            recoverable=False,
        )


class ProtocolVersionError(ProtocolError):
    """Versione protocollo non supportata."""

    def __init__(self, version: int, supported: list[int]):
        super().__init__(
            f"Unsupported protocol version: {version} (supported: {supported})",
            code="PROTOCOL_VERSION_ERROR",
            recoverable=False,
        )


class SessionIdMismatch(ProtocolError):
    """Il messaggio appartiene a una sessione diversa."""

    def __init__(self, expected: str, actual: str):
        super().__init__(
            f"Session id mismatch: expected {expected!r}, got {actual!r}",
            code="SESSION_ID_MISMATCH",
            recoverable=True,
        )
