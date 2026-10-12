> Design history, kept as written during the prototype (paths like `prototypes/war-room/` now live in `plugins/war-room/`).

# War Room: feasibility study and feature scout

Date: 2026-10-12. Branch `claude/strange-visvesvaraya-fce9c5`, not merged and not committed.
Machine: Windows 11, Windows Terminal 1.24.12741.0, Claude CLI 2.1.296, Team plan.
Screens: two 1920x1080 monitors at 96 DPI. The primary is `DISPLAY1` at (0,0), with a work area of 1920x1032 (taskbar excluded). `DISPLAY2` sits to its right at x=1920.

## 0. Bottom line

> **Update:** step-0 spikes are done; see [SPIKES.md](SPIKES.md). The Windows Terminal hang is worked around with one `conhost` window per worker (tiled, isolated, closes on stop). The usage-limit failsafe design is in SPIKES.md section (f).

The idea is viable, and more of it already exists in Claude Code than expected. Since 2.1.x the CLI ships a native background-session supervisor: `claude --bg`, `claude agents --json`, `attach`, `logs`, `stop`, `respawn` and `rm`. War Room should be a thin conductor on top of that supervisor, not a process manager of its own.

Three findings shape the design:

1. **Startup context tax.** Each full-profile instance loads about 127k to 137k tokens of context (95 plugins' skill and agent listings) before doing any work. A slim launch loads about 42k. Per-role plugin curation is mandatory.
2. **The tiled terminal is fragile.** Window placement works perfectly. But three `claude attach` TUIs in one Windows Terminal window hung the whole Terminal process. Because one process hosts every Terminal window, your other tabs hung with it. The live dashboard has to be the primary view, and terminal panes must be optional and isolated.
3. **Subscription limits are the binding constraint, not technology.** The plan meter is readable (5-hour and weekly windows), so auto-pause is feasible. Many parallel Opus instances will still drain a 5-hour window quickly.

## 1. Feasibility per requirement

| # | Requirement | Verdict | Evidence (probes run today) | Risks |
|---|---|---|---|---|
| 1 | Launch N `claude` instances from a script, in the project dir | **Works** | Ran `claude --bg --model haiku --effort low -n wr-probe-1 --permission-mode dontAsk "..."` twice. Both returned an id, reached `idle` and answered `READY`. `claude agents --json` lists pid, cwd, kind, sessionId, name and status (`busy`/`idle`) for every session, interactive and background. Flags available per instance: `--model`, `--effort`, `--name`, `--permission-mode`, `--settings <json>`, `--allowedTools`, `--disallowedTools`, `--add-dir`, `--worktree`, `--agent`, `--agents`, `--append-system-prompt`, `--mcp-config`, `--strict-mcp-config`, `--plugin-dir`, `--setting-sources`, `--fallback-model`. | Each instance runs every user-scope hook (claude-mem, ruflo-cost-tracker, ecc and so on) unless the plugin set is curated. |
| 2 | Force a tiled layout on the main screen | **Works with caveats** | `wt -w new --pos 0,0` plus Win32 `SetWindowPos` placed the window exactly at L=0 T=0 R=1920 B=1032, the primary work area (screenshot `tile_probe.png`). `split-pane -V/-H` builds the grid. | (a) `;` inside a pane command is taken as a `wt` separator: the first probe spawned 9 broken tabs. Use `-File script.ps1` or escape it as `\;`. (b) **A Terminal window can't be closed from a script.** `WM_CLOSE` is ignored, and synthetic Ctrl+Shift+W is blocked by focus-steal protection. Panes must end by their process exiting. (c) **Hang:** a 4-pane window with three `claude attach` panes went "Not Responding" and stayed at about 1 CPU core after the sessions stopped. `SetWindowPos` against the hung window blocked the caller. (d) One WindowsTerminal process (PID 88884) hosts every window, so the hang froze the unrelated Ubuntu tab too. |
| 3 | Instances talk to each other and to an orchestrator | **Works (design verified, not built)** | Interactive sessions can't be pushed messages from outside. Delivery has to go through (a) a local MCP server that all instances load via `--mcp-config` (tools such as `claim`, `post`, `inbox`, `heartbeat`), and (b) hooks: a `Stop` hook can return `block` with "N messages in inbox" so the worker keeps going, and `UserPromptSubmit` can inject context. MOAA already has lock primitives (`arena.py` `state_lock`, `atomic_json`). | ruflo's `claims_*` store has no locking and is per MCP-server cwd: unsafe with N writers. Write our own SQLite (WAL) store. |
| 4 | Watch them live | **Works** | Transcripts land at `~/.claude/projects/<cwd-slug>/<sessionId>.jsonl` immediately, and the sessionId comes from `agents --json`. Model, usage, text and tool calls parse with the same logic as council-replay `extract.py`. `claude logs <id>` gives a raw terminal snapshot (ANSI, 264 KB per call: too heavy to poll). | Transcripts are large (850 KB for a one-word reply, mostly attachments). Tail incrementally by byte offset and never re-parse. |
| 5 | Unattended runs without stalling on prompts, while staying safe | **Works with caveats** | Permission modes: `manual`, `acceptEdits`, `auto`, `dontAsk`, `plan`, `bypassPermissions`. `dontAsk` denies anything not allowed, so the worker never stalls; that is the right default for workers. Combine it with a per-role `--settings` allow/deny list and `--worktree` for writers. `--restricted` exists for read-only reviewers. | Auto mode's classifier still blocks destructive git, which is good. Human gates (push, publish, delete, spend) must go through the bus to the user, never through `bypassPermissions`. `--bare` would remove the hook and plugin tax but **requires an API key** (no OAuth), so it is unusable on your plan. |
| 6 | Stay inside rate and usage limits | **Works with caveats (central risk)** | The desktop tool `get_usage` returned live numbers for the Team plan: 5-hour window 13%, weekly all-models 33%, weekly Fable 5%, extra usage off. Per-instance cost: full profile = 137k cache write on the first turn (probe 1); a second instance got 30.7k cache read plus 96k write; slim profile = 11k write plus 30.7k read. Four probe turns did not visibly move the meter. | The CLI has no usage command; only the desktop app's MCP exposes the meter. Fallback: detect rate-limit errors in transcripts and back off. `--max-budget-usd` exists only with `--print`. |
| 7 | Continuous or indefinite runs | **Works with caveats** | Background sessions survive the terminal: `stop` keeps the conversation, `attach` reopens it, `respawn --all` restarts on a new CLI version, and `--resume` continues. A `Stop` hook plus the inbox keeps workers looping; `--autocompact` controls context growth. | Long runs mean repeated compaction and drift. The watchdog must compare heartbeat and progress, not only liveness. Cost grows linearly with time. |

### Probe side effects to clean up (your call)

- **One stray Terminal window** from probe 1 ("Start-Sleep 15", 9 dead tabs).
- **The Terminal process is hung** (PID 88884, title `wr-2d1408c3`). It hosts your Ubuntu-24.04 tab, so I did not kill it. Close it from Task Manager when the Ubuntu tab can go, or wait.
- Three stopped probe sessions (`wr-probe-1`, `wr-probe-2`, `wr-probe-slim`) remain in `claude agents --all`. `claude rm <id>` deletes them: ids `ba9eedb9`, `2d1408c3`, `5ccbd81c`.

## 2. Feature scout

| Existing | What it really is | Use |
|---|---|---|
| **Claude Code `--bg` / `agents` / `attach` / `logs` / `stop` / `respawn`** | A native supervisor for real, separate interactive sessions | **Core runtime. Wrap it.** |
| Claude Code `--worktree`, `--tmux` | A worktree per session; `--tmux` gives iTerm2 or tmux panes on macOS and Linux | Reuse: the writer isolation and the non-Windows tiling path |
| Claude Code native agent teams (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) | Harness-managed teammates | **Unverified overlap. Check first** (MVP step 0) |
| `get_usage` (desktop MCP) | Plan meter | Reuse for auto-pause, when the orchestrator runs in the desktop app |
| ecc `orchestrate-worktrees.js` + `tmux-worktree-orchestrator.js` | Plan JSON becomes a worktree plus a tmux pane per worker, with task, handoff and status files; dry run by default | **Copy the design.** It is the closest prior art, but tmux only |
| ecc `terminal-opener` | Opens a window without a shell; WezTerm adapter only | Optional: add a Windows Terminal adapter upstream |
| ecc `cost-tracker` hook | Writes `~/.claude/metrics/costs.jsonl` | Reuse as a cost feed if rows carry the session id (unchecked) |
| ruflo `claims_*` / `task_*` | Good semantics (claim, handoff, steal), unsafe storage | Copy the schema, not the store |
| ruflo `hive-mind spawn --claude` | One foreground `claude` with a generated `--mcp-config` | Copy the per-worker `--mcp-config` idea |
| ruflo-cost-tracker | Stop hook parses the newest jsonl | Disable in workers: it may attribute usage to the wrong session |
| ruflo swarm / observability / autopilot / loop-workers | MCP state records, prose, single-session loops | Ignore |
| ecc team-builder / dev-team / dmux, agent-teams skill, superpowers parallel-agents, AAS loki-mode / claude-monitor | In-process subagents, personas, tmux docs, `claude -p` loops | Ignore (loki's `.loki/{queue,messages,state}` layout is a useful reference) |
| **MOAA council.py `resolve`** | Role to model and effort | **Reuse** for each instance's `--model` and `--effort` |
| **MOAA arena** (`arena.py` lock, `library.py`, judge and redteam modes) | Locks, scoring, judge rubric | **Reuse** for the audit gates and the lock primitive |
| **MOAA council-replay** | jsonl parser, redaction, 127.0.0.1 server, canvas UI, GIF export | **Reuse** for the dashboard parser, redaction, design system and post-mortems |
| **MOAA flightdeck** | In-pane mod with no I/O by design | Keep it per pane. Don't extend it (it can't see across instances) |

**Genuinely new:** the plan/preview/launch conductor, the curated per-role launch profiles, the bus MCP server and its hooks, the dashboard, the watchdog, gates and merge queue, and the Windows tiler.

## 3. Recommended architecture

**Packaging: both, as one plugin carrying a CLI.** The `war-room` plugin provides `/war-room` (skill), the bus MCP server, the hooks and `warroom.py` (stdlib Python CLI: `plan`, `launch`, `status`, `tile`, `pause`, `stop`, `serve`, `resume`). The CLI also runs from any shell.

**Toggle.** A plugin `userConfig.warMode` defaults to off, and `/war-room` refuses while it is off. With it on, every launch first prints the plan preview (instances, roles, model and effort, permission profile, plugin set, estimated tokens and plan-percent range) with the resource warning, and waits for a typed `launch`.

```
user ─/war-room─▶ Orchestrator (your current session, opus or fable)
                  │ 1 decompose task, pick roles (council resolve), estimate cost
                  │ 2 warroom.py plan  → preview + warning → user types "launch"
                  ▼
            warroom.py launch ──▶ claude --bg  ×N   (native supervisor)
              per worker: --name wr-<run>-<role>  --model/--effort (council)
                          --permission-mode dontAsk  --settings <role profile>
                          --worktree (writers)  --setting-sources project,local
                          --plugin-dir <curated>  --mcp-config bus.json
                          --append-system-prompt <role brief + bus protocol>
                  │
   ┌──────────────┼───────────────────────────────┐
   ▼              ▼                               ▼
 bus MCP (stdio, one per worker)      transcripts *.jsonl         claude agents --json
   └─▶ .war-room/<run>/bus.sqlite3 (WAL): tasks, claims, messages,
       heartbeats, gates, budgets, checkpoints
                  ▼
 warroom.py serve  (127.0.0.1, SSE)  ◀── tails bus + transcripts (extract.py logic)
   dashboard: workers, graph, timeline, meters, gates [approve/deny], PANIC STOP
                  ▼
 optional: warroom.py tile → panes running `claude attach <id>`, primary screen
```

**Roles and gates.** Planner, then workers (builder, debugger and so on, from the council), then a reviewer on a different model (challenger or arena judge). An arbiter settles disagreements, or the user does. The merge queue is owned by an integration-engineer instance that rebases the worktrees in order. Human gates (push, publish, delete, spend) appear in the dashboard and as notifications.

**Budgets.** Caps per run on instances, wall time and an estimated token ceiling. Auto-pause at a 5-hour-window threshold (default 80%) via `get_usage`, falling back to rate-limit errors in transcripts. Panic stop = `claude stop` on every `wr-<run>-*` session, which keeps the conversations so the run can resume.

**Tiling (per OS).**

- Windows: the primary path is the dashboard. Panes are opt-in. Root-cause the hang first. If it is per-process, launch each pane as its own `conhost`/`wt` process and grid-place the windows with `SetWindowPos` from a non-blocking call (`SetWindowPos` with `SWP_ASYNCWINDOWPOS`), so a hang stays local.
- macOS: native `--tmux` (iTerm2).
- Linux: tmux or WezTerm `cli split-pane`.

**UI concept (council-replay language).** Flat graphite surfaces (#0b0d10 / #121519), hairline borders, IBM Plex Sans and Mono, a 2px accent rule on the focused panel, muted model-tier swatches. No gradients, glow or pills.

- Layout: a left rail of workers (status, model, context %, tokens). A centre graph of roles, with edges for messages and hand-offs that light up only while active. A bottom timeline swimlane per worker, with gates marked as hatched blocks. A right column for the gate queue, budget meters and log.
- A single red-bordered `STOP ALL` control, top right.

## 4. Name

**War Room.** Command `/war-room`, toggle "war mode". It is clear, professional and distinct from flightdeck. Foundry fits the brand but reads like a build tool. Skip the Goblin Mode alias in a public repo, or add it as a hidden easter egg later.

## 5. MVP and roadmap

- **Step 0: spikes, about one session each.**
  - (a) Root-cause the Windows Terminal hang (one attach pane vs three, pane size, flightdeck mod in attach).
  - (b) Check native agent teams for overlap.
  - (c) Prove that a `Stop` hook plus inbox keeps a `--bg` worker looping.
  - (d) Prove that a stdlib MCP stdio server shared through SQLite works under 3 writers.
  - (e) Confirm the curated `--plugin-dir` + `--setting-sources project,local` profile still loads council agents.
- **MVP (phase 1).** `warroom.py plan|launch|status|stop|serve` with at most 3 workers: planner, builder in a worktree, reviewer on a different model. The bus MCP, a read-only dashboard, the panic stop and caps. The toggle and preview warning. No tiling, no arena.
- **Phase 2.** Council-driven role picking, arena judge gates, the merge queue, human gates in the dashboard, auto-pause on the usage meter, and the opt-in Windows tiler.
- **Phase 3.** Watchdog (stuck or looping detection, respawn, escalate), checkpoint and resume, notifications, macOS and Linux tiling, recording to council-replay for GIFs and post-mortems, forged-member selection.

## 6. Risks and costs

**Token cost: rough estimates, to be measured in the MVP.**

- Fixed startup: about 130k per full-profile instance, about 42k slim.
- Running cost is dominated by cache reads of the growing context on every turn. A worker doing 60 turns at an average 120k context reads about 7M cached tokens and writes a few hundred thousand.
- A typical 3-worker, 1-hour run is therefore roughly 15M to 25M tokens processed, mostly cache reads.
- For scale: this one scouting session alone is at 217k context and the 5-hour window shows 13%.
- **Expect 4 or more parallel Opus or Fable workers to exhaust a 5-hour window within an hour or two.** Default to Sonnet or Haiku workers, with Opus or Fable only for the orchestrator and arbiter.

**Failure modes.**

- Terminal hangs that take the user's other tabs with them.
- Lost bus updates if storage isn't locked.
- Merge conflicts between worktrees.
- Context drift on long runs.
- Hooks from 95 plugins running N times: claude-mem is already failing, and ruflo-cost-tracker misattributes usage.
- Workers stalled on a denied tool under `dontAsk` (they fail closed, so the watchdog must surface it).
- Forged or suspended members (`resolve` already refuses those).

**Can't be done.**

- Pushing a message into a running interactive session from outside. It has to be a pull via MCP or hooks.
- Reading plan limits from the plain CLI.
- `--bare` on OAuth.
- Closing a Windows Terminal window programmatically. Panes must close by their process exiting.
- A guarantee against focus stealing: Windows blocks it, which is fine for unattended runs.
