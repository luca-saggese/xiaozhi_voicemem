# Milestone 2 — Xiaozhi Device Compatibility Gateway

> **Principi non negoziabili**
>
> - Il firmware ESP32 resta **stock**: nessuna modifica lato device.
> - VoiceMem è il **core del progetto** e ne vanno preservate tutte le capability.
> - Dal progetto Xiaozhi si riusano esclusivamente protocollo, transport, codec/framing e semantica device/server.
> - Il nuovo progetto è standalone: **nessun requisito di backward compatibility** con i repository originali.
> - Ogni incompatibilità con il device si risolve **lato server**.


## Obiettivo

Implementare lato server il contratto richiesto da un ESP32 Xiaozhi stock, senza introdurre alcuna logica AI.

## Deliverable della milestone

Un device con firmware stock deve:

- collegarsi al nuovo server;
- completare handshake;
- mantenere una sessione;
- inviare/ricevere messaggi di protocollo;
- riconnettersi;
- gestire abort/listen;
- senza accedere ancora a VoiceMem.

## Prerequisiti

- Milestone 1 completata.
- Firmware/device target identificato.
- Tracce o documentazione del protocollo disponibili.
- Possibilità di catturare log lato server e device.

## Passi operativi

### 1. Inventario completo del protocollo

Documentare:

- endpoint WebSocket;
- eventuale bootstrap/OTA;
- headers obbligatori/opzionali;
- `Device-Id`;
- `Client-Id`;
- authorization;
- protocol version;
- formato `hello`;
- `session_id`;
- capability advertisement;
- messaggi `listen`;
- `abort`;
- `stt`;
- `tts`;
- `iot`;
- `mcp`;
- audio binary frames;
- error semantics;
- keepalive/reconnect.

Produrre una tabella `message → direction → required fields → response`.

### 2. Implementare il WebSocket server

Creare:

```text
device/xiaozhi/server.py
device/xiaozhi/connection.py
device/xiaozhi/protocol.py
device/xiaozhi/messages.py
```

Responsabilità:

- accettare connessioni;
- validare headers;
- creare `DeviceSession`;
- leggere frame text/binary;
- smistare al parser.

### 3. Handshake `hello`

Implementare:

- parsing richiesta;
- protocol version;
- capability;
- audio parameters;
- generazione risposta compatibile;
- assegnazione `session_id`;
- errori deterministici per hello invalido.

### 4. State machine

Definire stati espliciti, per esempio:

```text
CONNECTED
HELLO_DONE
IDLE
LISTENING
SPEAKING
ABORTING
CLOSED
```

Definire transizioni consentite.

### 5. Event model interno

Tradurre protocollo in eventi interni:

```python
DeviceConnected
DeviceDisconnected
ListenStarted
ListenStopped
AbortRequested
IoTMessage
MCPMessage
AudioFrameReceived
```

Il runtime dovrà ricevere solo questi eventi.

### 6. Command model

Definire comandi:

```python
SendHello
SendTranscript
SendTTSStart
SendTTSStop
SendAudioFrame
SendIoT
SendMCP
SendError
```

### 7. Reconnect e cleanup

Implementare:

- chiusura socket;
- cleanup task;
- timeout;
- riconnessione senza leakage;
- invalidazione sessione precedente.

### 8. Bootstrap/OTA

Se il firmware target usa un endpoint bootstrap/OTA per ottenere URL server o configurazione:

1. implementare il minimo indispensabile;
2. replicare risposta attesa;
3. non introdurre logica di aggiornamento firmware non necessaria.

## Istruzioni di implementazione

- Non riusare `ConnectionHandler` Xiaozhi.
- Copiare solo semantica e parti di protocollo strettamente necessarie.
- Ogni parser deve avere test con payload reali.
- Conservare fixture di messaggi registrati da device reali.
- Il gateway non deve conoscere ASR, VAD, LLM, memory o TTS.

## Test obbligatori

1. Connessione con headers validi.
2. Rifiuto headers invalidi.
3. `hello` valido.
4. `hello` invalido.
5. `listen` parse.
6. `abort` parse.
7. `iot` parse.
8. `mcp` parse.
9. reconnect ripetuto.
10. socket close durante uno stato attivo.

## Gate di validazione

### Gate M2-A — Device stock connect

Un ESP32 non modificato completa connessione e hello.

### Gate M2-B — Protocol fidelity

Messaggi server osservati devono rispettare schema e sequenza attesa dal firmware.

### Gate M2-C — Nessuna logica AI nel gateway

Code review obbligatoria: nessun import da moduli ASR/LLM/memory/TTS.

## Criteri di uscita

- handshake reale con ESP32 stock riuscito;
- state machine testata;
- reconnect stabile;
- eventi/command interni definiti;
- eventuale bootstrap necessario operativo.

## Diagnostica

Se il device si disconnette:

1. catturare payload raw;
2. confrontare ordine dei messaggi;
3. verificare protocol version e audio params;
4. verificare `session_id`;
5. verificare timing/timeout;
6. non modificare firmware per aggirare il problema.
