# Xiaozhi Message Catalogue — Catalogo completo dei messaggi di protocollo

> Derivato dal codice firmware `_upstream/xiaozhi-esp32` e server `_upstream/xiaozhi-esp32-server`.
> Ogni messaggio è verificato contro almeno una delle due fonti.

---

## Tabella messaggi

| # | Message `type` | Direction | Transport | Required fields | Optional fields | Firmware handler | Server handler | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | `hello` | device → server | WS text, MQTT | Firmware emette `type`, `version`, `features`, `transport`, `audio_params` | `features.aec`, `features.glyph_push`, `text_font` dipendono dalla build | `websocket_protocol.cc:198-216` | `helloHandle.py` | Un solo type; bidirezionale. `version` è il valore configurato del framing/header. |
| 2 | `hello` | server → device | WS text, MQTT | Per il parser firmware: `type`, `transport="websocket"` | `session_id`, `audio_params`, `udp` | `websocket_protocol.cc:224-249` | `connection.py` | Il firmware legge solo `transport`, `session_id`, `audio_params.sample_rate` e `frame_duration`; per il gateway `session_id` è necessario per le richieste successive. |
| 3 | `listen` | device → server | WS text, MQTT | `session_id`, `type`, `state` | `mode` ("auto"\|"manual"\|"realtime"), `text` (solo state=detect) | `protocol.cc:52` | `listenMessageHandler.py:17` | Tre modalità di ascolto |
| 4 | `abort` | device → server | WS text, MQTT | `session_id`, `type` | `reason` ("wake_word_detected") | `protocol.cc:42` | `abortHandle.py:8` | Cancella TTS in corso |
| 5 | `stt` | server → device | WS text, MQTT | `session_id`, `type`, `text` | — | — | `sendAudioHandle.py` | Trascrizione ASR |
| 6 | `tts` | server → device | WS text, MQTT | `session_id`, `type`, `state` | `text` (solo sentence_start) | — | `sendAudioHandle.py` | Start/stop/sentence TTS |
| 7 | `llm` | server → device | WS text, MQTT | `session_id`, `type` | `emotion`, `text` | — | `sendAudioHandle.py` | Stato LLM/emotion |
| 8 | `mcp` | bidirezionale | WS text, MQTT | Request: `payload{jsonrpc:"2.0",method,id}` e `params` opzionale | Response: `payload{jsonrpc,id,result|error}`; notification: `payload{jsonrpc,method,params?}` senza `id` | `mcp_server.cc:350-433` | `mcpMessageHandler.py` | Il parser firmware accetta request con id numerico; ignora method che inizia con `notifications`; non parsea response come request. |
| 9 | `iot` | device → server | WS text | `session_id`, `type` | `descriptors[]`, `states[]` | — | `iotMessageHandler.py:12` | Capability IoT |
| 10 | `ping` | device → server | WS text | `type` | — | — | `pingMessageHandler.py:17` | Solo se `enable_websocket_ping` |
| 11 | `pong` | server → device | WS text | `type`, `timestamp` | — | — | `pingMessageHandler.py:17` | Risposta a ping |
| 12 | `server` | server → device | WS text | — | — | nessun handler firmware identificato | server legacy | Non requisito del compatibility gateway stock. |
| 13 | `system` | server → device | WS text, MQTT | `type`, `command` | — | — | — | Comando "reboot" |
| 14 | `alert` | server → device | WS text, MQTT | `type` | `status`, `message`, `emotion` | — | — | Notifica alert |
| 15 | `goodbye` | bidirezionale | MQTT | `session_id`, `type` | — | `mqtt_protocol.cc:241` | — | Solo MQTT |
| 16 | `custom` | server → device | WS text, MQTT | `type`, `payload` object, solo con `CONFIG_RECEIVE_CUSTOM_MESSAGE` | — | `application.cc:693-705` | — | Opzionale e build-dependent |
| 17 | `notify` | server → device | WS text | `type`, `audio_url` | `subtitles[]` | `application.cc:574-606` | server notification handler | Notifica audio distinta da `server`. |

---

## Dettaglio campi per messaggio

### 1. `hello` (device → server)

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

