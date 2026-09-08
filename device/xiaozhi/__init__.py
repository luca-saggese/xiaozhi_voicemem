"""Package `device.xiaozhi` — protocollo e transport verso il device ESP32 stock.

Vincolo architetturale non negoziabile:
- Questo package contiene **solo** protocollo, transport, framing/codec e semantica
  device/server.
- **NON** deve contenere logica ASR, VAD, LLM, Memory o TTS.
- **NON** deve importare moduli AI (voicemem o simili).
- Il firmware ESP32 resta stock: nessuna modifica lato device.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
