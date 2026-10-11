# Accounts and saved practice

Normal `/api/v2` operation requires a signed-in account. Register or sign in in the
React app, then build a plan. Practice history lists saved sessions with cursor
pagination and resumes an interview or opens its review. Signing in on a clean
second browser restores the latest ready plan from Tiger Data. The browser's
stored user ID is a draft/cache key, never an authorization credential.

## Run and configuration

Apply Alembic through `010_accounts`, install `backend/requirements.txt`, and start
Python/Uvicorn and Vite as documented in `mailbox/josh-agent/STATUS.md`. Docker is
not required. Existing root `.env` loading and provider settings are unchanged.

- Local development: `http://127.0.0.1:5173` with Vite's API/WS proxy.
- HTTPS deployment: set `PUBLIC_BASE_URL` to the exact frontend origin,
  `AUTH_COOKIE_SECURE=true`, and `CORS_ORIGINS` to exact trusted origins. Use an
  HTTPS proxy for HTTP and WebSockets. Do not use wildcard origins or enable
  untrusted sibling domains. Server configuration is not exposed in `VITE_*`.
- Same-origin hosting/proxying is the default. If using a separate API origin,
  the frontend sends credentialed requests; playback uses credentialed audio.
  Cross-site third-party cookie restrictions still apply, so prefer one origin.
- `LEGACY_API_ENABLED` defaults to false. Legacy `/api/*` and `/ws/*` product
  routes are disabled because they do not enforce v2 ownership or generation
  auditing. `/api/health` remains available. The legacy data is preserved. Do not
  enable those routes on a public deployment.

## Access policy

Passwords use Argon2id (`argon2-cffi==25.1.0`), with bounded off-loop password work.
Registration uses a new random server user ID. Email is a normalized sign-in
identifier; no verification email or password-reset email is sent. Email
verification/recovery and human security review remain release work.

Login issues a fresh 256-bit opaque token in an HttpOnly, SameSite=Lax cookie,
secure when configured for HTTPS. Only its SHA-256 hash is stored in Tiger Data.
Sessions expire after 14 days, are capped at ten per account, and are revocable.
Successful login replaces the current browser's old token. Sign out revokes this
browser's token; other devices remain signed in. Voice and transcript sockets
recheck account validity every 15 seconds and cancel their handlers after
revocation/expiry, including when idle. Account soft deletion invalidates cookies.

All plan/session/source/job/artifact reads and writes check authenticated
ownership. Starting a session and retest also checks the referenced track/parent.
Client user IDs must match the authenticated account; unknown/foreign resources
return the same 404. Binary imports, PNGs, speech and both owner sockets are
protected. Responses containing private workspace data use `Cache-Control:
no-store`. Account changes unmount session audio, cancel/clear query caches and
reset the local draft. Other tabs refresh after account-change notifications.

State-changing HTTP requests require `X-PrepCrew-Request: 1`; the app sends it.
Requests with an Origin must match the exact configured allowlist. Cross-origin
browser requests without Origin are also rejected using Fetch Metadata, so a
navigation/image cannot trigger a protected GET review or speech request.
Native clients use the same cookie and protection header. The API does not trust
request-body identity or forwarded headers as ownership credentials.

Authentication attempts use atomic 15-minute database windows shared across
workers: 12 per normalized email and 40 per client IP. Keys are hashes; neither
passwords nor raw addresses enter this table. Expired windows/sessions are pruned
on subsequent authentication activity. These conservative hackathon limits are
not a substitute for production edge limits/abuse monitoring. Configure trusted
proxy handling deliberately before deployment; do not trust arbitrary XFF input.

The paired iPad remains a separate limited drawing capability with its existing
one-use code/private reconnect token, expiry, lease and stroke-only replay. It
does not receive account credentials, transcript turns or permission to create
plans/jobs. Pairing is issued by an authenticated session owner. Signing out of
the laptop does not revoke an already paired device; ending the interview or its
device expiry does. Account/data erasure must revoke these capabilities too.

## Existing workspace records

Previously created browser-local workspaces and legacy tables are retained.
Public registration cannot claim them by supplying their user ID or an email.
To attach an existing v2 workspace, an operator with trusted local database
access can run:

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python backend/scripts/bind_account.py --user-id EXISTING_USER_ID
```

The tool prompts for the new email and password (not command-line secrets),
requires the exact workspace ID, and refuses an existing account/email. Confirm
ownership outside the public app before using this operator-only tool. It adds
credentials to that user without rewriting their sessions/evidence or merging
accounts. It does not infer ownership from a git identity.
Before clearing a pre-account draft, the app retains only its workspace ID in
browser storage as `prepcrew-legacy-workspace-id` for this operator lookup; it
does not retain the old transcript/draft there or make the ID an access token.

## Verification

`backend/tests/test_v2_auth.py` covers HTTP ownership, client-identity forgery,
binary/JSON CSRF, trusted CORS, legacy shutdown, owner socket access/revocation,
pair capabilities and the guarded test bypass. `verify_auth.py` runs on a fresh
disposable Tiger schema and verifies actual password/token hashes, foreign
artifact/job/source denial, two-page history, cookie expiry/revocation, duplicate
registration and shared rate limits.

```powershell
$env:PYTHONPATH='backend'
.\.venv\Scripts\python backend/scripts/e2e.py --auth accounts.spec.ts
```

This separate browser journey keeps authentication **enabled**. It exercises
registration, a saved interview, two-account isolation, a clean second device,
logout/replay rejection and browser cache reset. All identities/content are
synthetic; providers are disabled. Normal legacy browser journeys may bypass auth
only when all of these hold: explicit `V2_AUTH_TEST_BYPASS=true`, a uniquely named
`prepcrew_e2e_*` schema, `DEMO_MODE=true`, and all three provider keys blank. The
flag cannot disable authentication on the normal `prepcrew` schema.

Not yet completed: account recovery/verification, profile preferences, full
export/erasure reconciliation, public HTTPS hosting and external security review.

Implementation references: [Argon2 PasswordHasher](https://argon2-cffi.readthedocs.io/en/stable/api.html),
[Starlette cookie attributes](https://starlette.dev/responses/),
[OWASP CSRF custom-header and Fetch Metadata guidance](https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html).
