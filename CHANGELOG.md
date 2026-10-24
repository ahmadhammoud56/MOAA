# Changelog

All notable changes to MOAA. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [SemVer](https://semver.org/).

## [Unreleased]

## [0.13.0] - 2026-10-24

Long tasks that finish, after a harness-engineering write-up for long Opus 5.5 runs: a written brief with
acceptance checks, a progress file, a goal, an evidence review and a resume prompt.

### Added
- **Specialist Council 1.7.0, `/specialist-council:long-task`:** runs a long or multi-session task to completion.
  It writes `brief.md` (deliverables, checkable acceptance, constraints, budget) and keeps `progress.md` current after
  every step, under `.claude/long-task/<slug>/`. It gives the user a `/goal` line built from the acceptance checks,
  checks whether a timed-out or half-finished step already took effect before retrying it, and ends with an evidence
  review saved as `checks.md`. If the task is unfinished it writes `resume.md`, a prompt for a fresh session.
- **Evidence-review claim table:** the peer-reviewer and validation-auditor roles return one row per claim (claim,
  `verified` / `incorrect` / `unresolved`, source checked, required correction), name the missing evidence for
  unresolved rows and leave the edits to the parent.
- **Secret-file deny rules:** the installer adds `Read` deny rules for `.env` files, `keys.env`,
  `~/.claude/allies/keys.env`, `~/.ssh/**`, `~/.aws/credentials` and `*.pem`. It merges them like every other
  setting: the user's own rules stay, and `--uninstall` removes only what it added.
- **MCP health:** `install.py --status --mcp` checks every MCP server's connection (connected, needs
  authentication, failed) and suggests a one-time global install for a failing `npx` server, which `npx` fetches on
  every start. `--doctor` lists failing servers as warnings, and `--status` exits 1 when one fails.

### Changed
- **War Room 0.7.1, retry safety:** when an ally task times out, the retry brief says the first attempt's work is
  already in the worktree (with its commit) and to check `git log` and `git diff` before redoing anything. Workers
  are told to check whether a timed-out or partly failed action already took effect before retrying it.

## [0.12.1] - 2026-10-22

### Added
- **Council vs single-agent benchmark** (`benchmarks/council-vs-solo`): Sonnet alone, Opus alone and the council
  on 5 tasks with fixed answer keys (three code reviews with 25 planted bugs and 10 decoys, 10 statistics claims, 10
  trap questions), 3 runs each, in clean headless sessions with no shell or file writes. `bench.py` runs, resumes and
  scores it on a normal Claude Code login, and `verify_keys.py` re-proves every answer key by execution. Raw results
  for all 45 runs are included.
  - **Result:** both single models scored 100% in every run. The council never did better, cost 2.5–6× as much and
    took 3.5–7× as long. One council run lost its answer to a late worker report.
- **Replay tool, arena runs:** `tools/council-replay` now recognises an Agent Arena transcript and labels it as one:
  contestants, the judge, the verdict and the winner.

### Changed
- **Specialist Council 1.6.1:**
  - It now sizes the job first. Short tasks with a checkable answer get one worker or a direct answer, unless the
    user explicitly asks for several workers. Teams are for ambiguous, long or high-stakes work.
  - It waits for every worker, and after a late report it restates the full answer instead of pointing back to it.
    Headless use keeps only the last message.
- **Specialist Council README** rewritten: marketplace install, use, roles, cost ledger and commands. The old one still
  described the pre-plugin standalone install.
- **README:** the cost section states the benchmark result.
- **prismantis 0.11.0 → 0.34.0** (23 upstream releases).
  - The vendored copy is upstream v0.34.0 without its Codex plugin files and the 14 MB of screenshots in `docs/`
    (1.5 MB instead of 4.3 MB).
  - MOAA's PNG button is re-applied on top. It is now opt-in through `PRISMANTIS_PNG_BUTTON`, which the installer's
    default env sets to 1, so upstream's own test suite passes unchanged: 844 of 844 including the button's 2 tests.
  - `MODIFICATIONS.md` and `png-button.patch` describe the change against clean v0.34.0.

## [0.12.0] - 2026-10-22

The first milestone of the October roadmap: measure what the council costs, start proving what it adds, make the
first install one line, and trim per-prompt overhead.

