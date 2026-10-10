# Spike results

Measured on Sat Oct 10, 2026 from a laptop on whatever network it was on, one short prompt, 2 to 3 runs each.
These are single small samples, not benchmarks. Re-run on venue wifi before quoting anything.

## Gemini streaming (REST, `streamGenerateContent`, `alt=sse`): PASS with a model change

| Model | Setting | First token (ms), per run |
|---|---|---|
| gemini-3.8-flash | default | 4737, 5292, 28590 |
| gemini-3.8-flash | thinkingLevel low | 16586, 2737 |
| gemini-3.8-flash | thinkingLevel medium | 5012, 4808 |
| gemini-3.8-flash | thinkingLevel minimal | HTTP 400, not supported |
| gemini-3.5-flash-lite | default | 1050, 967 |
| gemini-3.1-flash-lite | default | 1025, 1016 |
| gemini-2.5-flash | any | HTTP 404, no longer available to new keys |

- The reply arrives in about 2 chunks, so first token is close to total time. There is little to gain from streaming Gemini text into TTS at this length.
- `gemini-3.8-flash` is too slow and too variable for the live loop with this setup. A lite model is about 1 s on this prompt.
- The model list never shows `streamGenerateContent`, only `generateContent`. Streaming works anyway.
- Not tested: a long prompt (resume plus posting plus history), which will be slower. Retest with a realistic prompt before choosing.
- Decision pending: live interviewer on a lite model, grading stays on the evaluator model.

## ElevenLabs TTS (streaming, `pcm_16000`): PASS

Needed two fixes on the account side: key permissions (`text_to_speech`, `speech_to_text`) and a voice ID
the free plan can use (library voices return 402 on the free plan). `voices_read` and `models_read` are still
missing from the key, so voices cannot be listed through the API. `ELEVENLABS_VOICE_ID` must be set.

Request sent to first audio bytes, same 65 character sentence, 3 runs each:

| Model | First audio (ms), per run |
|---|---|
| default (`eleven_multilingual_v2`) | 2345, 3292, 1534 |
| eleven_flash_v2_5 | 1382, 640, 588 |
| eleven_turbo_v2_5 | 617, 2557, 2600 |

- Total time is about equal to first audio on the default model, so audio arrives almost in one burst for a sentence this short.
- `eleven_flash_v2_5` looks best here, but 3 runs with a cold first one is thin. Retest on venue wifi.
- Model ids were tried by name and are not confirmed from docs, since the key cannot list models.

## ElevenLabs speech to text (`scribe_v2`, upload endpoint): PASS on one synthetic clip

Round trip of the 4.2 s TTS clip (`pcm_s16le_16`): upload to transcript 1558, 991, 824 ms.
The transcript matched the sentence exactly in all 3 runs. This is one synthetic voice, so it says nothing
about accuracy on real or noisy speech. Upload only: the docs page read did not mention a realtime websocket.

## What this means for turn latency

Unmeasured end to end. The pieces measured so far, taken separately and not added up as a claim:
speech to text about 0.8 to 1.6 s, a lite Gemini model about 1.0 s to first token, and TTS first audio about
0.6 to 1.4 s on the flash model. Expect a visible pause per turn. The real figure comes from the on-screen
`timing` readout once the loop exists. Ideas to hide it: speak a short filler acknowledgment while the model
works, and start TTS on the first sentence.
