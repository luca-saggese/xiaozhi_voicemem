# Xiaozhi Message Catalogue — Catalogo completo dei messaggi di protocollo

> Derivato dal codice firmware `_upstream/xiaozhi-esp32` e server `_upstream/xiaozhi-esp32-server`.
> Ogni messaggio è verificato contro almeno una delle due fonti.

---

## Tabella messaggi

| # | Message `type` | Direction | Transport | Required fields | Optional fields | Firmware handler | Server handler | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | `hello` | device → server | WS text, MQTT | `type`, `version`, `transport`, `audio_params{format,sample_rate,channels,frame_duration}`, `features{mcp}` | `features{aec,glyph_push}`, `text_font{bundle,charset,size,bpp}` | `websocket_protocol.cc:196` | `helloHandle.py:28` | Primo messaggio dopo connessione |
| 2 | `hello` | server → device | WS text, MQTT | `type`, `transport` | `session_id`, `audio_params{format,sample_rate,frame_duration}`, `udp{server,port,key,nonce}` | `websocket_protocol.cc:226` | `connection.py:146` | Timeout 10s firmware |
| 3 | `listen` | device → server | WS text, MQTT | `session_id`, `type`, `state` | `mode` ("auto"\|"manual"\|"realtime"), `text` (solo state=detect) | `protocol.cc:52` | `listenMessageHandler.py:17` | Tre modalità di ascolto |
| 4 | `abort` | device → server | WS text, MQTT | `session_id`, `type` | `reason` ("wake_word_detected") | `protocol.cc:42` | `abortHandle.py:8` | Cancella TTS in corso |
| 5 | `stt` | server → device | WS text, MQTT | `session_id`, `type`, `text` | — | — | `sendAudioHandle.py` | Trascrizione ASR |
| 6 | `tts` | server → device | WS text, MQTT | `session_id`, `type`, `state` | `text` (solo sentence_start) | — | `sendAudioHandle.py` | Start/stop/sentence TTS |
| 7 | `llm` | server → device | WS text, MQTT | `session_id`, `type` | `emotion`, `text` | — | `sendAudioHandle.py` | Stato LLM/emotion |
| 8 | `mcp` | bidirezionale | WS text, MQTT | `session_id`, `type`, `payload{jsonrpc,method,id}` | `payload{params,result,error}` | `mcp_server.cc` | `mcpMessageHandler.py:10` | JSON-RPC 2.0 envelope |
| 9 | `iot` | device → server | WS text | `session_id`, `type` | `descriptors[]`, `states[]` | — | `iotMessageHandler.py:12` | Capability IoT |
| 10 | `ping` | device → server | WS text | `type` | — | — | `pingMessageHandler.py:17` | Solo se `enable_websocket_ping` |
| 11 | `pong` | server → device | WS text | `type`, `timestamp` | — | — | `pingMessageHandler.py:17` | Risposta a ping |
| 12 | `server` | server → device | WS text | `type`, `action` | `content{secret}`, `status`, `message` | — | `serverMessageHandler.py:12` | Update config/restart |
| 13 | `system` | server → device | WS text, MQTT | `type`, `command` | — | — | — | Comando "reboot" |
| 14 | `alert` | server → device | WS text, MQTT | `type` | `status`, `message`, `emotion` | — | — | Notifica alert |
| 15 | `goodbye` | bidirezionale | MQTT | `session_id`, `type` | — | `mqtt_protocol.cc:241` | — | Solo MQTT |
| 16 | `custom` | server → device | WS text, MQTT | `type` | (implementation-specific) | `CONFIG_RECEIVE_CUSTOM_MESSAGE` | — | Opzionale |

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

### 8. `mcp` (bidirezionale)

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
{"type":"pong","timestamp":"2026-09-08T12:00:00Z"}
```

### 11. `server` (server → device)

```json
{"type":"server","action":"update_config","content":{"secret":"..."},"status":"ok","message":"Config updated"}
{"type":"server","action":"restart"}
```

### 12. `system` (server → device)

```json
{"type":"system","command":"reboot"}
```

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

- **Total message types**: 16
- **Device → Server**: hello, listen, abort, iot, ping, goodbye, mcp
- **Server → Device**: hello, stt, tts, llm, pong, server, system, alert, goodbye, custom, mcp
- **Bidirezionale**: mcp, goodbye
- **Transport**: WebSocket text (tutti), MQTT (hello, listen, abort, stt, tts, llm, mcp, system, alert, goodbye, custom), WebSocket binary (audio)