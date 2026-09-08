# Xiaozhi Protocol Audit — Specifica verificata del protocollo ESP32 stock

> **Regola delle fonti**: per ogni comportamento, l'ordine di autorità è:
> 1. Codice firmware `_upstream/xiaozhi-esp32` (sorgente di verità)
> 2. Codice server `_upstream/xiaozhi-esp32-server` (implementazione di riferimento)
> 3. Documentazione contenuta nei due repository
>
> Se firmware e server divergono, la divergenza è documentata. Il firmware stock è il requisito.

Data audit: 2026-09-08
Firmware SHA: `c7241272f2d5fd140c77542f3cf12d09e717fc2f` (v2.4.2-23-gc724127)
Server SHA: `5aa46538d5087aaee99a5fc318689a0da0a2a9c7` (v0.9.6-80-g5aa46538)

---

## 1. Transport

### 1.1 WebSocket

| Dettaglio | Valore | Fonte |
|---|---|---|
| Endpoint | `ws://{host}:{port}/xiaozhi/v1/` | Server: `websocket_server.py` |
| Libreria firmware | `esp_websocket_client` (ESP-IDF) | Firmware: `websocket_protocol.cc:14` |
| Libreria server | `websockets` (Python) | Server: `websocket_server.py:1` |
| Binary frames | Opus audio raw (v1) o con header (v2/v3) | Firmware: `protocol.h:17-31` |
| Text frames | JSON messages | Firmware: `websocket_protocol.cc` |
| Ping/keepalive | Firmware: `esp_websocket_client` ping built-in; Server: opzionale `{"type":"ping"}` → `{"type":"pong","timestamp":"..."}` | Server: `pingMessageHandler.py:17-38` |

**Headers WebSocket** (firmware `websocket_protocol.cc:107-110`):
```
Authorization: Bearer <token>
Protocol-Version: <version>
Device-Id: <MAC address>
Client-Id: <UUID>
```

**Fallback server**: se `device-id` manca dagli headers, prova query params URL (`websocket_server.py:93`).

### 1.2 MQTT + UDP (hybrid)

| Dettaglio | Valore | Fonte |
|---|---|---|
| MQTT libreria firmware | `esp_mqtt_client` (ESP-IDF) | `mqtt_protocol.cc` |
| Keepalive MQTT | 240s default | `mqtt_protocol.cc:83` |
| Reconnect MQTT | Timer 60s (`MQTT_RECONNECT_INTERVAL_MS`) | `mqtt_protocol.cc` |
| Ping MQTT | Ogni 90s (`MQTT_PING_INTERVAL_SECONDS`) | `mqtt_protocol.cc` |
| UDP audio | AES-CTR encrypted Opus | `mqtt_protocol.cc` |
| Topic publish | Da settings `publish_topic` | `mqtt_protocol.cc` |
| Topic subscribe | Configurato dal server OTA | `mqtt_protocol.cc` |

**Nota**: Il server originale non implementa direttamente MQTT+UDP; genera solo la configurazione MQTT per il firmware tramite l'endpoint OTA (`ota_handler.py`). La gestione UDP audio è solo lato firmware.

### 1.3 Scelta del transport

Il firmware sceglie WebSocket o MQTT in base alla configurazione ricevuta via OTA/bootstrap. Se il server OTA restituisce configurazione MQTT, il firmware usa MQTT+UDP; altrimenti WebSocket.

---

## 2. Connection

### 2.1 Headers richiesti

| Header | Obbligatorio | Valore | Fonte firmware |
|---|---|---|---|
| `Authorization` | **sì** | `Bearer <token>` | `websocket_protocol.cc:107` |
| `Protocol-Version` | **sì** | Numero intero (es. `1`) | `websocket_protocol.cc:108` |
| `Device-Id` | **sì** | MAC address | `websocket_protocol.cc:109` |
| `Client-Id` | **sì** | UUID (software-generated) | `websocket_protocol.cc:110` |

**Comportamento se mancanti**:
- Server: se `device-id` manca, prova query params URL. Se anche lì manca, invia messaggio di errore e chiude (`websocket_server.py:93-100`).
- Firmware: non gestisce esplicitamente risposte con headers mancanti (è il client).

### 2.2 Protocol versions

