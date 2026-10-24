# MOAA guide

The full reference behind the [README](../README.md): every component in detail, install options and maintenance. The generated plugin list is in [PLUGINS.md](PLUGINS.md).

## Council replays

`tools/council-replay` turns any council session transcript into the animation above. It is optional, isn't installed, and needs only Python and Chrome, Edge or Chromium:

```bash
python tools/council-replay/record.py ~/.claude/projects/<project>/<session>.jsonl -o council-run.gif
```

`record.py` serves the page on `127.0.0.1`, records it in a headless browser and writes the GIF. With no browser found it prints a URL instead; open it and click **Export GIF**. Run `extract.py <session>.jsonl` to see the replay data first. User paths, e-mail addresses and secret-looking strings are redacted, but check the GIF before you share it. To reproduce the demo, use `tests/fixtures/council-run/session.jsonl`.

The same task in an interactive session with Specialist Council 1.3.1: both workers were dispatched on the first try. The coordinator resolved only the forged member, so the analyst ran on its frontmatter defaults (`tests/fixtures/council-run-interactive`):

![Replay of an interactive Specialist Council session: one council.py resolve, two agents in parallel, both agree that 221 = 13 × 17](demo/council-run-interactive.gif)

## War Room

**A team of real Claude Code sessions working one big job in parallel.** Subagents share one context and one turn. A War Room is different: it starts several independent `claude` sessions, each with its own Specialist Council role, model, effort, plugins and permissions. They coordinate through a shared task board and message bus, review each other's work and merge it into one branch. A local app shows the whole team at work.

![War Room run view: a team of Claude, Codex and Gemini workers, the board, review gates and a needs-attention strip](../plugins/war-room/docs/media/run-live.png)

### How a run works

1. **Plan.** Describe the job, either in the app (Home → New run) or to Claude in a chat (`/war-room`). The plan names the workers (for example a planner, two builders, a reviewer and an arbiter), the seed tasks and the budget. In the app, **Draft with Claude** writes the plan with one headless Sonnet call (about 5k tokens, no tools); a team template costs nothing. You can edit every worker and task before saving, and run any worker on an ally engine (Codex, Gemini, Kimi, DeepSeek or OmniRoute) instead of Claude.
2. **Preview and launch.** The preview lists every worker with its role, model, effort and plugins, plus a calibrated token estimate and the usage guard. Launching needs war mode armed, an acknowledgement and a confirm code tied to that exact plan.
3. **Work.** Workers claim tasks from the board, message each other and checkpoint as they go. Builders write in their own git worktree. Parked workers wait for new work without using tokens, and the conductor wakes idle ones when work arrives.
4. **Review gates.** Finished work counts only after a reviewer on a **different model** passes it (score 85 by default). Failed work goes back to its author. After repeated failures an arbiter decides, and after that you do.
5. **Merge.** Approved commits merge into a per-run branch, `war-room/<run>`. Merge conflicts go back to the author.
6. **Finish.** When everything is merged, the run stops its workers, measures the real token cost (this calibrates later estimates), removes its sessions and merged worktrees, and writes a report. Merging into your own branch is a separate **Integrate** step, and it never pushes.

### The app

![War Room home: war mode, plan usage, quick-start templates and runs](../plugins/war-room/docs/media/home.png)

- **Pages:** Home (war mode switch, plan usage, quick-start templates, runs), New run, the run view, History and Settings, behind a slim sidebar. **Ctrl+K** opens a command palette everywhere.
- **New run:** a folder picker, a job prompt and team templates (feature team, bug hunt, review swarm, research fan-out, mixed allies, refactor) that fill the plan editor at no token cost. Each worker gets a role and an engine: a Claude tier, or an ally.
- **Run view:**
  - a **needs-attention** strip for human gates (approve or reject in place), failed reviews, spend near the cap and a silent conductor;
  - a KPI strip: tasks merged, the 5-hour window, spend, who is working (Claude versus allies) and gates waiting;
  - the team, coloured by model family (Claude, Codex, Gemini, Kimi, DeepSeek, OmniRoute);
  - **Board** (a kanban), **Flow**, **Tree**, **Topology** and **Cost** views, review gates, the merge queue, activity and a family-coloured timeline.
