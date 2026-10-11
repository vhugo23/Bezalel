# Demo runbook: the voice interviewer (fallback demo)

This demos the hardware and embedded voice interviewer from the throwaway test page `spikes/voice_check/`. It is not the React app. It shows a project interview from a posting and a resume, the patience meter moving, an early end and a debrief. It has **no circuit part**: nothing in either app lets a candidate probe a circuit, and after the project part the interviewer only plays a hand-off line and placeholder replies. Say that out loud in the demo.

Commands are PowerShell, from the repository root unless a step says otherwise. Replace the path with yours. Never paste a key into a command, a file in the repo or a chat. Do not quote latency numbers from memory: read them off the page.

## 0. Before you start (about 30 minutes ahead)

1. Close the React dev server if it is running. It also uses port 5173.
2. Install what the backend needs. Four packages were added in `9399673`, and the tests fail to collect without them.

   ```
   cd backend
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m pytest -q
   ```

   The tests use fake providers and need no keys or network. Every test should pass before you go on.
3. Where the keys live. The **repository root** `.env` is the file that always works. From `9399673` until `c891d23`, `backend/app/config.py` read only that file, so a machine whose keys sat only in `backend/.env` started with fake providers and in-memory storage and printed no error. From `c891d23` (on `origin/main`; a checkout cut at `4f2b84d` does not have it) the order is: variables already set in the terminal, then the root `.env`, then `backend/.env`. Whichever code you have, you find out from `/api/health` (it says `llm_provider: fake`) or from the page ("No skills were read from the posting"). Make a root `.env` that holds just what this demo needs (`LLM_PROVIDER=gemini`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `VOICE_PROVIDER=elevenlabs`, `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`), typed in by you, or set the same variables in the terminal before launching. Leave `DATABASE_URL` out of it. Do not copy `backend/.env` over: it holds the database URL. A `DATABASE_URL` in either file is loaded unless the process already holds an empty value, and the launch command below sets exactly that.

## 1. Start it (two terminals)

**Terminal 1, the backend, run from `backend/`:**

```
cd backend
$env:VOICE_PROVIDER = 'elevenlabs'
$env:ELEVENLABS_MODEL = 'eleven_flash_v2_5'
.\.venv\Scripts\python.exe -c "import os; os.environ['DATABASE_URL']=''; import uvicorn; uvicorn.run('app.main:app', port=8000)"
```

Why this long form: in PowerShell `$env:DATABASE_URL=''` and in cmd `set DATABASE_URL=` **remove** the variable instead of blanking it. The app then fills it in from `.env`, and with a real database URL the demo would write to Tiger Data and start the React app's grading worker. Setting it to an empty string inside Python, before the app loads, keeps storage in memory whatever `.env` says. Nothing is saved when you stop the server.

**Terminal 2, the test page:**

```
cd spikes\voice_check
python -m http.server 5173
```

Open http://localhost:5173/ and press Ctrl+F5. Leave the Backend box as `127.0.0.1:8000` and leave **Strict** ticked.

**Check the providers before you do anything else:**

