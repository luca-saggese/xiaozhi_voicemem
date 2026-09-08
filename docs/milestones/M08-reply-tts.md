# Milestone 8 — Reply + TTS italiano completamente VoiceMem

> **Principi non negoziabili**
>
> - Il firmware ESP32 resta **stock**: nessuna modifica lato device.
> - VoiceMem è il **core del progetto** e ne vanno preservate tutte le capability.
> - Dal progetto Xiaozhi si riusano esclusivamente protocollo, transport, codec/framing e semantica device/server.
> - Il nuovo progetto è standalone: **nessun requisito di backward compatibility** con i repository originali.
> - Ogni incompatibilità con il device si risolve **lato server**.


## Obiettivo

Completare la conversazione end-to-end usando `reply_stream()` e TTS VoiceMem, con streaming audio verso ESP32.

## Deliverable

Utente parla al device stock e riceve una risposta vocale italiana generata e sintetizzata dal core VoiceMem.

## Prerequisiti

- M7 completata.
- Provider LLM configurato.
- Provider TTS italiano selezionato.

## Passi operativi

### 1. Reply path

Usare come percorso canonico:

```text
VoiceMem turn
→ memory context
→ reply_stream()
```

Niente LLM Xiaozhi.

### 2. Persona/system prompt

Configurare prompt italiano e verificare che:

- memoria sia distinguibile da istruzioni;
- history sia ordinata;
- tool context futuro sia separato.

### 3. Streaming token

Consumare `reply_stream()` senza attendere risposta completa.

### 4. Sentence chunker

Implementare chunking italiano:

- punteggiatura;
- soglia minima caratteri;
- massimo buffer;
- flush finale.

### 5. TTS VoiceMem

Usare provider TTS interno/pluggable.

Configurare:

- lingua/voice;
- sample rate;
- formato PCM;
- timeout.

### 6. Text normalization

Prima del TTS gestire:

- date;
- numeri;
- sigle;
- URL;
- unità;
- abbreviazioni;
- simboli.

### 7. Audio bridge

Percorso:

```text
TTS PCM
→ resampler se necessario
→ Opus encoder
→ device queue
```

### 8. Protocol state

Inviare:

- TTS start;
- audio;
- TTS stop;

nell'ordine atteso dal firmware.

### 9. Assistant reply memory

Assicurarsi che la risposta completa venga associata al turno e resa disponibile all'ingest.

### 10. Metriche

Misurare:

- EOU→LLM first token;
- EOU→first TTS chunk;
- EOU→first Opus;
- total reply duration;
- realtime factor TTS.

## Istruzioni di implementazione

- Non aspettare la risposta completa prima del TTS.
- Non importare TTS Xiaozhi.
- Non fare buffering audio illimitato.
- Il TTS deve essere cancellabile.

## Test obbligatori

- risposta breve;
- risposta lunga;
- numeri/date;
- nomi propri;
- inglesismi;
- TTS provider timeout;
- disconnect durante speaking;
- output sample rate diverso.

## Gate di validazione

### Gate M8-A — End-to-end

Audio ESP32 → VoiceMem → risposta audio ESP32.

### Gate M8-B — Streaming

Il first audio arriva prima che LLM abbia completato l'intera risposta.

### Gate M8-C — Italiano

Pronuncia e comprensibilità superano review umana definita.

### Gate M8-D — Protocol correctness

Il device entra/esce correttamente dallo stato TTS.

## Criteri di uscita

Conversazione vocale italiana completa e stabile.

## Diagnostica

Per alta latenza separare:

- ASR/EOU;
- retrieval;
- LLM TTFT;
- chunker;
- TTS;
- Opus queue.

Non ottimizzare “a sensazione”.
