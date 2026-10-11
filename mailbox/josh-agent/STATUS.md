updated: 2026-10-11T15:55:00Z
branch: josh/mvp-release-hardening (PR #16, latest 5ab8833)
doing: live free-host demo deployed; implementation release ready for human merge
next: physical device voice/whiteboard and human grading review; teammate STAR integration
blocked_on: account recovery/deletion not implemented; STAR teammate-owned
touching: nothing
release: https://prepcrew.vercel.app (Vercel production); https://prepcrew-api.onrender.com (Render Free, deployed c8f61b0). Free artifact images are ephemeral; external DB records persist. No paid disk/service created.
validation: 670 backend tests, 126 frontend tests, production build, isolated session/Pi/account browser acceptance. Live HTTPS smoke all 4 passed; live cookie/export/isolation/second-device history/direct WebSocket single-use tickets/logout revocation passed. No paid provider calls during live acceptance. Four synthetic accounts and two untouched sessions retained, all logins signed out.
frontend_update: 2026-10-11T16:01:00Z user frontend refinements committed a5ad293 and deployed production dpl_BC4KfVR8wgDJyrPwpqmJ5BMbSB2n. Build and126 frontend tests passed; live HTML/privacy/health/auth smoke passed. Served CSS and Plan bundle visibly contain latest edits. All three local subagents completed. Full MVP outstanding items unchanged.
touching_header_refresh: frontend/src/components/Shell.tsx; frontend/src/styles.css. User requested cleaner top bar and removal of Sound button; branch josh/header-refresh.
