# xiaozhi_voicemem

Server standalone **VoiceMem-first** per device ESP32 Xiaozzi stock.

VoiceMem è il core del progetto. Il gateway Xiaozhi (`device/xiaozhi`) fornisce
solo protocollo, transport, framing/codec e semantica device/server. Il firmware
ESP32 resta **stock**: nessuna modifica lato device.

## Architettura

```text
device/xiaozhi     = protocollo e transport (gateway ESP32)
runtime            = orchestrazione device ↔ VoiceMem
voicemem           = AI/memory/audio cognition (core)
```

Vincoli non negoziabili:

- `device/xiaozhi` **non** contiene logica ASR, VAD, LLM, Memory o TTS.
- `voicemem` **non** conosce WebSocket, MQTT o protocollo Xiaozhi.
- Ogni incompatibilità con il device si risolve **lato server**.

## Stato

**Milestone 1 — Bootstrap** (in corso). Il server è avviabile, carica
configurazione e logging, espone la struttura modulare definitiva e passa
test/lint/CI di base. Nessuna comunicazione reale con ESP32 ancora.

## Installazione (sviluppo)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Avvio

```bash
# Health check locale (verifica processo, config, storage, VoiceMem, modelli)
python -m runtime --health

# Avvio del server (in M01 resta in attesa; WebSocket arriva con M02)
python -m runtime
```

## Test

```bash
pytest
ruff check .
mypy runtime device
```

## Upstream

Le revisioni congelate dei repository sorgente (VoiceMem e xiaozhi-esp32-server)
sono registrate in [`docs/UPSTREAM_SOURCES.md`](docs/UPSTREAM_SOURCES.md). I
repository clonati vivono in `_upstream/` (esclusi dal versionamento).

## Licenza

Apache License 2.0. VoiceMem è Apache-2.0; xiaozhi-esp32-server è MIT (usato
solo come riferimento di protocollo).