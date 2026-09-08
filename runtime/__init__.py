"""Package `runtime` — orchestrazione device ↔ VoiceMem.

Il runtime è il livello che collega il gateway Xiaozhi (device/xiaozhi) al core
cognitivo (voicemem). Non contiene logica di protocollo né logica AI: coordina
solo i due lati.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
