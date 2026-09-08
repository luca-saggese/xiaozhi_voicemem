"""Logging strutturato e tracing (M01, passo 6).

Ogni log operativo può includere:
- session_id;
- device_id;
- turn_id;
- speaker_id (quando disponibile);
- componente;
- durata operazione;
- errore strutturato.

In M01 forniamo un logger strutturato (JSON) con un contesto per-sessione
(thread-local) e helper per misurare la durata delle operazioni.
"""

from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Any

#: Contesto operativo corrente (per-sessione), propagato via contextvars.
_current_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "xiaozhi_voicemem_log_context", default=None
)


@dataclass
class LogContext:
    """Contesto strutturato associato a una sessione/turno."""

    session_id: str | None = None
    device_id: str | None = None
    turn_id: str | None = None
    speaker_id: str | None = None
    component: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        for k in ("session_id", "device_id", "turn_id", "speaker_id", "component"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        d.update(self.extra)
        return d


class _ContextFilter(logging.Filter):
    """Aggiunge il contesto corrente (contextvars) a ogni record."""

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = _current_context.get()
        if ctx:
            for k, v in ctx.items():
                if not hasattr(record, k):
                    setattr(record, k, v)
        return True


class _JsonFormatter(logging.Formatter):
    """Formatter JSON per log strutturati."""

    def format(self, record: logging.LogRecord) -> str:
        entry: dict[str, Any] = {
            "ts": round(record.created, 3),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Contesto operativo.
        for k in ("session_id", "device_id", "turn_id", "speaker_id", "component"):
            v = getattr(record, k, None)
            if v is not None:
                entry[k] = v
        # Durata operazione, se presente.
        if hasattr(record, "duration_ms"):
            entry["duration_ms"] = record.duration_ms
        # Errore strutturato.
        if record.exc_info:
            entry["error"] = self.formatException(record.exc_info)
        if hasattr(record, "error_code"):
            entry["error_code"] = record.error_code
        return json.dumps(entry, ensure_ascii=False)


def setup_logging(level: str = "INFO", fmt: str = "json") -> logging.Logger:
    """Configura il logger radice del progetto e restituisce il logger `app`."""
    root = logging.getLogger("xiaozhi_voicemem")
    root.setLevel(level.upper())
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(_JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
    handler.addFilter(_ContextFilter())
    root.addHandler(handler)
    root.propagate = False
    return root


def get_logger(name: str = "app") -> logging.Logger:
    """Restituisce un logger figlio del logger radice del progetto."""
    return logging.getLogger(f"xiaozhi_voicemem.{name}")


class log_context:
    """Context manager che imposta il contesto operativo per la durata del blocco.

    Uso::

        with log_context(LogContext(session_id="s1", device_id="d1")):
            logger.info("hello")
    """

    def __init__(self, ctx: LogContext):
        self._ctx = ctx
        self._token: contextvars.Token | None = None

    def __enter__(self) -> log_context:
        prev = _current_context.get() or {}
        merged = {**prev, **self._ctx.as_dict()}
        self._token = _current_context.set(merged)
        return self

    def __exit__(self, *exc) -> None:
        if self._token is not None:
            _current_context.reset(self._token)


class timed:
    """Misura la durata di un'operazione e la aggiunge al log.

    Uso::

        with timed(logger, "ingest") as t:
            ...
        # logga "ingest" con duration_ms
    """

    def __init__(self, logger: logging.Logger, operation: str, **extra: Any):
        self._logger = logger
        self._operation = operation
        self._extra = extra
        self._start = 0.0

    def __enter__(self) -> timed:
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        duration_ms = (time.monotonic() - self._start) * 1000.0
        level = self._logger.error if exc_type else self._logger.info
        level(
            self._operation,
            extra={"duration_ms": round(duration_ms, 2), **self._extra},
        )
