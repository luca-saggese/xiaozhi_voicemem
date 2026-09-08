"""Configurazione centralizzata del progetto (M01, passo 5).

Un unico schema di configurazione per:
- server;
- logging;
- VoiceMem;
- modelli;
- storage;
- device gateway;
- audio;
- lingua;
- feature flags interni di sviluppo.

Vincolo: niente configurazioni legacy replicate solo per compatibilità.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

#: Percorso di default per la configurazione (YAML/JSON) se presente.
DEFAULT_CONFIG_PATH = Path("config/config.yaml")


@dataclass
class ServerConfig:
    """Configurazione del server (host/porta)."""

    host: str = "0.0.0.0"
    port: int = 8765
    #: Timeout (s) per l'handshake/hello del device.
    handshake_timeout_s: float = 10.0


@dataclass
class LoggingConfig:
    """Configurazione del logging strutturato."""

    level: str = "INFO"
    #: Formato dei log operativi (vedi runtime/logging.py).
    format: str = "json"
    #: Componenti da includere nei log (session_id, device_id, turn_id, ...).
    include_context: bool = True


@dataclass
class VoiceMemConfig:
    """Configurazione del core VoiceMem.

    I campi qui esposti sono un sottoinsieme dichiarativo di ciò che VoiceMem
    accetta. In M01 non viene ancora costruito un VoiceMem completo: serve a
    tracciare la configurazione in modo esplicito.
    """

    mode: str = "text_mode"
    memory_language: str = "it"
    memory_root: str | None = None
    space: str | None = None
    user_id: str = "voice_user"
    api_key: str | None = None
    base_url: str | None = None
    top_k: int = 5
    #: Config dichiarativa stile `VoiceMem.from_config` (provider/config).
    providers: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelConfig:
    """Configurazione dei modelli (chat/reply/embedding/tts/realtime)."""

    chat: str | None = None
    reply: str | None = None
    embedding: str | None = None
    tts: str | None = None
    realtime: str | None = None


@dataclass
class StorageConfig:
    """Configurazione dello storage (memoria VoiceMem)."""

    #: Directory root per gli spazi di memoria VoiceMem.
    memory_root: str = "voicemem_memoryspace"
    #: Schema version dello storage.
    schema_version: int = 1


@dataclass
class DeviceGatewayConfig:
    """Configurazione del gateway Xiaozhi (device/xiaozhi)."""

    #: Endpoint WebSocket esposto per i device.
    websocket_path: str = "/xiaozhi"
    #: Timeout (s) keepalive/ping.
    keepalive_s: float = 30.0
    #: Timeout (s) reconnect.
    reconnect_s: float = 5.0


@dataclass
class AudioConfig:
    """Configurazione audio (contratto con il device ESP32)."""

    #: Sample rate PCM16 atteso dal core VoiceMem.
    sample_rate: int = 16000
    channels: int = 1
    #: Codec di trasporto verso il device (Opus).
    codec: str = "opus"
    frame_duration_ms: int = 60


@dataclass
class LanguageConfig:
    """Configurazione lingua."""

    #: Lingua della memoria VoiceMem (en/zh per upstream; it in arrivo con M06).
    memory_language: str = "it"
    #: Lingua di default per ASR/TTS (M05/M08).
    asr_language: str = "it"
    tts_language: str = "it"


@dataclass
class FeatureFlags:
    """Feature flags interni di sviluppo."""

    #: Abilita l'health check locale (M01, passo 8).
    health_check: bool = True
    #: Abilita il server WebSocket reale (M02). In M01 resta False.
    enable_websocket: bool = False
    #: Abilita il bridge audio (M03). In M01 resta False.
    enable_audio_bridge: bool = False


@dataclass
class AppConfig:
    """Configurazione radice del progetto."""

    server: ServerConfig = field(default_factory=ServerConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    voicemem: VoiceMemConfig = field(default_factory=VoiceMemConfig)
    models: ModelConfig = field(default_factory=ModelConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    device_gateway: DeviceGatewayConfig = field(default_factory=DeviceGatewayConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    language: LanguageConfig = field(default_factory=LanguageConfig)
    features: FeatureFlags = field(default_factory=FeatureFlags)


def _env_bool(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in {"1", "true", "yes", "on"}


def load_config(path: str | Path | None = None) -> AppConfig:
    """Carica la configurazione da file (YAML/JSON) se presente, altrimenti default.

    In M01 la configurazione è costruita con i default di dataclass, con la
    possibilità di sovrascrivere alcuni valori via variabili d'ambiente
    (prefisso `XIAOZHI_VOICEMEM_`). Il parsing di file YAML/JSON verrà
    completato quando la configurazione diventerà necessaria (M02+).
    """
    cfg = AppConfig()

    # Sovrascritture via env (esplicite e tracciabili).
    if v := os.environ.get("XIAOZHI_VOICEMEM_HOST"):
        cfg.server.host = v
    if v := os.environ.get("XIAOZHI_VOICEMEM_PORT"):
        cfg.server.port = int(v)
    if v := os.environ.get("XIAOZHI_VOICEMEM_LOG_LEVEL"):
        cfg.logging.level = v.upper()
    if v := os.environ.get("XIAOZHI_VOICEMEM_MEMORY_LANGUAGE"):
        cfg.voicemem.memory_language = v
        cfg.language.memory_language = v
    if v := os.environ.get("XIAOZHI_VOICEMEM_MEMORY_ROOT"):
        cfg.voicemem.memory_root = v
        cfg.storage.memory_root = v
    if v := os.environ.get("XIAOZHI_VOICEMEM_API_KEY"):
        cfg.voicemem.api_key = v
    if v := os.environ.get("XIAOZHI_VOICEMEM_BASE_URL"):
        cfg.voicemem.base_url = v

    cfg.features.enable_websocket = _env_bool(
        "XIAOZHI_VOICEMEM_ENABLE_WEBSOCKET", cfg.features.enable_websocket
    )
    cfg.features.enable_audio_bridge = _env_bool(
        "XIAOZHI_VOICEMEM_ENABLE_AUDIO_BRIDGE", cfg.features.enable_audio_bridge
    )

    return cfg
