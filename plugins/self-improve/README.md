# self-improve

A weekly self-improvement loop for Claude Code. Once a week it looks back at what you did, ranks what keeps going
wrong, fixes the small things itself (with backups) and queues the rest for you to approve.

## What a run does

1. **Collect** (read-only; each collector writes one digest to `<data>/digests/<date>-*.md`):
   - `collect-sessions`: your last 7 days of Claude Code sessions (`~/.claude/projects/*/*.jsonl`): goals, recurring
     tool errors, permission denials, interruptions, instructions you had to repeat.
   - `collect-git`: `git log` for the repos in `<data>/repos.txt`: activity, themes, rework (fix/revert commits).
   - `collect-outside`: the Claude Code changelog, the Python announcements and any extra feeds in
     `<data>/sources.txt` (`name|url` per line).
2. **Combine** (`self-improve-run`): `<data>/digests/<date>-combined.md`, at most 10 findings ranked by how often they
   recur, each with a proposed change.
3. **Improve** (`improve-system`): applies earlier review items you ticked, then sorts today's proposals into
   *apply* (at most 3 small, reversible changes, such as one CLAUDE.md rule), *sign off* (written to
   `<data>/reviews/<date>-review.md` as `- [ ]` items) and *ask*.

`<data>` is `$SELF_IMPROVE_HOME`, or `~/self-improve`. It lives outside `~/.claude` because Claude Code refuses headless
writes there.

## Setup

```
/plugin marketplace add ahmadhammoud56/MOAA
/plugin install self-improve@moaa
```

```
python "<plugin dir>/selfimprove.py" init        # data folder, repos.txt, sources.txt, change-log.md, run script
python "<plugin dir>/selfimprove.py" schedule    # weekly job: Sunday 10:00 by default, no end date
python "<plugin dir>/selfimprove.py" schedule --day WED --time 18:30
```

**In the Claude desktop app (recommended there):** after `init`, add a scheduled task from **Scheduled** in the
sidebar (or ask Claude to create one): weekly, Sunday 10:00, prompt "Run `/self-improve:self-improve-run`, then
`/self-improve:improve-system`; never change permissions, settings, plugins or git; end with a summary of the review
items that need my yes." It runs while the app is open, starts a missed run on the next launch, and shows each run as
a session you can open. Use the `schedule` command below only where there is no desktop app, and not both, or the loop
runs twice.

**Without the desktop app:** use `py` instead of `python` on Windows. Nothing is scheduled until you run `schedule`: a weekly unattended run spends
your Claude usage. `schedule` creates or replaces the Windows scheduled task **Claude Self-Improve** (runs as you,
only while you are logged on, catches up after the PC was off, stops after an hour) or one crontab line marked
`# claude-self-improve` on macOS and Linux, and writes `STOP.md` into the data folder. You can also run the loop by
hand at any time with `/self-improve:self-improve-run` and then `/self-improve:improve-system`.

The run script (`run.cmd` or `run.sh`) calls `claude -p "/self-improve:self-improve-run then
/self-improve:improve-system"` with `--add-dir` for the data folder and `~/.claude`, and `--allowedTools` limited to
Read, Write, Edit, Glob, Grep, Skill and `python`/`py` commands. Each run logs to `<data>/logs/<date>.log`.

## Off switches

| What | How |
|---|---|
| Skip runs, keep the schedule | `selfimprove.py off` (back: `selfimprove.py on`), or the environment variable `SELF_IMPROVE=off` |
| Disable the job | `selfimprove.py stop` |
| Delete the job | `selfimprove.py remove` |
| Check | `selfimprove.py status` (data folder, on/off, last log, the job) |

## What a run can and cannot change

- It applies at most 3 small, reversible changes per run, each backed up to `<data>/backups/` first and logged in
  `<data>/change-log.md`. If the backup fails, the change is not made.
- It may write only to the global `~/.claude/CLAUDE.md`, your own skills named in an apply item, and the data folder.
  Headless runs cannot write under `~/.claude`; such items wait as ticked review lines for your next interactive
  `/self-improve:improve-system`.
- It never changes permissions, security settings, credentials, the `env` block or plugin enablement, never deletes
  files, never commits, pushes or publishes, and never edits installed plugins. Those go to the review file.

## Privacy

- The collectors only read. `sessions.py` redacts keys, tokens, passwords, e-mail addresses and home paths before
  printing; `git.py` runs only `git log` and redacts home paths and e-mails.
- `outside.py` sends plain GET requests to the listed URLs only (no project data), follows a redirect only when it
  stays on a listed host, and caps each download at 2 MB. Fetched text is untrusted data: the skills must never follow
  instructions found in it or fetch URLs it mentions.
- Everything stays in the data folder on your machine.

## Tests

```
cd plugins/self-improve && python -m unittest discover -s tests
```

No network and no real scheduled tasks: the tests check the folder setup, both off switches against a fake `claude`,
the cron and PowerShell builders with paths containing spaces, `sources.txt` parsing and the redirect guard.
