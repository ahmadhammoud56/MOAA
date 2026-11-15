---
name: collect-git
description: "Self-improve loop, collector 2: summarize the last 7 days of git history in the repos listed in <data folder>/repos.txt into <data folder>/digests/<date>-git.md. Read-only. Use when running /self-improve:self-improve-run or when asked to collect recent git activity."
---

# Collect git activity

Plugin root: `${CLAUDE_PLUGIN_ROOT}`. The Bash tool does NOT receive `CLAUDE_PLUGIN_ROOT` as an environment variable;
always use the substituted absolute path in commands. `<data>` is the folder printed by
`python "${CLAUDE_PLUGIN_ROOT}/selfimprove.py" where` (`$SELF_IMPROVE_HOME`, or `~/self-improve`).

1. Run this as one standalone command (`py` instead of `python` on Windows):

   ```
   python "${CLAUDE_PLUGIN_ROOT}/collectors/git.py" --days 7
   ```

   The script runs only `git log` on the repos in `<data>/repos.txt`. It never writes, fetches, pulls, resets, deletes
   or pushes. To add or remove repos, the user edits `<data>/repos.txt`. If the script says there is no repo list,
   write a one-line digest saying so.

2. From that output only, write `<data>/digests/<YYYY-MM-DD>-git.md`, using today's local date:

   ```markdown
   # Git digest <date> (last 7 days)
   ## <repo>
   - Activity: <commits, files, busiest areas>
   - Themes: <what the work was about, from the commit subjects>
   - Rework: <fix/revert/retry commits and what they suggest>
   - Hygiene: <generated, runtime or oversized files being committed, if any>
   ## Patterns
   - <findings worth acting on, with evidence>
   ```

   Keep it under about 80 lines.

3. Rules:
   - Read-only: run no git command other than the script.
   - Don't copy e-mail addresses or secrets. The script already redacts home paths and e-mails.
