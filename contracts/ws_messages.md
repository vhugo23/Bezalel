# WebSocket messages

Status: proposed. The current backend has no WebSocket routes. Every message is JSON text unless marked binary.
Each message has a `type`. Unknown types are ignored and logged, never fatal.

## WS /ws/voice/{session_id}

Browser to server

| type | fields | notes |
|---|---|---|
| `audio` | binary frame | 16 kHz mono PCM chunks. Sent while the mic is open. |
| `speech_end` | `t_client` | Browser's voice activity detection thinks the user stopped. Starts the latency clock. |
| `barge_in` | `t_client` | User started talking while TTS was playing. Server stops sending `tts_chunk`. |
| `text_answer` | `text` | Typed fallback when the mic fails. |

Server to browser

| type | fields | notes |
|---|---|---|
| `transcript_partial` | `text`, `turn` | |
| `transcript_final` | `text`, `turn`, `answer_id` | `answer_id` is what evaluators will later reference. |
| `interviewer_text` | `text`, `turn` | Sent as soon as it exists so the screen can show it before audio. |
| `tts_chunk` | binary frame | Audio from ElevenLabs, passed straight through. |
| `tts_done` | `turn` | |
| `timing` | `turn`, `stage`, `ms` | `stage` is one of `stt`, `llm_first_token`, `tts_first_audio`, `turn_total`. Values are measured on the server. Feeds the on-screen latency readout. |
| `state` | `state` | `intake`, `interview`, `walkthrough`, `drill`, `debrief`, `lesson`, `retest`. |
| `error` | `code`, `message`, `recoverable` | |

On disconnect the server keeps the session. A reconnect with the same `session_id` resumes at the current `state` and replays the last `interviewer_text`.

## WS /ws/board/{session_id}

Used by the laptop schematic view and the paired iPad. Both connect to the same session. The iPad
first calls `pair` with the code shown on the laptop.

Client to server

| type | fields | notes |
|---|---|---|
| `pair` | `code` | iPad only. Server replies `paired` or `error`. |
| `probe` | `action`, `node` | Laptop only. Server answers with a `probe_result` and stores a probe event. The client never sends `seq`, `value` or `t`. |
| `stroke_snapshot` | `png_base64`, `purpose` | iPad or laptop canvas. `purpose` is `drill` or `walkthrough`. |
| `builder_netlist` | `parts`, `nets` | Snap-in builder output, same shape as the netlist schema. Exact, no vision needed. |

Server to client

| type | fields | notes |
|---|---|---|
| `paired` | `session_id` | |
| `probe_result` | full probe event (see `probe_event.schema.json`) | The reading comes from the solver, never from the client. |
| `critique` | `text`, `confidence`, `source` | `source` is `builder_diff` or `vision`. Vision results always carry a confidence and may be wrong. |
| `error` | `code`, `message`, `recoverable` | |

Faults are never sent to the browser. `probe_result` carries readings only.
