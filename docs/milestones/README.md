# VoiceMem ESP32 — Piano operativo in 10 milestone

Questa directory contiene il piano di sviluppo dettagliato del nuovo progetto standalone.

## Vincoli di progetto

- VoiceMem è il core.
- Il firmware ESP32 Xiaozhi resta stock.
- Dal server Xiaozhi si importa solo ciò che serve a protocollo, transport e comunicazione con il device.
- Nessuna compatibilità obbligatoria con i repository originali.
- Ogni incompatibilità viene risolta lato server.

## Milestone

1. [M01 — Project bootstrap](M01-project-bootstrap.md)
2. [M02 — Xiaozhi Device Gateway](M02-xiaozhi-device-gateway.md)
3. [M03 — Audio bridge](M03-audio-bridge.md)
4. [M04 — VoiceMem stream integration](M04-voicemem-stream-integration.md)
5. [M05 — ASR italiano](M05-italian-asr.md)
6. [M06 — VoiceMem italiano](M06-italian-voicemem.md)
7. [M07 — Memory lifecycle](M07-memory-lifecycle.md)
8. [M08 — Reply + TTS](M08-reply-tts.md)
9. [M09 — Barge-in + MCP/IoT](M09-bargein-mcp-iot.md)
10. [M10 — Hardening + RC](M10-hardening-release.md)

## Regola di avanzamento

Una milestone non è considerata completata finché tutti i suoi **gate di validazione** non sono superati.

È ammesso lavorare in parallelo su attività preparatorie della milestone successiva, ma non si deve integrare nel branch di release una dipendenza non validata dalla milestone precedente.
