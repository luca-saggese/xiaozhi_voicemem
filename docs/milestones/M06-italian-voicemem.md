# Milestone 6 — VoiceMem italiano completo: Left Brain + Right Brain

> **Principi non negoziabili**
>
> - Il firmware ESP32 resta **stock**: nessuna modifica lato device.
> - VoiceMem è il **core del progetto** e ne vanno preservate tutte le capability.
> - Dal progetto Xiaozhi si riusano esclusivamente protocollo, transport, codec/framing e semantica device/server.
> - Il nuovo progetto è standalone: **nessun requisito di backward compatibility** con i repository originali.
> - Ogni incompatibilità con il device si risolve **lato server**.


## Obiettivo

Rendere `it` una lingua di prima classe in tutta la pipeline di memoria VoiceMem, non solo nell'ASR.

## Deliverable

Input, memoria, retrieval, Left Brain, Right Brain, emotion/personality e prompt operano nativamente in italiano.

## Prerequisiti

- M5 completata.
- Suite di test testuale italiana predisposta.

## Passi operativi

### 1. Refactoring lingua

Sostituire logiche binarie `en/zh` con:

```python
LanguagePack
```

Contenente:

- code;
- display name;
- emotion labels;
- prompt fragments;
- lexical cues;
- normalization rules.

### 2. Aggiungere `it`

Configurare:

- `memory_language = "it"`;
- label italiane;
- prompt italiani;
- fallback coerenti.

### 3. Left Brain

Verificare/adattare:

- fact extraction;
- entities;
- slot/schema;
- preference extraction;
- relationships;
- temporal facts;
- negation;
- correction;
- contradictions.

### 4. Right Brain

Adattare:

- affect interpretation;
- trait inference;
- relationship cues;
- heartnotes;
- satisfaction/dissatisfaction;
- correction signals;
- affirmation;
- uncertainty.

### 5. Emotion localization

Mantenere ID canonici interni.

Separare:

```text
canonical emotion ID
≠
label localizzata
```

### 6. Cue italiani

Aggiungere casi per:

- “non intendevo”;
- “in realtà”;
- “te l’ho già detto”;
- “preferisco”;
- “non mi piace”;
- “esatto”;
- “perfetto”;
- “sono preoccupato”;
- “sono stanco”.

### 7. Memoria monolingua

Vincolo:

```text
italiano → memoria italiana → retrieval italiano → prompt italiano
```

Niente IT→EN→IT.

### 8. Temporalità e contraddizioni

Testare aggiornamenti:

```text
"Prima X, ora Y"
"Non X, intendevo Y"
"Una volta preferivo X"
```

### 9. Retrieval

Valutare:

- precision@k;
- recall@k;
- false memory;
- stale preference retrieval;
- conflicting facts.

### 10. Regression suite

Creare casi unitari e conversazionali.

## Istruzioni di implementazione

- Non fare traduzioni letterali cieche dei prompt.
- Conservare le semantiche interne VoiceMem.
- Gli ID canonici non vanno localizzati.
- Ogni nuova regola linguistica deve avere test.

## Test obbligatori

Categorie:

- persone;
- relazioni;
- preferenze;
- correzioni;
- temporalità;
- negazioni;
- emozioni;
- insoddisfazione;
- conferma;
- fatti multi-turno.

## Gate di validazione

### Gate M6-A — Storage italiano

Le memorie generate restano in italiano.

### Gate M6-B — Correzioni

Un fatto corretto non rimane dominante come se fosse ancora valido.

### Gate M6-C — Right Brain

Emotion/trait/relationship test italiani raggiungono soglie definite.

### Gate M6-D — Retrieval

Recall/precision raggiungono baseline accettata.

## Criteri di uscita

VoiceMem è semanticamente italiano end-to-end.

## Diagnostica

In caso di memoria incoerente isolare:

1. extraction;
2. normalization;
3. storage;
4. retrieval;
5. prompt assembly.

Non correggere retrieval se il dato è già errato in ingest.
