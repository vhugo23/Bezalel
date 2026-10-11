# Env additions

The current `backend/.env.example` has: `DATABASE_URL`, `GEMINI_API_KEY`, `ELEVENLABS_API_KEY`,
`BACKBOARD_API_KEY`, `LLM_PROVIDER`, `VOICE_PROVIDER`, `MEMORY_BACKEND`,
`TASK_TIMEOUT_SECONDS`. Keep those names. `DATABASE_URL` is also the Tiger Data connection string.

Missing, needed for the contracts:

    # Evaluators. Built on Gemini through core/ai.py (no extra key).
    EVALUATOR_PROVIDER=              # blank = same as LLM_PROVIDER; fake | gemini
    EVALUATOR_MODEL=                 # blank = GEMINI_MODEL; a stronger model is fine here, grading is not live
    EVALUATOR_CONCURRENCY=4          # semaphore size
    EVALUATOR_TIMEOUT_SECONDS=60     # grading is slower than a live turn, TASK_TIMEOUT_SECONDS is 20

    # Live interviewer (Gemini Flash). Separate from the evaluator so the two can differ.
    INTERVIEWER_MODEL=

    # ElevenLabs
    ELEVENLABS_VOICE_ID=

    # Deploy only, do not set locally
    PUBLIC_BASE_URL=                 # used for the QR code

Never commit a real value.
