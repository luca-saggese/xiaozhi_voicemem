# Fixtures protocollo Xiaozzi

Questa directory contiene payload di messaggi di protocollo Xiaozhi, ricavati con
certezza dal codice firmware (`_upstream/xiaozhi-esp32`) e server
(`_upstream/xiaozhi-esp32-server`).

## Regole

- Ogni fixture deve indicare la **provenienza** esatta (file, funzione, riga).
- **Non** creare payload inventati.
- Se un payload non può essere ricavato con certezza, non va inserito.

## Fixture attuali

*(nessuna fixture ancora inserita — in attesa di M02 per estrarre payload reali
da test o tracce)*

## Provenienze disponibili per estrazione futura

| Messaggio | Fonte firmware | Fonte server | Stato |
|---|---|---|---|
| `hello` device → server | `websocket_protocol.cc:196-217` | `helloHandle.py:28-44` | Documentato in `XIAOZHI_MESSAGE_CATALOG.md` |
| `hello` server → device | `websocket_protocol.cc:226-249` | `connection.py:146-147` | Documentato |
| `listen` start/stop/detect | `protocol.cc:52-70` | `listenMessageHandler.py:17-72` | Documentato |
| `abort` | `protocol.cc:42-49` | `abortHandle.py:8-17` | Documentato |
| `mcp` initialize | `mcp_server.cc` | `mcpMessageHandler.py:10-14` | Documentato |
| `mcp` tools/list | `mcp_server.cc` | — | Documentato |
| `mcp` tools/call | `mcp_server.cc` | — | Documentato |
| `iot` descriptors/states | — | `iotMessageHandler.py:12-16` | Schema non completamente verificato |
| `ping` / `pong` | — | `pingMessageHandler.py:17-38` | Documentato |
| `server` update_config | — | `serverMessageHandler.py:12-72` | Documentato |
| `goodbye` | `mqtt_protocol.cc:241-252` | — | Documentato |

## Estrazione futura

In M02, durante l'implementazione del gateway, queste fixture verranno popolate
con payload reali catturati da:
1. Test unitari del server originale
2. Log di connessione con device reale
3. Payload generati dal nostro stesso gateway in fase di test