# MOAA: Mother of All Agents

[![CI](https://github.com/ahmadhammoud56/MOAA/actions/workflows/ci.yml/badge.svg)](https://github.com/ahmadhammoud56/MOAA/actions/workflows/ci.yml) [![Release](https://img.shields.io/github/v/release/ahmadhammoud56/MOAA)](https://github.com/ahmadhammoud56/MOAA/releases) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**Turn Claude Code into a team.** MOAA gives you a **Specialist Council** of 60 expert agents, each with its own model and effort level, and an **Agent Arena** where agents compete and get judged. Agents that keep winning are **forged** into new permanent council members. It installs with one command or loads as a plugin marketplace.

Created by **[Ahmad Hammoud](https://github.com/ahmadhammoud56)**. The Specialist Council and the Agent Arena are original work; everything else is credited in [NOTICE](NOTICE) and [THIRD_PARTY.md](THIRD_PARTY.md).

## Quick start

```bash
git clone https://github.com/ahmadhammoud56/MOAA.git && cd MOAA
./install.sh              # macOS / Linux / Git Bash  (Windows PowerShell: .\install.ps1)
```

Restart Claude Code, then try:

```
/specialist-council:specialist-council  Is 221 prime? Factor it.
/agent-arena-mode:judge --quick -- Write fib(n) with fib(1)=fib(2)=1 and give fib(20).
```

Prefer to pick plugins yourself? Run `/plugin marketplace add ahmadhammoud56/MOAA` inside Claude Code; see [Use it as a plugin marketplace](#use-it-as-a-plugin-marketplace).

## What a council run looks like

![Replay of a real Specialist Council run: council.py resolves each role's model and effort, two agents run in parallel, the coordinator cross-checks them and returns 221 = 13 × 17](docs/demo/council-run.gif)

The animation replays a real run from its transcript, compressed from 44 s. Here is the coordinator's text output from an earlier run of the same task (lightly trimmed):

```
221 is not prime. 221 = 13 × 17.
Both workers agree. Check: 13 × 17 = 221, and 15² − 2² = 221. 13 and 17 are prime.

Dispatched (mode: ensemble, parent as judge):
- specialist-council:council-analyst                        claude-opus-5-5 / high    (Fermat factorization, gcd test)
- council-forged-independent-method-arithmetic-checker      claude-sonnet-5-5 / high  (trial division, difference of squares)
council.py resolve ran for both, with no permission prompt.
```

The forged checker in this run is an arena agent that was validated in 2 separate runs with scores of 97 and 95, then promoted into the council. That loop is what MOAA is built around:

```
 task ──► Specialist Council (60 roles, per-role model + effort) ──► verified answer
            ▲                                      │
            │ forge (≥2 validated runs, every      ▼
            │ score ≥ 85, spread ≤ 10)      Agent Arena (8 modes, judge + validator)
            └──────────── library of winning agents ◄─┘
```

### Record your own

`tools/council-replay` turns any council session transcript into the animation above. It is optional, isn't installed, and needs only Python and Chrome, Edge or Chromium:

```bash
python tools/council-replay/record.py ~/.claude/projects/<project>/<session>.jsonl -o council-run.gif
```

`record.py` serves the page on `127.0.0.1`, records it in a headless browser and writes the GIF. With no browser found it prints a URL instead; open it and click **Export GIF**. Run `extract.py <session>.jsonl` to see the replay data first. User paths, e-mail addresses and secret-looking strings are redacted, but check the GIF before you share it. To reproduce the demo, use `tests/fixtures/council-run/session.jsonl`.

The same task in an interactive session with Specialist Council 1.3.1: both workers were dispatched on the first try. The coordinator resolved only the forged member, so the analyst ran on its frontmatter defaults (`tests/fixtures/council-run-interactive`):

![Replay of an interactive Specialist Council session: one council.py resolve, two agents in parallel, both agree that 221 = 13 × 17](docs/demo/council-run-interactive.gif)

## War Room

For giant or multi-workflow jobs, `war-room` runs a team of real Claude Code workers in parallel. The coordinator picks council roles, models, efforts and a curated plugin set per worker; finished work goes through review gates on a different model tier and merges into a per-run branch. Usage limits pause, stop and resume the team automatically, and a finished run cleans up after itself. Everything is visible live in a local app:

![War Room run view: workers, the Flow view with tasks merged, review gates with pass and fail scores, merge queue and activity](plugins/war-room/docs/media/run-live.png)

Arm war mode in the app (`python plugins/war-room/warroom.py app`), then ask Claude for a War Room; you review the plan and launch it yourself. See [plugins/war-room/README.md](plugins/war-room/README.md).

## Profiles

| | Core (default) | Full (`--full`) |
|---|---|---|
| Plugins | 11: council, arena, war-room, flightdeck, plot-deck, prismantis, superpowers, mattpocock-skills, karpathy-skills, document-skills, understand-anything | 93 (95 with `--with-claude-mem`) |
| Standalone skills | 10 | 10 |
| MCP servers | `rea` | `rea`, `ansys` |
| Context cost | light | heavy: 1,000+ skills and many hooks |

Start with core. Rerunning with `--full` later adds the rest without disturbing anything already installed.

### Guided builds

The `local-build` skill walks you through a build guide one step at a time. It fills each step with your real project, runs a step only after you confirm it, and has a fresh sub-agent verify the step before moving on. Everything runs locally, with no account and no network access. The builds are plain Markdown files in [`skills/local-build/builds/`](skills/local-build/builds/):

| Build | What you get |
|---|---|
| `self-improving-system` | A loop that reviews your recent sessions on a schedule, applies small fixes itself, and asks you before any big change. It has three local collectors, an orchestrator, and an improve step that turns findings into CLAUDE.md rules, skills and fixes. A scheduled task runs it, and one command stops it. |
| `token-efficient-system` | More work before you hit your usage limit, by cutting what Claude Code loads and re-reads every session. |

```
/local-build self-improving-system
```

To add a build, drop a new `builds/<slug>.md` file in the same format.

## Security, in short

MOAA installs third-party plugins, and some of them run hooks, meaning commands that fire on prompts, tool calls or session start, with your user permissions. Every third-party plugin is pinned to a tested commit, but pinning is not an audit.

The core profile keeps hooks to a handful. Your `settings.json` is backed up and merged into, never overwritten, and `--uninstall` reverses every change the installer recorded. Read [SECURITY.md](SECURITY.md) before using `--full`, and use `--dry-run` to preview every command.

## Requirements

- Claude Code 2.1.296 or newer, logged in (`claude --version`). The council pins `claude-*-5-5` and `claude-fable-5-1` model IDs, and older builds reject them.
- git, Python 3.10+, and Node 20+ (for `npx`).
- Optional: an Ansys install, so the ansys MCP server (`--full`) can do real work. Without one it installs but stays idle.
- Windows: if your Claude config dir has a long path, marketplace clones can fail with `Filename too long`. Run `git config --global core.longpaths true` once to fix it.

## Install options

Both wrappers pass these flags through to `scripts/install.py`:

| Flag | Effect |
|---|---|
| `--full` | Install all 93 plugins and the ansys MCP server. The default is the core profile. |
| `--with-claude-mem` | Also install claude-mem and claude-mem-cowork (with `--full`). They need a model-provider key, which you set up through claude-mem's own setup, and they run a background worker on port 37777. |
| `--upstream` | Install third-party plugins from their own marketplaces at the latest version, instead of the pinned `moaa` catalog. |
| `--skip-ansys` / `--skip-mcp` | Skip the ansys server, or both MCP servers. |
| `--dry-run` | Print every command without changing anything. |
| `--uninstall` | Reverse everything recorded in `~/.claude/.moaa-manifest.json`. |

Restart Claude Code afterwards. The installer respects `CLAUDE_CONFIG_DIR`, so you can trial it in a throwaway config directory:

```bash
CLAUDE_CONFIG_DIR=/tmp/moaa-test ./install.sh --dry-run
```

## Use it as a plugin marketplace

The `moaa` marketplace lists all 96 plugins of the setup: the 6 MOAA plugins plus 90 third-party plugins. The third-party ones are referenced at the exact commit tested here, never copied.

```
/plugin marketplace add ahmadhammoud56/MOAA
/plugin install specialist-council@moaa
/plugin install agent-arena-mode@moaa
/plugin install superpowers@moaa        # any of the 96, e.g. ruflo-core@moaa, ecc@moaa
```

- **MOAA plugins:** `specialist-council`, `agent-arena-mode`, `war-room`, `flightdeck`, `plot-deck` and `prismantis`. Install the first two together to get the full council → arena → forging loop; add `war-room` to run whole teams of council workers in parallel (see [War Room](plugins/war-room/README.md)).
- **Third-party plugins** keep their upstream names. The exceptions are three names that are reserved for Anthropic's own plugins and so can't appear in a third-party marketplace:

  | Upstream name | Name in `moaa` |
  |---|---|
  | `claude-api` | `llm-api-reference` |
  | `claude-mem` | `persistent-memory` |
  | `claude-mem-cowork` | `persistent-memory-cowork` |

- **Allow rules:** to let `council.py` run without permission prompts, add `Bash(python *specialist-council*council.py*)` and `PowerShell(python *specialist-council*council.py*)` to your settings. The full installer adds them for you.
- **Installer only:** the standalone skills, the MCP servers and the settings come only with the full installer above.

Every agent's model and effort are stored inside the plugins themselves; see [MODELS.md](MODELS.md).

## Plugin list

<!-- PLUGIN-LIST:START (generated by scripts/sync_catalog.py) -->

**96 plugins**: 6 MOAA plugins and 90 third-party plugins pinned to tested commits. Install any of them with `/plugin install <name>@moaa`.

### MOAA plugins

| Install | Description |
|---|---|
| `specialist-council@moaa` | Specialist Council: 60 role agents with per-role model/effort and arena-forged members; assembles teams and d… |
| `agent-arena-mode@moaa` | Eight multi-agent arena modes with a persistent best-agent library that forges Specialist Council members. |
| `flightdeck@moaa` | Live agent dashboard for Claude Code. |
| `plot-deck@moaa` | Side panel listing plot images; Enter copies and opens one. |
| `prismantis@moaa` | Colorful, themeable rendering for Claude Code replies. |
| `war-room@moaa` | War Room: a team of real, parallel Claude Code workers with council roles, review gates, a merge queue, usage… |

### Third-party plugins

<details><summary><b>ruvnet/ruflo</b>: 39 plugins (pinned <code>ea0ea3d</code>)</summary>

| Install | Description |
|---|---|
| `ruflo-adr@moaa` | ADR lifecycle management — create, index, supersede, and link Architecture Decision Records to code |
| `ruflo-agent@moaa` | Agent runtimes — local WASM-sandboxed agents (rvagent) + Anthropic Claude Managed Agents (cloud); one interfa… |
| `ruflo-agentdb@moaa` | AgentDB memory controllers with HNSW vector search, RuVector embeddings, and causal graphs |
| `ruflo-agntcy@moaa` | AGNTCY/Outshift Internet-of-Cognition runtime integration — SLIM secure transport, CASA intent-scoped tool au… |
| `ruflo-aidefence@moaa` | AI safety scanning, PII detection, prompt injection defense, and adaptive threat learning |
| `ruflo-arena@moaa` | Competitive ruliology for ruflo swarms — arenas, tournaments, and adaptive co-evolution of program strategies… |
| `ruflo-autopilot@moaa` | Autonomous /loop-driven task completion with learning, prediction, and progress tracking |
| `ruflo-bbs-federation@moaa` | AgentBBS cross-host agent federation (ADR-164). Phase 1: register/publish/watch/human-join room coordination.… |
| `ruflo-browser@moaa` | Agentic browser automation with Playwright for testing, scraping, and UI interaction |
| `ruflo-business-pods@moaa` | Business-domain pod templates for the federated business autopilot (ADR-164 Phase 2) — pod templates plus a d… |
| `ruflo-core@moaa` | Core Ruflo MCP tools, commands, and Claude Code orchestration patterns |
| `ruflo-cost-tracker@moaa` | Token usage tracking, model cost attribution per agent, budget alerts, and optimization recommendations |
| `ruflo-daa@moaa` | Dynamic Agentic Architecture with cognitive patterns, knowledge sharing, and adaptive agents |
| `ruflo-ddd@moaa` | Domain-Driven Design scaffolding — bounded contexts, aggregate roots, domain events, and anti-corruption laye… |
| `ruflo-docs@moaa` | Documentation generation, drift detection, and API docs automation |
| `ruflo-federation@moaa` | Cross-installation agent federation with zero-trust security, PII-gated data flow, and compliance-grade audit… |
| `ruflo-goals@moaa` | Long-horizon goal planning, deep research orchestration, and adaptive replanning using GOAP |
| `ruflo-graph-intelligence@moaa` | Real-time graph intelligence — personalized PageRank, streaming delta updates, witness-signed reasoning, and… |
| `ruflo-intelligence@moaa` | Self-learning neural intelligence with SONA patterns, trajectory learning, and model routing |
| `ruflo-iot-cognitum@moaa` | IoT device lifecycle, telemetry anomaly detection, fleet management, and witness chain verification for Cogni… |
| `ruflo-jujutsu@moaa` | Advanced git workflows with diff analysis, risk scoring, and reviewer recommendations |
| `ruflo-knowledge-graph@moaa` | Knowledge graph construction — entity extraction, relation mapping, and pathfinder graph traversal |
| `ruflo-loop-workers@moaa` | Cache-aware /loop workers and CronCreate background automation |
| `ruflo-market-data@moaa` | Market data ingestion — feed normalization, OHLCV vectorization, and HNSW-indexed pattern matching |
| `ruflo-metaharness@moaa` | MetaHarness integration — surfaces score/genome/mint/mcp-scan/threat-model via skills; pairs with @metaharnes… |
| `ruflo-migrations@moaa` | Schema migration management — generate, validate, dry-run, and rollback database migrations |
| `ruflo-music@moaa` | AI music generation via Cognitum Music (cogmusic MCP) — compose lyrics/prompts, generate tracks, separate ste… |
| `ruflo-neural-trader@moaa` | Neural trading strategies — self-learning LSTM/Transformer/N-BEATS models with Rust/NAPI backtesting |
| `ruflo-observability@moaa` | Structured logging, distributed tracing, and metrics — correlate agent swarm activity with application teleme… |
| `ruflo-plugin-creator@moaa` | Scaffold, validate, and publish new Claude Code plugins with proper structure |
| `ruflo-rag-memory@moaa` | RuVector memory with HNSW search, AgentDB, and semantic retrieval |
| `ruflo-ruvector@moaa` | Self-learning vector database — HNSW, FlashAttention-3, Graph RAG, hybrid search, DiskANN, and Brain AGI |
| `ruflo-ruvllm@moaa` | RuVLLM local inference with chat formatting, MicroLoRA fine-tuning, and SONA adaptation |
| `ruflo-rvf@moaa` | RVF format for portable agent memory, session persistence, and cross-platform transfer |
| `ruflo-security-audit@moaa` | Security review, dependency scanning, policy gates, and CVE monitoring |
| `ruflo-sparc@moaa` | SPARC methodology — Specification, Pseudocode, Architecture, Refinement, Completion phases with quality gates |
| `ruflo-swarm@moaa` | Agent teams, swarm coordination, Monitor streams, and worktree isolation |
| `ruflo-testgen@moaa` | Test gap detection, coverage analysis, and automated test generation |
| `ruflo-workflows@moaa` | Visual workflow automation with templates, orchestration, and lifecycle management |

Source: https://github.com/ruvnet/ruflo

</details>

<details><summary><b>sickn33/agentic-awesome-skills</b>: 35 plugins (pinned <code>f8d5d2c</code>)</summary>

| Install | Description |
|---|---|
| `agentic-awesome-skills@moaa` | Expose the plugin-safe Claude Code subset of Agentic Awesome Skills through a single marketplace entry. |
| `agentic-bundle-aas-accessibility-inclusive-ux@moaa` | Install the "AAS Accessibility & Inclusive UX" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-agent-mcp-builder@moaa` | Install the "AAS Agent & MCP Builder" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-ai-product-evaluation-ops@moaa` | Install the "AAS AI Product & Evaluation Ops" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-api-platform-builder@moaa` | Install the "AAS API Platform Builder" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-automation-builder@moaa` | Install the "AAS Automation Builder" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-data-analytics@moaa` | Install the "AAS Data Analytics" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-data-engineering-platform@moaa` | Install the "AAS Data Engineering Platform" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-devops-cloud@moaa` | Install the "AAS DevOps & Cloud" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-documents-presentations@moaa` | Install the "AAS Documents & Presentations" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-localization-international-growth@moaa` | Install the "AAS Localization & International Growth" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-marketing-seo-growth@moaa` | Install the "AAS Marketing, SEO & Growth" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-mobile-app-builder@moaa` | Install the "AAS Mobile App Builder" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-observability-ir@moaa` | Install the "AAS Observability IR" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-privacy-compliance-engineering@moaa` | Install the "AAS Privacy & Compliance Engineering" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-product-design-studio@moaa` | Install the "AAS Product Design Studio" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-python-api-builder@moaa` | Install the "AAS Python API Builder" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-qa-test-automation@moaa` | Install the "AAS QA & Test Automation" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-saas-launch-revenue@moaa` | Install the "AAS SaaS Launch & Revenue" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-secure-app-builder@moaa` | Install the "AAS Secure App Builder" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-security-engineer@moaa` | Install the "AAS Security Engineer" editorial skill bundle for Claude Code. |
| `agentic-bundle-aas-web-app-builder@moaa` | Install the "AAS Web App Builder" editorial skill bundle for Claude Code. |
| `agentic-bundle-agent-architect@moaa` | Install the "Agent Architect" editorial skill bundle for Claude Code. |
| `agentic-bundle-apple-platform-design@moaa` | Install the "Apple Platform Design" editorial skill bundle for Claude Code. |
| `agentic-bundle-architecture-design@moaa` | Install the "Architecture & Design" editorial skill bundle for Claude Code. |
| `agentic-bundle-automation-builder@moaa` | Install the "Automation Builder" editorial skill bundle for Claude Code. |
| `agentic-bundle-azure-ai-cloud@moaa` | Install the "Azure AI & Cloud" editorial skill bundle for Claude Code. |
| `agentic-bundle-business-analyst@moaa` | Install the "Business Analyst" editorial skill bundle for Claude Code. |
| `agentic-bundle-commerce-payments@moaa` | Install the "Commerce & Payments" editorial skill bundle for Claude Code. |
| `agentic-bundle-creative-director@moaa` | Install the "Creative Director" editorial skill bundle for Claude Code. |
| `agentic-bundle-data-analytics@moaa` | Install the "Data & Analytics" editorial skill bundle for Claude Code. |
| `agentic-bundle-data-engineering@moaa` | Install the "Data Engineering" editorial skill bundle for Claude Code. |
| `agentic-bundle-ddd-evented-architecture@moaa` | Install the "DDD & Evented Architecture" editorial skill bundle for Claude Code. |
| `agentic-bundle-devops-cloud@moaa` | Install the "DevOps & Cloud" editorial skill bundle for Claude Code. |
| `agentic-bundle-essentials@moaa` | Install the "Essentials" editorial skill bundle for Claude Code. |

Source: https://github.com/sickn33/agentic-awesome-skills

</details>

<details><summary><b>anthropics/skills</b>: 5 plugins (pinned <code>dbd4588</code>)</summary>

| Install | Description |
|---|---|
| `academy-guide@moaa` | Recommends relevant Claude Academy courses, tutorials, and use cases when users ask how to use Claude |
| `discernment-nudge@moaa` | Appends two or three short follow-up questions after a substantive answer to help users check key facts, prob… |
| `document-skills@moaa` | Collection of document processing suite including Excel, Word, PowerPoint, and PDF capabilities |
| `example-skills@moaa` | Collection of example skills demonstrating various capabilities including skill creation, MCP building, visua… |
| `llm-api-reference@moaa` | Claude API and SDK documentation skill for building LLM-powered applications. Upstream plugin `claude-api` fr… |

Source: https://github.com/anthropics/skills

</details>

<details><summary><b>thedotmack/claude-mem</b>: 2 plugins (pinned <code>3939fbb</code>)</summary>

| Install | Description |
|---|---|
| `persistent-memory@moaa` | Persistent memory system for Claude Code - context compression across sessions. Upstream plugin `claude-mem`… |
| `persistent-memory-cowork@moaa` | Claude-Mem for Cowork (Claude app cloud sessions) - hooks stream tool use to cmem.ai and inject observations… |

Source: https://github.com/thedotmack/claude-mem

</details>

<details><summary><b>affaan-m/ECC</b>: 1 plugin (pinned <code>e04ea0b</code>)</summary>

| Install | Description |
|---|---|
| `ecc@moaa` | Harness-native ECC operator layer - 68 agents, 286 skills, 94 legacy command shims, reusable hooks, rules, se… |

Source: https://github.com/affaan-m/ECC

</details>

<details><summary><b>dietrichgebert/ponytail</b>: 1 plugin (pinned <code>e3ba2aa</code>)</summary>

| Install | Description |
|---|---|
| `ponytail@moaa` | Forces the laziest solution that works. YAGNI, stdlib first, one line over fifty. |

Source: https://github.com/dietrichgebert/ponytail

</details>

<details><summary><b>Egonex-AI/Understand-Anything</b>: 1 plugin (pinned <code>787da45</code>)</summary>

| Install | Description |
|---|---|
| `understand-anything@moaa` |  |

Source: https://github.com/Egonex-AI/Understand-Anything

</details>

<details><summary><b>JuliusBrussee/caveman</b>: 1 plugin (pinned <code>5184b3d</code>)</summary>

| Install | Description |
|---|---|
| `caveman@moaa` | Talk like caveman. Cut 65% output tokens vs unprompted baseline (measured). Keep all technical accuracy. |

Source: https://github.com/JuliusBrussee/caveman

</details>

<details><summary><b>kyryl-shtefiienko/LPS</b>: 1 plugin (pinned <code>a4363de</code>)</summary>

| Install | Description |
|---|---|
| `lps@moaa` | Personal shared and Claude-specific skills from LPS. |

Source: https://github.com/kyryl-shtefiienko/LPS

</details>

<details><summary><b>mattpocock/skills</b>: 1 plugin (pinned <code>3cca18b</code>)</summary>

| Install | Description |
|---|---|
| `mattpocock-skills@moaa` | Matt Pocock's agent skills for real engineering (grilling, spec/ticket flows, TDD, code review, domain modell… |

Source: https://github.com/mattpocock/skills

</details>

<details><summary><b>multica-ai/andrej-karpathy-skills</b>: 1 plugin (pinned <code>2c60614</code>)</summary>

| Install | Description |
|---|---|
| `andrej-karpathy-skills@moaa` | Behavioral guidelines to reduce common LLM coding mistakes: Think Before Coding, Simplicity First, Surgical C… |

Source: https://github.com/multica-ai/andrej-karpathy-skills

</details>

<details><summary><b>obra/superpowers</b>: 1 plugin (pinned <code>5bf4e78</code>)</summary>

| Install | Description |
|---|---|
| `superpowers@moaa` | Superpowers teaches Claude brainstorming, subagent driven development with built in code review, systematic d… |

Source: https://github.com/obra/superpowers

</details>

<details><summary><b>typesafe-ai/skills</b>: 1 plugin (pinned <code>65a39f3</code>)</summary>

| Install | Description |
|---|---|
| `typesafe@moaa` | Full context on the TypeSafe API: question types, architectural patterns, and best practices |

Source: https://github.com/typesafe-ai/skills

</details>

<!-- PLUGIN-LIST:END -->

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
   - `rea` (`npx rea-agents@6.3.0`).
   - `ansys`: cloned at a pinned commit into `~/.claude/kit-tools/ansys-mcp-server`, with `vendor/ansys-mcp-server.patch` applied, inside its own venv.
7. Runs `council.py check` and writes the manifest.

Rerunning is safe: anything already present is skipped.

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
- **Command line:** you can run the library by hand without Claude Code: `python <plugin dir>/scripts/library.py list|show|promote|council`. It finds the installed library on its own, so `--database` is optional.
- **Not shipped:** no forged members come with this kit. Every machine forges its own.

## Tests

```bash
python -m unittest discover -s tests                         # installer
(cd plugins/specialist-council && python -m unittest discover -s tests)
(cd plugins/agent-arena-mode && python -m unittest discover -s tests)
```

`python scripts/scan.py` checks the tree for secrets and machine-specific paths. Run it before every push. `python scripts/scan.py --public` also fails on any vendored item without a clear licence.

## Updating the kit from a working machine

This repo is the canonical source: on the maintainer machine it lives at `~/code/claude-kit`, and the live install's `moaa` marketplace points at it. Edit here, bump the plugin version in `plugins/<name>/.claude-plugin/plugin.json`, then rerun the installer. It runs `claude plugin marketplace update moaa` before installing. Plugin versions that were tested together are recorded as `tested_version` in `config/kit.json`. After updating any third-party plugin, run `python scripts/sync_catalog.py` to re-pin the catalog to the installed commits, and run `python scripts/models_doc.py` after changing any model or effort preset. The tests fail if `MODELS.md` drifts.

See [THIRD_PARTY.md](THIRD_PARTY.md) for the source and licence of everything vendored or referenced.

## Author and licence

MOAA is created and maintained by **Ahmad Hammoud** ([@ahmadhammoud56](https://github.com/ahmadhammoud56)). To cite it, use [CITATION.cff](CITATION.cff); GitHub shows a "Cite this repository" button.

MOAA's own code is released under the [MIT licence](LICENSE). Vendored third-party plugins and skills keep their own licences: MIT and Apache-2.0, listed in [NOTICE](NOTICE). Plugins installed from other marketplaces are fetched from their authors and are not redistributed here.
