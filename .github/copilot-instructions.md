# Instructions for Copilot

This repo uses a mailbox for agent-to-agent messages. Follow the rules in `AGENTS.md` (repo root) and `mailbox/README.md`.

Short version:

1. Work out who you are: run `git config user.email` and look it up in the table in `AGENTS.md`. If the email is not listed, do not write to the mailbox except a block in `mailbox/HUMAN.md`, and tell the user.
2. Read your inbox in `mailbox/<your-name>/inbox/` at the start of a session and before you finish.
3. Send messages as new files in the other agent's inbox. Never edit a file you did not create.
4. No secrets, no invented numbers, no pushing to `main`, no deploying.

If you cannot run commands (plain chat mode), say so and ask the user to run `git config user.email` and paste the result.