Il firmware supporta versioni multiple del protocollo binario, selezionate dal campo `version` nelle impostazioni:

- **Version 1** (default): Raw Opus frames, nessun metadata aggiuntivo.
- **Version 2**: Header strutturato `BinaryProtocol2` (`protocol.h:17-24`):
  ```
  | version (uint16) | type (uint16) | reserved (uint32) | timestamp (uint32) | payload_size (uint32) | payload |
  ```
  - `type`: 0 = OPUS, 1 = JSON
  - Tutti i campi in network byte order
- **Version 3**: Header compatto `BinaryProtocol3` (`protocol.h:26-31`):
  ```
  | type (uint8) | reserved (uint8) | payload_size (uint16) | payload |
  ```

---

## 3. Hello

### 3.1 Device → Server

| Campo | Tipo | Obbligatorio | Valori ammessi | Fonte firmware |
|---|---|---|---|---|
| `type` | string | **sì** | `"hello"` | `websocket_protocol.cc:200` |
| `version` | int | **sì** | `1` (WS), `3` (MQTT) | `websocket_protocol.cc:201` |
| `transport` | string | **sì** | `"websocket"`, `"udp"` | `websocket_protocol.cc:210` |
| `features.mcp` | bool | **sì** | `true` | `websocket_protocol.cc:205` |
| `features.aec` | bool | no | `true` (se `CONFIG_USE_SERVER_AEC`) | `websocket_protocol.cc:203-204` |
| `features.glyph_push` | bool | no | `true` | `protocol.cc:17` |
| `text_font` | object | no | `{bundle, charset, size, bpp}` | `protocol.cc:20-27` |
| `audio_params.format` | string | **sì** | `"opus"` | `websocket_protocol.cc:212` |
| `audio_params.sample_rate` | int | **sì** | `16000` | `websocket_protocol.cc:213` |
| `audio_params.channels` | int | **sì** | `1` | `websocket_protocol.cc:214` |
| `audio_params.frame_duration` | int | **sì** | `60` | `websocket_protocol.cc:215` |

**Esempio** (firmware `websocket_protocol.cc:196-217`):
```json
{
  "type": "hello",
  "version": 1,
  "features": {
    "mcp": true,
    "aec": true,
    "glyph_push": true
  },
  "text_font": {
    "bundle": "noto-v1",
    "charset": "common",
    "size": 20,
    "bpp": 4
  },
  "transport": "websocket",
  "audio_params": {
    "format": "opus",
    "sample_rate": 16000,
    "channels": 1,
    "frame_duration": 60
  }
}
```

### 3.2 Server → Device

| Campo | Tipo | Obbligatorio | Valori ammessi | Fonte |
|---|---|---|---|---|
| `type` | string | **sì** | `"hello"` | Firmware: `websocket_protocol.cc:226` |
| `transport` | string | **sì** | `"websocket"`, `"udp"` | Firmware: `websocket_protocol.cc:228` |
| `session_id` | string | no | UUID string | Firmware: `websocket_protocol.cc:233` |
| `audio_params.format` | string | no | `"opus"` | Firmware: `websocket_protocol.cc:239` |
| `audio_params.sample_rate` | int | no | `24000` (default firmware) | Firmware: `websocket_protocol.cc:241-243` |
| `audio_params.frame_duration` | int | no | `60` | Firmware: `websocket_protocol.cc:244-246` |
| `udp` (solo MQTT) | object | **sì** (MQTT) | `{server, port, key, nonce}` | `mqtt_protocol.cc:380+` |

**Esempio** (atteso dal firmware `websocket_protocol.cc:226-249`):
```json
{
  "type": "hello",
  "transport": "websocket",
  "session_id": "xxx",
  "audio_params": {
    "format": "opus",
    "sample_rate": 24000,
    "channels": 1,
    "frame_duration": 60
  }
}
```

**Divergenza firmware/server**: Il server (`connection.py:146-147`) non include `transport` nel welcome message. Il firmware valuta `transport == "websocket"` — se manca, logga errore ma non blocca la connessione.

### 3.3 Timeout hello

- Firmware: 10 secondi (`pdMS_TO_TICKS(10000)`) in `websocket_protocol.cc:175`
- Server: `close_connection_no_voice_time` (default 120s) + 60s extra in `connection.py:118-119`

---

## 4. Audio

