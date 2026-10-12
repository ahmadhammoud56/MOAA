---
name: war-room
description: Run a War Room - a team of real, parallel Claude Code workers for a giant or multi-workflow job, with Specialist Council roles, per-role plugins and permissions, a shared task and message bus, usage-limit failsafes, tiled consoles and a live dashboard. Use only when the user asks for War Room / war mode or explicitly wants several Claude instances working in parallel on one large job. Not for ordinary tasks - it costs far more than subagents.
---

# War Room

You are the orchestrator. The workers are separate `claude` background sessions; you steer them only through
`warroom.py` (the bus and the conductor). Never type into a worker's console and never launch workers without the
user's confirmation of the preview.

`WR` below means `python "${CLAUDE_PLUGIN_ROOT}/warroom.py"`. Run every `WR` command as one standalone command (no
`cd`, `&&` or pipes): routine subcommands are pre-approved by the MOAA installer, while `toggle`, `launch`, `integrate`,
`finish`, `shutdown` and `approve` ask for permission on purpose.

## 1. Gate

1. `WR toggle status`. If war mode is off, ask the user to arm it on the War Room app's master switch (`WR app`
   opens it) or approve `WR toggle on`. Never turn it on silently. To show the user what a run looks like first,
   `WR demo` plays a simulated run in the app at no token cost. A finished run can be replayed from the app's History.
2. Check the job is big enough: several independent streams of work, or work that needs audits between steps. If a few
   subagents would do, say so and stop.

## 2. Plan

Write a plan JSON (anywhere in the scratchpad) and run `WR plan <file>`:

```json
{
  "name": "short-name",
  "goal": "One paragraph: what done looks like.",
  "project": "<absolute project path>",
  "workers": [
    {"name": "planner",  "role": "project-planner", "brief": "Break the goal into tasks on the board, assign them."},
    {"name": "builder",  "role": "builder",         "brief": "Implement tasks in your worktree, commit, report to reviewer."},
    {"name": "reviewer", "role": "challenger",      "brief": "Review each finished task in the builder's worktree; pass or send fixes back."}
  ],
  "tasks": [{"title": "...", "detail": "...", "assignee": "planner", "gate": 0}],
  "budget": {"max_workers": 3, "pause_at": 85, "stop_at": 95, "max_hours": 4,
             "gates": true, "gate_score": 85, "max_fails": 2, "wait_seconds": 570}
}
```

- Roles are Specialist Council role ids (or `forged-<slug>`). Model and effort come from `council.py resolve` unless a
  worker sets `model` and `effort` (aliases `haiku`, `sonnet`, `opus`, `fable` or full ids).
- Default to Sonnet or Haiku workers; keep Opus or Fable for planning, arbitration and hard reviews.
- The reviewer must use a different model tier from the builder it audits.
- Plugins are curated per worker kind in `profiles.json` (planner, builder, reviewer). Add a plugin only when the
  worker's task needs it: `"plugins": ["name@marketplace"]`. Add MCP servers with `"tags": ["fem"]` or `"mcp": ["ansys"]`.
- Writers (`builder` kind) get their own git worktree; readers get read access to the worktrees.
- Review gates are on by default: a finished work task goes to a reviewer worker on a different model tier, and
  only its `verdict` (pass with score >= `gate_score`) approves it. After `max_fails` failed reviews an `arbiter`
  role worker decides, then you. Seed coordination-only tasks with `"gate": 0`.
- Include a reviewer whenever there is a writer (add an `arbiter` role worker for long or risky runs).
- `wait_seconds` is how long an idle worker stays parked (no tokens) before it goes idle; the conductor re-wakes idle
  workers when work arrives, so the default is fine. Long waits (e.g. 1500) also work.

Show the user the whole preview (workers, models, plugins, estimate, meter, warning). They launch it themselves from
the app (Home → Preview & launch), or approve explicitly and you run the printed `WR launch <run> --confirm <code>`.

## 3. Run

- Launch starts the conductor (usage guard, auto-wake, merge queue, auto finish, watchdog) in the background, shows
  the run in the War Room app (live Flow, Tree, Topology and Cost views, worker drill-down, review gates, merge
  queue, timeline) and opens one
  attached console per worker (the user can type into any of them). Windows: app on the left of the primary screen,
  consoles gridded on the right. macOS/Linux: a tiled tmux session in a terminal window.
- Check progress with `WR status <run>`.
- Add work with `WR post <run> "<title>" --detail "<detail>" [--to <worker>]`. Parked workers pick it up by themselves.
- Talk to a worker with `WR send <run> <worker> "<message>"`; use `WR wake <run> <worker> "<message>"` if it is idle
  (wake restarts it with full context when it is not parked).
- Workers write to `orchestrator`; read their messages in `WR status <run> --json` (messages) and answer.
- Human gates: workers cannot push, publish, delete or spend. When one asks, relay the request to the user.
- Blocked tasks (failed review and arbitration) need a decision: `WR approve <run> <task>` or
  `WR approve <run> <task> --reject "<what to fix>"`.
- Approved commits merge into branch `war-room/<run>` in its own worktree; conflicts go back to the author.
  `WR merge <run>` processes the queue immediately.

## 4. Usage limits

The conductor reads the plan meter every worker reports. At `pause_at` it pauses claims (workers checkpoint and park);
at `stop_at`, or when a worker hits the limit, it stops every worker (conversations kept) and resumes them all after
the reset. `WR watch <run> --schedule` also registers a one-shot OS task so the resume survives a reboot - ask the user
before using `--schedule`, since it creates a scheduled task.

## 5. Stop

- Pause new work: `WR pause <run>` (and `WR unpause <run>`).
- Panic stop: `WR stop <run>` or STOP ALL on the dashboard. Every worker stops; consoles close; nothing is lost.
- Resume later: `WR resume <run>`.
- When all work is merged the conductor finishes the run by itself: workers stop, the cost is measured (it calibrates
  future estimates), every session and fully merged worktree is removed, and a report is written. Unreviewed or
  uncommitted work is kept and reported. `WR finish <run>` (or Finish in the app) does this on demand.
- Merging into the user's branch is their decision: show `WR integrate <run>` (the report), then they press
  Integrate in the app or approve `WR integrate <run> --apply` (clean tree only, --no-ff, never pushed). Only plans
  with `"auto_integrate": true` merge by themselves.
