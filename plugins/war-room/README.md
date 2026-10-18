# War Room

Run a team of real, parallel Claude Code workers on one large job. Each worker:

- has a Specialist Council role, with its own model and effort
- loads only the plugins and MCP servers its kind of work needs
- runs unattended on a narrow allow-list

Finished work is reviewed by another worker on a different model before it counts. Approved commits merge into a per-run integration branch. Usage limits are survived by checkpointing and resuming automatically. When the work is done, the run cleans up after itself. A local app shows the whole thing live.

Install with `/plugin install war-room@moaa` (the MOAA installer adds it to both profiles). Design history: [feasibility study](docs/FEASIBILITY.md) and [step-0 spikes](docs/SPIKES.md).

![The run view: needs-attention strip, KPI strip, team with Claude and ally workers, the board, review gates and the timeline](docs/media/run-live.png)

![Home: war mode, plan usage, quick-start templates and runs](docs/media/home.png)

![New run: project, job, templates and the plan editor with an engine per worker](docs/media/new-run.png)

![A finished run: the board with every task merged, review gates, the report and the timeline](docs/media/run-finished.png)

![The Tree tab: the run as an agent tree with the reviewer rail, bus meters, workers and session log](docs/media/run-tree.png)

![The Cost tab: spend per worker, the 5-hour window with its projection, and the cost model](docs/media/run-cost.png)

![A finished run replayed halfway through, with the scrubber above the run view](docs/media/run-replay.png)

![History: finished runs with their team, outcome, cost and report](docs/media/history.png)

![The light theme](docs/media/run-light.png)

To see the app without spending any tokens, run `python warroom.py demo` (or press **Start demo** on Home). It plays a simulated six-worker run (four Claude workers, a Codex builder and a Gemini reviewer) through the real bus for two to three minutes: no Claude session is started.

## The app

`python warroom.py app` opens the War Room as a desktop window. It is a local hub on 127.0.0.1, shown in a chromeless Edge, Chrome or Brave `--app` window with its own profile, so it has no tabs or address bar. The hub serves every run, and you can also reach it with `warroom.py app <run>`.

`python warroom.py app --install-shortcut` adds **War Room** to the Start menu and the desktop on Windows, with its own icon, or a menu entry on Linux. The shortcut runs a small launcher in `~/.claude/war-room/` that opens whichever War Room version is installed, so it survives plugin updates. No console window appears. `--remove-shortcut` takes it away again. War Room stays a MOAA plugin: the app still needs Claude Code and Python.

Every page shares a slim sidebar: **Home**, **New run**, **Run** (the live run, with a green dot while one is running), **History** and **Settings**, plus the theme switch. **Ctrl+K** opens a command palette on every page: go anywhere, arm war mode, start a demo or a template, open or replay a run, and in a run pause, finish, stop, switch views, or jump to any worker or task.

Workers are coloured by model family everywhere: Claude amber, Codex teal, Gemini blue, Kimi violet, DeepSeek sky, OmniRoute steel. An ally worker carries a family badge. Claude workers also show their tier (Haiku, Sonnet, Opus, Fable) as a small swatch.

**Home**

- **War mode.** The master switch: Safe or Armed. Arming it opens a warning, the live plan meter and an acknowledgement. While it is Safe, launches are blocked; disarming never touches live runs.
- **Plan usage.** The 5-hour window with the pause and stop thresholds marked, the weekly meter, and the cost model (median tokens per worker-task over measured runs).
- **Quick start.** Every team template, each showing its model families, plus a demo run. A template fills the plan editor at no token cost.
- **Runs.** Live and planned runs first. Each card shows its status, goal, the team as family-coloured avatars with ally badges, and progress. A planned run has **Preview and launch**: the roster with engines, plugins, the calibrated token estimate, guard, gates and warning, then an acknowledgement and a launch sequence that hands over to the run view.

**New run**

- Pick the project folder with **Browse…** (the system folder dialog) or type its path; it must be a folder Claude Code already trusts. Describe the job, then either:
  - **Draft with Claude:** one headless Sonnet call with no tools, no session file and no plugins drafts the plan (about 5–10k tokens of your plan; the app asks first and shows the progress and any error), or
  - start from **a template** (feature team, bug hunt, review swarm, research fan-out, mixed allies, refactor) or a blank team, at no token cost.
