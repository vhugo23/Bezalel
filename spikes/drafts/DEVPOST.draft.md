<!--
Draft for the Devpost description. Same honesty rules as the repo: every number is copied from spikes/RESULTS.md or
CONTEXT.md with its sample size, or left out. Anything marked FILL IN needs a person. Delete this block before pasting.
-->

# PrepCrew

**Tagline:** A voice interview coach for hardware and embedded engineering students.

**Team:** FILL IN (names)

**Demo link / video:** FILL IN

**Code:** FILL IN (repository link; confirm it is public before submitting)

## What it does

Hardware interviews are spoken: you explain a project from your resume, defend your choices, and talk through how you would debug a circuit. PrepCrew is a place to practice the first part out loud and get specific feedback.

You paste a job posting and your resume. A voice interviewer opens on one of your projects and follows up on what you actually say. It reads the skills the posting asks for and marks each as required or preferred. A hidden patience meter then reacts the way a real interviewer might. If you say you have never used a skill the job requires, or you dodge the question, the meter rises and the interviewer starts to wrap up. In strict mode two required gaps end the interview with a closing line. It then shows a debrief: each gap with your own words quoted back, what you did show you know, and where to learn each gap.

The same repository also holds a React app with a longer loop: a plan with skill circles, a voice and whiteboard session, grading where every claim has to point at quoted evidence from the session, a lesson written from a verified gap, and a changed retest.

**What is not built, so nobody is misled:**

- The circuit debugging walkthrough (a schematic with a planted fault that you probe while you talk) is not built in either app. There is no circuit solver and no schematic view. A reversed-LED scenario exists as data, and nothing loads it yet.
- The React app can only run one session, a software design question (a rate limiter). Its hardware tracks are preview cards that cannot be started.
- The hardware voice interviewer and the React app do not share an interviewer yet. The hardware interview with the patience meter and debrief runs from a separate test page.
- No person has reviewed the grading rubrics, the resource links or the lessons. Nothing is deployed.

## How we built it

- **Backend:** Python, FastAPI and asyncio, one process. No agent framework.
- **Models:** Gemini for plans, interviewer replies, the gap check and grading, using a small fast model for live turns. ElevenLabs for speech to text and streamed text to speech.
- **Data:** Postgres with TimescaleDB on Tiger Data for the React app (events, scores, mastery). The hardware interviewer runs in memory without a database.
- **Frontend:** React, Vite and TypeScript, with a Pointer Events whiteboard.
- **Safe by default:** when a model call times out, errors or returns bad JSON, the interviewer asks the next planned question and counts nothing against you. A gap only counts if the quote the model reports appears word for word in what you said. The debrief is built from those checked quotes and a hand-picked resource list, and no model writes it, so nothing in it is invented.
- **Spoken, not chatty:** replies are written to be said aloud (short, no praise, no stock phrases), and a cheap checker counts the ones that still sound like a chatbot.
- **Tests as the spec:** the backend tests run with stubbed models and no keys, and try to break the main flow: bad JSON, timeouts, a skipped question, a strict interview reaching its end, and the same answers run through two code paths and compared. FILL IN (the test count at submission time, from a real run).

## Challenges

- **The model was sometimes busy.** In bursts, about half the Gemini calls returned busy errors or timed out even after one retry (`spikes/RESULTS.md`). The design lets the interview carry on, but it means the meter can under-count, so the app tells you when it could not check an answer.
- **Speed.** A larger Gemini model took 4.7 s, 5.3 s and 28.6 s to first token in three runs, too slow for a conversation. A small model took about 1 s in two runs. One short prompt, not a benchmark.
- **Sounding like a person.** Early replies restated what you said and then asked one long question. Changing the style and the prompt brought the average from 18.5 to 11.7 words per reply over 10 replies per side, with scripted candidate answers. Whether it sounds human is still for a person to judge; we did not measure that.
- **Fairness of the meter.** A wrong "you don't know this" would end a real person's practice interview. The weights are hand-picked and not validated. One answer can add at most 0.6, so ending always takes two answers, and a run of failed checks counts for nothing. The false-end rate still needs a second person's labels.
- **Two apps.** The team built a long React app and a voice interviewer in parallel. They ended up side by side instead of together. Joining them was the thing we ran out of time for.

## Accomplishments we are proud of

- A voice interviewer whose scoring can be audited: every gap in the debrief has the candidate's own words next to it.
- The gap check agreed with our own hand labels on 17 of 20 skill checks and 14 of 14 ignored-question checks. We wrote those labels ourselves, so this is a smoke test and not an accuracy figure.
- One live run over real sockets with every real provider passed 23 of 23 checks (`CONTEXT.md`). One run, one synthetic voice.
- With the real model, the meter ended a strict interview early with a closing line and a debrief in the runs recorded in `spikes/RESULTS.md` (meter 0.0, 0.6, 1.2 in one run; 0.0, 0.6, 0.95, 1.55 in another). It did not end it in every attempt: later runs hit busy Gemini errors.

## What we learned

- Make the failure path the default path. Most of the work was deciding what the app does when the model is slow, wrong or silent.
- A model's evidence is only evidence if it can be checked mechanically. Requiring exact quotes removed a whole class of unfair penalties.
- Measure each piece before claiming a total. We measured speech to text, the reply and first audio separately and did not add them into a headline latency, because a full spoken turn was never measured end to end.
- Two parallel builds need one integration point decided early. We wrote the single entry point for the hardware interviewer only at the end.

## What's next

- Join the two apps: put the hardware interviewer into the React app as a track, using the single entry point now in the repo.
- Build the part that is missing: a circuit solver and a schematic view, so the debugging walkthrough exists. Start from the reversed-LED scenario, whose 2.0 V LED drop is an assumption we need to replace with a datasheet value.
- Have people review the rubrics, the lessons and the resource links, and check the meter's false-end rate with a second person's labels.
- Measure a full spoken turn on real wifi with a real person, and run sessions with consenting testers.
- Deploy.

## Built with

Python, FastAPI, asyncio, Gemini, ElevenLabs, PostgreSQL, TimescaleDB (Tiger Data), Alembic, React, Vite, TypeScript, WebSockets.
