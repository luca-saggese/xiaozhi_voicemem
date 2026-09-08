"""Health check locale (M01, passo 8).

Verifica:
- processo attivo;
- config caricata;
- storage accessibile;
- VoiceMem inizializzato;
- dipendenze modello risolte o chiaramente segnalate.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from runtime.config import AppConfig
from runtime.logging import get_logger

logger = get_logger("health")


@dataclass
class HealthReport:
    """Risultato dell'health check."""

    ok: bool
    checks: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "checks": self.checks}


def _check_process() -> dict[str, Any]:
    return {"ok": True, "pid": os.getpid()}


def _check_config(config: AppConfig) -> dict[str, Any]:
    return {"ok": True, "server": f"{config.server.host}:{config.server.port}"}


def _check_storage(config: AppConfig) -> dict[str, Any]:
    root = Path(config.storage.memory_root)
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".health_probe"
        probe.write_text("ok")
        probe.unlink()
        return {"ok": True, "path": str(root), "writable": True}
    except OSError as e:
        return {"ok": False, "path": str(root), "error": str(e)}


def _check_voicemem(config: AppConfig) -> dict[str, Any]:
    """Verifica che VoiceMem sia importabile e inizializzabile.

    In M01 non costruiamo un VoiceMem completo (richiederebbe modelli/API key):
    verifichiamo che il package sia importabile e che la costruzione dichiarativa
    sia possibile senza errori a import-time.
    """
    try:
        import voicemem  # noqa: F401

        return {"ok": True, "importable": True, "version": getattr(voicemem, "__version__", "unknown")}
    except Exception as e:  # pragma: no cover
        return {"ok": False, "importable": False, "error": str(e)}


def _check_models(config: AppConfig) -> dict[str, Any]:
    """Segnala lo stato delle dipendenze modello (risolte o chiaramente assenti).

    In M01 i modelli non sono ancora richiesti: riportiamo solo lo stato
    dichiarato in config, senza tentare download.
    """
    missing: list[str] = []
    if not config.voicemem.api_key:
        missing.append("api_key")
    return {
        "ok": True,
        "configured": not missing,
        "missing": missing,
        "note": "modelli non ancora richiesti in M01",
    }


def run_health_check(config: AppConfig) -> HealthReport:
    """Esegue tutti i controlli e produce un report aggregato."""
    checks = {
        "process": _check_process(),
        "config": _check_config(config),
        "storage": _check_storage(config),
        "voicemem": _check_voicemem(config),
        "models": _check_models(config),
    }
    ok = all(c.get("ok", False) for c in checks.values())
    report = HealthReport(ok=ok, checks=checks)
    logger.info("health_check", extra={"report": report.to_dict()})
    return report
