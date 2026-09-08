# Fixtures protocollo Xiaozzi

Questa directory contiene payload di messaggi di protocollo Xiaozhi, ricavati con
certezza dal codice firmware (`_upstream/xiaozhi-esp32`) e server
(`_upstream/xiaozhi-esp32-server`).

## Regole

- Ogni fixture deve indicare la **provenienza** esatta (file, funzione, riga).
- **Non** creare payload inventati.
- Se un payload non può essere ricavato con certezza, non va inserito.

## Fixture validate e provenienza esatta

Tutte le fixture presenti in questa directory sono ricavate direttamente dal codice sorgente upstream.

| File fixture | Tipo messaggio | Fonte firmware | Fonte server | Note |
|---|---|---|---|---|
| `hello_device_v1.json` | `hello` (device → server) | `main/protocols/websocket_protocol.cc:196-217` (`GetHelloMessage`) | `main/xiaozhi-server/core/handle/helloHandle.py:28` | Include features (mcp, aec, glyph_push) e audio_params |
| `hello_server_v1.json` | `hello` (server → device) | `main/protocols/websocket_protocol.cc:226-249` (`ParseServerHello`) | `main/xiaozhi-server/core/connection.py:146` | Contiene transport ("websocket"), session_id, audio_params |
| `listen_start_manual.json` | `listen` start manual | `main/protocols/protocol.cc:52-60` (`SendStartListening`) | `main/xiaozhi-server/core/handle/textHandler/listenMessageHandler.py` | mode: "manual" |
| `listen_start_auto.json` | `listen` start auto | `main/protocols/protocol.cc:52-60` (`SendStartListening`) | `main/xiaozhi-server/core/handle/textHandler/listenMessageHandler.py` | mode: "auto" |
| `listen_stop.json` | `listen` stop | `main/protocols/protocol.cc:62-65` (`SendStopListening`) | `main/xiaozhi-server/core/handle/textHandler/listenMessageHandler.py` | state: "stop" |
| `listen_detect.json` | `listen` wake word | `main/protocols/protocol.cc:67-70` (`SendWakeWordDetected`) | `main/xiaozhi-server/core/handle/textHandler/listenMessageHandler.py` | state: "detect", text: wake_word |
| `abort_simple.json` | `abort` base | `main/protocols/protocol.cc:42-49` (`SendAbortSpeaking`) | `main/xiaozhi-server/core/handle/abortHandle.py` | Senza reason |
| `abort_wake_word.json` | `abort` con reason | `main/protocols/protocol.cc:42-49` (`SendAbortSpeaking`) | `main/xiaozhi-server/core/handle/abortHandle.py` | reason: "wake_word_detected" |
| `mcp_initialize.json` | `mcp` JSON-RPC | `main/mcp_server.cc`, `docs/mcp-protocol.md` | `main/xiaozhi-server/core/handle/textHandler/mcpMessageHandler.py` | JSON-RPC 2.0 initialize envelope |
| `ota_response.json` | OTA/version response | `main/ota.cc:140-220` (`CheckVersion`) | deployment-specific | Sezioni `websocket` e `server_time` parsate dal firmware; il path è `ota_url`, non un endpoint firmware fisso |
| `ota_request_headers.json` | Header POST OTA stock | `main/ota.cc:54-68` (`SetupHttp`) | `main/xiaozhi-server/core/api/ota_handler.py:143-166` | I nomi e le semantiche sono upstream; gli identificativi sono valori sintetici di test |