### 4.1 Codec

| Parametro | Valore | Fonte |
|---|---|---|
| Codec | Opus | Firmware: `websocket_protocol.cc:212` |
| Sample rate device → server | 16000 Hz | Firmware: `websocket_protocol.cc:213` |
| Sample rate server → device | 24000 Hz (default firmware) | Firmware: `protocol.h:server_sample_rate_` |
| Canali | 1 (mono) | Firmware: `websocket_protocol.cc:214` |
| Frame duration | 60 ms | Firmware: `websocket_protocol.cc:215` |
| Frame size (device → server) | 960 samples (16000 × 0.06) | Calcolato |
| Frame size (server → device) | 1440 samples (24000 × 0.06) | Calcolato |
| Opus bitrate server | 24000 bps | Server: `opus_encoder_utils.py:30` |
| DTX firmware | `true` | Firmware: `audio_service.h` |
| VBR firmware | `true` | Firmware: `audio_service.h` |
| Complessità firmware | 0 | Firmware: `audio_service.h` |
| Complessità server | 10 | Server: `opus_encoder_utils.py:31` |

### 4.2 Binary layout

**Version 1** (default): Opus frame raw, WebSocket binary frame.

**Version 2** (`protocol.h:17-24`):
```
| version (uint16) | type (uint16) | reserved (uint32) | timestamp (uint32) | payload_size (uint32) | payload (bytes) |
```
- `type`: 0 = OPUS, 1 = JSON
- Network byte order

**Version 3** (`protocol.h:26-31`):
```
| type (uint8) | reserved (uint8) | payload_size (uint16) | payload (bytes) |
```

---

## 5. Listen

### 5.1 Device → Server

| Campo | Tipo | Obbligatorio | Valori ammessi | Fonte |
|---|---|---|---|---|
| `session_id` | string | **sì** | UUID | `protocol.cc:52-70` |
| `type` | string | **sì** | `"listen"` | `protocol.cc:52-70` |
| `state` | string | **sì** | `"start"`, `"stop"`, `"detect"` | `protocol.cc:52-70` |
| `mode` | string | no | `"auto"`, `"manual"`, `"realtime"` | `protocol.cc:52-70` |
| `text` | string | no (solo `state=detect`) | Testo del wake word | `protocol.cc:68` |

**Esempi** (firmware `protocol.cc:52-70`):

Start listening (manual):
```json
{"session_id":"xxx","type":"listen","state":"start","mode":"manual"}
```

Start listening (auto-stop):
```json
{"session_id":"xxx","type":"listen","state":"start","mode":"auto"}
```

Start listening (realtime, richiede AEC):
```json
{"session_id":"xxx","type":"listen","state":"start","mode":"realtime"}
```

Stop listening:
```json
{"session_id":"xxx","type":"listen","state":"stop"}
```

Wake word detected:
```json
{"session_id":"xxx","type":"listen","state":"detect","text":"<wake_word>"}
```

### 5.2 Server handling

Il server (`listenMessageHandler.py:17-72`):
- `state == "start"`: resetta stati audio, prepara ASR
- `state == "stop"`: finalizza ASR, avvia elaborazione
- `state == "detect"`: wake word rilevato, avvia chat con testo

---

## 6. Abort

### 6.1 Device → Server

| Campo | Tipo | Obbligatorio | Valori ammessi | Fonte |
|---|---|---|---|---|
| `session_id` | string | **sì** | UUID | `protocol.cc:42-49` |
| `type` | string | **sì** | `"abort"` | `protocol.cc:42-49` |
| `reason` | string | no | `"wake_word_detected"` | `protocol.cc:44` |

**Esempio** (firmware `protocol.cc:42-49`):
```json
{"session_id":"xxx","type":"abort"}
```
Con reason:
```json
{"session_id":"xxx","type":"abort","reason":"wake_word_detected"}
```

### 6.2 Server handling

Il server (`abortHandle.py:8-17`):
- Setta `conn.client_abort = True`
- Svuota code audio
- Invia `{"type":"tts","state":"stop"}` al device

---

## 7. STT/TTS States

### 7.1 Server → Device: `type: "stt"`

| Campo | Tipo | Obbligatorio | Valori ammessi |
|---|---|---|---|
| `session_id` | string | **sì** | UUID |
| `type` | string | **sì** | `"stt"` |
| `text` | string | **sì** | Testo trascritto |

