# Collision Guard (mod)

A Claude Code mod that stops two Claude chats from overwriting each other's files.

- Every chat writes a heartbeat (folder, branch) and a claim for each file it edits to
  `~/.claude/moaa-mods/claims.json`. A Write, Edit or NotebookEdit of a file another live chat edited in the last 10
  minutes is refused, naming that chat, its folder and branch, and suggesting a separate worktree (War Room,
  `allies.py run --write`) or a team-board claim (`team.py claim`).
- Claims expire after 10 minutes and chats count as gone after 3 minutes without a heartbeat, so a crashed chat never
  locks a file. It also warns when another chat in the same folder switches branch.
- `/collision-guard` opens a panel listing the live chats (this folder first), their branches and the files they hold.
- `MOAA_COLLISION_GUARD=warn` only warns; `off` turns it off. A failing guard never stops an edit.
- Known limit: Windows 8.3 short paths (`DEATHS~1`) and long paths of the same file may not match.
