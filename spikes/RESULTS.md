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

## Speech in, push-to-talk (`spikes/e2e_stt.py`)

Sat Oct 10, 2026, one run. ElevenLabs spoke a sentence (4.74 s, flash model), the PCM went back through the
real `/ws/voice` route as 100 ms frames plus `speech_end`, and the transcript was compared with the sentence.

- Heard: the same words, ignoring the final period. Speech to text (`scribe_v2`, upload) took 935 ms.
- The reply (real Gemini lite) came back as text and 156 audio frames. `speech_end` to the end of the reply audio
  was 2872 ms. That includes the whole reply being spoken, so it is not the pause before the interviewer starts.
- This is one synthetic voice. It says nothing about accuracy on real, accented or noisy speech.
  A real browser microphone check by a person is still needed.

## Real interviewer, 5 scripted turns (gemini-3.5-flash-lite, `spikes/e2e_interview.py`)

Sat Oct 10, 2026, one laptop, in-memory storage. Posting about 800 characters and resume about 1200 characters
(made-up test text). The candidate answers are scripted and some do not answer the question asked, so they
test follow-up behavior, not interview quality. One plan model call plus 5 live turns per run, 2 runs.

| Run | Plan | Fallback turns | Reply text ready (ms, server), turns 1 to 5 | First audio after that (ms), turns 1 to 5 |
|---|---|---|---|---|
| 1, with TTS | model plan, not degraded | 0 | 1133, 1008, 1076, 964, 974 | 827, 688, 676, 852, 774 |
| 2, no TTS (prompt tweak) | model plan, not degraded | 0 | 1049, 1081, 1110, 1066, 1270 | not run |

- "Reply text ready" is the server's `turn_total`: storing the answer, the Gemini call, and storing the reply.
  It is not speech-end to first sound. Adding first audio puts the pause after the answer around 1.6 to 2.0 s
  on these runs, without speech to text (about 0.8 to 1.6 s in the spike), so expect roughly 2.5 to 3.5 s
  with a spoken answer. That sum is an estimate from separate measurements, not a measured end to end turn.
- Every reply referenced something the candidate had just said.
- Problem found in run 1: with an unanswered question the model repeated it word for word (turns 4 and 5).
  Fixed with one prompt line ("never repeat a question in the same words"). Run 2 rephrased each time.
  Still unsolved: it keeps steering back to the one unanswered question instead of moving on sooner.
- Retest on venue wifi, with a real person talking, before quoting any number.

## Humanlike interviewer, old versus new persona (`spikes/compare_interviews.py`)

Sat Oct 10, 2026. The same 5 scripted candidate answers, real Gemini lite (`gemini-3.5-flash-lite`), two runs per
side, 10 replies per side. In each side one of the two runs failed to get a model plan (Gemini 503 "high demand"),
so it used the generic fallback questions. That makes the sides only roughly comparable. Tiny sample, not a benchmark.

| Measure (10 replies per side) | Old persona | New persona |
|---|---|---|
| Average words per reply | 18.5 | 11.7 |
| Replies over 25 words | 2 | 0 |
| Replies repeating an earlier opening word | 1 | 0 |
| First sentence mostly repeats the candidate's answer | 2 | 0 |
| Verbatim repeated questions | 0 | 0 |
| Live checker violations (`humanness.check`) | 0 | 0 |

- The live checker found nothing on either side, so it is a guard rail and not evidence of improvement. It did not
  catch the old "restate what you said, then ask" pattern at its 60 percent threshold, so the comparison uses a looser
  first-sentence measure.
- What a person hears is not measured. `spikes/_runs/blind_read.md` has the 10 reply pairs in random order for a
  blind read, and `spikes/ab_voice.py` writes 12 WAV files (4 lines, 3 voice settings) to listen to. The presets are
  guesses and the model may ignore settings it does not support. No result is claimed until a person has judged.
- The plan call takes about 5 s (5 runs: 4.5 to 5.8 s), unlike a live turn at about 1 s. One run in six hit a 503;
  the plan call now retries once after a pause. Live turns still do not retry.
