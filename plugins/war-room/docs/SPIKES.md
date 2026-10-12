> Design history, kept as written during the prototype (paths like `prototypes/war-room/` now live in `plugins/war-room/`).

# War Room: step-0 spike results

Date: 2026-10-12. Prototype files live in this folder and are not committed.

| Spike | Verdict | Evidence |
|---|---|---|
| (a) Terminal hang, and a way around it | **Workaround proven. Root cause not reproduced.** | See section (a) |
| (b) Native agent teams overlap | **No real overlap** (docs only, not run live) | See section (b) |
| (c) A Stop hook plus inbox keeps a `--bg` worker alive | **Pass** | Live worker woke on a bus message and did task 2 |
| (d) Stdlib MCP bus on SQLite, 3 writers | **Pass** | `test_bus.py`: 300 tasks claimed exactly once, 120 messages delivered exactly once, 3 runs |
| (e) A slim profile still loads the council | **Pass** | 60 `specialist-council:council-*` agents via `--plugin-dir`; no user-plugin hooks ran |
| (f) Usage-limit failsafe (added at your request) | **Mechanisms proven; the real limit was not triggered** | The meter is readable in workers; resume restores full context; checkpoints persist |

## (a) Terminal

**Root cause hunt.** I tried three times to reproduce the earlier hang in a Terminal process that held only my windows:

- 1 attach pane
- 3 attach panes in one window
- resizing that window to full screen, then sending `WM_CLOSE` and opening a new window

The Terminal stayed responsive every time (CPU about 1 s). So the hang needed something from the first run: the broken 9-tab window bombarded with `WM_CLOSE` and synthetic keys, or your WSL tab sharing the same process. It is unconfirmed and may come back.

**The way around it: one classic console (`conhost.exe`) per worker.**

- `conhost.exe claude attach <id>` gives each worker its own OS process, so a hang can't spread to other workers or to your Windows Terminal tabs.
- **Tiling works.** Find the windows by class (`ConsoleWindowClass`) and place them with `SetWindowPos`, using `SWP_ASYNCWINDOWPOS` so a hung window can't block the conductor. Result: three windows in an exact 2x2 grid on the primary work area (`term_conhost3_tiled.png`). They stayed responsive for 25 s.
- Note that `Process.MainWindowHandle` from `Start-Process conhost` is **not** the console window. Without the by-class lookup the windows cascade.
- **Clean exit for free.** `claude stop <id>` ends the session; the attach client exits and its window closes. So panic stop also clears the screen, with no `WM_CLOSE` and no synthetic keys.
- **Each pane is a real attached session.** You can click into any pane and take over.
- Cost: older glyph rendering (a few box characters show as placeholders) and no tabs. Windows Terminal panes stay available as an opt-in, with a warning that one process hosts all its windows.

**Recommendation.** Default viewer on Windows = a conhost grid on the primary screen. The grid is `ceil(sqrt(n))` columns, and the dashboard window takes one cell.

## (b) Native agent teams (docs: code.claude.com/docs/en/agent-teams.md)