- **Inspectors:** click a task for its reviews, notes, commit and diff stat; click a worker for its tool calls, messages, checkpoints and usage charts, and a button to raise its console.
- **Settings:** team size, the usage guard, a spend cap, gates, presets, alerts, theme, plugins per worker kind and a default model per role.
- **Replay** of any finished run at up to 120x, and a **History** page with outcomes, review results and measured cost.
- **Alerts:** a toast, a desktop notification and a sound when a human gate opens or a run stops or finishes.
- **Look:** flat graphite and amber in dark, light or system theme, sans for text and mono for data, with mechanical motion that turns off under reduced-motion settings.

![War Room Cost view: spend per worker, the 5-hour window with its projection, and the cost model](../plugins/war-room/docs/media/run-cost.png)

On Windows the app sits on the left of the main screen, with one attached console per worker in a grid on the right, so you can type into any worker. Each console's title shows the worker's state. On macOS and Linux the workers run in a tiled tmux session.

### Safety rails

- **Nothing launches without you.** War mode starts SAFE. Every launch needs the switch armed, an acknowledgement and the plan's confirm code, and Claude cannot arm it silently.
- **Narrow permissions.** Each worker runs with an allow-list for its kind. Push, publish, delete and spend are denied, and workers bring those requests to you as human gates.
- **Usage guard.** At the pause threshold (85% of the 5-hour window by default), workers stop claiming new tasks, checkpoint and park. At the stop threshold (95%) every worker stops; conversations are kept, and the team resumes after the limit resets.
- **Spend cap.** Set a cap in USD (the API-equivalent statusline cost of all workers, counted across resumed sessions) in Settings or a plan's `budget.max_cost_usd`. The run stops when it is reached and does not resume by itself; `warroom.py resume RUN --max-cost USD` (or Resume in the app) continues with a higher cap.
- **Trusted folders only.** War Room works only in folders Claude Code already trusts, and never bypasses the trust prompt.
- **Local only.** The app's server listens on 127.0.0.1, checks the Host header and requires a per-session token on every action.

### Cost, and when to use it

A War Room costs far more than subagents. Every worker loads its own context, and a measured three-worker Haiku/Sonnet run processed 3–4M tokens, mostly cache reads. Use it for jobs with several independent streams of work, or with audits between steps. The `/war-room` skill tells you when a few subagents would do instead.

### Try it

```bash
python plugins/war-room/warroom.py demo
```

The demo plays a simulated six-worker run in the app for two to three minutes, with claims, a failed review, an arbitration and merges. It starts no Claude sessions and uses no tokens. Add `--max-cost 1` to watch the spend cap stop it.

`python plugins/war-room/warroom.py template` lists the team templates; `template feature-team --project PATH --goal "..." > plan.json` writes one as a plan file for `warroom.py plan`.

```bash
python plugins/war-room/warroom.py app --install-shortcut
```

This adds War Room to the Start menu and the desktop. `python plugins/war-room/warroom.py app` opens the app directly. Full details are in [plugins/war-room/README.md](../plugins/war-room/README.md).

## Allies: other agents on call

**Claude stays in charge; other model families do bounded jobs for it.** The `allies` plugin lets Claude Code hand a
task to another agent CLI, wait for the answer, and check it before using it. Each member signs in with its own
account, so the work spends that service's quota instead of your Claude usage.