### Added
- **moaa-core 0.1.0 (new plugin):** `/plugin install moaa-core@moaa` installs the Specialist Council, the Agent Arena
  and moaa-catalog as plugin dependencies, with no clone and no installer. It has no components of its own.
- **Specialist Council 1.6.0, cost ledger:** a `SubagentStop` hook records every finished subagent's input, output
  and cache tokens (each message counted once) in `~/.claude/specialist-council/ledger.jsonl`.
  `council.py cost [--session ID | --days N]` sums them per agent type, and the council skill ends each answer with
  one cost line. Tokens only: no price table is guessed.
- **Specialist Council eval suite** in `plugins/specialist-council/evals/` for `claude plugin eval`: 4 cases
  (factoring, a digit count, an off-by-one review and a Simpson's-paradox claim), each run with and without the
  council so the report shows what the council adds. It needs an API key, so it runs by hand or through the new
  manual **Council evals** workflow (`ANTHROPIC_API_KEY` secret, cost ceiling as an input).
- **`install.py --report`** names enabled plugins that only repeat another enabled plugin's skills.
- **docs/GUIDE.md** (the detailed reference) and **docs/PLUGINS.md** (the generated plugin list);
  `docs/media/social-preview.png` (1280×640) and its HTML source for the repository's social preview.

### Changed
- **`--mode all-on` leaves duplicate plugins off:** a plugin whose every skill another plugin of the same
  marketplace already lists (the 34 `agentic-bundle-*` subsets of agentic-awesome-skills) is no longer enabled, and
  is disabled if it was. On the maintainer machine that drops 283 skills, about 1.8k tokens from every request (23,490 to 21,676 under the all-on listing caps), with
  nothing lost. `--restore` re-enables them. `strict: false` marketplace entries count only their listed skill
  folders.
- **Faster hooks (moaa-catalog 0.3.1, strata 0.1.1):** hook commands no longer start Python once just to check its
  version. The scripts exit 3 on Python older than 3.10 and the command tries the next interpreter, skipping the
  Windows Store alias (exit 49). The catalog prompt hook went from 108–184 ms to 81–117 ms per prompt here.
- **README rewritten** around one first screen: a one-line hook, a two-line `/plugin` install, the council GIF, the
  arena-to-council loop and a feature table (49 KB to about 7 KB). Everything else moved to docs/GUIDE.md.
- **`scripts/sync_catalog.py`** writes the plugin list to docs/PLUGINS.md instead of the README.
- **Marketplace description** now describes MOAA instead of "agent arena and UI mods".

### Fixed
- **CI now runs moaa-catalog's tests** (its prompt hook runs on every prompt but had no CI step).
- **CITATION.cff:** earlier releases bumped `cff-version` (the format version, back to 1.2.0) instead of `version`
  (now 0.12.0).

## [0.11.1] - 2026-10-22

### Changed
- **Agent Arena 0.6.1:** forged council members get every tool except Agent again (`disallowedTools: [Agent]`),
  MCP servers included, so an arena-proven specialist can use whatever the session has. The 60 role agents keep
  their core tool list. With tool search, MCP tools are listed by name and loaded on demand, so the extra cost per
  call is small.

## [0.11.0] - 2026-10-22

### Added
- **`install.py --mode all-on|lean`.** `all-on` enables every catalog plugin (packs included, opt-in ones such as
  claude-mem excepted), so every hook, agent, MCP server and command is live, and sets the skill listing to names
  plus short descriptions (`skillListingMaxDescChars` 200, `skillListingBudgetFraction` 0.003). `lean` disables the
  big packs and restores the earlier listing limits. Settings are backed up; `--uninstall` also restores them.
- **moaa-catalog 0.3.0:** in all-on mode the index and the prompt hook also cover enabled skills whose descriptions
  the listing trims, and point to the Skill tool for them.
- **kit.json `pack` marker** on the 73 big skill packs that `--lean` and the modes switch.

### Fixed
- **`--report` token estimate:** it now follows Claude Code's own listing caps (every name, descriptions cut per
  skill and to a share of the context window) instead of counting full descriptions, which overstated the cost
  several times over. It shows 200k- and 1M-context figures and points to `/context` for exact numbers.
