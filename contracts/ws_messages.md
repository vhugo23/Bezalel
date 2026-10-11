# WebSocket messages

Status: proposed. The current backend has no WebSocket routes. Every message is JSON text unless marked binary.
Each message has a `type`. Unknown types are ignored and logged, never fatal.

## WS /ws/voice/{session_id}

Browser to server

| type | fields | notes |
|---|---|---|
| `audio` | binary frame | 16 kHz mono 16-bit PCM, any chunk size (about 100 ms is fine). Sent only while the push-to-talk button is held. Buffered on the server, capped at 60 s. |
| `speech_end` | `t_client` | Button released. Server transcribes the buffered audio and answers as if the text had been typed. |
| `barge_in` | `t_client` | Button pressed. Server stops the interviewer's audio (`tts_done` with `interrupted: true`) and clears the audio buffer, so send it at the start of every press. |
| `start` | | A click in the browser. Server speaks the opening question (browsers block audio before a click). |
| `text_answer` | `text` | Typed fallback when the mic fails. |

Server to browser

| type | fields | notes |
|---|---|---|
| `transcript_partial` | `text`, `turn` | Not sent. Speech to text is a batch upload, so only `transcript_final` exists. |
| `transcript_final` | `text`, `turn`, `answer_id` | `answer_id` is what evaluators will later reference. |
| `interviewer_text` | `text`, `turn` | Sent as soon as it exists so the screen can show it before audio. |
| (binary frame) | audio | The interviewer's voice: 16-bit mono PCM at 16000 Hz (`ELEVENLABS_OUTPUT_FORMAT`), always whole samples. Set `binaryType = "arraybuffer"`. Frames arrive after `interviewer_text` and before `tts_done`. |
| `tts_done` | `turn`, `interrupted` | `interrupted` is true after a barge in or a new answer cut the audio off. |
| `timing` | `turn`, `stage`, `ms` | `stage` is one of `stt` (the transcribe call, upload to transcript), `tts_first_audio` (request sent to first audio bytes), `turn_total` (store answer, model call, store reply). `llm_first_token` is not sent: the model call is not streamed. Values are measured on the server. Feeds the on-screen latency readout. |
| `state` | `state` | `intake`, `interview`, `walkthrough`, `drill`, `debrief`, `lesson`, `retest`. |
| `error` | `code`, `message`, `recoverable` | Voice codes, all recoverable, none close the socket: `bad_answer`, `no_audio`, `too_short` (under 0.2 s), `no_speech` (empty transcript, nothing stored), `stt_failed` (type your answer instead), `audio_too_long` (over 60 s, the recording is dropped), `tts_failed` (the text reply is still valid). |

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
