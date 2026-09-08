# Upstream Sources — Repository sorgente acquisiti e congelati

Questo documento registra i repository upstream usati come sorgente per il nuovo
progetto standalone **xiaozhi_voicemem**. Le revisioni qui riportate sono quelle
acquisite localmente in `_upstream/` e rappresentano il riferimento congelato
per tutto il ciclo di sviluppo.

> **Nota**: `_upstream/` è escluso dal versionamento (vedi `.gitignore`).
> Questo documento è l'unico registro persistente delle revisioni acquisite.

---

## VoiceMem

| Campo | Valore |
|---|---|
| Repository URL | `https://github.com/xzf-thu/VoiceMem.git` |
| Branch acquisito | `main` |
| Commit SHA (HEAD) | `a450911fc8cbb44c46d810aace2f3288bad287e4` |
| Tag / versione | `v0.0.2-24-ga450911` (describe); package `voicemem` v`0.2.3` |
| Data acquisizione | 2026-09-08 |
| Licenza | Apache License 2.0 (file `LICENSE` presente nel repository) |
| Stato working tree | pulito (nessuna modifica locale) |

### Ruolo nel nuovo progetto

- **Sorgente principale / core** del nuovo progetto.
- Tutte le capability devono essere **preservate**:
  - `VoiceMem` / `VoiceStream`;
  - Left Brain (fact extraction, cognitive graph, memory repository, slot split);
  - Right Brain (emotion, traits, experience, attribution, anchor router);
  - ingest / search / retrieval;
  - emotion;
  - speaker / voiceprint;
  - entity / schema;
  - embedding;
  - reply / reply_stream;
  - TTS / speak_stream;
  - modalità multimodali.
- Sarà **modificato direttamente** nel nuovo codebase.
- L'upstream è usato come **baseline e riferimento** (non come dipendenza).

---

## xiaozhi-esp32-server

| Campo | Valore |
|---|---|
| Repository URL | `https://github.com/xinnan-tech/xiaozhi-esp32-server.git` |
| Branch acquisito | `main` |
| Commit SHA (HEAD) | `5aa46538d5087aaee99a5fc318689a0da0a2a9c7` |
| Tag / versione | `v0.9.6-80-g5aa46538` (describe) |
| Data acquisizione | 2026-09-08 |
| Licenza | MIT License (file `LICENSE` presente nel repository) |
| Stato working tree | pulito (nessuna modifica locale) |

### Ruolo nel nuovo progetto

- **Esclusivamente riferimento / fornitore** per protocollo e comunicazione con
  il device ESP32 stock.
- Aree di interesse (solo ciò che serve al device):
  - WebSocket / MQTT se necessario;
  - handshake (`hello`);
  - message protocol;
  - audio framing;
  - Opus transport (encode/decode);
  - `listen` / `abort`;
  - MCP / IoT;
  - OTA / bootstrap **solo se richiesto dal firmware stock**.
- **NON** è sorgente per: ASR, VAD, LLM, Memory, TTS o agent runtime.
- Il firmware ESP32 resta **stock**: nessuna modifica lato device.

---

## Vincoli di riuso

- VoiceMem è il core: nessuna compatibilità obbligatoria con gli upstream.
- Da Xiaozhi entrano solo protocollo, transport, framing/codec e semantica
  device/server.
- Il package `device/xiaozhi` non deve contenere logica ASR, VAD, LLM, Memory o
  TTS.
- VoiceMem non deve conoscere WebSocket, MQTT o protocollo Xiaozhi.
- Ogni incompatibilità con il device si risolve **lato server**.