- **Reinstalling kept `pruned`, `mode` and the report history** in the manifest instead of dropping them.

## [0.10.0] - 2026-10-22

Making MOAA easier to start with and cheaper to run.

### Added
- **Work profiles:** `install.py --profile web|data|devops|research|science` (comma-separated for several) adds
  that kind of work's packs to core or full, installed and enabled; `science` also sets up the ansys MCP server.
- **`install.py --report`:** a local summary of the skills listed in every request and their rough token cost, what
  disabled plugins keep out of the prompt, the most used plugins, the skills moaa-catalog served and what was pruned.
  Each run adds a dated line, so the trend shows over time. Nothing leaves the machine.
- **Agent Arena 0.6.0, effort trial:** `/agent-arena-mode:effort-trial` and `scripts/effort.py` measure whether a
  council role finds more at a higher effort, blind-judged, and suggest a preset only when the dearer effort earns
  it (at least 5 points of score or 25% more findings). It never edits `profile.json`.
- **Getting started:** `docs/GETTING_STARTED.md` (a 5-minute walkthrough) and `/moaa-catalog:moaa-help`, which
  explains what is installed and which MOAA tool fits a task.

### Changed
- **moaa-catalog 0.2.0:** short forms expand (k8s, tf, js, ts, py, db, docs, xlsx, pptx, a11y and others), marker
  files in the project (`package.json`, `pyproject.toml`, `main.tf`, `Chart.yaml` and others) boost matching skills
  without ever triggering a suggestion on their own, and harness notices (background tasks) no longer reach the
  hook.

### Fixed
- **`--prune` usage counting:** a slash command now counts only when a user typed it, not when the same text
  appears inside code or a tool call in a transcript.

## [0.9.0] - 2026-10-22

Context cost, after Cloudflare's write-up of their AI code reviewer ("obsessive inference optimization"): most of
their savings came from sending fewer tokens and making fewer calls, not from cheaper models.

### Added
- **moaa-catalog 0.1.0** (core plugin): skills on demand. A cached index of the skills in installed but disabled
  plugins (rebuilt only when plugins or settings change; lookups take milliseconds), `catalog.py search`, a
  `UserPromptSubmit` hook that names up to three strong matches (ordinary prompts add nothing), and
  `catalog.py use`, which loads one skill into the current session and suggests enabling a pack used three times in
  30 days. Its read-only subcommands run without prompts.
- **`install.py --prune [--days N] [--yes]` and `--restore`:** list, and optionally disable, enabled plugins with no
  recorded use (skill, agent, MCP or slash-command use in the transcripts). Plugins with hooks or MCP servers and
  MOAA's own are kept. `--restore` re-enables what was pruned.
- **`install.py --lean`:** brings an install made before 0.9.0 in line with the catalog by disabling the packs it
  now ships disabled; `--restore` undoes it.
- **Context budget:** `--status` and `--doctor` report how many skills and agents every session lists and warn above
  300.
- **README:** a "Context cost: skills on demand" section.

### Changed
- **`--full` installs the big skill packs disabled:** agentic-awesome-skills and its bundles, and every ruflo plugin
  except `ruflo-core` (73 plugins). They stay installed; `claude plugin enable <id>` loads one from the next session.
  Existing installs keep their current choices.
- **Specialist Council 1.5.0:** workers carry an explicit core tool list instead of `disallowedTools: [Agent]`, so no
  call carries MCP tool definitions. The runtime guide orders briefs for prompt caching (identical common part
  first, role-specific part last) and dispatches same-type ensemble workers after the first has started.
- **Agent Arena 0.5.1:** forged council members get the same core tool list.
- **War Room 0.7.0:** an ally task that times out is retried once with double the limit (up to 60 min) instead of the
  same one; a task taken away from an ally worker stops its member process within 15 s; workers are told to batch
  file reads into one turn and to end without a closing summary.
- **Allies 0.2.0:** runs poll for cancellation while the member works, and each run records why it failed
  (`timeout`, `cancelled`, `exit`, `empty`).

## [0.8.1] - 2026-10-18

