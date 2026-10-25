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
| Another model family, or saving Claude usage | `/allies:allies`: Codex, Gemini (and others) on bounded tasks; read-only by default, writes on their own branch. |
| Remember things across sessions | `strata`: recalls at session start and saves at session end automatically; `/strata:strata` to search. |
| A skill that is not listed | `/moaa-catalog:moaa-catalog`: searches installed but disabled packs and loads one skill into this session. |
| What to set up for this project | `claude-code-setup` (Anthropic's automation recommender): ask "recommend automations for this project". It reads the code and suggests 1-2 hooks, subagents, skills, plugins and MCP servers; prefer the MOAA tools above where they fit. |
| Clearer requests, automatically | `prompt-refiner` (always on): every prompt becomes a brief; ambiguous points come back as questions with options. `refiner.py off` or a `raw:` prefix skips it. |
| A chat that is running out of context | strata's context handoff (always on): at ~85% Claude writes `.claude/handoff/` and you open a new chat that resumes. `strata.py handoff off` or `strata.py handoff threshold N`. |
| A long or multi-session task | `/specialist-council:long-task`: brief with acceptance checks, progress file, evidence review, resume prompt. |
| A knowledge base that compounds | `/strata:wiki`: Karpathy-style LLM Wiki; Claude compiles sources into linked pages (ingest, query, lint of the link graph). |
| Findings with their sources | `/strata:graph`: typed claim-source graph shared by parallel agents, with a grounding check (score, specific failures). |
| Improve something against a number | `/agent-arena-mode:karpathy-loop`: edit, measure with a fixed script, keep or discard, repeat. |

Installer commands (run in the MOAA repo; `--dry-run` previews any of them):

- `--profile web|data|devops|research|science`: add packs for a kind of work.
- `--report`: skills listed per request, rough token cost, most used plugins, catalog hits.
- `--mode all-on|lean`: every plugin on with a trimmed skill listing, or the big packs off.
- `--prune [--yes]`, `--lean`, `--restore`: keep the skill listing small, and undo it.
- `--status` (compare with the repo), `--uninstall` (reverse everything recorded).

Full walkthrough: `docs/GETTING_STARTED.md` in the MOAA repo (github.com/ahmadhammoud56/MOAA).