- The **plan editor**: name, goal, and per worker a council role, an **engine** (Claude or an ally: Codex, Gemini, Kimi, DeepSeek, OmniRoute), and for Claude a model tier and effort, plus a brief. Seed tasks have an assignee and review on or off. The budget comes from Settings. **Create plan** resolves roles and plugins exactly like `warroom.py plan` and opens Preview and launch; nothing starts until you arm war mode, acknowledge and launch. The draft survives a reload.

**Settings** (saved with **Save settings** in the header; **Defaults** restores the built-in values)

- Team and usage guard: max workers; pause and stop thresholds on a gauge with the live meter; max run length; spend cap in USD (0 = none), the API-equivalent statusline cost of all workers summed across resumed sessions. The conductor stops the run at the cap and never resumes it by itself; resuming asks for a higher cap.
- Review gates (on/off, pass score, failed reviews before arbitration), keep-alive wait, auto finish and auto integrate. Values are validated server-side.
- **Presets** save the settings under a name and apply them later. **Alerts and appearance**: desktop notifications, sound and the theme (graphite dark, light, or follow the system; `?theme=light` on any page previews a theme without saving it).
- **Worker profiles:** the plugins each worker kind loads (planner, builder, reviewer), and a default model tier and effort per Specialist Council role, kept in `~/.claude/war-room/profiles.json` and `config.json`. Allow and deny lists are never changed here, but a plugin brings its own hooks and MCP servers, so add only plugins you trust for that kind of worker. A plan that names a model or engine still wins.

**Run view**

- **Header:** the goal, run id, uptime, conductor status and branch, a status tag (Live, Paused, Stopped, Finishing, Finished, Replay), and Alerts, Integrate, Resume, Pause, Finish and Stop all (each shown when it applies).
- **Needs attention:** a strip that appears only when something wants you: a human gate (with **Approve** and **Reject** right there, the same as `warroom.py approve`), a failed review being reworked, spend near the cap, the 5-hour window near the pause line, a silent conductor, or the run's own state (stopped, paused, finishing countdown, complete, integrated).
- **KPI strip:** tasks merged, the 5-hour window with its thresholds, spend against the cap, who is working (Claude versus allies, by family), and how many human gates are waiting.
- **Team:** a card per worker with its family avatar, role and model, a status light (working, parked, booting, stopped), the task it holds, heartbeat, context, spend, inbox and a 20-minute activity sparkline. A launching or resumed worker steps through SPAWN → PROFILE → PLUGINS n → BUS → READY; while workers boot, a fleet boot panel shows them all together. Click a card for the **worker drill-down**: tool calls with a histogram, messages, checkpoints, tasks, and context and spend charts. A Claude worker has **Focus console** and **Copy attach command**; an ally worker has no console.
- **Board** (default tab): the kanban. Board, Building, In review and Merged lanes; each card shows who holds it (family colour), the commit, tries and the score, and glides to its new lane when it moves. Click a card for the **task inspector**: status, every review with its verdict, score and notes, the commit with its diff stat, the people involved, the author's summary and the task's history. A task at a human gate can be approved or sent back from there.
- **Flow** tab: five stations (Board → Build → Review → Merge queue → Integrated) linked by moving belts; tasks glide between them, leaving an amber trail forward and a red one when a review sends them back.
- **Tree** tab: the run as a terminal-style agent tree with the reviewer rail, the bus meters, the workers and a session log. It stays dark in the light theme, as a terminal pane would.
- **Topology** tab: who talks to whom, with messages travelling along the edges as packets.
- **Cost** tab: total spend, the 5-hour window with its burn rate and a dotted projection to the pause and stop thresholds, spend per worker over time with a crosshair, a per-worker table, and the measured runs behind the cost model.
- **Timeline:** the last 30 minutes per worker, with busy stretches and events in each worker's family colour and review verdicts as diamonds.
- **Review gates:** every verdict with a score bar against the pass line, reviewer → author (allies named) and the notes; click one to inspect its task. Below it the **merge queue** (the report once the run finishes) and the **activity** feed.
- **Alerts:** a toast when a human gate opens or the run stops or finishes, plus a desktop notification and two beeps when Alerts is on.
- **Replay** (`/run/<run>?replay=1`, or Replay on History and Home): the run rebuilt from its full logs at any moment and played through the same panels, with play and pause, 1× to 120× speed and a scrubber. `&at=0.5` opens it halfway through.

**History:** finished and stopped runs, filterable by name, goal, outcome or demo. Each shows its team, length, tasks, reviews, measured tokens and statusline spend, the report, and Replay, Open and Delete.

