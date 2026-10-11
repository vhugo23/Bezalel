# Whiteboard and paired drawing

The inline board and paired board share candidate strokes through the persisted session event log. Dana's annotations remain separate. A critique snapshots exactly the current step's active saved strokes; removed, missing or extra strokes fail validation. A step change, pause, edit or changed drawing during vision prevents stale annotations from publishing. Critiques are serialized per session across API workers.

`look: "on_done"` waits for Done or an explicit spoken review request. `look: "on_pause"` also looks after six seconds without drawing, pending saves, candidate transcript activity, detected audio activity or interviewer playback/generation. This is an authored inactivity setting, not a claim of perfect speech classification. Manual controls remain available. Edit drawing invalidates the previous review; Undo/Clear and paired changes also invalidate its stroke set. A successful review with zero marks is still complete.

The exact demo board uses a labelled recorded critique. A differing board requires live Gemini; custom vision correctness and latency are not established by the recorded acceptance tests. Every critique call has a generation job and its image/transcript/stroke provenance. Target IDs are validated and geometry is computed locally.

## Pair a device

1. During a live whiteboard session, choose **On my iPad**. The QR encodes the same link shown below it. You can also type the link on the device.
2. The **Address your iPad can reach** field defaults to the current web origin. Change it to a reachable LAN or HTTPS origin when the laptop was opened through localhost. Optional `VITE_PAIR_ORIGIN` supplies a deployment default. Credentials and non-HTTP(S) origins are rejected.
3. A code expires after ten minutes and claims one paired tab. That tab holds a separate 256-bit reconnect token in session storage; the server stores its hash. The consumed code alone cannot claim a second device. The reconnect capability expires after 24 hours or when the session ends. Reload in the same tab works; a new tab needs a new code.
4. The paired page replays saved candidate strokes and separate Dana annotations, offers pen/box/arrow and Undo/Clear, follows the current scenario step, and blocks drawing outside the whiteboard or while paused. Pending strokes are journaled in the tab and replayed with the same IDs after reconnect. A lost confirmation does not create a duplicate stroke.

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

The isolated Tiger/Playwright harness covers a whiteboard at step 0, actual QR rendering, paired drawing without randomUUID, same-tab reconnect, simulated lost-acknowledgement replay, rejected second-device reuse, expired-code rejection, paired Undo/Clear, separate annotation pixels, edit/reload, pause review and removed-stroke rejection. The tests use synthetic/recorded fixtures and delete their own test schema afterwards. They do not claim to be physical-device or live-vision field tests.
