# Milestone 1 — Bootstrap del nuovo progetto e separazione architetturale

> **Principi non negoziabili**
>
> - Il firmware ESP32 resta **stock**: nessuna modifica lato device.
> - VoiceMem è il **core del progetto** e ne vanno preservate tutte le capability.
> - Dal progetto Xiaozhi si riusano esclusivamente protocollo, transport, codec/framing e semantica device/server.
> - Il nuovo progetto è standalone: **nessun requisito di backward compatibility** con i repository originali.
> - Ogni incompatibilità con il device si risolve **lato server**.


## Obiettivo

Creare il nuovo repository standalone, VoiceMem-first, con una struttura chiara che separi il core cognitivo dal gateway Xiaozhi/ESP32.

## Deliverable della milestone

Al termine deve esistere un server avviabile che:

- inizializza VoiceMem;
- carica configurazione e logging;
- espone una struttura modulare definitiva;
- non include ancora comunicazione reale con ESP32;
- passa test, lint e CI di base.

## Prerequisiti

- Accesso ai repository VoiceMem e xiaozhi-esp32-server.
- Python/versione runtime definita.
- Ambiente Linux di sviluppo.
- Git repository nuovo e vuoto.
- Decisione preliminare su package name e licenze da mantenere.

## Struttura target

```text
project/
├── pyproject.toml
├── README.md
├── config/
├── voicemem/
├── device/
│   └── xiaozhi/
├── runtime/
├── tests/
└── scripts/
```

## Passi operativi

### 1. Creare il nuovo repository

1. Inizializzare un repository indipendente.
2. Impostare branch principale e convenzioni di commit.
3. Aggiungere `.gitignore`, `LICENSE`, `README.md`.
4. Registrare origine e commit di VoiceMem importato.
5. Registrare origine e commit Xiaozhi usato come riferimento di protocollo.

### 2. Importare VoiceMem come base

1. Copiare i package realmente necessari.
2. Preservare:
   - `VoiceMem`;
   - `VoiceStream`;
   - Left Brain;
   - Right Brain;
   - ingest;
   - search/retrieval;
   - emotion;
   - speaker/voiceprint;
   - entity/schema;
   - embedding;
   - reply/reply_stream;
   - TTS/speak_stream;
   - mode multimodali.
3. Non modificare ancora comportamento funzionale.
4. Eliminare solo demo, asset o tool chiaramente non necessari al server finale.
5. Eseguire subito i test originali importabili.

### 3. Creare i boundary architetturali

Definire tre livelli:

```text
device/xiaozhi     = protocollo e transport
runtime            = orchestration device ↔ VoiceMem
voicemem           = AI/memory/audio cognition
```

Il package `device/xiaozhi` non deve importare moduli AI.

Il package `voicemem` non deve conoscere WebSocket, MQTT, Opus framing Xiaozhi o Device-Id.

### 4. Definire le interfacce minime

Creare almeno:

```python
class DeviceEvent: ...
class DeviceCommand: ...

class DeviceSession:
    async def run(self): ...
    async def send(self, command): ...

class AssistantSession:
    async def handle(self, event): ...
```

Non implementare ancora logica completa.

### 5. Configurazione centralizzata

Creare uno schema configurazione per:

- server;
- logging;
- VoiceMem;
- modelli;
- storage;
- device gateway;
- audio;
- lingua;
- feature flags interne di sviluppo.

Vincolo: niente configurazioni legacy replicate solo per compatibilità.

### 6. Logging e tracing

Ogni log operativo deve poter includere:

- `session_id`;
- `device_id`;
- `turn_id`;
- `speaker_id` quando disponibile;
- componente;
- durata operazione;
- errore strutturato.

### 7. Test e CI

Configurare:

- unit test;
- type checking se adottato;
- lint;
- format check;
- smoke test di startup;
- CI su push/PR.

### 8. Health check locale

Aggiungere un comando o endpoint che verifichi:

- processo attivo;
- config caricata;
- storage accessibile;
- VoiceMem inizializzato;
- dipendenze modello risolte o chiaramente segnalate.

## Istruzioni di implementazione

- Non creare shim di compatibilità per le vecchie API.
- Non copiare `ConnectionHandler` Xiaozhi.
- Non inserire logica AI in `device/xiaozhi`.
- Ogni dipendenza pesante deve essere inizializzata in modo esplicito e tracciabile.
- Evitare singleton impliciti difficili da testare.

## Test obbligatori

1. `import voicemem` funziona.
2. VoiceMem può essere inizializzato in un test.
3. Il processo server parte con configurazione valida.
4. Configurazione invalida produce errore esplicito.
5. `device/xiaozhi` non importa moduli AI.
6. CI verde.

## Gate di validazione

### Gate M1-A — Integrità VoiceMem

Passa se tutte le capability VoiceMem importate risultano presenti e i test baseline passano.

### Gate M1-B — Separazione dei moduli

Passa se non esistono dipendenze circolari fra `device`, `runtime` e `voicemem`.

### Gate M1-C — Avvio ripetibile

Passa se un nuovo ambiente può:

1. installare dipendenze;
2. caricare config;
3. avviare il server;
4. inizializzare VoiceMem.

## Criteri di uscita

La milestone è completa solo se:

- repository standalone creato;
- baseline VoiceMem verde;
- struttura definitiva approvata;
- logging e config funzionanti;
- CI verde;
- nessun codice protocollo ESP32 ancora accoppiato al core.

## Diagnostica / fallback

Se i test VoiceMem falliscono dopo l'import:

1. confrontare con commit sorgente;
2. ripristinare il comportamento originale;
3. rinviare refactoring non essenziali;
4. non procedere alla milestone 2 finché la baseline non è stabile.
