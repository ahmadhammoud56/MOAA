---
name: effort-trial
description: Measure whether council roles find more at a higher effort than at a lower one, per unit of cost, and suggest each role's effort preset. Use when the user asks to tune council effort or model costs, or invokes /agent-arena-mode:effort-trial.
argument-hint: "--roles r1,r2 [--efforts medium,high] [--repeats N] -- TASKS or a tasks.json path"
---

# Agent Arena: effort trial

Request: `$ARGUMENTS`. Plugin root: `${CLAUDE_PLUGIN_ROOT}`. Use the substituted absolute path in commands.

Effort is a cost lever, and lowering it can lose real findings, so measure instead of guessing.

1. **Tasks.** Use tasks with checkable findings: planted bugs, known errors, a reference answer. Write
   `tasks.json` as `[{"id", "brief", "rubric", "expected_findings"}]` in a fresh folder under the session
   scratchpad. Two to four tasks per role give a first signal; say how small the sample is.
2. **Plan.** `python "${CLAUDE_PLUGIN_ROOT}/scripts/effort.py" plan --roles ROLES --efforts medium,high --tasks
   <tasks.json> --out <folder>`. It prints every cell (role, effort, task) in shuffled order with a blind label.
3. **Run.** For each cell, dispatch `specialist-council:council-<role>` with the task's brief, byte-identical across
   cells of that task, and the cell's effort in the Agent tool's per-call `effort` field. Launch independent cells
   together. Note the tokens each run reports.
4. **Judge blind.** Give `agent-arena-mode:agent-arena-judge` the task, rubric and the answers under their blind
   labels only, never role or effort. Get a 0 to 100 score and the count of correct findings per answer.
5. **Record.** `python ".../effort.py" record --dir <folder> --cell ID --score S --findings N --tokens T`.
6. **Summarize.** `python ".../effort.py" summary --dir <folder>`. It keeps the cheaper effort unless the dearer one
   adds at least 5 points of score or 25% more findings. Report the table and the suggestion. Change a role's preset
   in `specialist-council/profile.json` (then `scripts/models_doc.py`) only after the user agrees.
