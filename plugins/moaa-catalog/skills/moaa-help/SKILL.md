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

Installer commands (run in the MOAA repo; `--dry-run` previews any of them):

- `--profile web|data|devops|research|science`: add packs for a kind of work.
- `--report`: skills listed per request, rough token cost, most used plugins, catalog hits.
- `--mode all-on|lean`: every plugin on with a trimmed skill listing, or the big packs off.
- `--prune [--yes]`, `--lean`, `--restore`: keep the skill listing small, and undo it.
- `--status` (compare with the repo), `--uninstall` (reverse everything recorded).

Full walkthrough: `docs/GETTING_STARTED.md` in the MOAA repo (github.com/ahmadhammoud56/MOAA).
