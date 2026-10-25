# Team

Several people, each on their own Claude account, work on one git repository together. The team board splits the
work between them: tasks with claims, path locks, dependencies and handoffs, messages, and a shared decision log.
Each member's Claude Code reads the board at session start and hears about new messages and assignments as they
come in.

## Accounts and usage

Every member runs Claude Code on their own account and plan, and the board never shares credentials or routes one
account's usage through another; Anthropic's terms do not allow that. What the board does is split the work, so
three members on three plans get roughly three plans' worth of work done on one project, without two of them
doing the same task. A Claude Team or Enterprise plan is the official way to pool usage under one bill, and the
board works the same there.

## How it works

- **Its own branch.** The board is an orphan branch (`team-board`) of the shared repository, checked out in a hidden
  worktree at `.git/team-board`. Board commands commit and push small JSON files there; they never touch your
  working files, your index or your code branches.
- **No double claims.** Every change is applied to the newest board, committed and pushed. When someone else pushed
  first, the change is redone on their board, so a task that was claimed a moment ago fails cleanly with "claimed
  by NAME" instead of being taken twice.
- **Tasks:** `open`, `claimed`, `review`, `done` or `blocked`, with an owner, an optional assignee, `paths` that are
  locked while the task is active, and `after` dependencies. A claim lasts 24 hours from the owner's last update;
  after that anyone can take it over. A handoff reopens the task with notes for whoever claims it next.
- **Messages and notes:** `send NAME|all`, `inbox` (read state is kept per clone), and `note` for decisions.
- **Hooks:** SessionStart fetches the board (8 s at most; offline it uses the last one) and tells Claude whose tasks
  are whose, what is free for this member and what is unread. Later prompts refresh the board in the background at
  most every five minutes and announce only new messages and new assignments. Teammates' text is marked as coming
  from teammates, not from the user, so Claude asks before acting on requests in it. Repositories without a board
  get nothing.

## Setup

One member, once per repository (the remote must be one everyone can push to):

```
python team.py init                  # creates team-board on origin
python team.py join alice --role "lead, solver" --capacity "Max plan, evenings"
```

Every other member, in their own clone:

```
python team.py init                  # finds team-board on origin and checks it out
python team.py join bob --role "meshing"
```

Or just ask Claude: "set up the team board and add me as bob".

## Commands

```
python team.py board [--json]                     members, tasks by status, notes, unread count
python team.py add "TITLE" [--detail D] [--paths P ...] [--after ID ...] [--assign NAME]
python team.py claim [ID]                         the next free task (yours first) or that one; prints the branch
python team.py update ID --status review --note "PR #12"
python team.py handoff ID "what is done, what is next"
python team.py send bob "please review PR 12"     python team.py send all "freeze on Friday"
python team.py inbox [--all]                      python team.py note "We use SI units everywhere"
python team.py sync | whoami | on | off           TEAM_BOARD=off silences the hooks for one shell
```

A task ID can be shortened to any unique prefix. Without a remote (`init` in a repository with none) the board is
local, which suits several accounts on one machine.

## Limits

- Everyone needs push access to the remote; the board adds a commit per change on its own branch.
- Path locks are advisory: they stop claims, not edits. Code still meets in pull requests as usual.
- Read state of messages is per clone. Strata memory and handoffs stay with each member; share what matters with
  `note`, a task's handoff, or the repository itself (which each member's project RAG indexes).

MIT licensed; see [LICENSE](LICENSE). Part of [MOAA](https://github.com/ahmadhammoud56/MOAA).
