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

## Stato di implementazione

La parte server-side della milestone e implementata nel package `device/xiaozhi`:

- endpoint WebSocket stock-compatible su `/xiaozhi/v1/` con validazione degli headers;
- parser e serializer tipizzati per hello, listen, abort, MCP, IoT, keepalive ed errori;
- negoziazione hello con `session_id` e parametri audio server-side;
- state machine di sessione, timeout hello/idle e cleanup completo;
- ricezione dei frame audio binari come bytes raw, senza decodifica o pipeline AI;
- eventi e comandi interni separati dalla logica applicativa;
- policy di sostituzione della connessione precedente per lo stesso device;
- bootstrap OTA su `/xiaozhi/ota/`: il `POST` firmware-compatible è servito da un
	listener HTTP separato (`ota_port`, porta effimera se non configurata), mentre
	il `GET` sul listener WebSocket è mantenuto per compatibilità diagnostica;
- fixture di protocollo e test WebSocket reali, inclusi reconnect, timeout e chiusure durante listen.

La suite automatica e Ruff passano. Il type-check ristretto ai moduli M02 non segnala errori nei file del gateway; il type-check globale continua a riportare errori preesistenti nell’area `voicemem`, fuori dall’ambito di questa milestone.

Validazione finale: 128 test passati. La coverage non è disponibile perché
`pytest-cov` non è installato nell’ambiente corrente.

Il bootstrap usa `ota_port=0` come default dinamico: il listener HTTP sceglie una
porta effimera quando non viene configurata esplicitamente e la porta effettiva è
esposta da `server.ota_port`.

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

**PENDING HARDWARE.** Un ESP32 non modificato deve ancora completare connessione e hello in una prova con hardware reale. I test automatici coprono lo stesso contratto tramite client WebSocket e fixture.

### Gate M2-B — Protocol fidelity

**PASS SOFTWARE.** Parser, serializer, headers, sequenza hello, timeout, keepalive,
errori, framing binario e bootstrap OTA sono coperti da fixture e test di
integrazione WebSocket. Il `POST /xiaozhi/ota/` è verificato sul listener HTTP
separato e restituisce URL WebSocket e `server_time.timestamp` in millisecondi.
La conferma finale con messaggi osservati dal firmware resta parte di M2-A.

### Gate M2-C — Nessuna logica AI nel gateway

**PASS.** Il package `device/xiaozhi` non importa `voicemem` o moduli AI; i test runtime e il controllo AST verificano il boundary. Il gateway emette eventi astratti e non implementa ASR, VAD, LLM, memory o TTS.

## Criteri di uscita

- handshake reale con ESP32 stock riuscito (pendente prova hardware);
- state machine testata;
- reconnect stabile;
- eventi/command interni definiti;
- bootstrap OTA operativo; in deployment il device deve raggiungere la porta
	`ota_port` oltre alla porta WebSocket `port` (oppure usare un reverse proxy
	che esponga il percorso HTTP previsto).

## Diagnostica

Se il device si disconnette:

1. catturare payload raw;
2. confrontare ordine dei messaggi;
3. verificare protocol version e audio params;
4. verificare `session_id`;
5. verificare timing/timeout;
6. non modificare firmware per aggirare il problema.
