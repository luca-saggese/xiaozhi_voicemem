# Milestone 7 — Memory lifecycle, identity e `ingest_turn()`

> **Principi non negoziabili**
>
> - Il firmware ESP32 resta **stock**: nessuna modifica lato device.
> - VoiceMem è il **core del progetto** e ne vanno preservate tutte le capability.
> - Dal progetto Xiaozhi si riusano esclusivamente protocollo, transport, codec/framing e semantica device/server.
> - Il nuovo progetto è standalone: **nessun requisito di backward compatibility** con i repository originali.
> - Ogni incompatibilità con il device si risolve **lato server**.


## Obiettivo

Rendere la memoria persistente, efficiente e associata a un'identità stabile senza legarla alla singola sessione WebSocket.

## Deliverable

Memoria VoiceMem persistente fra reconnect/restart, con ingest ottimizzato del turno già processato.

## Prerequisiti

- M6 completata.
- Storage target definito.
- Schema identità deciso per v1.

## Passi operativi

### 1. Identity model

Per v1:

```text
device_id
→ hash/UUID interno
→ memory_space
```

Non usare `session_id` come identità persistente.

### 2. `MemorySpace`

Creare astrazione con:

- internal user/device key;
- language;
- storage path/id;
- metadata;
- creation/version info.

### 3. Persistenza

Garantire:

- reconnect;
- restart;
- crash recovery ragionevole;
- storage version.

### 4. `ingest_turn()`

Aggiungere API:

```python
vm.ingest_turn(turn_state)
```

Riutilizzando ciò che esiste già:

- transcript;
- PCM;
- emotion;
- speaker;
- voiceprint;
- entity;
- schema;
- embedding;
- assistant reply.

### 5. Eliminare ricalcoli

Non rieseguire:

- ASR;
- speaker inference;
- emotion;
- embedding;

se i risultati validi sono già presenti.

### 6. Ingest asincrono

Il write/consolidation non deve bloccare il first audio del turno successivo.

Implementare queue controllata e retry.

### 7. Failure semantics

Definire:

- retry count;
- dead-letter/error log;
- comportamento se storage non disponibile;
- consistenza in caso di crash.

### 8. Administration API interna

Implementare:

- list/search memories;
- delete single memory;
- reset space;
- export;
- inspect metadata.

### 9. Schema versioning

Ogni storage deve dichiarare:

- schema version;
- language;
- migration level.

### 10. Concorrenza

Testare:

- due sessioni;
- due device;
- accesso simultaneo;
- ingest + search contemporanei.

## Istruzioni di implementazione

- Non esporre direttamente MAC/device id nello storage se evitabile.
- Non bloccare il path audio su write memoria.
- Ogni retry deve essere idempotente o protetto da deduplicazione.

## Test obbligatori

- memoria dopo reconnect;
- memoria dopo restart;
- 100 turni;
- 1000 turni;
- due device simultanei;
- write failure;
- storage temporaneamente read-only;
- delete/export.

## Gate di validazione

### Gate M7-A — Persistence

La memoria sopravvive a restart.

### Gate M7-B — Identity

Sessioni diverse dello stesso device accedono allo stesso space.

### Gate M7-C — No duplicate work

`ingest_turn()` non ricalcola capability già disponibili.

### Gate M7-D — Concurrency

Nessuna corruzione con accesso concorrente.

## Criteri di uscita

Memory lifecycle stabile e amministrabile.

## Diagnostica

Per duplicati:

- controllare turn id;
- idempotency key;
- retry logic.

Per perdita memoria:

- distinguere write failure da retrieval failure.