The visual style is flat graphite with an amber accent, hairline borders and 6–8 px corners: IBM Plex Sans for text and Plex Mono only for data. There are no gradients or glow; hard hazard stripes mark only armed and danger states. The Cost charts use a categorical palette checked for colour-blind separation. Motion is mechanical (stepped lights, gliding cards, belts) and is switched off under reduced-motion settings.

## Command line

```
python warroom.py toggle on|off|status
python warroom.py plan plan.json                  # preview: roles, models, curated plugins, calibrated estimate, warning
python warroom.py launch <run> --confirm <code>   # or Preview & launch in the app
python warroom.py app [<run>] [--quit]
python warroom.py app --install-shortcut          # Start-menu and desktop shortcuts (Windows) or a menu entry (Linux)
python warroom.py demo [--speed N] [--max-cost USD]  # a simulated run in the app: no Claude sessions, no tokens
python warroom.py template [NAME --project P --goal "..."]  # list team templates, or print one as a plan file
python warroom.py status <run> [--json]
python warroom.py post <run> "title" --detail "..." [--to worker]
python warroom.py send <run> <worker> "message"
python warroom.py wake <run> <worker> ["message"]
python warroom.py approve <run> <task> [--reject "notes"]   # human gate for blocked tasks
python warroom.py merge <run>                     # process the merge queue now
python warroom.py integrate <run> [--apply]       # report, or merge the run branch into the current branch (no push)
python warroom.py pause|unpause|stop|resume <run>
python warroom.py resume <run> --max-cost USD     # continue a run stopped at its spend cap with a new cap (0 = none)
python warroom.py finish <run> / shutdown <run>   # finish: stop, measure, clean up; shutdown also closes the window
python warroom.py measure <run>                   # record real token use (calibrates estimates)
python warroom.py watch <run> [--schedule]        # the conductor (normally a background daemon)
python warroom.py tile <run> / restart-daemons <run> [--open] / list
```

## How it works

- **Workers** are `claude --bg` sessions. They are launched with:
  - `--model` and `--effort` from `council.py resolve`, or set in the plan
  - `--setting-sources project,local` and `--strict-mcp-config`, so user plugins and MCP servers are not loaded
  - `--plugin-dir` for each plugin of the worker's kind
  - `--mcp-config` with the bus plus any tagged servers
  - `--settings` with allow and deny lists, hooks and statusLine
  - `--worktree` for writers; `--add-dir` to the worktrees folder for readers
  - `--append-system-prompt` with the protocol

  The prompt goes after a `--` separator, because variadic flags would otherwise swallow it.
- **Curated plugins** come from `profiles.json`: planners and builders get specialist-council, reviewers get specialist-council and agent-arena-mode, and a plan can add plugins or tag MCP servers per worker. A slim worker starts at about 42k tokens of context, against about 130k with every user plugin.
- **Bus** (`bus.py`): SQLite in WAL mode, served to each worker as a stdlib MCP server.
  - Tools: `post_task`, `claim_task`, `complete_task`, `verdict`, `send`, `inbox`, `heartbeat`, `checkpoint`, `last_checkpoint`, `board`.
  - Claims are atomic.
  - Older runs gain new columns automatically when opened.
- **Review gates:**
  - A writer must commit and pass the hash to `complete_task`. The task goes to `review`, and the bus creates a review task for a reviewer worker on a different model tier, falling back to the human when there is none.
  - `verdict` passes only at or above the pass score (default 85). A fail reopens the task for its author with the notes; re-submitting claims it again automatically.
  - After `max_fails` failures an `arbiter` worker decides, then you (`approve`). Nobody can review their own work.
- **Merge queue:** the conductor merges approved commits `--no-ff`, oldest approval first, into `war-room/<run>`. That branch lives in its own worktree and is based on the commit the writers' worktrees start from (`claude --worktree` branches from the default branch). A conflict aborts the merge and sends the task back with instructions.
- **Finishing:**
  - When all work is merged, nothing is open or under review, and every worker is parked for 90 s, the conductor finishes the run. It stops the workers, records the measured cost, and writes `report.md`.
  - It then unlocks and removes writer worktrees that are clean and fully merged (deleting their branches), removes the integration worktree (keeping the branch if it holds commits), and deletes every session the run used.
  - Sessions must be deleted because resuming a stopped background session forks a copy in Claude Code 2.1.296, so old copies pile up. Worktrees are cleaned first because `claude rm` keeps a session while its worktree exists.
  - Unreviewed or uncommitted work is kept and reported, never deleted.
  - Integration into your branch is the Integrate button or `integrate --apply` (clean tree only, `--no-ff`, never pushed). `auto_integrate` does it automatically.