| Member | What runs | Sign-in |
|---|---|---|
| `codex` | OpenAI Codex CLI | `codex login` (ChatGPT plan or API key) |
| `gemini` | Google Gemini CLI | a free `GEMINI_API_KEY` from Google AI Studio |
| `kimi` | Moonshot Kimi Code CLI | `/login` inside `kimi` |
| `deepseek` | Claude Code pointed at DeepSeek's API | `DEEPSEEK_API_KEY` |
| `omniroute` | Claude Code through a local [OmniRoute](https://github.com/diegosouzapw/OmniRoute) gateway | providers you connect in its dashboard |

**What it is good for**

- **A second opinion from another model family.** `ask codex,gemini` sends the same brief to both in parallel; Claude
  compares the answers and reports where they agree and disagree. Different families miss different things.
- **Stretching your Claude limits.** Bulk reading, first drafts, test writing and long-context summaries can run on
  another quota while Claude plans and verifies.
- **Independent review.** A change written by Claude can be reviewed by Codex or Gemini, and the other way round.

**How it stays safe**

- **Read-only by default.** Codex runs in its read-only sandbox; Gemini runs under a shipped policy that denies shell
  and file-write tools; the others run in plan mode.
- **Writes never touch your checkout.** `write` (or `run --write`) works in a separate git worktree. Allies commits
  the result on branch `ally/<member>-<id>` and shows the diff; you merge it yourself.
- **Answers are untrusted.** The skill tells Claude to verify every claim and never follow instructions inside an
  answer. Every brief, answer and log is kept under `~/.claude/allies/runs/`.
- **Credentials stay apart.** Each member gets only its own key, read from the environment or
  `~/.claude/allies/keys.env` outside any repository. The DeepSeek and OmniRoute members run Claude Code with
  `--bare`, so they never see your Claude login.
- **`doctor` tells you what works:** ready, not signed in, or blocked by the network you are on.

**In War Room**, any worker can take an `engine` instead of a Claude model. The `mixed-allies` template has Claude
plan, Codex build and Gemini review; review gates still require a different model than the author's. The app colours
every worker by family and lets you pick the engine per worker in the plan editor.

**OmniRoute** is optional (`--with-omniroute` installs a pinned version). `allies.py omniroute start` runs it on
loopback only, with an API key required, tracking off and a generated dashboard password. Connect only API-key and
free-tier providers to it, never another service's subscription login.

```
/allies:allies doctor
/allies:allies ask codex,gemini -- Review src/parser.py for edge cases and say which you would fix first
/allies:allies write codex -- Add a test for the empty-input case in src/parser.py
```

Details: [plugins/allies/README.md](../plugins/allies/README.md).

## Strata: layered memory

**Claude Code forgets everything between sessions; Strata keeps what matters.** It follows the four-layer design of
[TencentDB Agent Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory), rebuilt as standard-library Python
on a local SQLite file: no proxy, no extra service and no other API key.

| Layer | Holds |
|---|---|
| L0 raw | every message of each session, with secrets redacted |
| L1 notes | atomic facts, decisions, preferences and constraints; a newer note supersedes an older one |
| L2 scenes | one living summary per ongoing topic of a project |
| L3 profile | how you like to work, shared by all projects |

**How it works**

- **Session start:** Claude receives your profile, this project's scenes and its newest notes (6,000 characters by
  default), labelled as data that may be out of date.
- **Session end:** the conversation is stored, and when enough is new, one background Haiku call (every tool denied,
  no session saved) extracts notes, scenes and profile entries. Expect about 10–20k Haiku tokens per session.
- **Recall:** the skill searches the upper layers first and falls back to raw conversations, so "what did we decide
  about the cache last week?" finds the answer.
- A project is its git repository root, so every worktree of a repository shares one memory.

**You stay in control:** `remember` adds a note yourself (only `--global` makes it shared across projects), `forget`
removes a note, a scene or a whole session, `show` and `stats` list what is stored, and `config auto off` stops the
background extraction. Secrets that look like keys, tokens or passwords are redacted before storage, extraction
output is validated before it is saved, and injected memory is marked as data, never instructions.

```
/strata:strata search cache invalidation
/strata:strata remember "Always run the WSL suite before a release" --kind preference
/strata:strata forget 42
```

