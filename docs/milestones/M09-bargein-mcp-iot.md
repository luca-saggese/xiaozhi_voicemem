# Milestone 9 — Interruption, barge-in, MCP e IoT

> **Principi non negoziabili**
>
> - Il firmware ESP32 resta **stock**: nessuna modifica lato device.
> - VoiceMem è il **core del progetto** e ne vanno preservate tutte le capability.
> - Dal progetto Xiaozhi si riusano esclusivamente protocollo, transport, codec/framing e semantica device/server.
> - Il nuovo progetto è standalone: **nessun requisito di backward compatibility** con i repository originali.
> - Ogni incompatibilità con il device si risolve **lato server**.


## Obiettivo

Completare l'interazione richiesta dal device stock: interruption affidabile e bridge dei protocolli MCP/IoT senza importare il runtime AI Xiaozhi.

## Deliverable

- Abort e barge-in funzionanti.
- MCP/IoT negoziati e gestiti.
- Tool layer indipendente da Xiaozhi.

## Prerequisiti

- M8 completata.
- Protocollo MCP/IoT già parsato in M2.

## Parte A — Abort e barge-in

### 1. Cancellation model

Creare un token/task group per turno.

Task cancellabili:

- reply generation;
- sentence chunking;
- TTS;
- resampling;
- Opus encoding;
- outgoing queue.

### 2. Gestire `abort`

Quando arriva `AbortRequested`:

1. marcare turno cancellato;
2. cancellare LLM;
3. cancellare TTS;
4. flush queue;
5. inviare stato protocollo corretto;
6. lasciare sessione pronta al turno successivo.

### 3. Barge-in

Quando arriva nuovo speech/listen durante speaking:

- interrompere output;
- non perdere nuovo input;
- aprire nuovo turno VoiceMem.

### 4. Race conditions

Testare abort:

- prima del first token;
- durante LLM;
- durante TTS;
- all'ultimo audio frame;
- subito dopo TTS stop.

## Parte B — MCP

### 5. Capability negotiation

Registrare capability device e sessione.

### 6. Tool registry nuovo

Creare un registry indipendente:

```python
ToolRegistry
ToolInvocation
ToolResult
```

### 7. Adapter MCP

Tradurre:

```text
protocol MCP message
↔ internal tool request/result
```

### 8. Error handling

Gestire:

- tool missing;
- invalid arguments;
- timeout;
- exception;
- disconnect.

## Parte C — IoT

### 9. Device capability model

Registrare:

- componenti;
- proprietà;
- azioni;
- stato.

### 10. Command bridge

Tradurre richieste VoiceMem/tool layer verso messaggi IoT Xiaozhi.

### 11. State updates

Aggiornare stato runtime quando il device notifica cambiamenti.

## Istruzioni di implementazione

- Riutilizzare solo il protocollo Xiaozhi.
- Non importare intent/plugin runtime Xiaozhi.
- Un tool non deve poter bloccare indefinitamente il turn loop.
- Abort deve avere priorità sulle altre operazioni.

## Test obbligatori

Abort:

- 50+ interruzioni casuali;
- nessun audio residuo;
- turno successivo valido.

MCP:

- call valida;
- tool inesistente;
- timeout;
- result.

IoT:

- capability;
- state;
- command;
- failure.

## Gate di validazione

### Gate M9-A — Hard abort

Nessun audio del turno cancellato viene riprodotto oltre la soglia accettata.

### Gate M9-B — Next-turn integrity

Dopo abort il turno successivo funziona normalmente.

### Gate M9-C — MCP interoperability

Device stock completa scambio MCP previsto.

### Gate M9-D — IoT interoperability

Stato e comandi device funzionano senza codice AI Xiaozhi.

## Criteri di uscita

Interazione naturale e protocolli device avanzati operativi.

## Diagnostica

Per audio residuo cercare task non cancellati o queue non flushate.

Per race usare correlation/turn id in ogni task e comando.
