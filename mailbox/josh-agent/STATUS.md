updated: 2026-10-11T15:55:00Z
branch: josh/mvp-release-hardening (PR #16, latest 5ab8833)
doing: live free-host demo deployed; implementation release ready for human merge
next: physical device voice/whiteboard and human grading review; teammate STAR integration
blocked_on: account recovery/deletion not implemented; STAR teammate-owned
touching: nothing
release: https://prepcrew.vercel.app (Vercel production); https://prepcrew-api.onrender.com (Render Free, deployed c8f61b0). Free artifact images are ephemeral; external DB records persist. No paid disk/service created.
validation: 670 backend tests, 126 frontend tests, production build, isolated session/Pi/account browser acceptance. Live HTTPS smoke all 4 passed; live cookie/export/isolation/second-device history/direct WebSocket single-use tickets/logout revocation passed. No paid provider calls during live acceptance. Four synthetic accounts and two untouched sessions retained, all logins signed out.