### 7.2 Server → Device: `type: "tts"`

| Campo | Tipo | Obbligatorio | Valori ammessi |
|---|---|---|---|
| `session_id` | string | **sì** | UUID |
| `type` | string | **sì** | `"tts"` |
| `state` | string | **sì** | `"start"`, `"stop"`, `"sentence_start"` |
| `text` | string | no (solo `sentence_start`) | Testo della frase |

### 7.3 Server → Device: `type: "llm"`

| Campo | Tipo | Obbligatorio | Valori ammessi |
|---|---|---|---|
| `session_id` | string | **sì** | UUID |
| `type` | string | **sì** | `"llm"` |
| `emotion` | string | no | Emotion label |
| `text` | string | no | Testo |

---

## 8. MCP (Model Context Protocol)

### 8.1 Feature negotiation

MCP è annunciato dal device via `features.mcp: true` nel messaggio `hello`.

### 8.2 Message envelope

```json
{
  "session_id": "...",
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "method": "...",
    "params": { ... },
    "id": ...
  }
}
```

### 8.3 Metodi JSON-RPC

| Metodo | Direction | Descrizione |
|---|---|---|
| `initialize` | server → device | Inizializza sessione MCP |
| `tools/list` | server → device | Elenca tool disponibili |
| `tools/call` | server → device | Chiama un tool |
| `notifications/*` | bidirezionale | Notifiche (es. `notifications/state_changed`) |

### 8.4 Tool registry (firmware `mcp_server.cc`)

**Common tools** (accessibili dal backend):
- `self.get_device_status`
- `self.audio_speaker.set_volume`
- `self.screen.set_brightness`
- `self.screen.set_theme`
- `self.camera.take_photo`

**User-only tools** (accessibili solo da companion app):
- `self.get_system_info`
- `self.reboot`
- `self.upgrade_firmware`
- `self.screen.get_info`
- `self.screen.snapshot`
- `self.screen.preview_image`
- `self.assets.set_download_url`

### 8.5 Server handling

Il server (`mcpMessageHandler.py:10-14`) inoltra il `payload` a `handle_mcp_message()`.

---

## 9. IoT

### 9.1 Device → Server

| Campo | Tipo | Obbligatorio | Valori ammessi |
|---|---|---|---|
| `session_id` | string | **sì** | UUID |
| `type` | string | **sì** | `"iot"` |
| `descriptors` | array | no | Array di descrittori |
| `states` | array | no | Array di stati |

### 9.2 Server handling

Il server (`iotMessageHandler.py:12-16`) gestisce `descriptors` e `states`.

---

## 10. OTA/Bootstrap

### 10.1 Endpoint

Il firmware chiama un endpoint HTTP per ottenere configurazione e URL WebSocket/MQTT.

**Server**: `ota_handler.py` — endpoint HTTP via `aiohttp`.

### 10.2 Request

Il firmware invia una richiesta HTTP con:
- `Device-Id` (MAC address)
- `Client-Id` (UUID)
- `Authorization` (token)

### 10.3 Response

Il server OTA restituisce:
- URL WebSocket o configurazione MQTT
- Eventuale URL firmware update
- Token/auth

### 10.4 Campi obbligatori

Per poter usare il nostro server senza modificare firmware, il server OTA deve restituire almeno:
- `ws_url` o configurazione MQTT completa
- `token` valido

---

## 11. Altri messaggi

### 11.1 `type: "ping"` / `type: "pong"`

| Direction | Messaggio | Fonte |
|---|---|---|
| device → server | `{"type":"ping"}` | `pingMessageHandler.py` |
| server → device | `{"type":"pong","timestamp":"..."}` | `pingMessageHandler.py:17-38` |

Attivato solo se `enable_websocket_ping == true` nel server.

### 11.2 `type: "server"` (server → device)

| Campo | Tipo | Obbligatorio | Valori ammessi |
|---|---|---|---|
| `type` | string | **sì** | `"server"` |
| `action` | string | **sì** | `"update_config"`, `"restart"` |
| `content` | object | no | `{secret}` |
| `status` | string | no | Stato |
| `message` | string | no | Messaggio |

### 11.3 `type: "system"` (server → device)

