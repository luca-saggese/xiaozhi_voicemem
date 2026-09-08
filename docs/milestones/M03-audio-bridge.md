# Milestone 3 — Audio bridge ESP32 ↔ PCM VoiceMem

> **Principi non negoziabili**
>
> - Il firmware ESP32 resta **stock**: nessuna modifica lato device.
> - VoiceMem è il **core del progetto** e ne vanno preservate tutte le capability.
> - Dal progetto Xiaozhi si riusano esclusivamente protocollo, transport, codec/framing e semantica device/server.
> - Il nuovo progetto è standalone: **nessun requisito di backward compatibility** con i repository originali.
> - Ogni incompatibilità con il device si risolve **lato server**.


## Obiettivo

Implementare un percorso audio bidirezionale stabile tra protocollo Xiaozhi e PCM utilizzabile dal core VoiceMem.

## Deliverable

- Opus dal device → PCM16 mono.
- PCM server → Opus compatibile device.
- Queue, rate control, resampling e cancellation affidabili.
- Nessuna AI coinvolta.

## Prerequisiti

- M2 completata.
- Parametri audio negoziati disponibili.
- Codec Opus scelto e testabile.

## Passi operativi

### 1. Formalizzare il contratto audio

Registrare per sessione:

- codec;
- input sample rate;
- output sample rate;
- channel count;
- frame duration;
- bytes/sample;
- eventuale timestamp/framing version.

### 2. Parser frame binari

Implementare `framing.py`:

- validazione lunghezza;
- estrazione timestamp se previsto;
- gestione protocol version;
- errori su frame malformati.

### 3. Decoder Opus

Implementare `opus_decoder.py`:

- inizializzazione per sessione;
- decoder mono;
- output PCM16;
- gestione decoder error;
- reset al reconnect.

### 4. Input normalizer

Garantire formato VoiceMem:

```text
PCM signed 16-bit
mono
little-endian
sample rate definito
```

Se necessario applicare resampling lato server.

### 5. Buffering input

Creare buffer con:

- limite massimo;
- backpressure;
- metriche depth;
- drop policy esplicita solo in condizioni critiche.

### 6. Encoder Opus output

Implementare:

- PCM chunking;
- sample rate corretto;
- encoder Opus;
- frame duration conforme al device;
- timestamp/framing richiesto dal protocollo.

### 7. Resampling output

Se TTS produce rate diverso:

```text
TTS PCM → resampler → Opus encoder
```

Il device non deve essere modificato.

### 8. Outgoing queue

Implementare:

- queue ordinata;
- rate control real-time;
- flush;
- stop;
- cancel immediato.

### 9. Loopback harness

Creare tool di test che:

1. legge PCM/WAV;
2. encoda come device;
3. passa nel parser/decoder;
4. riconfronta PCM;
5. effettua percorso inverso.

### 10. Metriche

Registrare:

- frame received;
- frame dropped;
- decode errors;
- encode errors;
- queue depth;
- resample time;
- output pacing lag.

## Istruzioni di implementazione

- Non fare DSP non richiesto.
- Non cambiare sample rate del firmware.
- Ogni conversione deve essere server-side.
- Evitare buffer non limitati.
- Le queue devono essere cancellabili atomicamente.

## Test obbligatori

- 1 minuto audio continuo.
- 30 minuti audio continuo.
- frame corrotti.
- disconnect durante audio.
- reconnect e nuovo decoder.
- output TTS simulato.
- abort durante playback.
- test no drift fra clock input/output.

## Gate di validazione

### Gate M3-A — Input fidelity

Il PCM decodificato è intelligibile e con parametri corretti.

### Gate M3-B — Output fidelity

Il device riproduce PCM test senza pitch/speed errati.

### Gate M3-C — Realtime stability

30 minuti senza crescita incontrollata della queue o drift.

### Gate M3-D — Abort audio

L'audio pendente viene eliminato entro il limite stabilito dal progetto.

## Criteri di uscita

Audio bidirezionale stabile, misurato e indipendente da VoiceMem.

## Diagnostica

Per audio accelerato/lento verificare prima:

- sample rate;
- frame duration;
- numero sample per frame;
- resampler;
- pacing.

Per glitch:

- queue starvation;
- frame size;
- timestamp;
- CPU saturation.