Strata needs no worker process or background service; claude-mem is still available with `--with-claude-mem`. Details:
[plugins/strata/README.md](../plugins/strata/README.md).

## Using it: council, arena, saving, forging

All four work at any time and on their own. Nothing needs to be started first.

| What | How | What happens |
|---|---|---|
| **Council** | Ask for a council or a specialist team, or run `/specialist-council:specialist-council`. | Picks 2 to 3 of the 60 role agents (plus any active forged members), resolves each one's model and effort with `council.py resolve`, runs them, then integrates and verifies the result. |
| **Arena** | `/agent-arena-mode:<mode> [--agents N] [--reuse IDS] -- TASK`, where mode is judge, tournament, swarm, league, evolution, synthesis, redteam or cascade. | Workers compete on a frozen task and rubric, and the `agent-arena-judge` scores them. |
| **Saving** | Automatic. Every judged arena result is written to the library. Add `--no-library` to opt out. | Stored in `~/.claude/plugins/data/agent-arena-mode-moaa/library.sqlite3`. Browse with `/agent-arena-mode:library list`; reuse with `library use ID -- TASK`, or `--reuse ID` in any mode. |
| **Forging** | `/agent-arena-mode:library promote ID`. It shows the evidence first (`promote --check`). | Writes `council-forged-<slug>` with its validated model and effort, a knowledge base, and a registry entry. The council can use it from the next session. |

Forging rules:
- **Eligibility:** the agent must be validated in 2 or more independent runs, with every validated score at least 85, a score spread of at most 10, and nothing in its lineage invalidated.
- **Earning a second run:** reuse a saved agent in a new arena run with `--reuse ID`.
- **Suspension:** a later failed validation suspends the member automatically and unregisters its agent card. `python <council plugin dir>/council.py check` validates the 60 roles plus every forged member.
- **Command line:** you can run the library by hand without Claude Code: `python <plugin dir>/scripts/library.py list|show|promote|council|view`. It finds the installed library on its own, so `--database` is optional.
- **Library page:** `library.py view --open` (or `/agent-arena-mode:library view`) writes one self-contained HTML page: forged members, each task's champion and champion changes, and every saved agent with its assessment scores and lineage. It reads the database read-only and leaves out answers and evidence.
- **Not shipped:** no forged members come with this kit. Every machine forges its own.

## Profiles

| | Core (default) | Full (`--full`) |
|---|---|---|
| Plugins | 15: moaa-core, council, arena, moaa-catalog, war-room, allies, strata, flightdeck, plot-deck, prismantis, superpowers, mattpocock-skills, karpathy-skills, document-skills, understand-anything | 98 (100 with `--with-claude-mem`) |
| Standalone skills | 10 | 10 |
| MCP servers | `rea` | `rea`, `ansys` |
| Context cost | light | heavy: 1,000+ skills and many hooks |

Start with core. Rerunning with `--full` later adds the rest without disturbing anything already installed.

### Guided builds

The `local-build` skill walks you through a build guide one step at a time. It fills each step with your real project, runs a step only after you confirm it, and has a fresh sub-agent verify the step before moving on. Everything runs locally, with no account and no network access. The builds are plain Markdown files in [`skills/local-build/builds/`](../skills/local-build/builds/):

| Build | What you get |
|---|---|
| `self-improving-system` | A loop that reviews your recent sessions on a schedule, applies small fixes itself, and asks you before any big change. It has three local collectors, an orchestrator, and an improve step that turns findings into CLAUDE.md rules, skills and fixes. A scheduled task runs it, and one command stops it. |
| `token-efficient-system` | More work before you hit your usage limit, by cutting what Claude Code loads and re-reads every session. |

```
/local-build self-improving-system
```

To add a build, drop a new `builds/<slug>.md` file in the same format.

## Context cost: skills on demand