- **Waking a worker:**
  - (1) A parked worker wakes on a bus message (the Stop hook long-polls at no token cost).
  - (2) An idle worker is restarted with its stored flags and `--resume`, or relaunched fresh if it never finished a turn; the conductor does this automatically when work is waiting.
  - (3) The orchestrator session can message a worker natively with `SendMessage`.
- **Usage limits:**
  - Every worker reports `rate_limits` through its statusLine.
  - At the pause threshold, claims pause (a manual pause is never lifted by the guard).
  - At the stop threshold, or on a "hit your limit" message, every worker stops with its conversation kept, and auto-resumes at the real reset time plus 2 minutes. `--schedule` also registers an OS task, so the resume survives a reboot.
  - The SessionStart hook restores checkpoints and claimed tasks after a resume.
- **Cost model:** `measure` sums token use from transcripts, deduplicated across resumed copies. `plan` estimates from the median measured cost per worker per task.
- **Tiling:**
  - Windows: one `conhost` console per worker running `claude attach`, so a hang stays local. The conductor writes each worker's state into its console's title (`swift · working · War Room`: working, waiting, idle, stopped or done). Claude Code reports the same states through the Program Status Protocol (OSC 7501) to terminals that support it, and conhost does not. The consoles start with `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1`, so Claude Code's own title spinner never overwrites the status. The dashboard app takes the left 56% of the primary screen and the consoles grid on the right, with the last row stretching. Placement uses asynchronous `SetWindowPos`. The conductor reopens any console that is missing.
  - macOS / Linux: a tiled tmux session in a Terminal window (checked live on Linux with tmux 3.4; the macOS Terminal launch is untested).
  - Workers retry an overloaded API (HTTP 529) with a longer backoff (`CLAUDE_CODE_OVERLOADED_RETRY_BASE_DELAY_MS` 5 s, `..._MAX_DELAY_MS` 5 min) rather than fail a turn while unattended.
- **Safety:**
  - Workers run in `dontAsk` mode with allow-lists. Push, publish, branch and tag deletion, `rm -rf` and web access are denied.
  - The hub listens only on 127.0.0.1. Every POST needs a per-start token embedded in the page.
  - Home paths are redacted.
  - `plan` refuses repositories Claude Code doesn't trust yet; War Room never bypasses the trust prompt.

## Verified live (2026-10-12)

| Check | Result |
|---|---|
| End-to-end job | Planner → builder (own worktree, commits) → reviewer (different tier) → merged, no human input |
| Gates with failure and recovery | Both build tasks failed review at 70 (house-rule docstrings), were fixed, re-reviewed and passed at 93–95, then merged |
| Merge queue | Approved commits merged in order into `war-room/<run>`; conflict handling covered by a real-git unit test |
| Auto finish | Fired 90 s after completion: stopped, measured (2.96M and 3.95M tokens), cleaned sessions and merged worktrees, and kept an unreviewed extra commit with a report |
| Launch from the app | Preview → acknowledge → launch sequence → run view: workers booted, tasks flowed live, then auto finish |
| Wake paths | Parked (bus, 6 s), idle (resume, 8 s, recalled its commit from memory), native `SendMessage`, conductor auto-wake |
| Long keep-alive | Parked 13+ minutes on a 1560 s hook, then woke in 6 s |
| Usage guard | Stop at the threshold, `resume_at` = real reset + 2 min, auto-resume with context |
| Tiling | Dashboard app plus 3 consoles laid out on 1920x1032; restarted workers re-enter the layout; the conductor self-heals missing consoles |

## Tests

```
python -m unittest discover -s tests   # policy, argv replay, plan curation, hooks, gates, arbitration, merge queue (real git),
                                       # finish, cleanup, integrate, layout, tmux plan, calibration, migration
python tests/test_bus.py               # 3 MCP server processes, 300 contended claims, exactly-once delivery
```

## Known limits

- **Resume makes a copy.** Resuming a stopped background session always forks a copy under a new ID (Claude Code 2.1.296 behaviour). The conductor tracks the copy, and finishing deletes them all.
- **macOS tiling** opens the tmux session through Terminal via `osascript`; the tmux part is checked on Linux, the Terminal launch is untested.
- **The cost model** is calibrated on small Haiku/Sonnet runs, so expect larger jobs to differ until they have been measured.
- **The app window** needs Edge, Chrome or Brave; otherwise War Room opens in the default browser.
