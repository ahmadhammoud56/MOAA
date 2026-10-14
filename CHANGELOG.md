# Changelog

All notable changes to MOAA. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [SemVer](https://semver.org/).

## [Unreleased]

## [0.5.5] - 2026-10-14

### Changed
- **Specialist Council 1.3.3: four role presets retuned.** Each change brings a role in line with the council's own tier and effort policy.
  - `scout`: Haiku, effort medium → **low**. It does lookups only.
  - `information-architect`: Haiku → **Sonnet**, effort medium. Structuring knowledge and navigation needs judgment, not just scanning.
  - `requirements-analyst`: Opus medium → **Sonnet high**. Its output can be checked, so the cheaper tier with verification-level effort fits.
  - `integration-engineer`: Opus medium → **Sonnet high**, for the same reason.
  - The change was made in `profile.json`. The agent files, the model-profile reference and `MODELS.md` were regenerated from it, and `council.py check` passes.

## [0.5.4] - 2026-10-14

### Changed
- **Vendored skills updated to upstream.**
  - networkx, pyzotero, scientific-brainstorming and uncertainty-and-units are now K-Dense v1.4 (`a1043ef`; was v1.2). The update adds a `review.md` reference to networkx and uncertainty-and-units.
  - reverse-engineer-anything is now rea skill v42 (`322506d`; was v37).
  - paper2agent was already current.
  - MOAA's LICENSE and NOTICE files are kept.
  - THIRD_PARTY.md now records the upstream commit each skill was taken from.
- **headroom** is re-checked against upstream `f1bc260`:
  - `wrap vscode-claude` and the other wrappable agents;
  - `wrap claude` side effects (MCP and Serena registration, `--1m`, `--memory`) and `unwrap --keep-mcp`;
  - `headroom mcp install`, with HTTP MCP on port 8788 and `--direct` deprecated;
  - output shaping and `headroom update`;
  - deploy order and `install apply --env`;
  - the Rust proxy, described as upstream's direction rather than a deprecation.
- **The rea MCP server is pinned to `rea-agents@6.4.0`** (was 6.3.0).
- **agent-teams:**
  - Mixed-model rosters now set model and effort per Agent call (the per-call `effort` arrived in Claude Code 2.1.292) instead of writing agent files and restarting.
  - New warnings about settings that silently break a mixed roster (`CLAUDE_CODE_SUBAGENT_MODEL_FORCE` and others), plus failure modes in wide fan-outs: 529 slowdowns, resuming a worker by ID, and the Workflow concurrency cap.
  - Pointers to War Room for giant jobs and to council roles for models.
  - New `scripts/validate_team.py` (standard library only, with a self-check) validates a team JSON: fields, IDs, dependency cycles and shared outputs.
- **path-safety** is rewritten as a general skill. The old text was a coding standard for one other project (Data Formulator).
  - It now covers 7 rules: resolve once, `is_relative_to` instead of `startswith`, no re-parsing by helpers, LLM tool arguments as user input, archive extraction ("zip slip"), deployment gating, and sandboxing generated code.
  - New `scripts/confine.py` rejects `..`, absolute, drive and UNC paths, NUL bytes, NTFS streams, device names, and symlinks or junctions that escape the root.
- **local-build:**
  - `/local-build <slug> step N` resumes a build at a step, and the resume command is given before any restart.
  - Blind verification stops and asks after two failed fixes.
  - Hooks a build adds are tested by hand first; `onFailure: "block"` is reserved for safety gates.
  - The token-efficient build is updated for the current subagent-model settings.

### Fixed
- **The installer now updates skills and MCP servers from earlier MOAA installs instead of skipping them.**
  - A skill that is byte-identical to a version MOAA shipped (line endings aside) is updated; a copy you edited is still left alone.
  - An MCP server MOAA installed, or one with MOAA's exact command at an older pinned version, is re-added at the current pin; your own MCP setups are left alone.
  - Before this fix, skills and MCP servers installed before the manifest tracked them never received updates.

## [0.5.3] - 2026-10-13

### Changed
- **War Room 0.3.1: a new app icon, the situation table.** Seen from above, an amber ring holds a Claude-style spark (the orchestrator), wired to eight workers (War Room's hard cap) in the model-tier colours, on a plotting table with range rings. The spark is a generic asterisk drawn for War Room, not Anthropic's logo. It ships as `assets/icon.svg`, used as the favicon of every page and served at `/icon.svg`, with a 256-px `assets/icon.png` for the Start-menu, desktop and Linux shortcuts. Run `warroom.py app --install-shortcut` again to refresh existing shortcuts. The old drawing code is gone.

## [0.5.2] - 2026-10-12

### Added
- **War Room 0.3.0:** start a run from the app.
  - **New run** on Home: pick the project folder with the system folder dialog (or type it), describe the job, then **Draft with Claude** (one headless Sonnet call with no tools, no session file and no plugins, about 5–10k tokens, asked first) or **Write by hand** (no tokens). The draft opens in an editor for workers, roles, models, effort, briefs and seed tasks. **Create plan** resolves it like `warroom.py plan` and opens Preview & launch, so war mode, the acknowledgement and the confirm code still gate every launch. The planner refuses a folder Claude Code does not trust before spending anything, and a plan from the app can set no plugins, permissions or worker kinds.
  - `warroom.py app --install-shortcut` (and `--remove-shortcut`): Start-menu and desktop shortcuts with a War Room icon on Windows, or a menu entry on Linux. They run a launcher in `~/.claude/war-room/` that opens the installed version, so they survive plugin updates.
  - The app's pages carry the War Room icon.

## [0.5.1] - 2026-10-12

### Added
- **War Room 0.2.0:** a bigger app, and a way to see it without spending tokens.
  - **Demo mode** (`warroom.py demo`, or Start demo on Home): a simulated six-worker run that drives the real bus for two to three minutes, with claims, a failed review, an arbitration, merges and a usage meter. No Claude session is started.
  - **Tree tab** in the run view: the run as a terminal-style agent tree, with a phase stepper, a reviewer rail showing the live gate, the bus with block meters, workers fanned out by tier, the integration branch, a session log and a status line.
  - **Cost tab:** spend and burn per worker, the 5-hour window with a projection to the pause and stop thresholds, and the measured runs behind the cost model. Usage history comes from a new `meter_log` table.
  - **Worker drill-down:** click a worker for its recent tool calls, messages, checkpoints, tasks and usage charts, and to raise or open its console.
  - **History page:** finished and stopped runs with their outcome, review results, measured tokens and report; runs can be deleted there.
  - **Alerts:** a toast, plus an optional desktop notification and sound, when a human gate opens or a run stops or finishes.
  - **Settings v2:** named presets, plugin lists per worker kind (kept in `~/.claude/war-room/profiles.json`; permissions stay as shipped) and a default model and effort per council role.
  - A fleet boot panel in the Flow view, and a narrower right column so the run view fits beside the worker consoles.
  - **Replay:** a finished run is rebuilt from its full logs and played through the run view, with a scrubber, play and pause, and speeds up to 120x. It opens from History or a run card.
  - **Light theme:** dark (default), light or system, chosen on Home and applied before the first paint. The Tree tab stays dark.
  - **Console status:** each worker's console title shows working, waiting, idle, stopped or done. This stands in for OSC 7501, which conhost does not implement. Consoles start with `CLAUDE_CODE_DISABLE_TERMINAL_TITLE=1` so Claude Code's own title does not overwrite it.
  - Workers back off longer on an overloaded API (529): 5 s base, 5 min maximum.
  - New README screenshots of every view.
- The installer pre-approves `warroom.py demo`.

### Fixed
- `config/kit.json` records the tested versions actually shipped: specialist-council 1.3.2 and plot-deck 0.2.1 (it still said 1.3.0 and 0.2.0).
- Agent Arena 0.4.5: the README now explains installing from the `moaa` marketplace and points at the real library path, `~/.claude/plugins/data/agent-arena-mode-moaa/`. It had still described the pre-MOAA `Agent_arena` folder and the `agent-arena-local` marketplace.

### Changed
- ruflo's 39 plugins are re-pinned from `277c7bc` to `ea0ea3d`. This includes ruflo's Windows hook-launch fix: hooks now start through `node -e` instead of `cmd /c`, which used to open an interactive `cmd`. superpowers stays at 6.4.1, because Anthropic's official marketplace doesn't list 7.0.0 yet.
- The installer also sets `CLAUDE_CODE_OVERLOADED_RETRY_MAX_DELAY_MS=60000` (new in Claude Code 2.1.296). Long council and arena runs now back off for up to a minute when the API is overloaded, instead of failing early. War Room workers don't load user settings, so War Room sets its own, longer backoff for them. `--uninstall` removes it like the other settings.

## [0.5.0] - 2026-10-12

### Added
- **War Room 0.1.0** (`war-room@moaa`), a new plugin for giant or multi-workflow jobs.
  - Runs a team of real, parallel Claude Code workers (`claude --bg`). Each worker has a Specialist Council role, model and effort, loads only the plugins and MCP servers its kind of work needs, and runs unattended on a narrow allow-list in its own git worktree.
  - Workers coordinate through a local SQLite bus, served as a stdlib MCP server, with tasks, claims, messages, heartbeats and checkpoints.
  - **Review gates:** finished work is reviewed by a worker on a different model tier and counts only after a pass at score 85 or above. Repeated failures go to an arbiter, then to the user. A writer must submit a full commit hash.
  - **Merge queue:** approved commits merge into a per-run `war-room/<run>` branch. A conflict goes back to its author; any other git failure is retried.
  - **Usage-limit failsafe:** claims pause at the pause threshold. At the stop threshold every worker stops with its conversation kept and resumes automatically at the real reset time. Checkpoints are restored on resume.
  - **Auto finish:** when all work is merged, the run stops its workers, records the measured token cost (which calibrates future estimates), writes a report, and removes every session and fully merged worktree. Unreviewed or uncommitted work is kept and reported. Integration into the user's branch is one click and is never pushed.
  - **Wake paths:** a bus message (parked worker), a resume with stored launch flags (idle worker), native `SendMessage`, and conductor auto-wake.
  - **The War Room app** (`warroom.py app`): a local hub on 127.0.0.1, shown in a chromeless Edge or Chrome window.
    - Home has a war mode master switch with an arming warning, settings for plan defaults, and a runs list with preview and launch.
    - The run view shows a live Flow view of tasks moving Board → Build → Review → Merge queue → Integrated, a Topology view with messages in flight, worker boot sequences, review gates, the merge queue and report, a timeline and an activity feed.
  - **Tiling:** on Windows, one console per worker with the app on the primary screen. On macOS and Linux, a tmux session; this was checked live on Linux.
- The installer pre-approves War Room's routine subcommands. `toggle`, `launch`, `integrate`, `finish`, `shutdown` and `approve` still ask for permission.
- README: a "Guided builds" section for the `local-build` skill and its `self-improving-system` and `token-efficient-system` builds. Both were already shipped and installed, but not documented.

## [0.4.3] - 2026-10-11

### Added
- `docs/demo/council-run-interactive.gif`, recorded from an interactive Claude Code session running Specialist Council 1.3.1, with its scrubbed transcript in `tests/fixtures/council-run-interactive`.

### Fixed
- council-replay reads worker results that newer Claude Code versions return through the `SubagentHandback` tool instead of a final text block.
- It also finds the `council.py resolve` JSON when the command was chained after other output, stops a worker's headline at a table, and accepts `**1. Label**` check headings.
- An agent dispatched without an effort shows its model only, instead of `?`.
- Specialist Council 1.3.2: the skill tells the coordinator to resolve every role, not only forged members. It no longer needs to read `registry.json` itself, because `resolve` already refuses suspended members, and it must not chain `resolve` with `cat`, which triggered a permission prompt. It also says where `runtime.md` lives. An interactive run had done all three wrong.
- plot-deck 0.2.1 credits its author in `plugin.json`, which clears the last `claude plugin validate` warning.

## [0.4.2] - 2026-10-11

### Fixed
- Specialist Council 1.3.1: the runtime guide no longer tells the coordinator to pass full model IDs to the Agent tool. Its `model` field only takes the tier aliases `haiku`, `sonnet`, `opus` and `fable`, so a full ID failed validation and the first dispatch had to be retried. The frontmatter already pins the full ID.
- council-replay redacts user names that contain spaces, and the current user's home in every form, including the project-folder slug.

### Changed
- superpowers now comes from Anthropic's official marketplace listing (v6.4.1, `obra/superpowers` at `5bf4e78`) instead of the `superpowers-dev` marketplace (v6.3.0). The catalog generator handles marketplaces whose entries point at external repos.
- council-replay: IBM Plex is bundled under `tools/council-replay/fonts` (SIL OFL), so the GIF renders the same on every machine and offline.
- Checks now appear when the worker's result arrives, instead of on an invented schedule during the run.
- Three or more agents are laid out in a two-column grid, and three or more `resolve` calls use compact rows.
- `extract.py` skips Agent calls that were rejected, reads methods from the coordinator's summary table, and falls back to the resolved model and effort when the Agent call omits them.
- The demo GIF and test fixture come from a new real run with a cleaner prompt: "Is 221 prime? Factor it. Include the forged arithmetic checker."

## [0.4.1] - 2026-10-11

### Added
- `tools/council-replay`: replays a real Specialist Council transcript as an animation and records it as a GIF. `extract.py` turns a session into replay data and redacts paths and secrets, `replay.html` animates it on a canvas with a built-in GIF encoder, and `record.py` records it in headless Chrome, Edge or Chromium. It is optional and not installed. Standard library only, with no third-party JavaScript.
- `docs/demo/council-run.gif` near the top of the README, recorded from a scrubbed real run in `tests/fixtures/council-run`.

## [0.4.0] - 2026-10-11

### Added
- `--full` installer profile. The default is now a lighter **core** profile: 10 plugins (council, arena, the UI mods, superpowers, mattpocock-skills, karpathy-skills, document-skills, understand-anything), the standalone skills and the `rea` MCP server. `--full` installs all 93 plugins plus the `ansys` MCP server.
- `SECURITY.md`: what the installer changes, which plugins run hooks, and private vulnerability reporting.
- `CONTRIBUTING.md`, this changelog, issue and pull-request templates.
- README: a new top section (what it is, quick start, an example council run) and a security summary.

### Changed
- CI's clean-install job tests the core profile on macOS and the full profile on Linux.

## [0.3.0] - 2026-10-11

### Added
- `moaa` marketplace with all 95 plugins. The 90 third-party ones are pinned to tested commits (`scripts/sync_catalog.py`). Reserved upstream names are listed under aliases: `llm-api-reference`, `persistent-memory` and `persistent-memory-cowork`.
- Specialist Council 1.3.0 ships as a plugin (`specialist-council@moaa`). Forged members live in `~/.claude/specialist-council/forged/`, and `council.py migrate` converts older standalone installs.
- `council.py resolve --role forged-<slug>` for forged members.
- `MODELS.md`, generated from the plugins, listing every agent's model and effort.
- Generated plugin list in the README.
- CI on Linux, macOS and Windows, with clean-install tests on Linux and macOS.
- MIT licence, NOTICE, CITATION.cff and THIRD_PARTY.md.

### Fixed
- The `council.py` allow rule never matched: the quoted path ends in `council.py"`, so the rule can't have a space after `.py`.
- `install.sh` and the scripts were not executable on a fresh Linux or macOS clone.
- The ansys MCP server failed with `mcp` 2.x; its dependencies are now pinned.

## [0.2.0] - 2026-10-11

### Added
- Agent Arena 0.4.x: suspension unregisters a forged member's agent card; `council.py check` validates forged members; one shared model table; the arena library is found automatically when scripts run by hand.

## [0.1.0] - 2026-10-11

### Added
- First one-command installer: plugins, council, arena, skills, MCP servers and settings merge, with uninstall.

[0.5.5]: https://github.com/ahmadhammoud56/MOAA/compare/v0.5.4...v0.5.5
[0.5.4]: https://github.com/ahmadhammoud56/MOAA/compare/v0.5.3...v0.5.4
[0.5.3]: https://github.com/ahmadhammoud56/MOAA/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/ahmadhammoud56/MOAA/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/ahmadhammoud56/MOAA/compare/v0.5.0...v0.5.1
[0.5.0]: https://github.com/ahmadhammoud56/MOAA/compare/v0.4.3...v0.5.0
[0.4.0]: https://github.com/ahmadhammoud56/MOAA/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/ahmadhammoud56/MOAA/releases/tag/v0.3.0
