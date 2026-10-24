---
name: karpathy-loop
description: Improve something against a fixed number - edit, measure with a script the agent may not change, keep the change if the number improved, otherwise revert, repeat until the budget runs out (after Karpathy's autoresearch). Use for tuning code speed, model loss, test pass rate, file size or any measurable target, or when the user invokes /agent-arena-mode:karpathy-loop.
argument-hint: "--metric \"CMD\" [--direction min|max] [--max-iters N] [--max-minutes M] -- GOAL"
---

# Agent Arena: Karpathy loop

Request: `$ARGUMENTS`. `L` means `python "${CLAUDE_PLUGIN_ROOT}/scripts/loop.py"` (`py` on Windows), one standalone
command. Loop folder: `.claude/loop/<slug>/` in the project.

The loop runs unattended because a number, not a reader, judges each attempt. Everything here protects that number.

1. **Metric first.** Agree with the user on a command that prints one number and finishes in minutes (a benchmark, a
   validation score, failing-test count, bundle size). The metric script, its data and the tests it uses are fixed:
   never edit them during the loop. If none exists, write it with the user before starting, and commit it.
2. **Set up.** In a git repository with a clean working tree (commit or stash the user's work first; ask if unsure),
   run `L init <dir> --metric "<cmd>" --direction min|max --max-iters N [--max-minutes M]`. It measures the baseline.
   Fill in `program.md` with the user: the goal, which files are editable, the rules and the stop condition. That file
   is the human's artifact; you follow it and do not edit it.
3. **Loop.** For each attempt:
   - Make one small change to the editable files only.
   - `L record <dir> "<what you changed>"`:
     - `KEEP` (exit 0): commit with that description.
     - `DISCARD` (exit 3): revert only this attempt's edits (`git checkout -- <files you edited>`; delete files you
       created), then try something else.
     - `STOP` (exit 4): stop.
   - Do not repeat an idea already in `results.tsv` without a reason; read it every few attempts.
4. **Finish.** Run `L status <dir>`. Report the baseline, the best value, attempts and kept changes, and the commits
   that made the difference. Leave `results.tsv` as the evidence.

Parallel version: several agents, each in its own worktree with its own loop folder and the same metric (War Room
does the worktrees). Record what each one learns in the shared findings graph (`/strata:graph`), not only in its
transcript, and merge only kept commits that still pass the metric together.
