# Raspberry Pi fault lab

`infra.pi_site` is a runnable, hand-built simulator in the canonical `/api/v2` app. Open **Infra → Fix the site on the Pi** from an existing or new plan. Migration `009_pi_linux` also offers it to older plans that had only a proposed Pi track; existing scenarios and sessions are preserved.

The five stages follow `prototype.html`: diagnose the 502, repair nginx's upstream, repair stylesheet permissions, recover log space, and investigate power. Terminal, config editor, simulated browser and Pi supply controls sit beside Dana's existing voice/transcript. The same Gemini/ElevenLabs loop handles questions and explanations. Model-driven transitions and the manual Next button both require the lab check; a candidate explanation is also required.

## What is real

Each action goes through a typed, bounded API, a locked session row, expected revision and stable request id. A replay returns the same event; an id collision, competing revision, paused session or stale step is rejected. State and action/result events survive reload. An internal state namespace is removed from the public session and model context. A client cannot append its own `command`/`edit`/`probe` event.

Before offering the scenario, a deterministic reference run reproduces each broken symptom and repairs all five stages. The migration carries a frozen version of that checked scenario. Two authored deployment variants use distinct application ports; the second is available to subsequent retest integration.

The rubric covers proxy, permission, disk/log, power and debugging reasoning. `tool_action` claims require candidate tool events with server simulator provenance, exact quoted text and matching session/step/seq. Interpretation and scores still require the independent evaluator review. Tool output establishes an observed simulated result; it does not establish that the candidate explained a concept or has a particular ability. Human rubric calibration remains pending.

## What is simulated or still pending

No Linux process, nginx, Node app, hardware, browser request to a Pi, or candidate shell runs. This reducer has a documented command subset (`help`). Unsupported commands do nothing. The configuration checker accepts a restricted server-block grammar; it is not the nginx compiler. Power, temperature, filesystem sizes, service state, uptime and response times are synthetic fixtures, explicitly labelled in the UI. They are never inserted into Tiger's measured latency metrics. The Pi view is an SVG illustration with a functional supply/cable swap, not the prototype's interactive 3D model or a real device connection.

The recorded grading mode exercises the plumbing without publishing ability scores. Live interviewer/evaluator calls use the existing audited Gemini integration. This slice did not run paid providers or establish grading quality, real hardware behavior or human audio performance. Lessons and changed executable retests for this engine remain a following slice; the current lesson generator still supports the conceptual system-design engine only.

## Technical references checked

- [nginx command switches](https://nginx.org/en/docs/switches.html): `-t` validates configuration; reload loads a new configuration. The simulator permits a valid reload without a prior test, while recording that process choice.
- [Linux unlink](https://man7.org/linux/man-pages/man2/unlink.2.html): an open unlinked file retains allocation until its last descriptor closes. The simulator models this trap rather than immediately freeing deleted log blocks.
- [Raspberry Pi vcgencmd](https://www.raspberrypi.com/documentation/computers/os.html#vcgencmd): low throttle bits indicate current conditions, high bits indicate history, and `measure_volts core` concerns VC4 core voltage. After replacing the weak supply, this fixture changes `0x50005` to `0x50000`; simulated reboot clears the historical flags when power is adequate.
- [Pi 4 datasheet](https://datasheets.raspberrypi.com/rpi4/raspberry-pi-4-datasheet.pdf): the supply/cable fixture uses a suitable 5 V / 3 A USB-C supply. It is a simplified model, not an electrical measurement or universal diagnosis of slow Pis.

## Run and verify

Use the normal root `.env`, apply Alembic `upgrade head`, then run FastAPI on 8000 and Vite on 5173 as documented in `mailbox/josh-agent/STATUS.md`. Docker is not needed.

`python -m pytest backend/tests/test_v2_pi_lab.py -q` tests the simulator, safety boundaries, reference solutions and evidence validation. `python backend/scripts/e2e.py --grep "Pi lab"` runs the complete synthetic browser journey against its own freshly migrated Tiger schema with paid providers disabled. The journey includes reload, stage gates, forged-event rejection, idempotence, competing writes, pause, and grading. Logs/screenshots remain ignored under `.artifacts/e2e`.
