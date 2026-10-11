# Vercel frontend + Render backend (no purchased domain)

Use Vercel's generated `*.vercel.app` hostname and Render's generated
`*.onrender.com` hostname. HTTP requests use Vercel's
[external HTTP rewrites](https://vercel.com/docs/routing/rewrites). Event and
voice WebSockets connect directly to Render using scoped short-lived tickets;
they do not depend on Vercel WebSocket proxy support.

The app keeps its host-only HttpOnly `SameSite=Lax` cookie on the Vercel origin.
Keep `VITE_API_URL` and `VITE_PAIR_ORIGIN` empty, and set `VITE_WS_URL` to the
Render HTTPS origin. The client requests a single-use, 45-second socket ticket
over the authenticated same-origin HTTP API, then sends it in the WebSocket
subprotocol handshake to Render. Tickets are scoped to the session and socket
channel. Pairing retains its existing capability flow. Do not move API requests
directly to Render or weaken cookie policy. Do not log ticket headers or put
session credentials in URLs.

## Render Free setup for today's temporary demo

Import the repo's `render.yaml` as a Blueprint and select Free. It prepares a
single free web service with **no persistent disk and no paid pre-deploy step**.
These files create no resources themselves. This is a temporary demo: whiteboard
PNG files under `/app/.artifacts` disappear on restarts, redeploys and idle
spin-down, while relational history remains in the external Tiger database.
Older image references can consequently stop opening after a restart. This
configuration does not meet the durable-artifact release goal.

Render Free spins down after 15 minutes without traffic; the next request can
take about a minute to wake it. Free instances can also restart and have monthly
usage limits. Open the backend health URL shortly before presenting, wait for
readiness, then run the smoke CLI: its eight-second request timeout can fail
during cold start. Do not represent Free compute as always available. Database
and AI/voice usage retain their own charges. See
[free-service limits](https://render.com/docs/free).

Supply `DATABASE_URL` for the existing Tiger/Timescale database, provider keys,
available model/voice IDs, and the final Vercel origin for **both**
`PUBLIC_BASE_URL` and `CORS_ORIGINS`. Never select a plain Render PostgreSQL
database without confirming required Timescale extensions. The backend image
includes `backend/` and `contracts/` using the repository root build context.
Its launcher uses Render's `PORT`, prepares the local artifact directory and drops privileges
before starting one uvicorn process. See [Docker on Render](https://render.com/docs/docker).

Free has no paid pre-deploy phase. The Blueprint's Docker Command is:

```sh
python deploy/render_start.py
```

Set `RENDER_MIGRATE_ON_START=true` (exact lowercase `true`, included in the
Blueprint). The launcher invokes Alembic through the current Python executable
with checked subprocess arguments before dropping privileges and starting the
API. Every instance start therefore checks/applies migrations against the external
database. A migration failure prevents serving traffic. Keep a
single instance and one deployment pointed at this schema; do not run concurrent
migration commands. Back up an existing database before deploying schema changes.
`/api/v2/health` is the database-readiness endpoint. See
[health checks](https://render.com/docs/health-checks).

For a later durable release, optionally upgrade to paid compute and a persistent
disk at `/app/.artifacts`, then move migrations to `preDeployCommand`. Paid
pre-deploy tasks run separately without disk access, which is safe for these
database-only migrations. The currently listed smallest paid web compute is
$7/month and a 1 GB disk is $0.25/month, approximately $7.25/month before taxes,
overages, database and provider charges. No upgrade is authorized for today's
free demo. See [Render pricing](https://render.com/pricing),
[pre-deploy commands](https://render.com/docs/deploys#pre-deploy-command) and
[disk limitations](https://render.com/docs/disks).

## Vercel setup and release gate

Import or link the **repository root**, leaving Vercel Root Directory empty
(or `.`), with Framework Preset Other and Node 22. The root `vercel.json` sets
`cd frontend && npm ci` for installation, `cd frontend && npm run build` for
building, and `frontend/dist` for output. Keep the entire repository available
during the build: frontend contract checks read the sibling `contracts/`
directory. Deploying only `frontend/` omits those required files. For CLI use,
link and deploy from the repository root rather than `--cwd frontend`.

The root `vercel.json` is the active deployment configuration. Its `/api/*`
rewrite targets `https://prepcrew-api.onrender.com`; update that destination if
the Render hostname changes. The nested `frontend/vercel.json` does not control
this root deployment. Set `VITE_WS_URL` to
`https://prepcrew-api.onrender.com` in Vercel's Production build environment;
keep `VITE_API_URL` and `VITE_PAIR_ORIGIN` empty. Rebuild after changing Vite
variables. No provider keys belong on Vercel. Enable only the final production
Vercel origin in backend trusted origins; preview URLs need separate explicit
authorization, not a wildcard. Ensure demo visitors can access the Vercel URL
without deployment protection.

Run `python deploy/smoke.py https://YOUR_PROJECT.vercel.app`, then register a
synthetic account and verify login/logout and authenticated history. Confirm
DevTools shows the cookie scoped to the Vercel hostname, with Secure/HttpOnly
and SameSite=Lax. Open a session and confirm **HTTP 101** for its authenticated
event and voice sockets directly to Render's `/ws/v2/` routes after ticket minting
through Vercel. Confirm missing/expired/reused tickets cannot open an owned
session, wrong-channel tickets are rejected, and logout closes the socket.
Pair a second device
using the Vercel hostname and verify live strokes plus reconnect. Keep a socket
open for a full practice session. HTTP health alone does not pass this gate.
Vercel documents a 120-second external HTTP proxy timeout; long-running work
should use the app's jobs/polling flows. Direct Render sockets bypass that HTTP
proxy. See [proxy limits](https://vercel.com/docs/limits) and
[Render WebSockets](https://render.com/docs/websocket).

## Hosted operations

For today's Free demo, inspect Render events/logs and readiness before presenting.
After any restart, verify login/history and create a fresh whiteboard snapshot;
previous local PNGs are expected to be gone. Free has no service shell/SSH or
persistent-disk backup. Back up Tiger data, but do not describe that as a complete
image backup. Do not rely on automatic uptime polling to make Free always-on.

After a future paid upgrade, monitor the final origin's `/api/v2/health` and disk
usage. Back up Tiger and the artifact disk together during maintenance, using
service shell/SSH for the disk (one-off jobs cannot see it). Keep encrypted
off-host copies and test restoration on a separate service. Disk snapshots do
not replace matched backups. Retain the previous release and a database backup
before migrations; destructive schema downgrades are intentionally unavailable.

## Alternate single-host Docker deployment

This package runs one API process with its background workers behind Caddy on
one public HTTPS origin. It builds the React app, proxies HTTP and WebSockets,
and persists whiteboard images and Caddy certificates in named volumes. It does
not provision a server, DNS, a database, email delivery or external monitoring.

## Required operator values

- A Linux host with Docker Engine and Compose v2, reachable on TCP 80 and 443.
  Point `DEMO_DOMAIN` DNS to it. UDP 443 is optional for HTTP/3.
- A backed-up Tiger/Timescale-compatible PostgreSQL database. Migrations use
  Timescale features; plain PostgreSQL is not a substitute. The database role
  must be allowed to create the selected schema and run its migrations.
- `ACME_EMAIL`, `PUBLIC_BASE_URL`, `CORS_ORIGINS`, database connection and
  provider settings from `deploy/.env.example`. Choose available model/voice
  IDs in your provider account; no model availability or quota is assumed.
- A dedicated release database/schema and disposable synthetic test accounts.
  Never point the release at an acceptance-test schema or enable auth bypass.

Copy `deploy/.env.example` to `.env.production` at the repository root, fill it
on the server and restrict it to the operator (`chmod 600 .env.production`).
It is ignored by git and excluded from Docker builds. Never put API keys in
`VITE_*`: browser settings are public. Keep the hostname settings consistent.

Run all commands from the repository root. `--env-file` supplies Compose
interpolation; service `env_file` supplies backend process settings. Both are
intentional.

```sh
docker compose --env-file .env.production config --quiet
docker compose --env-file .env.production build
# Review migrations and take a backup before this command on an existing DB.
docker compose --env-file .env.production up -d
docker compose --env-file .env.production ps -a
docker compose --env-file .env.production logs --tail=100 migrate api web
```

The one-shot migration service must succeed before the API starts. API readiness
must pass before Caddy starts. The API port is internal only; do not publish it
when trusting proxy headers. All users, paired devices and WebSockets use the
same hostname. Caddy automatically obtains and renews HTTPS certificates.

## Release verification

```sh
curl --fail https://YOUR_HOSTNAME/api/v2/health
curl --fail --head https://YOUR_HOSTNAME/
python deploy/smoke.py https://YOUR_HOSTNAME
```

`/api/v2/health` queries the database/schema version. `/api/health` is only
process liveness and cannot establish database readiness. Health does not prove
provider availability, worker progress, grading quality or speech functionality.
The smoke CLI makes exactly four read-only requests with eight-second socket
timeouts, normal certificate validation and no redirects. It checks the frontend
root/deep link, database health in live mode, and unauthenticated history denial.
It creates no accounts and makes no model calls. DNS resolution is governed by
the host resolver; socket timeouts are not a process-level execution deadline.

Using synthetic data, register, log out/in, create a plan, complete each visible
practice track, grade it, open a lesson and start its retest. Pair a real second
device over HTTPS, draw, reload both devices and reconnect. Exercise microphone,
interruption, quota fallback and typed continuation. Check downloaded artifact
images and saved history after `docker compose --env-file .env.production
restart api`. Record device/browser versions and failures; local automated
tests do not establish physical-device compatibility.

## Monitoring and failure recovery

Configure an external uptime monitor to request `/api/v2/health` every minute
and alert the operator on repeated failures. Inspect `ps -a`, recent API logs,
database connectivity and work-item progress when it alerts. Docker health
marks a container unhealthy but does **not** restart an unhealthy process;
`restart: unless-stopped` covers process exits and host restarts only. Logs are
rotated, not a centralized error-tracking service. Restrict access to logs and
avoid sharing request paths containing session or pairing identifiers.

```sh
docker compose --env-file .env.production logs --since=10m --tail=200 api
docker compose --env-file .env.production restart api
```

Recheck readiness and saved history after a restart. Retry a failed generation
using the product's retry action rather than inserting manual database rows.
Use typed conversation if speech/provider/local-model loading fails. Check
provider quota and dashboard errors before retrying provider work. Avoid retry
loops that incur charges. A dead database requires database recovery, not a
container restart loop. Maintain one API replica until multi-replica pairing,
worker leasing and recovery have been separately verified.

## Backup and restore

Back up the database **and** the artifact volume together. Configure provider
snapshots/PITR and a tested retention policy. For a consistent manual snapshot,
schedule downtime, stop `web` and `api`, and leave both stopped until the DB
backup and artifact archive finish. Use a PostgreSQL `PGSERVICE` configuration
and a protected `.pgpass` file so credentials do not appear in shell history.
The database client must match the server and support its extensions.

```sh
mkdir -p backups
docker compose --env-file .env.production stop web api
pg_dump --dbname=service=prepcrew --format=custom --file=backups/database.dump
docker compose --env-file .env.production run --rm --no-deps --user root \
  -v "$PWD/backups:/backup" api tar -czf /backup/artifacts.tgz -C /app/.artifacts .
docker compose --env-file .env.production start api web
```

If either backup command fails, retain prior backups and explicitly restart
services once safe. Encrypt archives, copy them off-host and restrict access;
they contain private user data. Do not use `docker compose down -v`: that
deletes persistent artifact and certificate volumes.

Test restores on a separate database/host first. Stop release writers, restore
the database into an empty compatible database using `pg_restore` (or provider
PITR), and restore the matching archive into an empty artifact volume:

```sh
docker compose --env-file .env.production run --rm --no-deps --user root \
  -v "$PWD/backups:/backup:ro" api sh -c \
  'tar -xzf /backup/artifacts.tgz -C /app/.artifacts && chown -R 10001:10001 /app/.artifacts'
```

Point `.env.production` at the restored database, start the reviewed matching
release, then verify readiness, login, history and images before reopening
access. A database snapshot without matching artifact files is incomplete.
Back up Caddy `/data` separately if retaining certificate state across hosts.

## Updates and rollback

Set a distinct `RELEASE_TAG` for each reviewed build and retain the previous
images and configuration securely. Back up before migrating an existing
schema. Migration downgrades are intentionally disabled; rolling the image
back does not undo database changes. For an incompatible failed migration,
restore the matched database/artifacts backup and previous release during
downtime. Do not run migrations from two deployments against the same schema.

## Validation limits

The deployment files are preparation for an operator-controlled release. This
workspace has a Docker CLI but no running Docker Engine, so container build,
Caddy certificate issuance, deployed WebSockets, backup restore and real-device
behavior must be verified on the target host before calling the demo stable.
Local validation passed: Compose parsing with the example settings; installed
project-environment dependency consistency; an isolated copy of the image's
backend/contracts layout importing the application with no secrets; and smoke
CLI success plus recorded-mode rejection using synthetic HTTP responses.
The API image includes `contracts/`: startup reads its demo board and critique
even in live mode. Omitting that directory prevents the server from starting.
Backend dependencies currently include unpinned packages; retain built images
by digest for rollback rather than assuming a later rebuild is identical.