Every enabled plugin lists each of its skills (name and one-line description) in every request Claude Code sends,
whether the skill is used or not; only a used skill's full instructions are loaded. With all 98 plugins enabled that
is about 2,500 listed skills on every turn, every subagent call and every council worker. Prompt caching makes the
repeats cheap but not free, and anything that changes early in the prompt (the tool set, a CLAUDE.md edit) rewrites
the whole cached prefix. The cache also expires after about five minutes idle.

Claude Code already caps the listing: every skill name is always listed, but descriptions are cut to
`skillListingMaxDescChars` (default 1536) and to `skillListingBudgetFraction` of the context window (default 1%),
least-used first. Names alone for about 3,600 skills still come to roughly 20,000 tokens per request.

MOAA offers two modes, switched with `install.py --mode`:

- **`all-on`**: every plugin enabled, so every hook, agent, MCP server and command is live, with the listing
  cut to names plus short descriptions (200 characters, 0.3% of the window). moaa-catalog then supplies the full
  description of an enabled skill too when a prompt matches it.
- **`lean`** (what `--full` installs): the big packs below are disabled; their skills are served on demand.

Either way:


- **`--full` installs the big packs disabled**: agentic-awesome-skills and its bundles, and every ruflo plugin except
  `ruflo-core`. They stay on disk; `claude plugin enable <id>` turns one on from the next session. An install from
  before 0.9.0 gets the same with `install.py --lean` (here it cut the listed skills from 3,630 to 1,148).
- **[moaa-catalog](../plugins/moaa-catalog/README.md)** (core) indexes the skills of disabled plugins. Claude searches it
  when no listed skill fits, a prompt hook names up to three strong matches (ordinary prompts add nothing), and
  `catalog.py use` loads one skill into the current session. A pack used three times in 30 days gets an enable
  suggestion.
- **`--prune`** lists enabled plugins with no recorded use in `--days` (default 45), keeping plugins that work through
  hooks or MCP servers and MOAA's own; `--yes` disables them and `--restore` undoes it.
- **`--status` and `--doctor`** report how many skills and agents every session lists, and warn above 300.
- **Council workers** carry an explicit core tool list instead of every MCP tool, and the council and War Room briefs
  keep the shared part first and identical so parallel workers of one type reuse the cache.
- **Effort is measured, not guessed:** `/agent-arena-mode:effort-trial` runs council roles at two efforts on tasks
  with checkable findings, judges them blind and suggests a preset only when the dearer effort earns it.
- **`--report`** shows what every request costs you and what the catalog saved.

## Install options

Both wrappers pass these flags through to `scripts/install.py`:

