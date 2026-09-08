# Milestone 5 — ASR italiano nativo VoiceMem

> **Principi non negoziabili**
>
> - Il firmware ESP32 resta **stock**: nessuna modifica lato device.
> - VoiceMem è il **core del progetto** e ne vanno preservate tutte le capability.
> - Dal progetto Xiaozhi si riusano esclusivamente protocollo, transport, codec/framing e semantica device/server.
> - Il nuovo progetto è standalone: **nessun requisito di backward compatibility** con i repository originali.
> - Ogni incompatibilità con il device si risolve **lato server**.


## Obiettivo

Portare l'italiano nel percorso ASR nativo usato da `VoiceStream.feed()`, con partial stabili e latenza compatibile con speculative retrieval.

## Deliverable

ASR italiano streaming robusto, integrato come backend VoiceMem, benchmarkato su audio reale ESP32.

## Prerequisiti

- M4 completata.
- Dataset italiano disponibile.
- Infrastruttura benchmark pronta.

## Passi operativi

### 1. Definire contratto ASR

Interfaccia minima:

```python
class StreamingASR:
    def reset(self): ...
    def feed(self, pcm: bytes) -> str: ...
    def flush(self) -> str: ...
```

Se VoiceMem richiede interfaccia differente, adattarla nel core in modo pulito.

### 2. Selezionare candidati

Valutare almeno due backend adatti all'italiano.

Criteri:

- accuratezza IT;
- streaming reale o simulabile bene;
- partial;
- latenza;
- footprint;
- stabilità;
- licenza;
- supporto CPU/GPU.

### 3. Dataset benchmark

Preparare casi:

- italiano standard;
- accenti regionali;
- speech veloce;
- rumore domestico;
- distanza microfono;
- nomi propri;
- date;
- numeri;
- indirizzi;
- code-switching.

### 4. Partial stabilizer

Implementare:

- longest common prefix;
- word commitment;
- deduplicazione;
- rollback limitato;
- final normalization.

### 5. Normalizzazione italiana

Gestire:

- apostrofi;
- accenti;
- numeri;
- date;
- ore;
- abbreviazioni;
- punteggiatura.

### 6. Integrazione VoiceMem

Il backend deve essere configurabile dentro VoiceMem, non davanti ad esso.

### 7. Tuning speculative retrieval

Misurare `spec_min_chars` e trigger frequency.

Ottimizzare per evitare retrieval su partial troppo instabili.

### 8. Metriche

Per utterance:

- WER;
- partial revisions;
- stable prefix ratio;
- first partial latency;
- final latency;
- EOU-to-final latency.

## Istruzioni di implementazione

- Non tradurre audio italiano in altra lingua.
- Non bypassare `VoiceStream.feed()`.
- Non scegliere un backend solo perché già presente in VoiceMem.
- La qualità italiana prevale sulla compatibilità col default upstream.

## Test obbligatori

Almeno:

- 100+ utterance curate;
- 20+ nomi propri;
- 20+ date/orari;
- 20+ frasi con inglesismi;
- test rumorosi;
- test da device reale.

## Gate di validazione

### Gate M5-A — Qualità

WER sotto la soglia concordata sul dataset interno.

### Gate M5-B — Stabilità partial

Numero di revisioni e rollback entro limiti definiti.

### Gate M5-C — Speculation efficiency

Il retrieval speculativo non viene rilanciato in modo patologico.

### Gate M5-D — Device realism

Benchmark superato su audio catturato realmente da ESP32.

## Criteri di uscita

ASR italiano scelto, integrato, configurabile e con benchmark registrato.

## Diagnostica

Se WER è buono ma VoiceMem lavora male:

- controllare partial instability;
- punctuation timing;
- EOU;
- normalizzazione;
- trigger speculation.

Se latenza è troppo alta, benchmarkare separatamente ASR e stabilizer.
