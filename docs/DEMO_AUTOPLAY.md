# Demo autoplay

Open either original **System design: whiteboard** or **Fix the site on the Pi** track and click the small **D / play** button at bottom left. Personalized opening text is supported. Changed retests require your own answers.

This is a fast, authored walkthrough like the prototype. Dana and the candidate use distinct ElevenLabs voices, with pitch-preserving 1.2x playback. Each fixed utterance is cached on the backend and reused across sessions. It needs no microphone, speech-model download, live interviewer, live vision or evaluator. Uncached audio uses the configured ElevenLabs quota. Drawing and simulator actions are saved through the usual validated APIs; the dedicated demo endpoints save scripted replies and whiteboard notes.

The candidate deliberately makes mistakes. The end screen shows an explicitly **scripted demo recap** with improvement points, authored coaching and a changed next-practice prompt. It does not claim live grading, publish verified weaknesses, create a real retest, or update skill scores. The saved recap can be reopened from history. Normal practice continues to use the configured interviewer, board review and assessment providers.

**Stop & take over** cancels speech and prevents later scripted actions after any submitted action finishes. The transcript remains saved. Restarting resumes the current script; safe simulator actions may repeat. Navigating away stops playback. A session marked as a scripted walkthrough remains a demo, including after manual takeover; start a new practice session for real grading.

If ElevenLabs is unavailable, the demo visibly labels its browser-voice fallback. If browser audio also fails, playback continues with visible dialogue. Configure ELEVENLABS_DEMO_CANDIDATE_VOICE_ID to override the default candidate voice; Dana uses ELEVENLABS_VOICE_ID. Keys remain on the server. Browser acceptance accelerates speech in an isolated database and verifies both tracks, personalized whiteboard availability, stop behavior, saved recap and absence of live-model endpoint requests.
