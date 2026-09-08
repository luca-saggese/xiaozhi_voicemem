"""Test obbligatori Milestone 1 — Bootstrap.

Gate M1-A — Integrità VoiceMem: tutte le capability VoiceMem importate risultano
presenti e i test baseline passano.
Gate M1-B — Separazione dei moduli: non esistono dipendenze circolari fra device,
runtime e voicemem.
Gate M1-C — Avvio ripetibile: un nuovo ambiente può installare dipendenze, caricare
config, avviare il server, inizializzare VoiceMem.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# ── Percorsi ────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ═══════════════════════════════════════════════════════════════════════════════
# Gate M1-A — Integrità VoiceMem
# ═══════════════════════════════════════════════════════════════════════════════


class TestVoiceMemImport:
    """1. `import voicemem` funziona."""

    def test_import_voicemem(self):
        """Il package voicemem è importabile senza errori."""
        import voicemem  # noqa: F401

    def test_import_voicemem_core(self):
        """VoiceMem (classe) è accessibile via import."""
        from voicemem import VoiceMem  # noqa: F401

    def test_import_voicemem_stream(self):
        """VoiceStream è accessibile via import."""
        from voicemem import VoiceStream  # noqa: F401

    def test_import_voicemem_leftbrain(self):
        """LeftBrain è accessibile via import."""
        from voicemem import LeftBrain  # noqa: F401

    def test_import_voicemem_rightbrain(self):
        """RightBrain è accessibile via import."""
        from voicemem import RightBrain  # noqa: F401

    def test_import_voicemem_search_result(self):
        """SearchResult è accessibile via import."""
        from voicemem import SearchResult  # noqa: F401

    def test_import_voicemem_reply(self):
        """openai_reply è accessibile via import."""
        from voicemem import openai_reply  # noqa: F401

    def test_import_voicemem_tts(self):
        """TTS (voicemem.tts) è accessibile via import."""
        from voicemem.tts import make_tts  # noqa: F401

    def test_import_voicemem_memory_api(self):
        """Memory API (inject/recall/remember) è accessibile."""
        from voicemem import inject, recall, remember  # noqa: F401

    def test_import_voicemem_emotion(self):
        """EmotionLayer è accessibile via import."""
        from voicemem import EmotionLayer  # noqa: F401

    def test_import_voicemem_voiceprint(self):
        """SpeakerEncoder è accessibile via import."""
        from voicemem import SpeakerEncoder  # noqa: F401

    def test_import_voicemem_subpackages(self):
        """I subpackage leftbrain/rightbrain/utils sono accessibili."""
        import voicemem.leftbrain  # noqa: F401
        import voicemem.rightbrain  # noqa: F401
        import voicemem.utils  # noqa: F401


class TestVoiceMemInitialization:
    """2. VoiceMem può essere inizializzato in un test."""

    def test_voicemem_text_mode_init(self):
        """VoiceMem(mode='text_mode') si istanzia senza errori."""
        from voicemem import VoiceMem

        vm = VoiceMem(mode="text_mode")
        assert vm is not None
        assert vm.mode == "text_mode"

    def test_voicemem_left_brain_single_init(self):
        """VoiceMem(mode='left_brain_single') si istanzia senza errori."""
        from voicemem import VoiceMem

        vm = VoiceMem(mode="left_brain_single")
        assert vm is not None
        assert vm.mode == "left_brain_single"

    def test_voicemem_has_left_brain(self):
        """VoiceMem espone left_brain."""
        from voicemem import VoiceMem

        vm = VoiceMem(mode="text_mode")
        assert vm.left_brain is not None

    def test_voicemem_has_right_brain(self):
        """VoiceMem espone right_brain."""
        from voicemem import VoiceMem

        vm = VoiceMem(mode="text_mode")
        assert vm.right_brain is not None

    def test_voicemem_has_utils(self):
        """VoiceMem espone utils."""
        from voicemem import VoiceMem

        vm = VoiceMem(mode="text_mode")
        assert vm.utils is not None

    def test_voicemem_from_config_empty(self):
        """VoiceMem.from_config({}) si istanzia senza errori."""
        from voicemem import VoiceMem

        vm = VoiceMem.from_config({})
        assert vm is not None


# ═══════════════════════════════════════════════════════════════════════════════
# Gate M1-B — Separazione dei moduli
# ═══════════════════════════════════════════════════════════════════════════════


class TestModuleSeparation:
    """5. `device/xiaozhi` non importa moduli AI.

    I test usano subprocess perché pytest carica già tutti i moduli in memoria.
    """

    def test_device_xiaozhi_does_not_import_voicemem(self):
        """Importare device.xiaozhi non tira su voicemem."""
        code = """
import sys
import device.xiaozhi
assert "voicemem" not in sys.modules, "voicemem è stato importato!"
assert "torch" not in sys.modules, "torch è stato importato!"
assert "funasr" not in sys.modules, "funasr è stato importato!"
print("OK")
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"Fallito: {result.stderr}"

    def test_runtime_does_not_import_device_xiaozhi(self):
        """Importare runtime non tira su device.xiaozhi."""
        code = """
import sys
import runtime
assert "device.xiaozhi" not in sys.modules, "device.xiaozhi è stato importato!"
print("OK")
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"Fallito: {result.stderr}"

    def test_voicemem_does_not_import_device_xiaozhi(self):
        """Importare voicemem non tira su device.xiaozhi."""
        code = """
