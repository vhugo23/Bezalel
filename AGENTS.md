# Agent instructions

You are one of four team agents.

**Stop check, first and again after every `git pull`:** if `mailbox/STOP` exists, or `mailbox/<your-name>/STOP` exists, do nothing except tell your user "the mailbox is stopped". Do not read inboxes, edit code, commit or push. A human removes the file to resume. You still may read `mailbox/HUMAN.md`.

Before anything else:

1. Run `git config user.email` and find it in the table below. That row is who you are. Use that name for your inbox (`mailbox/<name>/inbox`) and in the `from:` of every message.
2. If the email is not in the table, you do not know who you are. Write nothing to the mailbox except a block in `mailbox/HUMAN.md`, then stop and tell your user.
3. Read `mailbox/README.md` and follow it. Check your inbox at the start of each session and before you finish.

| Agent | Git emails | GitHub login |
|---|---|---|
| trey-agent | kerrydedeiii@gmail.com, 145514260+KTreyD@users.noreply.github.com | KTreyD |
| hugo-agent | 124480267+vhugo23@users.noreply.github.com | vhugo23 |
| shamah-agent | shamahllhama@gmail.com | shamahamichoh |
| josh-agent | eworojoshua@gmail.com | JoshuaEworo |

This identifies you honestly. It does not prove it: anyone can set any git email. If `git config user.name` clearly disagrees with the row (for example the email says josh but the name says Trey), stop and add a block to `mailbox/HUMAN.md`.
