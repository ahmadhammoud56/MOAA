---
name: moaa-help
description: Explain what MOAA installed and how to use it (council, arena, War Room, allies, strata, skill catalog, installer commands). Use when the user asks what MOAA is, what it can do, how to start, or which MOAA tool fits a task.
---

# MOAA help

Answer from this page and from what is actually installed. To see that, run
`claude plugin list` (enabled vs disabled) and, if the MOAA repo is available, `python scripts/install.py --report`
in it. Keep the answer short and point to the one tool that fits the user's task.

| Need | Use |
|---|---|
| A verified answer from several experts | `/specialist-council:specialist-council <task>`: picks roles (60, each with its own model and effort), runs them in parallel, cross-checks. |
| Compare approaches or find the best agent | `/agent-arena-mode:judge`, `tournament`, `league`, `swarm`, `redteam`, ... Winners are kept in a library; repeated validated winners are forged into the council. |
| A big job split across real parallel sessions | `/war-room:war-room`: council-role workers, task board, review gates, merge queue, local app. |
| Another model family, or saving Claude usage | `/allies:allies`: Codex, Gemini, OpenCode (free zero-retention models, no sign-in) and others on bounded tasks; read-only by default, writes on their own branch. |
| Docs that tell agents how a project works | `/moaa-core:project-docs`: checks for AGENTS.md (shared by Claude, Codex, Gemini, OpenCode), ARCHITECTURE, README, TESTING, SECURITY, and PRD / DESIGN_SYSTEM for apps, and drafts what is missing. |
| Remember things across sessions | `strata`: recalls at session start and saves at session end automatically (Haiku, with a no-model `local` fallback, so no provider limit stops it); `/strata:strata` to search, `--scene` to narrow. |
| A skill that is not listed | `/moaa-catalog:moaa-catalog`: searches installed but disabled packs and loads one skill into this session. |
| What to set up for this project | `claude-code-setup` (Anthropic's automation recommender): ask "recommend automations for this project". It reads the code and suggests 1-2 hooks, subagents, skills, plugins and MCP servers; prefer the MOAA tools above where they fit. |
| Clearer requests, automatically | `prompt-refiner` (always on): every prompt becomes a brief; ambiguous points come back as questions with options. `refiner.py off` or a `raw:` prefix skips it. |
| A chat that is running out of context | strata's context handoff (always on): at ~85% Claude writes `.claude/handoff/` and you open a new chat that resumes; its virtual context brings back evicted turns when a prompt needs them. `strata.py handoff off`, `handoff threshold N`, `handoff mode compact` (one long chat), `handoff recall off`. |
| Answers from this project's own files | strata's project RAG (always on): matching passages with `path:lines` are added to prompts that clearly need them; `rag.py search "QUERY"` to search, `rag.py off` to stop. |
| Several people on one project, each on their own account | `/team:team`: a board on its own git branch with task claims, path locks, handoffs, messages and a decision log. `team.py init`, then `team.py join NAME`. |
| A long or multi-session task | `/specialist-council:long-task`: brief with acceptance checks, progress file, evidence review, resume prompt. |
| Finding a note by meaning | `strata.py search` blends keyword and meaning matches when local Ollama runs (`embed.py status`; `ollama pull nomic-embed-text`); `viewer.py --open` browses memory read-only at 127.0.0.1:37778. `embed.py off`. |
| A newer release of a vendored plugin | moaa-catalog says so once a day; `py scripts/sync_vendored.py NAME` copies it in, re-applies the patch and tests it (`--check` lists them). |
| A second brain across all projects | strata's Obsidian vault (default `~/code/brain`, created by the first chat that ends): `Home.md`, a page per project and a daily line per chat, rewritten automatically in every project; `strata.py capture "TEXT"` from any chat; `/strata:wiki distill` into linked pages, `/strata:wiki ask` answers from them with citations; `raw/` sources are protected. `strata.py vault refresh`, `vault off`. |
| Knowing when a chat has drifted | strata's canary (always on): an invisible line ends each reply; two long replies without it above 30% context start the handoff early. `strata.py canary off`. |
| A knowledge base that compounds | `/strata:wiki`: Karpathy-style LLM Wiki; Claude compiles sources into linked pages (ingest, query, lint of the link graph). |
| Findings with their sources | `/strata:graph`: typed claim-source graph shared by parallel agents, with a grounding check (score, specific failures). |
| Improve something against a number | `/agent-arena-mode:karpathy-loop`: edit, measure with a fixed script, keep or discard, repeat; `--target` stops after two passing runs in a row, two stalls stop it. |
| Answers I can trust from my notes | `/strata:wiki ask` checks every quote against the cited page (`graph.py verify`; `rag.py verify` for project files) and says "Not in the wiki." when nothing holds. |
| What will this cost? Which model or ally? | `python <moaa-core>/cost.py blended|breakeven|bundle|local|cloud|success|rewarm`; `allies.py route private|routine|bulk|complex` (private stays local, one escalation then stop). |
| Meters and guards in the app | Mods: the **Meters** panel (`/strata-meter`: context vs handoff, cache, goal, canary, memory, vault), Cache Keeper (`/cache-keeper on` keeps a chat's cache warm), Goal Meter (bar on `/goal`), Collision Guard (`/collision-guard`; stops two chats editing one file). |
| Are subagents or other harnesses worth it here? | `/agent-arena-mode:fold-trial` (one loop vs a council) and `/agent-arena-mode:harness-league` (Claude Code vs Codex, Gemini, OpenCode) on your own frozen tasks, judged blind, cost shown first. |

Installer commands (run in the MOAA repo; `--dry-run` previews any of them):

- `--profile web|data|devops|research|science`: add packs for a kind of work.
- `--report`: skills listed per request, rough token cost, most used plugins, catalog hits.
- `--mode all-on|lean`: every plugin on with a trimmed skill listing, or the big packs off.
- `--prune [--yes]`, `--lean`, `--restore`: keep the skill listing small, and undo it.
- `--status` (compare with the repo), `--uninstall` (reverse everything recorded).

Full walkthrough: `docs/GETTING_STARTED.md` in the MOAA repo (github.com/ahmadhammoud56/MOAA).