### Fixed
- **War Room 0.6.1:** the hub no longer does a reverse DNS lookup of the machine when it starts.
  - Python's HTTP server does this by default (`socket.getfqdn()`).
  - On macOS the lookup can stall for 30 seconds or more, so the app could be slow to open or never open.
  - The new hub tests caught it on macOS CI. The hub tests now also wait up to 30 seconds and report a crash clearly.

## [0.8.0] - 2026-10-18

### Changed
- **War Room 0.6.0: the app is redesigned around allies.**
  - Every page shares an icon sidebar (Home, New run, Run, History, Settings) and a **Ctrl+K** command palette.
  - Text is set in IBM Plex Sans and Plex Mono is kept for data. The style stays flat graphite and amber, with 6–8 px corners.
  - Workers are coloured by model family everywhere: Claude, Codex, Gemini, Kimi, DeepSeek and OmniRoute. Ally workers carry a badge and have no console button.
  - **Run view:**
    - A **needs-attention** strip: human gates can be approved or rejected in place.
    - A KPI strip.
    - Team cards.
    - A kanban **Board** (the new default view) whose cards glide between lanes.
    - A **task inspector**: reviews and notes, the commit with its diff stat, the people involved and the task's history.
    - A timeline coloured by family, showing busy stretches.
    - Flow, Tree, Topology, Cost, replay and the worker drill-down are kept.
  - **Home** is split into Home (war mode, plan usage, quick-start templates, runs), **New run** (with a plan editor that picks an engine per worker) and **Settings**.
  - **History** gains a filter and shows each run's team.
  - **New hub routes:**
    - `POST /api/run/<run>/decide` answers a human gate, the same as `warroom.py approve`. It accepts blocked tasks only and needs the app token.
    - `GET /api/run/<run>/task/<id>/diff` gives a commit's diff stat.
    - `/ui.css` and `/ui.js` serve the shared styles and helpers.
  - `/?template=<name>#new` opens a template in the editor.
  - The demo team now includes a Codex builder and a Gemini reviewer.
- **README:** the Allies and Strata sections now explain what each is for, how it stays safe, and how to use it.

## [0.7.1] - 2026-10-18

### Fixed
- **Allies 0.1.1:** the npm shim parser now splits the script path the shim gives (written with backslashes) into
  folders, so it is correct on every OS. 0.7.0's CI failed on Linux and macOS because of this; Windows, where shims
  are used, was not affected. All suites were also run on Linux (WSL) before this release.

## [0.7.0] - 2026-10-17

