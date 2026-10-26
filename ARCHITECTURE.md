# Architecture

How MOAA's parts fit together. For rules and commands, see [AGENTS.md](AGENTS.md); for each plugin's details, its
own `plugins/<name>/README.md`.

## System overview

```
install.sh / install.ps1 ──> scripts/install.py ──> ~/.claude/settings.json (merged, backed up)
                                   │                 marketplaces: moaa (this repo) + pinned third-party
                                   │                 deny rules for secret files
                                   ▼
               .claude-plugin/marketplace.json ──> plugins/*  (MOAA's own, versioned per plugin)
                                                   config/kit.json (catalog: third-party pins, modes, skills)
```

Claude Code loads each enabled plugin's agents, skills and hooks. MOAA plugins are Python standard-library scripts
called from `hooks/hooks.json` or from skills; nothing runs as a server except the War Room app and the optional
OmniRoute gateway, both started by the user.

## Plugins and how they connect

| Layer | Plugin | Role | Talks to |
|---|---|---|---|
| Entry | `moaa-core` | Meta plugin: pulls in council, arena, catalog; inline-Python guard hook; `project-docs` skill | dependencies |
| Doing the work | `specialist-council` | 60 role agents with model/effort presets (`profile.json`), team assembly, cost ledger | arena (forged members) |
| | `agent-arena-mode` | Eight multi-agent modes, judge, best-agent library (SQLite) | forges council members |
| | `war-room` | Parallel real Claude Code workers, board, review gates, merge queue, local app | council roles, allies as engines |
| | `allies` | Hands bounded tasks to other agents (Codex, Gemini, OpenCode, Kimi, DeepSeek, OmniRoute) | `members.json`, own accounts |
| | `team` | Several people on separate Claude accounts share a board on a `team-board` branch | git remote |
| Context | `strata` | Memory layers, handoff, virtual context, project RAG, LLM Wiki, findings graph, canary, vault | every session via hooks |
| | `prompt-refiner` | Turns each prompt into a brief, asks about open points | every prompt |
| | `moaa-catalog` | Names the right skill per prompt, loads disabled skills on demand, update notices | `config/kit.json` |
| Display (vendored) | `prismantis`, `flightdeck`, `plot-deck` | Reply rendering, agent dashboard, plot panel | Claude Code UI |

## Hook flow per session

| Event | Plugins | What happens |
|---|---|---|
| SessionStart | strata, moaa-catalog, team | Recall memory and pending handoff, refresh RAG index, update notice, team briefing, canary rule |
| UserPromptSubmit | prompt-refiner, strata, moaa-catalog, team | Brief instruction, context check, RAG passages, skill hint, new team messages |
| PreToolUse | moaa-core | Inline-Python note (never blocks) |
| PostToolUse | strata | Context check (handoff near a full window) |
| Stop | strata | Canary check on the last reply |
| SubagentStop | specialist-council | Token ledger |
| PreCompact | strata | Store the whole conversation before compaction |
| SessionEnd | strata | Store the session, consolidate notes, daily vault line |

Every hook wrapper tries `py`, `python3`, `python` in turn and exits 0 on failure, so a missing interpreter or a
crash never blocks Claude Code.

## Data locations (outside the repository)

| Data | Path |
|---|---|
| Strata memory, RAG index, state | `~/.claude/strata/` |
| Second-brain vault (optional) | `STRATA_VAULT`, default `~/code/brain` (own git repo, never pushed by MOAA) |
| Context handoffs | `<project>/.claude/handoff/<stamp>/` |
| Briefs | `<project>/.briefs/` (git-ignored) |
| Allies keys and member data | `~/.claude/allies/` (`keys.env` is denied to Claude's file tools) |
| Arena library | `~/.claude/plugins/data/agent-arena-mode-moaa/library.sqlite3` |
| Forged council members | `~/.claude/specialist-council/forged/`, `~/.claude/agents/council-forged-*.md` |

Uninstalling a plugin deletes its `plugins/data` folder: back up the arena library first.

## Install modes

`scripts/install.py` installs at user scope. `--mode all-on` enables every catalog plugin and trims the skill listing;
`--mode lean` keeps large packs disabled and lets moaa-catalog load single skills on demand. `--status` compares an
install with the repository, `--doctor` runs every check, `--dry-run` previews, `--uninstall` reverses recorded
changes.

## Tests and CI

Each plugin has a `tests/` folder (unittest). `.github/workflows/ci.yml` runs all suites on Linux, macOS and Windows,
plus the public scan, MODELS.md check, plugin validation and a clean install. Live end-to-end evidence (headless
`claude -p` runs) is kept in `plugins/<name>/tests/e2e/`.
