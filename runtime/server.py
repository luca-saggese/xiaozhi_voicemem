"""Server avviabile del progetto (M01, passo 7).

In M01 il server:
- carica configurazione e logging;
- inizializza VoiceMem (verifica importabilità);
- espone la struttura modulare definitiva;
- NON include ancora comunicazione reale con ESP32 (feature flag `enable_websocket`
  resta False fino a M02);
- espone un health check locale.

Il server è un processo asincrono che resta in esecuzione finché non riceve
SIGINT/SIGTERM. In M01 non apre ancora socket WebSocket: si limita a inizializzare
i componenti e a servire l'health check.
"""

from __future__ import annotations

import asyncio
import signal
import sys

from runtime.config import AppConfig, load_config
from runtime.health import run_health_check
from runtime.logging import get_logger, setup_logging

logger = get_logger("server")


class Server:
    """Server del progetto xiaozhi_voicemem."""

    def __init__(self, config: AppConfig | None = None):
        self.config = config or load_config()
        self._stop = asyncio.Event()
        self._voicemem_ready = False

    # ── inizializzazione ──────────────────────────────────────────────────────

    def init_voicemem(self) -> None:
        """Verifica che VoiceMem sia importabile e inizializzabile.

        In M01 non costruiamo un VoiceMem completo (richiederebbe modelli/API
        key): verifichiamo l'importabilità del package. La costruzione completa
        arriverà con le milestone successive.
        """
        try:
            import voicemem  # noqa: F401

            self._voicemem_ready = True
            logger.info(
                "voicemem_ready",
                extra={"version": getattr(voicemem, "__version__", "unknown")},
            )
        except Exception as e:  # pragma: no cover
            self._voicemem_ready = False
            logger.error("voicemem_init_failed", extra={"error": str(e)})
            raise

    # ── ciclo di vita ────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Avvia il server: inizializza i componenti e attende lo stop."""
        self.init_voicemem()
        logger.info(
            "server_started",
            extra={
                "host": self.config.server.host,
                "port": self.config.server.port,
                "websocket_enabled": self.config.features.enable_websocket,
            },
        )
        if self.config.features.enable_websocket:
            # M02: qui verrà avviato il WebSocket server del gateway Xiaozhi.
            logger.warning("websocket_not_implemented_yet")
        await self._stop.wait()

    async def stop(self) -> None:
        """Ferma il server."""
        self._stop.set()
        logger.info("server_stopped")

    async def health(self) -> dict:
        """Esegue l'health check locale."""
        report = run_health_check(self.config)
        return report.to_dict()


async def _run(config: AppConfig | None = None) -> int:
    setup_logging()
    server = Server(config)
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, server.stop)
        except NotImplementedError:  # pragma: no cover (Windows)
            pass

    await server.start()
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entrypoint CLI del server."""
    argv = argv if argv is not None else sys.argv[1:]

    # Supporto minimo: `--health` esegue l'health check e termina.
    if "--health" in argv:
        config = load_config()
        report = run_health_check(config)
        import json

        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0 if report.ok else 1

    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:  # pragma: no cover
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
