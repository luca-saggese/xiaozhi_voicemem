# Milestone 4 — Integrazione VoiceMem streaming nativa

> **Principi non negoziabili**
>
> - Il firmware ESP32 resta **stock**: nessuna modifica lato device.
> - VoiceMem è il **core del progetto** e ne vanno preservate tutte le capability.
> - Dal progetto Xiaozhi si riusano esclusivamente protocollo, transport, codec/framing e semantica device/server.
> - Il nuovo progetto è standalone: **nessun requisito di backward compatibility** con i repository originali.
> - Ogni incompatibilità con il device si risolve **lato server**.


## Obiettivo

Collegare il PCM reale dell'ESP32 direttamente a `VoiceStream.feed()` preservando tutte le capability percettive VoiceMem.

## Deliverable

Parlato da ESP32 stock produce un `turn_over` VoiceMem affidabile, con PCM del turno e proprietà percettive disponibili.

## Prerequisiti

- M3 completata.
- VoiceMem baseline stabile.
- Audio PCM validato.

## Passi operativi

### 1. Creare `AssistantSession`

Responsabilità:

- possedere riferimento `DeviceSession`;
- creare/gestire `VoiceStream`;
- assegnare `turn_id`;
- ricevere eventi device;
- non duplicare capability VoiceMem.

### 2. Collegare audio

Percorso canonico:

```text
AudioFrameReceived
→ decode Opus
→ PCM16
→ VoiceStream.feed(pcm)
```

Non usare ASR Xiaozhi.

Non usare `feed_partial()` come default.

### 3. Lifecycle VoiceStream

Definire:

- creazione stream;
- reset;
- nuovo turno;
- cleanup;
- disconnect;
- abort;
- errore ASR/VAD.

### 4. Turn context

Creare struttura server-side:

```python
TurnContext(
    session_id,
    turn_id,
    device_id,
    started_at,
    ended_at,
    stream_state
)
```

### 5. Conservazione PCM

Verificare che il PCM del turno rimanga disponibile per:

- emotion;
- speaker;
- voiceprint;
- eventuale ingest ottimizzato.

### 6. Stato del turno

Gestire almeno:

- silence;
- speech active;
- partial transcript;
- turn over;
- cancelled;
- failed.

### 7. Input durante output

Definire comportamento quando arriva audio mentre il sistema parla:

- non scartare implicitamente;
- preparare supporto barge-in;
- per ora loggare/rilevare correttamente.

### 8. Osservabilità

Per turno loggare:

- start speech;
- partial count;
- EOU;
- duration;
- PCM duration;
- VoiceMem state;
- speculative task state.

## Istruzioni di implementazione

- VoiceMem decide VAD/EOU.
- Non duplicare VAD nel gateway.
- Non ricalcolare proprietà già prodotte dal core.
- Errori di uno stream non devono abbattere il server.

## Test obbligatori

1. Silenzio.
2. Una frase.
3. Due frasi separate.
4. Parlato lungo.
5. Pausa breve interna.
6. Noise-only.
7. reconnect.
8. abort.
9. audio mentre stato server è speaking.

## Gate di validazione

### Gate M4-A — Native feed

Il percorso reale usa `VoiceStream.feed()`.

### Gate M4-B — Turn correctness

EOU corrisponde ragionevolmente ai turni reali.

### Gate M4-C — Perceptual integrity

PCM e proprietà lazy rimangono disponibili dopo il turno.

## Criteri di uscita

ESP32 stock → VoiceMem `turn_over` senza bypassare il core audio.

## Diagnostica

Se EOU è errato:

- verificare frame PCM;
- VAD threshold/config;
- silence window;
- pacing input;
- non aggiungere VAD esterno come scorciatoia.