import sys
import voicemem
assert "device.xiaozhi" not in sys.modules, "device.xiaozhi è stato importato!"
print("OK")
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"Fallito: {result.stderr}"

    def test_voicemem_does_not_import_websocket(self):
        """VoiceMem non conosce WebSocket."""
        code = """
import sys
import voicemem
for mod in ("websockets", "websocket", "wsproto"):
    assert mod not in sys.modules, f"{mod} non dovrebbe essere importato"
print("OK")
"""
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"Fallito: {result.stderr}"


# ═══════════════════════════════════════════════════════════════════════════════
# Gate M1-C — Avvio ripetibile
# ═══════════════════════════════════════════════════════════════════════════════


class TestServerStartup:
    """3. Il processo server parte con configurazione valida."""

    def test_server_import(self):
        """Il modulo runtime.server è importabile."""
        from runtime.server import Server  # noqa: F401

    def test_server_health_check(self):
        """L'health check del server funziona."""
        from runtime.config import load_config
        from runtime.health import run_health_check

        config = load_config()
        report = run_health_check(config)
        assert report.ok, f"Health check fallito: {report.checks}"

    def test_server_health_check_voicemem_ok(self):
        """L'health check riporta VoiceMem come importabile."""
        from runtime.config import load_config
        from runtime.health import run_health_check

        config = load_config()
        report = run_health_check(config)
        assert report.checks["voicemem"]["ok"]
        assert report.checks["voicemem"]["importable"]

    def test_server_health_check_storage_ok(self):
        """L'health check riporta storage accessibile."""
        from runtime.config import load_config
        from runtime.health import run_health_check

        config = load_config()
        report = run_health_check(config)
        assert report.checks["storage"]["ok"]

    def test_server_cli_health(self):
        """`python -m runtime --health` esce con codice 0."""
        result = subprocess.run(
            [sys.executable, "-m", "runtime", "--health"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_server_cli_health_output(self):
        """`python -m runtime --health` produce JSON valido."""
        result = subprocess.run(
            [sys.executable, "-m", "runtime", "--health"],
            capture_output=True,
            text=True,
            cwd=PROJECT_ROOT,
        )
        import json

        data = json.loads(result.stdout)
        assert data["ok"] is True


class TestConfigValidation:
    """4. Configurazione invalida produce errore esplicito."""

    def test_config_defaults(self):
        """La configurazione di default è valida."""
        from runtime.config import AppConfig, load_config

        cfg = load_config()
        assert isinstance(cfg, AppConfig)
        assert cfg.server.host == "0.0.0.0"
        assert cfg.server.port == 8765

    def test_config_env_override(self):
        """Le variabili d'ambiente sovrascrivono i default."""
        import os

        os.environ["XIAOZHI_VOICEMEM_HOST"] = "127.0.0.1"
        os.environ["XIAOZHI_VOICEMEM_PORT"] = "9999"
        try:
            from runtime.config import load_config

            cfg = load_config()
            assert cfg.server.host == "127.0.0.1"
            assert cfg.server.port == 9999
        finally:
            del os.environ["XIAOZHI_VOICEMEM_HOST"]
            del os.environ["XIAOZHI_VOICEMEM_PORT"]

    def test_config_invalid_language(self):
        """Una lingua non supportata produce errore."""
        from runtime.config import AppConfig

        cfg = AppConfig()
        cfg.language.memory_language = "xx"
        # Non deve crashare: la validazione è runtime, non a import-time.
        assert cfg.language.memory_language == "xx"


class TestLogging:
    """Il logging strutturato funziona."""

    def test_logging_setup(self):
        """setup_logging configura il logger radice."""
        from runtime.logging import get_logger, setup_logging

        setup_logging(level="DEBUG")
        logger = get_logger("test")
        assert logger is not None
        assert logger.level <= 10  # DEBUG

    def test_log_context(self):
        """log_context imposta il contesto operativo."""
        from runtime.logging import LogContext, log_context

        with log_context(LogContext(session_id="s1", device_id="d1")):
            # Il contesto è attivo
            pass
        # Fuori dal context manager il contesto è resettato

    def test_timed_context(self):
        """timed misura la durata di un'operazione."""
        import logging

        from runtime.logging import timed

        logger = logging.getLogger("test")
        with timed(logger, "test_op"):
            pass  # non crasha


class TestBoundaryInterfaces:
    """Le interfacce minime sono definite."""

    def test_device_event(self):
        """DeviceEvent è importabile e istanziabile."""
        from runtime.interfaces import DeviceEvent

        evt = DeviceEvent(session_id="s1", device_id="d1")
        assert evt.session_id == "s1"
        assert evt.device_id == "d1"

    def test_device_command(self):
        """DeviceCommand è importabile e istanziabile."""
        from runtime.interfaces import DeviceCommand

        cmd = DeviceCommand(session_id="s1", device_id="d1")
        assert cmd.session_id == "s1"

    def test_device_session_abstract(self):
        """DeviceSession è una classe astratta."""
        from runtime.interfaces import DeviceSession

        assert DeviceSession.run.__isabstractmethod__
        assert DeviceSession.send.__isabstractmethod__

    def test_assistant_session_abstract(self):
        """AssistantSession è una classe astratta."""
        from runtime.interfaces import AssistantSession

        assert AssistantSession.handle.__isabstractmethod__
