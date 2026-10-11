# Local speech on quota exhaustion

Live interviews prefer ElevenLabs. An explicit realtime `quota_exceeded` switches
recognition to Parakeet without replacing the authenticated interview socket.
For TTS, an explicit quota response (provider `quota_exceeded` or HTTP 402) switches
playback to Kokoro. A plain 429 rate limit, bad credentials, denied permissions,
network failure or Gemini failure does not silently change providers.

No new secrets or environment variables are needed. Start voice normally. The
status below the voice controls shows loading and local execution. Wait for
Listening before speaking during the first download. End voice cancels downloads,
terminates workers and releases the microphone. Text input remains available.
If the provider failed mid-utterance, repeat the unfinished utterance after
Listening appears; previously saved turns remain in the transcript.

## Runtime

- Kokoro: `kokoro-js` 1.2.1, `onnx-community/Kokoro-82M-v1.0-ONNX`, FP32 WebGPU,
  `af_heart`. This is a different voice from the configured ElevenLabs Dana voice.
- Parakeet: `parakeet.js` 1.4.4, `parakeet-tdt-0.6b-v3`. The encoder runs on
  WebGPU (FP16 when `shader-f16` exists, FP32 otherwise); the int8 decoder runs on
  single-threaded WASM. This is not an entirely GPU implementation.
  Converted model assets are pinned to Hugging Face revision `f88260fa` so
  partially cached downloads cannot mix revisions.
  Its ONNX Runtime Web dependency is pinned to 1.30.0; the bundled 1.24.1
  failed actual GPU inference with a destroyed-buffer validation error.
- Dedicated workers keep model inference off the UI thread. Models are loaded
  only on fallback. Kokoro uses its library's browser cache; Parakeet uses
  explicit model URLs and a streaming CacheStorage wrapper. Caching is best
  effort: a failed cache write can require another download next time.
  Workers and GPU sessions are released when voice ends. Clearing site storage
  removes downloaded caches. Model assets come from Hugging Face and runtime
  assets may come from jsDelivr; first use still needs internet access.
  Model weights total about 330 MB for Kokoro, 1.3 GB for FP16 Parakeet or
  2.5 GB for FP32 Parakeet (Hugging Face file metadata checked October 11, 2026).
- HTTPS or localhost, a working WebGPU adapter and sufficient GPU memory are
  required. An unsupported browser or failed download leaves an actionable error
  and typing controls. There is no silent CPU-only fallback.
- The overall interview remains online: recognized text is sent to the server
  and Gemini. Local microphone audio and locally synthesized waveforms are not
  uploaded by this path. The normal ElevenLabs path still sends audio upstream.

The local segmenter uses browser echo cancellation/noise suppression plus an
adaptive energy gate. It previews recognized speech during an utterance, commits
after an 800 ms quiet interval and bounds segments to 12 seconds. Recognition
previews, not raw volume spikes, trigger the server's existing interruption
protocol. Mute drops buffered and in-flight transcripts. One final segment can
wait behind inference; overload stops voice with an error instead of silently
dropping answers. Send now, Interrupt, Mute and typed turns remain available.

This does not identify the candidate's voice or reliably reject a nearby person
or television. Acoustic testing with speakers, headphones, accents and real
background noise remains necessary. First download and inference latency depend
on hardware; there is no measured latency guarantee. Large Parakeet weights and
two simultaneous models can exceed mobile GPU memory. Kokoro playback and the
cloud TTS path currently buffer the complete clip before playback so the client
can inspect quota errors before choosing a provider.

## Evidence and auditing

Each actual local STT preview/final or TTS synthesis first creates a
`generation_jobs` row through authenticated session-owned endpoints. Completion
records latency and success/failure with `client_reported: true`; browser reports
are not independent proof of model execution or audio authenticity. Model loading
does not create an inference row. TTS accepts only an existing interviewer event
seq and obtains its text from the database.

The socket accepts a local transcript only in fallback mode, after a successful
STT audit for that session and step, with exactly matching text. Each audit can be
consumed once. Canonical candidate `turn` events retain `source_job_id`; board
flags and questions are computed on the server. Grading continues to cite saved
`session_events.seq`. The browser never declares a grading claim verified.

Failed/cancelled inference completion is best effort if the browser or network
disappears; the pre-created row can remain running after a hard browser crash.

## Verification

Normal checks use synthetic PCM and mocked model workers; no paid API calls:

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python -m pytest backend/tests -q
cd frontend
npm test
npm run build
```

From the root, browser acceptance runs against a disposable Tiger schema:

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python backend/scripts/e2e.py local-speech.spec.ts local-voice.spec.ts
```

An optional real-model synthetic Kokoro-to-Parakeet roundtrip downloads model
weights and uses the local GPU, with every inference audited in the disposable
schema. It does not call paid speech or Gemini APIs:

```powershell
$env:PREPCREW_LOCAL_GPU_SMOKE='1'
.\.venv\Scripts\python backend/scripts/e2e.py local-speech.spec.ts
Remove-Item Env:PREPCREW_LOCAL_GPU_SMOKE
```

That acceptance browser explicitly enables WebGPU on Windows headless Chromium;
normal users must have browser WebGPU support enabled themselves. Package
overrides update unused Node-only `sharp`/`onnxruntime-node` dependencies pulled
in by Transformers.js; this application runs these models only in the browser.

Primary references: [Kokoro.js](https://github.com/hexgrad/kokoro/tree/main/kokoro.js),
[Parakeet.js API and backend semantics](https://github.com/ysdede/parakeet.js),
[ONNX Runtime WebGPU imports](https://onnxruntime.ai/docs/tutorials/web/ep-webgpu.html).

Parakeet model attribution: NVIDIA (original Parakeet model), istupakov (ONNX
export), ysdede (canonical packaging), and hellguz (weight-only quantized export).
The converted Parakeet weights retain CC-BY-4.0; see the
[quantized model card](https://huggingface.co/hellguz/parakeet-tdt-0.6b-v3-onnx-q8).
