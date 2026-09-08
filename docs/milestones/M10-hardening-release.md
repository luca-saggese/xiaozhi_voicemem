# Milestone 10 — Hardening, benchmark e Release Candidate

> **Principi non negoziabili**
>
> - Il firmware ESP32 resta **stock**: nessuna modifica lato device.
> - VoiceMem è il **core del progetto** e ne vanno preservate tutte le capability.
> - Dal progetto Xiaozhi si riusano esclusivamente protocollo, transport, codec/framing e semantica device/server.
> - Il nuovo progetto è standalone: **nessun requisito di backward compatibility** con i repository originali.
> - Ogni incompatibilità con il device si risolve **lato server**.


## Obiettivo

Portare il progetto da integrazione funzionante a Release Candidate misurabile, ripetibile e resistente ai failure mode reali.

## Deliverable

RC1 deployabile con firmware ESP32 stock, VoiceMem completo e italiano production-ready secondo metriche concordate.

## Prerequisiti

- M1–M9 completate.
- Hardware ESP32 target disponibile.
- Ambiente di staging simile alla produzione.

## Passi operativi

### 1. Protocol Compatibility Suite

Automatizzare/verificare:

- boot;
- bootstrap;
- connect;
- hello;
- listen;
- audio input;
- STT state;
- TTS start;
- audio output;
- TTS stop;
- abort;
- reconnect;
- MCP;
- IoT.

### 2. Italian Regression Suite

Mantenere dataset versionato per:

- ASR;
- fact extraction;
- corrections;
- temporal memory;
- Left Brain;
- Right Brain;
- emotion;
- retrieval;
- reply;
- TTS normalization.

### 3. Performance instrumentation

Per ogni turno raccogliere:

```text
speech_start
first_asr_partial
eou
asr_final
speculation_start
memory_ready
llm_first_token
tts_first_pcm
first_opus_sent
tts_end
```

### 4. Thresholds/SLO

Definire soglie esplicite per:

- latency;
- error rate;
- memory recall/precision;
- ASR WER;
- abort latency;
- resource usage.

### 5. Soak test

Eseguire:

- 8–12 ore;
- centinaia/migliaia di turni;
- restart controllati;
- reconnect ripetuti;
- più device simultanei.

### 6. Resource profiling

Misurare:

- RAM;
- VRAM;
- CPU;
- GPU;
- file descriptor;
- task count;
- queue depth;
- storage growth.

### 7. Failure injection

Simulare:

- ASR crash;
- LLM timeout;
- TTS timeout;
- storage unavailable;
- corrupted Opus;
- WebSocket drop;
- tool timeout;
- model OOM;
- process restart.

### 8. Recovery policy

Documentare comportamento atteso per ogni failure:

- retry;
- fallback;
- session close;
- user-visible state;
- log/metric.

### 9. Packaging

Preparare:

- Dockerfile;
- compose/example deployment;
- env/config template;
- model bootstrap;
- health endpoint;
- readiness endpoint;
- migration command;
- backup/restore memory.

### 10. Security

Verificare:

- auth headers;
- secrets management;
- no secret nei log;
- device identity handling;
- path traversal storage;
- malformed payload;
- rate limits appropriati.

### 11. Privacy e amministrazione memoria

Supportare:

- export;
- reset;
- delete;
- retention config;
- audit log amministrativo se richiesto.

### 12. Release checklist

Versionare:

- application;
- storage schema;
- protocol compatibility baseline;
- model versions;
- config schema.

## Istruzioni di implementazione

- Nessuna RC senza benchmark registrati.
- Nessuna ottimizzazione non misurata.
- Ogni failure critico deve avere test riproducibile.
- Il firmware stock resta il riferimento di compatibilità.

## Test obbligatori

- device reale;
- rete instabile;
- almeno due device simultanei;
- server restart;
- storage restart;
- 8h soak;
- 100+ abort;
- 1000+ turni aggregati;
- regression suite IT completa.

## Gate di validazione

### Gate M10-A — Protocol

Tutti i test device stock passano.

### Gate M10-B — VoiceMem capability

Nessuna capability core prevista è stata persa.

### Gate M10-C — Italiano

ASR, memory/retrieval e TTS superano soglie accettate.

### Gate M10-D — Reliability

Soak e failure injection non producono leak/corruzione critica.

### Gate M10-E — Operabilità

Deployment, health, backup/restore e log sono documentati e verificati.

## Exit criteria RC1

```text
Firmware ESP32 stock: invariato
Protocol compatibility: verificata
VoiceMem core: completo
ASR italiano: validato
Left/Right Brain italiano: validati
Memory persistence: validata
Reply/TTS streaming: validati
Abort/barge-in: validati
MCP/IoT: operativi
Soak test: superato
Packaging: pronto
```

## Post-RC

Solo dopo RC1 valutare:

- multi-speaker household;
- MQTT/UDP aggiuntivo se non già necessario;
- ottimizzazioni modello;
- UI amministrativa;
- ulteriori lingue.
