# Whiteboard and paired drawing

Both boards are [Excalidraw](https://github.com/excalidraw/excalidraw) (MIT, `@excalidraw/excalidraw` 0.18.1), loaded lazily. Candidates get shapes, labelled boxes, arrows that stay attached, lines, freehand, text, select/move, undo and zoom. Images, frames and embeds are disabled or refused.

The inline board and paired board share candidate elements through the persisted session event log. Each `stroke` event holds one saved version of one Excalidraw element (`{id, version, element}`, validated by `BoardElement`). The newest version of an id wins and an `isDeleted` version removes it. A retried version is idempotent; an older or forked version is refused with 409, and a batch (`POST /sessions/{id}/board/elements`, up to 200) is saved whole or not at all. Edits are saved after the pointer settles, not on every move, and a version bump that changes nothing visible is not saved. A small pill in the board corner shows Saved / Saving / Not saved (tap to retry); saving never shifts the layout.

Dana's annotations remain separate: they are drawn as locked, local-only Excalidraw elements and are never saved as candidate work or included in the critique PNG. A critique snapshots exactly the current step's active saved elements (as the server holds them); removed, missing, extra or older-version elements fail validation. Sessions recorded before Excalidraw still display: their fixed-board strokes are converted for viewing (`legacyToSkeletons`), as are the demo board and circuit stamps. A step change, pause, edit or changed drawing during vision prevents stale annotations from publishing. Critiques are serialized per session across API workers.

`look: "on_done"` waits for Done or an explicit spoken review request. `look: "on_pause"` also looks after six seconds without drawing, pending saves, candidate transcript activity, detected audio activity or interviewer playback/generation. This is an authored inactivity setting, not a claim of perfect speech classification. Manual controls remain available. Edit drawing invalidates the previous review; Undo/Clear and paired changes also invalidate its stroke set. A successful review with zero marks is still complete.

The exact demo board uses a labelled recorded critique. A differing board requires live Gemini; custom vision correctness and latency are not established by the recorded acceptance tests. Every critique call has a generation job and its image/transcript/stroke provenance. Target IDs are validated and geometry is computed locally.

## Pair a device

1. During a live whiteboard session, choose **On my iPad**. The QR encodes the same link shown below it. You can also type the link on the device.
2. The **Address your iPad can reach** field defaults to the current web origin. Change it to a reachable LAN or HTTPS origin when the laptop was opened through localhost. Optional `VITE_PAIR_ORIGIN` supplies a deployment default. Credentials and non-HTTP(S) origins are rejected.
3. A code expires after ten minutes and claims one paired tab. That tab holds a separate 256-bit reconnect token in session storage; the server stores its hash. The consumed code alone cannot claim a second device. The reconnect capability expires after 24 hours or when the session ends. Reload in the same tab works; a new tab needs a new code.
4. The paired page is the same Excalidraw board. It replays saved candidate elements and separate Dana annotations, follows the current scenario step, and is read-only outside the whiteboard or while paused. Unconfirmed element versions are journaled in the tab and resent as `elements` batches after reconnect; the server echoes each batch id in its `ack` or `error`. A lost confirmation does not create a duplicate version, and an edit the laptop saved first wins.

Device connections use a database heartbeat/connection lease rather than occupying a database connection for their entire lifetime. A new connection with the same token waits for disconnect or a stale lease; an old connection cannot overwrite the new connection's status.

## Local network setup

Normal development remains loopback-only. To test drawing on a trusted local network, run the frontend explicitly:

```powershell
cd frontend
npm run dev -- --host 0.0.0.0
```

Keep the backend on 127.0.0.1:8000; Vite proxies `/api` and `/ws`. Allow the chosen web port through the host firewall if necessary, and set the pairing address to `http://<laptop-LAN-address>:5173`. Leave VITE_API_URL empty for the same-origin proxy. Plain HTTP drawing uses `crypto.getRandomValues`, which works in an insecure context; microphone access still needs localhost or HTTPS. See [MDN getRandomValues](https://developer.mozilla.org/en-US/docs/Web/API/Crypto/getRandomValues) and [randomUUID](https://developer.mozilla.org/en-US/docs/Web/API/Crypto/randomUUID). QR generation uses the documented browser API from [node-qrcode](https://github.com/soldair/node-qrcode).

Production needs HTTPS and websocket reverse proxying. Physical Safari/iPad/Pencil and real room-audio testing have not been performed. The app's account/authorization slice remains necessary before public rollout; a trusted-LAN drawing check does not establish public access security.

## Verification

The isolated Tiger/Playwright harness covers a whiteboard at step 0, actual QR rendering, drawing with the Excalidraw toolbar on the paired page without randomUUID, same-tab reconnect, simulated lost-acknowledgement replay, rejected second-device reuse, expired-code rejection, paired erase, Dana's marks on both boards, edit/reload, pause review, stale/forked version refusal, atomic batches and removed-element snapshot rejection. The tests use synthetic/recorded fixtures and delete their own test schema afterwards. They do not claim to be physical-device or live-vision field tests.
