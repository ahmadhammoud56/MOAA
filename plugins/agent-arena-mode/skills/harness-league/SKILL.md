---
name: harness-league
description: Compare agent harnesses (Claude Code, Codex, Gemini CLI, OpenCode through allies) on the same frozen tasks, judged blind, with score, pass rate, cost and the tasks where they differ - real data for routing work to allies. Use when the user asks which agent or harness is best for a kind of task, or invokes /agent-arena-mode:harness-league.
argument-hint: "[--arms claude,codex,gemini,opencode] [--repeats K] -- TASKS or a tasks.json path"
---

# Agent Arena: harness league

Request: `$ARGUMENTS`. `T` means `python "${CLAUDE_PLUGIN_ROOT}/scripts/trial.py"` (`py` on Windows), one standalone
command. The same model can score very differently in two harnesses (tools, prompts, loop limits), so measure on the
user's tasks before routing work.

1. **Arms.** `claude` (this session's Agent tool) plus the allies members that `allies.py doctor` reports ready
   (`/allies:allies`). Leave out members that are not ready, and say so.
2. **Tasks.** Up to 10 frozen, read-only tasks with a checkable pass condition, as `tasks.json`
   `[{"id", "brief", "rubric", "pass"}]` in a fresh scratchpad folder. Read-only, because allies members answer
   without writing to the user's tree; a task that needs edits runs in allies worktrees (`allies.py run --write`).
   Keep secrets and private data out of the briefs: the briefs leave the machine for other providers.
3. **Plan and cost.** `T plan --arms <arms> --tasks <tasks.json> --out <dir> [--repeats K]`; show the run count and
   token line and get the user's yes before running (more than 40 runs needs `--max-runs` and an explicit yes).
4. **Run each cell** with the byte-identical brief: `claude` through a `general-purpose` agent; an ally through
   `allies.py ask <member> --task-file <brief file>`. Note tokens where the harness reports them, and wall time.
5. **Judge blind** with `agent-arena-mode:agent-arena-judge`: answers under blind labels only, never the harness name.
   Then `T record --dir <dir> --cell ID --score S [--passed] --tokens N --seconds S`.
6. **Report** `T summary --dir <dir>`: the table per harness and the flipped tasks with a reason each. Suggest routing
   (which harness for which task type) only as far as the sample supports; with 10 tasks, call it a first signal.