### 2. `hello` (server → device)

```json
{
  "type": "hello",
  "transport": "websocket",
  "session_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "audio_params": {
    "format": "opus",
    "sample_rate": 24000,
    "channels": 1,
    "frame_duration": 60
  }
}
```

### 3. `listen` (device → server)

```json
// Start manual
{"session_id":"xxx","type":"listen","state":"start","mode":"manual"}
// Start auto-stop
{"session_id":"xxx","type":"listen","state":"start","mode":"auto"}
// Start realtime (richiede AEC)
{"session_id":"xxx","type":"listen","state":"start","mode":"realtime"}
// Stop
{"session_id":"xxx","type":"listen","state":"stop"}
// Wake word detected
{"session_id":"xxx","type":"listen","state":"detect","text":"xiaozhi"}
```

### 4. `abort` (device → server)

```json
{"session_id":"xxx","type":"abort"}
{"session_id":"xxx","type":"abort","reason":"wake_word_detected"}
```

### 5. `stt` (server → device)

```json
{"session_id":"xxx","type":"stt","text":"trascrizione ASR"}
```

### 6. `tts` (server → device)

```json
{"session_id":"xxx","type":"tts","state":"start"}
{"session_id":"xxx","type":"tts","state":"sentence_start","text":"Ciao, come posso aiutarti?"}
{"session_id":"xxx","type":"tts","state":"stop"}
```

### 7. `llm` (server → device)

```json
{"session_id":"xxx","type":"llm","emotion":"happy","text":"Ciao! Sono qui per aiutarti."}
```

### 8. `mcp` (request, response, notification)

```json
{
  "session_id": "xxx",
  "type": "mcp",
  "payload": {
    "jsonrpc": "2.0",
    "method": "tools/list",
    "params": {"cursor": "", "withUserTools": false},
    "id": 1
  }
}
```

Response:

```json
{"session_id":"xxx","type":"mcp","payload":{"jsonrpc":"2.0","id":1,"result":{"tools":[]}}}
```

Notification, senza `id`:

```json
{"session_id":"xxx","type":"mcp","payload":{"jsonrpc":"2.0","method":"notifications/state_changed","params":{}}}
```

Il firmware stock corrente accetta request con `jsonrpc="2.0"`, `method` stringa,
`id` numerico e `params` oggetto opzionale. Ignora i metodi che iniziano con
`notifications`; non richiede `method` nelle response e non richiede `id` nelle
notification come regola generale JSON-RPC.

### 9. `iot` (device → server)

```json
{
  "session_id": "xxx",
  "type": "iot",
  "descriptors": [
    {"name": "speaker", "properties": {"volume": {"type": "integer", "min": 0, "max": 100}}}
  ],
  "states": [
    {"name": "speaker", "state": {"volume": 50}}
  ]
}
```

### 10. `ping` / `pong`

```json
// device → server
{"type":"ping"}
// server → device
{"type":"pong","timestamp":1788888000000}
```

### 11. `server` (server legacy, non richiesto)

```json
Non esiste un handler firmware stock corrente per questo type; gli esempi del
server originale non sono requisiti del compatibility gateway.
```

### 12. `system` (server → device)

```json
{"type":"system","command":"reboot"}
```

`reboot` è l'unico comando consumato dal firmware. `upgrade` non è supportato
dal dispatch firmware e non va documentato come valore valido.

### 13. `alert` (server → device)

```json
{"type":"alert","status":"warning","message":"Batteria in esaurimento","emotion":"concerned"}
```

### 14. `goodbye` (MQTT only)

```json
{"session_id":"xxx","type":"goodbye"}
```

---

## Summary

- **Total unique JSON `type` values**: 16 (`hello` è contato una sola volta)
- **Device → Server**: hello, listen, abort, iot, ping, mcp
- **Server → Device**: hello, stt, tts, llm, pong, notify, system, alert, custom
- **MQTT lifecycle**: goodbye
- **Bidirezionale**: mcp
- **Server legacy / non richiesto**: server
- **Transport**: WebSocket text per i messaggi applicativi; MQTT per i messaggi
  supportati dalla configurazione MQTT; WebSocket binary per audio.