# PrepCrew frontend

React, strict TypeScript and Vite. The supported root launcher serves the built frontend with the API at one origin: `npm run setup`, then `npm start`. Connections configures each account's model and voice providers. Never place secrets in `VITE_*` variables.

For frontend development: `npm ci`, `npm run dev`. Vite proxies `/api/v2` and WebSockets to `PREPCREW_API_ORIGIN` (default localhost:8000). `npm test` runs unit tests; `npm run build` type-checks and builds. Excalidraw, Three.js and local speech load separately. Opening a session does not automatically download speech models; enabling local voice does.

Kokoro and Parakeet run in a worker with matching same-origin ONNX runtime files supplied by the Vite plugin. Compact Parakeet uses FP16 encoder/INT8 decoder and requires WebGPU shader-f16. Compatibility mode has a much larger FP32 encoder fallback. Local models are browser-cached. See the root README for realistic download sizes and cloud/local audio boundaries.

Browser acceptance is run from the root using `backend/scripts/e2e.py`, with a local disposable Postgres schema. Add `--auth accounts.spec.ts connections.spec.ts` for signed-in isolation. Set `PREPCREW_LOCAL_GPU_SMOKE=1` for the opt-in actual model smoke; mocked voice tests alone do not validate hardware/audio behavior.

Runnable drills are the simulated Pi lab and system design. Recorded autoplay is explicitly labeled; regular practice uses the reviewed assessment pipeline. API contracts can be regenerated with `npm run api:generate`.
