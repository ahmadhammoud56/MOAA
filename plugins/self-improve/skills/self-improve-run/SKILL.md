---
name: self-improve-run
description: "Self-improve loop orchestrator: run the three collectors (collect-sessions, collect-git, collect-outside) in order, then write <data folder>/digests/<date>-combined.md with the top findings ranked by how often they recur. Use when the user says /self-improve:self-improve-run, 'run the self-improve loop', or when the scheduled task runs it."
---

# Self-improve run

Plugin root: `${CLAUDE_PLUGIN_ROOT}`. The Bash tool does NOT receive `CLAUDE_PLUGIN_ROOT` as an environment variable;
always use the substituted absolute path in commands.

Data folder: print it once with `python "${CLAUDE_PLUGIN_ROOT}/selfimprove.py" where` (`py` on Windows), as one
standalone command. It is `$SELF_IMPROVE_HOME`, or `~/self-improve`. Below, `<data>` means that folder.

1. Run the collectors in this order, each as its own skill invocation, and let each write its own digest for today:
   1. `self-improve:collect-sessions` → `<data>/digests/<date>-sessions.md`
   2. `self-improve:collect-git` → `<data>/digests/<date>-git.md`
   3. `self-improve:collect-outside` → `<data>/digests/<date>-outside.md`

   If a collector fails, note it and carry on with the others. Don't retry more than once.

2. Read the three digests for today, plus the previous combined digest if there is one, so you can tell new findings
   from recurring ones. Write `<data>/digests/<YYYY-MM-DD>-combined.md`:

   ```markdown
   # Combined digest <date>
   Sources: sessions ✓/✗ · git ✓/✗ · outside ✓/✗

   ## Top findings (ranked)
   | # | Finding | Evidence (count) | Seen in | New or recurring |
   |---|---|---|---|---|
   | 1 | <finding> | <the count or quote that proves it> | sessions, git | recurring since <date> |

   ## Proposed changes
   - <for each top finding, the smallest change that would address it, and the file it would touch>
   ```

   Rank by how often a finding recurs (its count), then by how many sources show it, then by whether it recurred in
   the previous combined digest. Keep at most 10 findings.

3. Rules:
   - Use the digests only. Don't open raw transcripts, repos or web pages.
   - Never copy secrets.
   - Change nothing here: deciding and applying changes is `self-improve:improve-system`'s job.