```
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

You want `database: False`, `llm_provider: gemini` and `voice_provider: elevenlabs`. If it says `fake`, the keys were not found (section 0, step 3). Stop here and fix that first.

## 2. Rehearse once, then record it

Run section 3 start to finish once. Screen-record that run with sound. If Gemini fails on stage, the recording is your fallback, and you say it is a recording. A recording is not in the repository.

Each answer costs two Gemini calls (the reply and the gap check) and starting a session costs one. In our spikes a burst of about 25 calls in a minute got rate limited (`spikes/RESULTS.md`). Wait a minute between full runs and do not click around to test.

## 3. The demo script

The page already holds a made-up posting (a motor controls intern role that requires I2C, SPI and UART, oscilloscopes and C, and prefers KiCad or Altium) and a made-up resume. The meter checks what you say against the posting's skills, not against the resume, so answer as a candidate who is honest about a gap.

| # | You do | You say (typed, or hold "Hold to talk") | The audience sees and hears |
|---|---|---|---|
| 1 | Click **1. Start session** | Say: "It reads the skills from the posting and marks which ones are required." | A list "Skills from the posting: ... [required] ... [preferred]". The Patience meter row reads `0 of 1.0, ok`. The log says `plan degraded=false`. After the first answer the row reads `0 of 1, ok` (the page prints the number without the `.0`). |
| 2 | Click **2. Speak opening question** | Say: "It opens on a project from the resume." | A spoken question about one resume project, the same text in the box, State row `interview`. |
| 3 | Answer 1: a normal answer | "The board kept resetting under load, so I put a scope on the 5V rail and found it dipping." | A short spoken follow-up that picks up something you said. The meter stays at `0`. The timing rows fill in from the server. |
| 4 | Answer 2: a required gap | "Honestly I've never used SPI." | The meter row moves to `0.6 of 1, wrapping_up`. Say: "One missed required skill is not enough to end it. A missed preferred skill would barely move it." |
| 5 | Answer 3: a second required gap | "And I've never used I2C either." | The meter row reads `1.2 of 1, ended`. The interviewer says a closing line out loud. State reads `debrief (requirement_gaps)`. The **Debrief** panel appears by itself. |
| 6 | Read the debrief | Say: "Every gap has your own words next to it, checked against what you said. No model writes this page." | SPI and I2C listed as required gaps, each with `You said: "..."`, up to two links per gap, and a line saying the links are hand-picked and not yet reviewed by a person. |
| 7 | Type any answer and send it | Anything. | A red error line in the log. The interview is over and the socket stays open. |

Notes for the presenter:

- **Do not promise the exact wording.** The follow-up questions come from the model and change every run. The meter numbers `0.6` and `1.2` come from the starting weights (a missed required skill is 0.6) and appeared in our recorded runs; they depend on the model reading your answer correctly.
- **The reply to answer 2 is not shortened.** The meter's pressure reaches the interviewer one turn behind, so the "wrap up" instruction goes to the model on the next turn. In this script that next turn is already the closing line.
- **Speaking instead of typing.** Click once in the page first so the browser allows audio, allow the microphone, hold **Hold to talk**, speak, release. The "You:" line shows what it heard. Speech to text changed "the motors started" to "the motor started" in one recorded run (`CONTEXT.md`), so a quoted gap may differ by a word from what you said. Use typing if the exact quote matters.
- **Optional second run, for the "ignored question" path.** Start a new session. Give answer 1 as above. Then answer a question about something else with "I mostly did the power stage." The meter row shows `0.35 of 1, ok, 1 unanswered`. A second dodge ("Um, not sure, idk.") takes it to `0.7 of 1, wrapping_up, 2 unanswered`, and a third ends a strict interview.
- **Say what the meter is.** The weights and thresholds are hand-picked starting values and are not validated. A wrong "you don't know this" would end a real person's practice interview, and we have not checked how often that happens with a second person's labels.

## 4. If Gemini is rate limited or slow

Signs: the log says `plan degraded=true` and the page says no skills were read; the Patience meter row says "(could not check that answer, the AI was too slow or busy)"; the interviewer keeps asking generic or planned questions whatever you say.

By design this is safe: a failed check counts for nothing and the interviewer falls back to the planned question. It also means the meter can stay at `0` while you demo. In our recorded runs about half the Gemini calls were busy in bursts (`spikes/RESULTS.md`).

1. Stop clicking. Wait about 60 seconds, then click **1. Start session** for a fresh plan and session.
2. If it keeps failing, stop the backend (Ctrl+C in terminal 1) and start it again with another small model, in the same terminal before the launch command:

   ```
   $env:GEMINI_MODEL = 'gemini-3.1-flash-lite'
   ```

   It had a first token of 1025 and 1016 ms in two spike runs (`spikes/RESULTS.md`, one short prompt). Check `/api/health` and do a plan check again. Do not switch to `gemini-3.8-flash`: it took 4.7 s, 5.3 s and 28.6 s to first token.
3. If a second Gemini key exists, set it in the terminal (`$env:GEMINI_API_KEY = '...'`) before the launch command. Do not write it into a file in the repository.
4. If it is still failing, do not pretend. Say: "Gemini is rate limiting us right now." Then either play your rehearsal recording and say it is a recording, or run `.\.venv\Scripts\python.exe -m pytest tests/test_threshold.py -q` from `backend/` to show the meter logic with a stubbed model (say that the model is a stub).
5. With `LLM_PROVIDER=fake` the interview still runs on generic questions, but there is no meter and no gap check. Say so if you show it.
6. If speech to text fails, type the answers. If speech out fails, the interviewer's text still shows in the box.

## 5. Shut down

Stop only the two listeners you started.

```
Get-NetTCPConnection -LocalPort 8000,5173 -State Listen | Select-Object LocalPort, OwningProcess
Stop-Process -Id <OwningProcess for each port>
```

## Checklist

- [ ] React dev server closed, ports 8000 and 5173 free
- [ ] `pytest -q` in `backend/` passes
- [ ] Root `.env` has the keys and no `DATABASE_URL`; `/api/health` shows `gemini`, `elevenlabs` and `database: False`
- [ ] One full rehearsal done and screen-recorded with sound
- [ ] Volume up, microphone allowed in the browser, wifi checked
- [ ] Everyone presenting knows to say plainly that the circuit debugging part is not built

## 6. Optional: a backup model for when Gemini is busy

This is off unless you turn it on. It was only tested with a stubbed model. No real model was called, so there is no measured number for how often it helps.

**What it does.** The plan call, the live reply and the gap check each retry once on a busy answer from the main model (`GEMINI_MODEL`), as before. If the main model is still busy (503, 429, 500, 502 or 504) or has not answered in time, the same call is tried once on the model named in `GEMINI_BACKUP_MODEL`. If that also fails, you get today's behaviour: the planned question, and the gap check counts nothing. Bad keys, bad JSON and empty replies do not go to the backup.

**Turn it on.** In the same terminal as the backend, before the launch command in section 1, or in the root `.env` as `GEMINI_BACKUP_MODEL=<name>`:

```
$env:GEMINI_BACKUP_MODEL = '<a model name your key can use>'
```

Pick a different model from `GEMINI_MODEL`; the same name is ignored. `spikes/RESULTS.md` has first-token times of about 1 s from two runs each for `gemini-3.5-flash-lite` and `gemini-3.1-flash-lite`, one short prompt. Whether a second model has free capacity at the moment the first is busy has not been measured. A wrong name only shows up as an error when the backup is needed, so check the name once before the demo: `spikes/spike_gemini.py` reads `INTERVIEWER_MODEL` as the model to test and makes a few short calls (not run for this runbook). To turn it off, remove the variable and restart the backend.

**Time.** Each call keeps the limit it already had: 5 s for a live reply (`LIVE_TURN_TIMEOUT_SECONDS`), 4 s for the gap check (`ASSESSOR_TIMEOUT_SECONDS`), 20 s for the plan (`TASK_TIMEOUT_SECONDS`). The backup shares that limit, so a turn is never slower than before. The main model, with its one retry, gets 60 percent of it (3.0 s, 2.4 s and 12 s) and the backup gets what is left, which is more when the main model failed quickly. The cost: a main model that is slow but would have answered after 3 s is now cut off and the backup is asked instead. Raising a limit gives the main model more patience and lengthens the worst silence by the same amount.

**What you will see.** Nothing on the page: a reply from the backup reads like any other, and the Patience meter row still shows the check as done. In the backend terminal, look for lines starting `backup_model`: `trying` (the main model was busy or timed out), `used` (the backup answered) and `failed` (it did not). Count the `used` lines to see how often it helped. Over the typed route (`POST /api/sessions/{id}/turns`) the reply's `source` is `model_backup` instead of `model`, and the stored interviewer events say the same; the test page and the voice socket do not show `source`, so the log is the way to see it there.

**What it does not fix.** Both models busy at once, a bad key, content the model refuses. In those cases the demo looks exactly as in section 4, and the same advice applies. You cannot make Gemini busy on demand, so you cannot rehearse this path from the page. `.\.venv\Scripts\python.exe -m pytest tests/test_backup_model.py -q` runs the logic against a stub model.