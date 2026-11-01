# Goal Meter (mod)

A Claude Code mod that puts a progress bar on `/goal`.

- When the goal names `.claude/long-task/<slug>`, the bar counts the brief's acceptance items and the rows of
  `checks.md` whose last verdict says verified.
- When it names `.claude/loop/<slug>`, it shows karpathy-loop attempts and the best value against the target.
- Otherwise it counts turns against "Stop after N turns" in the goal, or just turns.
- Status line (every surface), a band above the prompt (terminal, desktop), `/goal-meter` opens a panel.
- Off: `MOAA_GOAL_METER=off`.

Readings also go to `~/.claude/moaa-mods/meters/<session>.goal.json` for the strata Meters panel.
