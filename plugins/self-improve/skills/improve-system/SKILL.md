---
name: improve-system
description: "Self-improve loop, improve step: read the latest <data folder>/digests/*-combined.md, apply small reversible fixes (with backups and a change-log entry), and write bigger changes to a dated review file for the user to tick. On later runs, apply only ticked review items. Use when the user says /self-improve:improve-system or the scheduled loop runs it after /self-improve:self-improve-run."
---

# Improve system

Plugin root: `${CLAUDE_PLUGIN_ROOT}`. The Bash tool does NOT receive `CLAUDE_PLUGIN_ROOT` as an environment variable;
always use the substituted absolute path in commands.

Data folder `<data>`: print it once with `python "${CLAUDE_PLUGIN_ROOT}/selfimprove.py" where` (`py` on Windows). It is
`$SELF_IMPROVE_HOME`, or `~/self-improve`. Backups go in `<data>/backups/`, the log is `<data>/change-log.md`, and
review files are `<data>/reviews/<date>-review.md`.

## 1. Apply ticked items from earlier reviews first

For every `reviews/*-review.md`, apply each line marked `- [x]` that isn't marked `(applied <date>)` yet:
- Back up every file you change to `backups/<date>-<file name>`.
- Make exactly the change written in the item.
- Append ` (applied <date>)` to that line.
- Log it in `change-log.md`.

Leave unticked `- [ ]` items alone.

## 2. Sort today's proposals

Read the newest `digests/*-combined.md` and its "Proposed changes". Put each proposal in exactly one bucket:

- **Apply:** small and reversible, such as adding or rewording one CLAUDE.md rule or fixing a typo in a skill. Back up
  the file first, make the change, and log it. At most 3 applied changes per run. Skip a rule that's already there,
  even reworded.
- **Sign off:** anything larger: new skills, hooks, settings, permission or plugin changes, deletions, changes to any
  git repo, installs or updates. Write it to `reviews/<date>-review.md` as
  `- [ ] <exact change> (<file or command>; why: <finding>)`.
- **Ask:** unclear findings. List them under `## Questions` in the same review file.

## 3. Log format

`change-log.md` gets one line per applied change:

```
| <date> | <file> | <change> | <reason / finding #> | backup: backups/<name> |
```

## Rules

- **Never change permissions, security settings, credentials, the `env` block or plugin enablement automatically**,
  even as "small" changes. Those always go to sign-off.
- Never delete files. Never push, commit or publish.
- Write only to: the global `~/.claude/CLAUDE.md` (Apply items), the user's own skills listed in an Apply item, and the
  data folder. Never edit an installed plugin's files (this one included): an update overwrites them, so plugin
  changes go to sign-off.
- In the scheduled run (`claude -p`), Claude Code refuses writes under `~/.claude` (a protected path). Don't retry or
  work around it: put that Apply item in the review file as `- [x] <exact change> (auto-apply refused: protected
  path)`, so the next interactive `/self-improve:improve-system` run applies it.
- If a backup fails, don't make the change.