### Added
- **Allies 0.1.0 (new plugin): other agent CLIs on call.**
  - Claude Code hands a bounded brief to OpenAI Codex, Google Gemini, Moonshot Kimi Code, DeepSeek (Claude Code with
    `--bare` on DeepSeek's Anthropic-format API) or a local OmniRoute gateway. It then reads and checks the answer.
  - Each member uses its own account, so the work spends that service's quota rather than Claude usage.
  - `allies.py doctor` shows what is installed and signed in. `run` gives one member a read-only task, and `ask` sends
    the same brief to several members in parallel.
  - `run --write` works in a separate git worktree. Allies commits the result on branch `ally/<member>-<id>` and never
    touches your checkout.
  - Every run is kept under `~/.claude/allies/runs/`. Keys can live in `~/.claude/allies/keys.env`, outside any
    repository; each member gets only its own key.
  - In read-only work Gemini runs under a shipped policy that denies shell and file-write tools; headless Gemini
    otherwise waits forever for an approval no one can give.
  - Windows short (8.3) paths are expanded before a member runs, because Codex's sandbox denies them. Its
    sandbox also cannot enter the user Temp folder, so keep projects in normal folders.
  - Gemini uses an API key: Google sign-in no longer serves the CLI's free tier. Gemini runs in its own home, set to
    API-key sign-in, so your `~/.gemini` is left alone.
  - `doctor` reports `blocked` when a member's service cannot be reached from the current network.
  - The Claude-format members never read your Claude login.
  - An `allies` skill covers briefing, verification, stretching Claude limits, and what never to send.
  - Verified live with Gemini (API key) on a read-only question, and with Codex: a read-only question (correct answer, no files changed) and a write task (bug fixed
    with a test, committed on its own branch).
- **Strata 0.1.0 (new plugin): layered long-term memory across sessions.**
  - Four layers, after the design of TencentDB Agent Memory: raw sessions, extracted notes with supersession,
    per-project scenes and a user profile.
  - Stored in local SQLite with FTS5, using standard-library Python.
  - The SessionStart hook injects the profile, scenes and recent notes, labelled as data.
  - The SessionEnd hook stores the session and starts one background Haiku extraction. That call has all tools
    denied and saves no session, so it cannot recurse.
  - Secrets are redacted on the way in, and model output is validated before it is stored.
  - The `strata` skill searches, shows, remembers, corrects and forgets.
  - Verified on a real transcript: one Haiku call (71 s) produced 11 accurate notes, a project scene and a profile
    entry.
- **War Room 0.5.0: ally workers.**
  - A plan worker can set `"engine": "codex"` (or gemini, kimi, deepseek, omniroute).
  - The conductor claims that worker's tasks, runs them through allies in the worker's own worktree and completes them
    with the commit. As a reviewer, the worker returns a parsed verdict.
  - Review gates and the merge queue are unchanged, so model families can review each other.
  - A reviewer without a verdict is retried once, then blocked for the human.
  - Ally workers have no console, and stop and resume skip them.
  - The plan editor offers the engines in its model list.
  - New template: `mixed-allies` (Claude plans, Codex builds, Gemini reviews).
  - Verified live through the War Room bus. Codex fixed a function and added four tests in its worktree (58 s).
    Gemini reviewed the commit and passed it at 100 (41 s). The bus then approved the task and queued the merge.
- **OmniRoute checked live:** pinned 3.8.51 started through allies.
  - It listens only on 127.0.0.1 (all three ports).
  - The API and management endpoints refuse requests without a key (401).
  - The traffic inspector, TLS interception and cloud sync are off, and allies forces them off at every start.
  - The `omniroute` member reaches the gateway with your key. With no provider connected it fails at once with a
    clear message.
- **`install.py --with-omniroute`:** installs a pinned `omniroute` from npm and records it, so `--uninstall`
  removes it.
  - `allies.py omniroute start` runs it on 127.0.0.1 only, with an API key required, conversation tracking,
    browser-cookie providers and paid-credit fallback off, and a generated password and JWT secret instead of
    `CHANGEME`.
- Allies and strata join the core profile (13 plugins). Their read-only subcommands run without prompts.

### Changed
- superpowers is tested at 7.0.0 (the catalog already pinned it; `tested_version` said 6.4.1).

### Fixed
- **Allow rules were too broad (security).** MOAA's no-prompt rules for `council.py` and `warroom.py` used
  wildcards around the script and the subcommand. Three consequences:
  - `app*` also matched `approve`, so War Room's human gate could run without a prompt.
  - A subcommand word anywhere in the arguments matched too.
  - A crafted command such as `python -c "..." war-room warroom.py list` ran without a prompt.

  Rules are now pinned to each installed script's exact path, the way Claude calls it, with the subcommand right
  after the path. After a plugin update outside the installer the rules simply stop matching, and you get prompts
  again until you rerun the installer. Reinstalling removes the rules an earlier MOAA install added (recorded in its
  manifest); rules you added yourself are kept.

### Security
Hardening from an independent review before release:
- **Allies:**
  - npm `.cmd` shims are bypassed: allies runs the node script directly, because `cmd.exe` would re-parse task text
    (BatBadBut).
  - Model names are validated.
  - Each member sees only its own credentials. Claude, cloud and other providers' keys are removed from its
    environment.
  - A timeout kills the member's whole process tree.
  - `omniroute stop` checks the pid's command line before killing it.
  - The secrets file is created owner-only.
  - Allies' commits skip repository hooks.
- **War Room ally workers:**
  - A stop kills the running member process and does not report its result.
  - A task held by a job that no longer runs (for example after the conductor restarts) is reclaimed.
  - Finished work is never reopened.
  - A writer with no new commit reports its HEAD for review.
  - Verdicts are case-insensitive.
- **Strata:**
  - Redaction also catches JSON and quoted secrets, "password is ...", JWTs, credentials in URLs and AWS secret keys.
  - Extraction can no longer create global notes or supersede notes of other projects, so a transcript cannot plant
    notes in every project. Only `remember --global` makes global notes.
  - The supersede check and the write happen under one lock.
  - A resumed session is consolidated again only when it grew.
  - Forgetting a note brings back the notes it had superseded.
  - On Windows the background extraction breaks away from Claude Code's job object where allowed.
- `--uninstall` no longer removes an `omniroute` that was installed before MOAA.

## [0.6.0] - 2026-10-14

### Added
- **Installer `--status` and `--doctor`.**
  - `install.py --status` changes nothing. It compares the install with the repo:
    - MOAA plugins against their repo versions;
    - skills, the agent and MCP servers: current, an older MOAA copy (rerun the installer), or edited after install (and whether the installer would overwrite or keep the edit);
    - third-party plugins whose installed version differs from `tested_version` ("drift");
    - old plugin versions left in the cache.
    It exits 1 if anything is missing or outdated.
  - `install.py --doctor` runs every pre-commit check of the release routine in one go, with a pass/fail line each.
- **War Room 0.4.0: spend cap and team templates.**
  - **Spend cap:** `max_cost_usd` in Settings, presets or a plan's `budget`. When the run's API-equivalent statusline cost reaches it, the conductor stops every worker. Spend is summed across resumed sessions, whose counters restart at zero. The run never resumes by itself: `warroom.py resume RUN --max-cost USD`, or Resume in the app, asks for a higher cap. The Cost tab shows spend against the cap, and Preview & launch and `warroom.py plan` show the cap. `warroom.py demo --max-cost 1` shows it working.
  - **Team templates:** feature team, bug hunt, review swarm, research fan-out and refactor. Each has three workers (so it fits the default team size), a reviewer whenever someone writes, and seed tasks. Pick one next to **Write by hand** in New run, or run `warroom.py template NAME > plan.json`. No tokens are spent.
- **Specialist Council 1.4.0: `council.py diff`.** It compares `profile.json` with a git ref (default `HEAD`) or a file (`--against`) and shows changed roles, resolved team presets, model IDs, and roles per tier before and after (`--json` for scripts). It gives no dollar figure: cost depends on how often each role is dispatched.
- **Agent Arena 0.5.0: a library page.** `library.py view [--out FILE] [--open]`, or `/agent-arena-mode:library view`, writes one self-contained HTML page. It shows forged members, each task with its champion and champion changes, and a filterable table of saved agents with assessment-score sparklines and lineage links. It opens the database read-only and leaves out answers and evidence. `library.html#ID` opens one agent. It works offline in dark, light or system theme.
- **`scripts/sync_skills.py`** re-syncs the vendored skills from their upstream repos.
  - Upstream repo, path and full commit now live in `config/kit.json` under `vendored_skills`.
  - `--check` compares with upstream HEAD, and `--check --pinned` with the recorded commit.
  - An update rewrites the skill folders (keeping MOAA's LICENSE and NOTICE), the commits in `kit.json` and the short commits in THIRD_PARTY.md. The commit moves only when content changed.
  - It uses shallow sparse fetches into a short temp path, so deep upstream trees work on Windows.
- **`sync_catalog.py --drift`** lists pinned plugin repos whose upstream HEAD has moved. It needs only the network, not an install.
- **CI:**
  - A weekly **Upstream drift** workflow fails when a vendored skill differs from upstream HEAD, and lists moved plugin repos in the job summary.
  - The main workflow now checks that every vendored skill still matches its recorded upstream commit.

### Changed
- CITATION.cff now carries the current version (it said 0.5.0).

### Notes
- An independent review before release led to these fixes:
  - the conductor's own auto-resume after a usage reset now honours the spend cap;
  - a new cap is validated (a number, not negative, above what the run already spent);
  - `sync_skills.py` refuses an upstream path that is missing or empty, instead of reading it as "delete every file";
  - the library page coerces stored numbers before display;
  - `--drift` reports unreachable repos instead of hiding them;
  - `--status` reports a corrupt JSON file instead of crashing.
- Known limit: the spend cap reads each worker's statusline cost every 20 s, so it can stop a run slightly late.
- `sync_catalog.py --check` reads this machine's installed plugins, so CI cannot run it; `install.py --doctor` runs it locally.

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
