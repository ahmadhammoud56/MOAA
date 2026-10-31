---
name: fold-trial
description: Measure whether a council of subagents beats one agent loop on your own tasks, per unit of cost - the same frozen tasks run solo and as a council, judged blind, with the tasks whose outcome flips. Use when the user asks whether subagents or the council are worth it, or invokes /agent-arena-mode:fold-trial.
argument-hint: "[--recipe TEAM] [--repeats K] -- TASKS or a tasks.json path"
---

# Agent Arena: fold trial

Request: `$ARGUMENTS`. `T` means `python "${CLAUDE_PLUGIN_ROOT}/scripts/trial.py"` (`py` on Windows), one standalone
command.

Anthropic's guidance: one agent loop with the right skills often matches a lead with subagents, which pay for
themselves only through context isolation, real parallelism or conflicting tools. This trial measures that on the
user's own work instead of assuming it.

1. **Tasks.** Up to 10 frozen tasks with a checkable pass condition (planted bugs, a reference answer, tests), as
   `tasks.json` `[{"id", "brief", "rubric", "pass"}]` in a fresh folder under the session scratchpad. Use the user's
   tasks; otherwise propose some and get their OK.
2. **Plan and cost.** `T plan --arms solo,council --tasks <tasks.json> --out <dir> [--repeats K]`. It prints the run
   count and expected tokens, and refuses more than 40 runs. Show the cost line to the user and get a yes before any
   run; raise `--max-runs` only with that yes.
3. **Run each cell** with the byte-identical brief:
   - `solo`: one `general-purpose` agent, no further delegation, the relevant role card pasted in as guidance.
   - `council`: `/specialist-council:specialist-council` with the named recipe (or automatic team), spawn rule off for
     the trial so the council always convenes.
   Note tokens and wall time from each run's result.
4. **Judge blind.** `agent-arena-mode:agent-arena-judge` gets the task, rubric, pass condition and the answers under
   their blind labels only. It returns a 0-100 score and pass or fail.
5. **Record.** `T record --dir <dir> --cell ID --score S [--passed] --tokens N --seconds S`.
6. **Report.** `T summary --dir <dir>`: per arm mean score, pass rate, tokens, time, and the flipped tasks. Read the
   flips and say why they flipped. Recommend folding (solo) for the task type when the council adds under 5 points
   and no passes; keep the council where it wins. Changing defaults (the council's spawn rule, a recipe) is the
   user's decision.
