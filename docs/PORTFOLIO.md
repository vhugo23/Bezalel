# PrepCrew architecture and operations

React/TypeScript is built once and served by FastAPI alongside authenticated HTTP and WebSocket endpoints. A small Node launcher manages a native persistent PostgreSQL process, migrations and the Python API. This consolidates deployment into one service; it does not pretend that Python and TypeScript are the same language. One API worker owns the persisted background-job runner. No Redis, external memory service or Timescale extension is required.

## Provider connections

Connections stores per-user settings in Postgres and encrypts credentials with Fernet. The encryption key is persisted as `provider.key` under `PREPCREW_DATA_DIR`, unless `PREPCREW_ENCRYPTION_KEY` supplies an externally managed Fernet key. Keep that key with database backups, restrict filesystem access, and use HTTPS when hosting. Connection responses expose only presence flags. Blank key fields retain existing credentials; changing model vendors clears the old model credential. Disconnect affects only the current account.

The server resolves credentials from the authoritative session/plan owner, not a client-supplied user identifier. Model transports support Gemini, native OpenAI Responses, native Anthropic structured messages, and OpenAI-compatible chat completion endpoints. Original Pydantic/evidence validation remains authoritative across transports. Provider/model settings participate in job fingerprints. Subscription-account login integrations are not implemented.

Compatible model endpoints are restricted to approved hosts. `PREPCREW_PROVIDER_HOSTS` adds administrator-approved hostnames. Loopback custom endpoints are allowed only for local-app mode, and are disabled by public mode. Do not expose a local-mode instance publicly.

Voice supports local Kokoro/Parakeet, cloud speech and browser reply playback. The microphone stays active while Dana replies; barge-in cancels playback and the current response. ElevenLabs supports real-time captions; local Parakeet and OpenAI transcribe finalized utterances. Sparse tool observations share the conversation task and cancel when the candidate speaks. They never become candidate evidence or rubric scores. Local WebGPU speech was tested using synthesized audio on one Windows GPU; that is not a claim of universal hardware or acoustic reliability.

## Persistent data

Default local data: `.artifacts/app`. `PREPCREW_DATA_DIR` changes this location. Keep the database directory, password file, encryption key, and any separately configured artifact storage together in backup policy. For native database filesystem copies, stop the app first; use normal PostgreSQL backup tools for online backups. Existing Timescale deployments retain their historical schema; this work does not convert their data. New migrations render ordinary Postgres tables and analytical views.

The supported launcher ignores cloud provider credentials in a historical root `.env` and requires users to connect providers. `DATABASE_URL` from the process environment selects an external database instead of managed native Postgres. `PORT` and `PREPCREW_DB_PORT` select app/database ports.

## One-service hosting

Use a persistent disk, Python 3.11+, Node 22.12+, and HTTPS termination. Set `PREPCREW_PUBLIC=true`, `PUBLIC_BASE_URL` to the actual HTTPS origin, and `PREPCREW_DATA_DIR` to the persistent disk. Run `npm ci`, `npm run setup`, then `npm start` under the host's process manager. Start one instance/worker when using the managed database. For multiple replicas, job coordination and artifact storage require additional operational review.

An optional single-image packaging path is `docker build -f deploy/Dockerfile.app -t prepcrew .`. Mount a writable volume at `/data` (container user 10001), provide `PUBLIC_BASE_URL`, and expose port 8000 behind HTTPS. Docker is an optional hosting format, not a prerequisite for using the app. The old compose/local Vite launcher is retained for historical development compatibility, not the default setup.

## Portfolio scope

Team summary: “Co-developed PrepCrew, an interview practice app with live interruptible voice, simulated Linux debugging, system-design whiteboarding, and evidence-linked feedback and retests.” Mention the four-person hackathon team. Describe only work you personally owned; do not claim teammates' code, measured learning gains, production scale or real hardware execution.

The two authored drills and evidence-backed learning loop are implemented. Arbitrary generated tracks, validated mastery measurement, password recovery and complete account deletion are not. Local speech downloads are large; the compact Parakeet encoder is FP16, not fully INT8. Quality and latency depend on the chosen model/provider/device. Native cloud transports are contract-tested with mocked providers; final acceptance does not spend real provider credits.