| Flag | Effect |
|---|---|
| `--full` | Install all 98 plugins and the ansys MCP server; the big skill packs install disabled (see [Context cost](#context-cost-skills-on-demand)). The default is the core profile. |
| `--with-omniroute` | Also install the [OmniRoute](https://github.com/diegosouzapw/OmniRoute) gateway from npm (pinned) for the allies' free-tier fallback. It is not started; `allies.py omniroute start` runs it with locked-down settings. |
| `--with-claude-mem` | Also install claude-mem and claude-mem-cowork (with `--full`). They need a model-provider key, which you set up through claude-mem's own setup, and they run a background worker on port 37777. |
| `--upstream` | Install third-party plugins from their own marketplaces at the latest version, instead of the pinned `moaa` catalog. |
| `--skip-ansys` / `--skip-mcp` | Skip the ansys server, or both MCP servers. |
| `--dry-run` | Print every command without changing anything. |
| `--uninstall` | Reverse everything recorded in `~/.claude/.moaa-manifest.json`. |
| `--status` | Change nothing; compare the install with this repo. It lists MOAA plugins, skills, agents and MCP servers that are outdated, missing or edited after install, third-party plugins whose version differs from the tested one, and old plugin versions left in the cache. Add `--verbose` to list every plugin. Exits 1 if anything is missing or outdated. |
| `--prune [--days N] [--yes]` | List enabled plugins with no recorded use in N days (default 45); with `--yes`, disable them. Hook and MCP plugins and MOAA's own are kept. |
| `--profile NAME[,NAME]` | Add the packs for a kind of work on top of core (or full), installed and enabled: `web`, `data`, `devops`, `research`, `science` (also the ansys MCP server). |
| `--mode all-on` / `--mode lean` | Switch between every plugin enabled with a trimmed skill listing, and the big packs disabled. Settings are backed up; `lean` restores the earlier listing limits. |
| `--report` | Local summary: skills listed per request and their rough token cost, most used plugins, skills the catalog served, pruned plugins. Nothing leaves the machine. |
| `--lean` | On an install made before 0.9.0, disable the packs the catalog now ships disabled. |
| `--restore` | Re-enable every plugin `--prune` or `--lean` disabled. |
| `--update` | Clone installs: `git pull --ff-only`, reinstall with the same profile and mode, print the changelog since your version. |
| `--auto-update` | GitHub marketplace installs: set `autoUpdate` on the MOAA marketplace so Claude Code updates it in the background. |
| `--status --mcp` | Also check every MCP server's connection, with a hint for slow `npx` servers. `--doctor` lists any that fail. |
| `--doctor` | Run every pre-commit check: all test suites, `MODELS.md`, the catalog, the public-release scan and `claude plugin validate`. For maintainers. |

Restart Claude Code afterwards. The installer respects `CLAUDE_CONFIG_DIR`, so you can trial it in a throwaway config directory:

```bash
CLAUDE_CONFIG_DIR=/tmp/moaa-test ./install.sh --dry-run
```

## Use it as a plugin marketplace

The `moaa` marketplace lists all 100 plugins of the setup: the 10 MOAA plugins plus 90 third-party plugins. The third-party ones are referenced at the exact commit tested here, never copied.

```
/plugin marketplace add ahmadhammoud56/MOAA
/plugin install moaa-core@moaa         # council + arena + moaa-catalog, as dependencies
/plugin install war-room@moaa          # optional add-ons: war-room, allies, strata
/plugin install superpowers@moaa       # any of the 100, e.g. ruflo-core@moaa, ecc@moaa
```

- **MOAA plugins:** `moaa-core`, `specialist-council`, `agent-arena-mode`, `war-room`, `allies`, `strata`, `moaa-catalog`, `flightdeck`, `plot-deck` and `prismantis`. `moaa-core` has no components of its own; it pulls in the council, the arena and moaa-catalog, which is the full council → arena → forging loop; add `war-room` to run whole teams of council workers in parallel (see [War Room](../plugins/war-room/README.md)).
- **Third-party plugins** keep their upstream names. The exceptions are three names that are reserved for Anthropic's own plugins and so can't appear in a third-party marketplace:

  | Upstream name | Name in `moaa` |
  |---|---|
  | `claude-api` | `llm-api-reference` |
  | `claude-mem` | `persistent-memory` |
  | `claude-mem-cowork` | `persistent-memory-cowork` |

- **Allow rules:** to let `council.py` run without permission prompts, add `Bash(python *specialist-council*council.py*)` and `PowerShell(python *specialist-council*council.py*)` to your settings. The full installer adds them for you.
- **Installer only:** the standalone skills, the MCP servers and the settings come only with the full installer above.

Every agent's model and effort are stored inside the plugins themselves; see [MODELS.md](../MODELS.md).

## What the installer does

1. Adds each needed marketplace: the upstream GitHub ones, plus this repo as the `moaa` marketplace for the vendored plugins.
2. Installs the profile's plugins from `config/kit.json` at user scope, from the pinned `moaa` catalog. Pass `--upstream` to take third-party plugins from their own marketplaces at the latest version instead. A plugin you already have from its upstream marketplace is kept as is. prismantis is installed disabled; enable it with `claude plugin enable prismantis@moaa`.
3. Copies the standalone skills to `~/.claude/skills`. A skill that already exists there and wasn't installed by the kit is left untouched.
4. Installs the Specialist Council as the `specialist-council@moaa` plugin (60 `specialist-council:council-*` agents plus the skill). An older standalone council install is migrated: forged members move to `~/.claude/specialist-council/forged/`, and the duplicate skill and agents are backed up and removed.
5. Merges settings into `~/.claude/settings.json`, after writing a timestamped backup. The merge never overwrites anything:
   - Permission lists are unioned.
   - `env` keys and the defaults (model, theme, and so on) are added only when they're absent.
   - `enabledPlugins` entries you already set are kept.
   - It adds allow rules so `council.py` runs without permission prompts, plus the env settings `ECC_GATEGUARD=off` and `CLAUDE_CODE_OVERLOADED_RETRY_MAX_DELAY_MS=60000` (Claude Code 2.1.296: retry an overloaded API for up to a minute instead of giving up early).
6. Adds the MCP servers at user scope:
   - `rea` (`npx rea-agents@6.4.0`).
   - `ansys`: cloned at a pinned commit into `~/.claude/kit-tools/ansys-mcp-server`, with `vendor/ansys-mcp-server.patch` applied, inside its own venv.
7. Runs `council.py check` and writes the manifest.

Rerunning is safe: anything already present is skipped.

## Tests

```bash
python -m unittest discover -s tests                         # installer
(cd plugins/specialist-council && python -m unittest discover -s tests)
(cd plugins/agent-arena-mode && python -m unittest discover -s tests)
(cd plugins/war-room && python -m unittest discover -s tests && python tests/test_bus.py)
(cd plugins/allies && python -m unittest discover -s tests)
(cd plugins/strata && python -m unittest discover -s tests)
(cd plugins/moaa-catalog && python -m unittest discover -s tests)
```

The council also has an eval suite in `plugins/specialist-council/evals/` for `claude plugin eval`. Each case runs
with the council and without it, so the report shows what the council adds. It spends API tokens and needs an API
key, so it runs only by hand: locally with

```bash
cd plugins/specialist-council
claude plugin eval . --allow-tools Agent --no-publish --max-cost-usd 10
```

or in GitHub Actions through the manual **Council evals** workflow (it needs the `ANTHROPIC_API_KEY` secret).

`python scripts/install.py --doctor` runs all of these plus every other pre-commit check in one go. `python scripts/scan.py` checks the tree for secrets and machine-specific paths. Run it before every push. `python scripts/scan.py --public` also fails on any vendored item without a clear licence.

## Updating the kit from a working machine

This repo is the canonical source: on the maintainer machine it lives at `~/code/claude-kit`, and the live install's `moaa` marketplace points at it. Edit here, bump the plugin version in `plugins/<name>/.claude-plugin/plugin.json`, then rerun the installer. It runs `claude plugin marketplace update moaa` before installing. Plugin versions that were tested together are recorded as `tested_version` in `config/kit.json`. After updating any third-party plugin, run `python scripts/sync_catalog.py` to re-pin the catalog to the installed commits, and run `python scripts/models_doc.py` after changing any model or effort preset. The tests fail if `MODELS.md` drifts. `python plugins/specialist-council/council.py diff` shows how a preset change moves roles, team presets and the tier mix against the last commit (or `--against REF|FILE`).

Vendored skills record their upstream repo, path and commit in `config/kit.json` (`vendored_skills`). `python scripts/sync_skills.py --check` compares them with upstream HEAD, and `python scripts/sync_skills.py` updates them, keeping MOAA's LICENSE and NOTICE files and rewriting the commits in `kit.json` and THIRD_PARTY.md. `python scripts/sync_catalog.py --drift` lists pinned plugin repos with newer upstream commits. A weekly GitHub Actions job runs both and fails when a vendored skill has drifted; CI also checks that every vendored skill still matches its recorded commit.

See [THIRD_PARTY.md](../THIRD_PARTY.md) for the source and licence of everything vendored or referenced.
