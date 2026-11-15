---
name: collect-sessions
description: "Self-improve loop, collector 1: summarize the last 7 days of Claude Code sessions into <data folder>/digests/<date>-sessions.md (goals, what worked, what failed or was retried, instructions the user had to repeat). Use when running /self-improve:self-improve-run or when asked to collect or summarize recent sessions."
---

# Collect sessions

Plugin root: `${CLAUDE_PLUGIN_ROOT}`. The Bash tool does NOT receive `CLAUDE_PLUGIN_ROOT` as an environment variable;
always use the substituted absolute path in commands. `<data>` is the folder printed by
`python "${CLAUDE_PLUGIN_ROOT}/selfimprove.py" where` (`$SELF_IMPROVE_HOME`, or `~/self-improve`).

1. Run this as one standalone command (`py` instead of `python` on Windows):

   ```
   python "${CLAUDE_PLUGIN_ROOT}/collectors/sessions.py" --days 7
   ```

   The script reads only `~/.claude/projects/*/*.jsonl` and skips subagent files, claude-mem observer sessions and
   automated probes. It redacts keys, tokens, passwords, e-mail addresses and home paths before printing anything.

2. From that output only, write `<data>/digests/<YYYY-MM-DD>-sessions.md`, using today's local date:

   ```markdown
   # Sessions digest <date> (last 7 days)
   <N> sessions, <M> projects.

   ## Per project
   ### <project>
   - Goals: <the main things worked on, merged and shortened>
   - Worked: <what visibly succeeded, if the output shows it>
   - Failed or retried: <recurring tool errors, denials, interruptions, with counts>
   - Repeated instructions: <prompts the user had to give more than once>

   ## Cross-project patterns
   - <the 3 to 8 findings that recur most, each with its count and the evidence line>
   ```

   Group by project, not by individual session; with dozens of sessions a week, per-session entries would bury the
   patterns. Keep the whole digest under about 150 lines.

3. Rules:
   - Never copy secrets. If any line still looks like a key, token or password, replace it with `[redacted]`.
   - Don't open the raw transcripts to "add detail". The script output is the only input.
   - Read-only, apart from writing the digest file.