| Campo | Tipo | Obbligatorio | Valori ammessi |
|---|---|---|---|
| `type` | string | **sì** | `"system"` |
| `command` | string | **sì** | `"reboot"` |

### 11.4 `type: "alert"` (server → device)

| Campo | Tipo | Obbligatorio | Valori ammessi |
|---|---|---|---|
| `type` | string | **sì** | `"alert"` |
| `status` | string | no | Stato |
| `message` | string | no | Messaggio |
| `emotion` | string | no | Emotion label |

### 11.5 `type: "goodbye"` (MQTT only)

| Direction | Messaggio |
|---|---|
| bidirezionale | `{"session_id":"...","type":"goodbye"}` |

### 11.6 `type: "custom"` (opzionale)

Attivato da `CONFIG_RECEIVE_CUSTOM_MESSAGE` nel firmware.

---

## 12. Code to reuse conceptually (KEEP / REIMPLEMENT vs DO NOT IMPORT)

### KEEP / REIMPLEMENT (da xiaozhi-esp32-server)

| Componente | Motivazione |
|---|---|
| WebSocket transport (`websocket_server.py`) | Struttura base del server WebSocket |
| Protocol parser (`textMessageType.py`, `textMessageProcessor.py`) | Schema messaggi e routing |
| Hello handler (`helloHandle.py`, `helloMessageHandler.py`) | Negoziazione parametri |
| Audio framing (`opus_encoder_utils.py`) | Opus encode/decode |
| Listen handler (`listenMessageHandler.py`) | Gestione stati listen |
| Abort handler (`abortHandle.py`) | Cancellazione turno |
| MCP wire protocol (`mcpMessageHandler.py`) | JSON-RPC envelope |
| IoT wire protocol (`iotMessageHandler.py`) | Messaggi IoT |
| OTA/bootstrap (`ota_handler.py`) | Configurazione device |
| Auth (`auth.py`) | Validazione token/device |
| Connection state machine | Stati connessione |

### DO NOT IMPORT (da xiaozhi-esp32-server)

| Componente | Motivo |
|---|---|
| VAD (`providers/vad/`) | VoiceMem ha il suo VAD |
| ASR (`providers/asr/`) | VoiceMem ha il suo ASR |
| LLM (`providers/llm/`) | VoiceMem usa il suo LLM |
| Memory (`providers/memory/`) | VoiceMem è il sistema di memoria |
| Intent (`providers/intent/`) | Non necessario, VoiceMem gestisce l'intento |
| TTS (`providers/tts/`) | VoiceMem ha il suo TTS |
| Voiceprint (`utils/voiceprint_provider.py`) | VoiceMem ha il suo voiceprint |
| Dialogue (`utils/dialogue.py`) | VoiceMem gestisce il dialogo |
| Agent/plugin runtime (`plugins_func/`) | Non necessario |
| Manager UI/API (`manager-api/`, `manager-web/`, `manager-mobile/`) | Non necessario al bootstrap |
| Wake word (`utils/wakeup_word.py`) | Non necessario (firmware gestisce wake word) |

---

## 13. Divergenze firmware/server documentate

| Area | Firmware | Server | Impatto |
|---|---|---|---|
| `transport` in hello response | Atteso e validato | Non inviato | Basso: firmware logga errore ma non blocca |
| Sample rate output | Default 24000 | Configurabile | Nessuno: server può inviare 24000 |
| Opus complexity | 0 | 10 | Nessuno: solo encode server-side |
| Ping/keepalive | `esp_websocket_client` built-in | Opzionale via messaggio | Medio: server deve rispondere a ping se abilitato |
| MCP initialization | Dopo hello ricevuto | Subito dopo hello inviato | Basso: entrambi funzionano |

---

## 14. Parti non ancora determinate

1. **Formato esatto della risposta OTA/bootstrap** — non completamente verificato nel firmware.
2. **Schema esatto dei descriptors IoT** — non completamente documentato.
3. **Formato `text_font` capabilities** — dipende da `Assets::GetInstance().text_font_capability()`.
4. **Versione esatta del protocollo binario usata dal firmware stock** — dipende da configurazione.
5. **Comportamento esatto su reconnect con sessione precedente** — non completamente tracciato.
6. **Formato messaggi `custom`** — implementazione-specifico.