- Experimental (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`). Teammates are separate instances, shown in-process by default. **Split panes need tmux or iTerm2 and are not supported in Windows Terminal.**
- Mailboxes live in `~/.claude/teams/<team>/inboxes/*.json` and tasks in `~/.claude/tasks/<team>/`. The team directory is deleted when the session ends.
- **Teammates are not restored by `/resume`.**
- Permission mode is inherited from the lead and can't be set when a teammate is spawned. A worktree per teammate is not documented.
- **Verdict.** It doesn't cover tiled, durable, per-role-permissioned, resumable workers. War Room stays justified. Later, a War Room worker could lead its own small team.

## (c) Keep-alive and wake-up

- `hook_stop.py` runs as the worker's Stop hook. It long-polls the bus inbox every 2 s and costs no tokens while waiting. On a message it returns `{"decision":"block","reason":...}`.
- Live run: the worker (Haiku, slim) claimed and completed task 1 (ALPHA), checkpointed and parked. I posted task 2 plus an inbox message, and the worker woke, completed BETA, checkpointed and parked again. Control key `run=stop` released it.
- While parked, `claude agents` shows the worker as **busy**. The dashboard must use the bus heartbeat ("idle: waiting for inbox"), not that status.
- Limits from the docs:
  - The hook timeout defaults to 600 s and is configurable.
  - The loop guard overrides a block after 8 continuations with no tool call in between. A tool call resets it, and `CLAUDE_CODE_STOP_HOOK_BLOCK_CAP` raises the cap.
- **Open:** waking a worker whose hook already timed out. Candidates: (1) a very long hook timeout (test in the MVP); (2) native cross-session `SendMessage` from the orchestrator session, since background sessions can be message targets (test in the MVP).

## (d) Bus

- `bus.py` is a stdlib JSON-RPC MCP stdio server with 8 tools: `post_task`, `claim_task`, `complete_task`, `send`, `inbox`, `heartbeat`, `checkpoint`, `last_checkpoint`. It uses SQLite in WAL mode, and `BEGIN IMMEDIATE` makes claims and inbox reads atomic.
- `test_bus.py` starts 3 server processes behind a start barrier, so claims really contend (one split was 154/57/89).
- Real Claude used it through `--mcp-config` with `permissions.allow: ["mcp__bus__*"]` under `dontAsk`.

## (e) Slim profile

- Flags: `--setting-sources project,local --strict-mcp-config --mcp-config <bus> --settings <role> --plugin-dir <cache>/specialist-council/1.3.2`
- 60 council agents were available. No claude-mem or ruflo hooks ran; the only claude-mem text came from your global CLAUDE.md.
- One full worker cycle (9 turns, 2 tasks, Haiku): 34k cache write, 401k cache read, 0.9k output.

## (f) Usage-limit failsafe

What the probes showed:

1. **Workers can read the meter.** The status-line stdin JSON in a background worker carries `rate_limits.five_hour.used_percentage` / `resets_at` and `seven_day.*` on your **Team** plan. The docs only promise this for Pro and Max. The live reading was 15% and 33%.
2. **The conversation survives a stop.** After `claude stop`, `claude --resume <full-id> --bg "..."` answered "Completed: task 1 (ALPHA) and task 2 (BETA)" from memory, with no tools and no re-entered context.
3. **Gotchas:**
   - (i) Resume **drops launch flags**: the copy came back with the full profile (142 agent types, 2915 skills) and without the bus MCP. The conductor must store each worker's full argv and replay it.
   - (ii) Resume **drops `-n` names**. Track workers by session ID.
   - (iii) Resuming before the stop completes **forks a copy** under a new ID. Wait for the pid to exit first.
4. **Checkpoints persist** in the bus and are readable with `last_checkpoint`.

Failsafe design, four layers:

| Layer | What | Why |
|---|---|---|
| 1. Transcript | Claude Code saves every turn. Resume = replay the stored argv + `--resume <id> --bg "Resumed after usage reset: call last_checkpoint, re-read your claimed task, continue."` | Full context back with no re-input (proven) |
| 2. Bus checkpoints | Done by the model after each step (proven), plus automatic ones: a `PostToolUse` hook logs each tool call to the bus, and a `PreCompact` hook forces a checkpoint. A `SessionStart` (resume/compact) hook injects the last checkpoint plus claimed tasks. | Fallback if a transcript is too large or lost: a fresh session rebuilds from the bus. Works even if the model forgets to checkpoint. |
| 3. Meter watch | Each worker's statusLine writes `rate_limits` to the bus. At **85%** of the 5-hour window: soft pause (`claim_task` returns nothing, workers checkpoint and park). At **95%**, or on "You've hit your ... limit" in a transcript or log: `claude stop` everything (conversations kept). Schedule a resume at `resets_at` + 2 min: the conductor sleeps, and a `schtasks /sc once` entry is registered in case the conductor dies or the PC reboots. | No lost work, no manual relaunch |
| 4. Tiering | Workers default to Sonnet or Haiku, with Opus or Fable for the orchestrator and arbiter. If a per-model weekly window is near its limit, resume that role on the next tier down (`--model` on resume). | Delays the limit; keeps going on a cheaper model |

The bus is SQLite (WAL), so it survives crashes and reboots. On restart the conductor reconciles its `workers` table (session ID, argv, role, worktree) against `claude agents --json --all`.

## Files

- `bus.py`: the bus and MCP server
- `test_bus.py`: concurrency test (3 writers)
- `hook_stop.py`: keep-alive hook
- `statusline_probe.py`: dumps the meter
- `peek.py`: prints bus state
- `term_probe.ps1`: Terminal and conhost tiling probe
- `run1/` and `*.png`: local probe output. It contains personal paths: **don't commit it** (ignored by the local `.gitignore`).
