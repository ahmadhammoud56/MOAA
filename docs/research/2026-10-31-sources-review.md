# Sources review and integration plan (2026-10-31)

Review of the links, videos and screenshot collected on 2026-10-31, judged against MOAA 0.19.3. The detailed notes for
each source are in [2026-10-31/](2026-10-31/): `REPOS.md` (repos and gist), `WEB.md` (X posts, article, YouTube) and
`VIDEOS.md` (WhatsApp export: 19 videos and 1 image, each transcribed with faster-whisper and checked against contact
sheets). Nothing from these sources was installed or run.

## Verdicts at a glance

| Source | What it is | Verdict |
|---|---|---|
| tigerless-labs/autoharness | Plugin that writes skills from your sessions with a detached Haiku "reflector" | Idea only: skill-usage counter, reviewed skill proposals |
| Speedrunlab/reverse-engineer-anything-self-learning-loop | Authorised rebuild loop: parity checklist, clean-room build, two-pass done rule | Idea only: long-task "reconstruction" preset, karpathy-loop stop rule |
| mempalace/mempalace | Local verbatim memory with embeddings, 47 MCP tools | Idea only: benchmark strata recall, scene filter, claim validity dates |
| Gist kju4q (weekly repo lists, ~30 repos) | Mixed list; 5 already in the catalog | Idea only: spec-kit "constitution", catalog discovery source |
| Anthropic article: when to fold subagents into the main loop | One loop with skills often beats lead + subagents; keep subagents for context bloat, real parallelism, tool conflicts | Integrate: council spawn rule, arena fold trial |
| @imryven Claude + Obsidian second brain (and the same thing reposted by @danikkk_wqs) | raw/ wiki/ output/ vault, ingest/query/lint, nightly and weekly runs | Integrate gaps into strata vault |
| @imryven "4 repos" | kepano/obsidian-skills, claude-obsidian, obsidian-second-brain, second-brain-starter | obsidian-skills already arrives through agentic-awesome-skills; the rest skip |
| @HowToPrompt__ "RAG is cooked" | IBM STAIR paper: model returns the section heading that answers a query | Idea only: heading-path retrieval in strata RAG |
| YouTube T6_Ges4j1qY (Cal AI story) | General startup story | Review only |
| YouTube 3R7yba577uA (Mac Mini vs $200 plan) | Local Qwen3.8-27B at ~10 tok/s, 9 min to first token on a 50K prompt | Review only; one allies note |
| WhatsApp videos | 19 reels; see section below | 4 ideas, rest skip |
| Threads screenshot ("Claude stopped REA") | Rumour plus advice to use uncensored models | Review only; see section below |

## Reviews of general (non-MOAA) items

- **Cal AI video:** a founder story about an app business. Nothing for MOAA.
- **Mac Mini vs $200 plan:** the useful number is the time to first token. A 50K-token agent prompt took about 9
  minutes on a 32 GB machine, so local models cannot carry Claude Code-sized prompts. They fit small, slim-prompt
  jobs only. A month of heavy use was worth about $62 at hosted prices, so the hardware does not pay back quickly.
- **STAIR paper:** a fine-tuned 7B model that names the table-of-contents section for a query. It reports Recall@1
  82.6% against 59.5% for BM25. The "65x" figure in the post appears in no source. There is no public code. The idea
  of returning the heading path costs little to copy.
- **Videos with general content:** N-gram embeddings explainer, inference-engine survey (llama.cpp, vLLM, SGLang and
  others), GLM 5.2 on a laptop (link behind Telegram), kimi-k3 in C at about 30 s per token, 3dcodeverse dataset,
  Cal AI-style lead finding with Firecrawl and Alexandria (the personal-data scraping is a privacy risk). None of these
  change MOAA. The survey names an inference engine "Strata"; it is unrelated to the MOAA plugin.
- **Not to touch:** dsh-purge (a jailbreak harness), DavidAU "Heretic" uncensored GGUF, the "replica" pack that clones
  apps for resale, and the "non-ethical GitHub projects" reel (licence and subscription bypass). These carry licence,
  ToS or malware risk and have no place in MOAA.

## The REA screenshot

The thread claims Claude "stopped" REA and suggests switching to an uncensored local model or a Chinese LLM.

- Upstream REA (morluto/rea) is active: commits pushed today, `rea-agents` 6.8.0 released 2026-10-25. Its issue tracker
  has no reports of Claude refusing REA work.
- The reply in the thread ("policy on cloning the license software") matches the likely cause. Claude declines to
  rebuild proprietary, licensed software or to bypass licensing. REA itself and lawful uses are still available:
  analysing your own software, interoperability, security research and debugging.
- Switching to an uncensored model to get around that is not a fix. It moves the legal risk onto the user.
- What MOAA can take from this is the Speedrunlab repo's **authorisation gate**: a short "what are you allowed to
  rebuild, and why" step before a reconstruction run (plan item 5). MOAA pins `rea-agents@6.4.0`, two minor versions
  behind (plan item 7).

## Memory status (claude-mem and the other memory stores)

| Store | State |
|---|---|
| claude-mem | Plugin disabled (`claude-mem@thedotmack: false`), no worker running. The quota lock dates from 2026-10-18 and covers a 7-day window, so it has lapsed. The database (31 MB) was last written 2026-10-18. Nothing to fix unless you want it back; strata replaced it. |
| strata | Active: 133 sessions, 11,683 L0 messages, 251 L1 atoms, 45 scenes, 25 profile facts, **66 pending**. Updated today. |
| Claude Code auto-memory | One entry for this project (screenshots never steal focus). |
| ruflo-rag-memory / `.claude-flow` | Enabled; keeps its own store in `~/.claude-flow` and `.claude-flow/memory` in this repo. It is a second memory layer beside strata. |
| mempalace | Not installed. Do not add it: its hooks would fire on the same events as strata's and inject context twice. |

The 66 pending strata items and the second ruflo memory layer are worth checking, but they are separate from this
review.

## Integration plan

Every item below follows the repo rules: Python standard library only, on by default with an off switch (a command
plus an environment variable), hooks that exit 0 silently on failure, a version bump, a changelog entry and README
updates per plugin.

### 1. specialist-council: spawn rule and compact returns (S)
- Source: the Anthropic article and the image in the WhatsApp export.
- Change: the `specialist-council` skill names which keep-condition applies before it spawns workers: context bloat,
  real parallelism, or tool and instruction conflicts. If none applies, it works in the main loop with the role
  loaded as a skill-style brief.
- Workers return a fixed short structure (result, evidence, open questions) instead of free prose.
- Switch: `council.py spawn-rule off`, `MOAA_COUNCIL_SPAWN_RULE=off`.
- Test: unit test of the rule text in the resolved profile; one live `claude -p` run that shows the rule being named.

### 2. agent-arena-mode: fold trial and harness league (M)
- Source: the Anthropic article, and the Hugging Face multi-harness guide video (the same model scored 62% in one
  harness and 33% in another).
- New skill `fold-trial`: runs the same frozen task set (about 10 golden tasks per council recipe) as one loop and as
  a council, k runs each. It logs score, tokens, wall time and flipped tasks to `library.sqlite3`.
- Extension `harness-league`: the same tasks through Claude Code and the allies harnesses (Codex, Gemini, OpenCode),
  judged by the existing arena judge. This gives measured data for routing tasks to allies.
- Risk: cost. Cap runs per trial and print the expected cost first, as `e2e.py --list` does.

### 3. strata vault: second-brain gaps (S each)
- Source: @imryven article and the claude-obsidian repo.
- `raw/` write guard: a PreToolUse hook that blocks Write and Edit inside the vault's `raw/` folder. Blocking is the
  point of this hook, so it may block. Off: `strata.py vault guard off`.
- Wiki-only answers: `/strata:wiki ask` answers from `wiki/` pages only, cites a page for each claim, and scores the
  answer with `graph.py check`.
- Scheduled care: a documented nightly `wiki distill` and weekly read-only `graph.py lint`, run through the existing
  scheduled-task tooling, off by default only if scheduling needs user setup.
- `vault init --interview`: writes the vault's CLAUDE.md from a short question round.
- Git snapshot of the vault before any bulk ingest (local commit only; the vault is never pushed).

### 4. strata retrieval (S to M)
- Source: STAIR post and mempalace.
- `rag.py`: store each chunk's heading path and return it with every hit; `rag.py outline` shows matching headings
  first (S-M).
- `strata.py search --scene` filter (S).
- Validity dates (`valid_from`, `valid_to`) on graph claims, so superseded facts drop out of recall (M).
- Benchmark: a LongMemEval-S subset run against strata search, with raw output saved under
  `plugins/strata/tests/e2e/`. Only if it shows a clear gap, consider an opt-in rerank through a local
  OpenAI-compatible embeddings endpoint over `urllib` (L, later).

### 5. long-task and karpathy-loop: reconstruction discipline (S)
- Source: Speedrunlab repo and the REA thread.
- `/specialist-council:long-task` gets a `reconstruction` preset: an authorisation step (what may be rebuilt, and on
  what grounds), a behaviour checklist in `checks.md`, a pointer to REA's `verify_reconstruction`, and the stop rules
  below.
- `/agent-arena-mode:karpathy-loop` gets two stop rules: done when every must-have passes in two runs in a row, stop
  when progress stalls twice. Switch: `--stop-rule off`.

### 6. moaa-catalog: skill-usage counter (S), then skill proposals (M)
- Source: autoharness.
- Counter: a PostToolUse hook on the Skill tool (and on reads of `SKILL.md`) increments a local count;
  `catalog.py usage` lists enabled skills that were never used. This gives real numbers for the lean/all-on modes.
  Off: `catalog.py usage off`, `MOAA_SKILL_USAGE=off`.
- Proposals (later): strata's SessionEnd step drafts possible new skills into `~/.claude/strata/skill-proposals/` with
  the reason and evidence. Nothing lands in a skills folder without review. MOAA does not copy autoharness's
  detached child running with `--dangerously-skip-permissions`.

### 7. Catalog and small ports (S)
- Bump the `rea` MCP pin from `rea-agents@6.4.0` to 6.8.0 and re-sync the vendored `reverse-engineer-anything` skill
  (`scripts/sync_skills.py --check` first).
- prompt-refiner: optional "constitution" section in briefs (project-wide rules the brief must respect), from
  github/spec-kit.
- Check before adding: Impeccable (only if it ships a Claude Code plugin) and K-Dense Scientific Agent Skills (likely
  overlaps `claude-scientific-skills` in agentic-awesome-skills and the ecc scientific skills; it would also raise
  the skill-listing cost). kepano/obsidian-skills already arrives through agentic-awesome-skills (`obsidian-bases`,
  `obsidian-cli`, `obsidian-markdown`, `json-canvas`), so no new entry.

### 8. Ideas parked for existing work
- War Room redesign (already approved, not started): add a compact session strip, with state (thinking or waiting),
  context %, cost and an interrupt button, from the touchscreen video.
- allies: one line per hand-off in the vault's daily note (S). If a local engine is ever added, send it a slim brief
  and log prompt size and time to first token.
- self-improve `collect-sessions`: the "mine ~/.claude/projects for repeated work" prompt from the harness-engineering
  video fits the existing collector; compare before changing anything.

### Suggested release order

| Release | Items | Size |
|---|---|---|
| 0.20.0 | 1 council spawn rule, 5 reconstruction preset and stop rules, 6 usage counter, 7 REA bump and constitution | small, one session |
| 0.21.0 | 3 strata vault gaps, 4 heading path and scene filter | small to medium |
| 0.22.0 | 2 fold trial and harness league, 4 recall benchmark and validity dates | medium, needs a cost cap |
| later | 6 skill proposals, rerank only if the benchmark shows a gap | medium to large |

Each release follows the release routine: version bumps, `install.py`, `--doctor`, the live e2e suites for changed
hooks, then push, CI on all three platforms, tag and release page.

## Skipped, with reasons

- **autoharness, mempalace, claude-mem as a whole:** a second unattended learner or memory beside strata; duplicate
  hooks; non-stdlib dependencies; detached child with permissions skipped (autoharness).
- **claude-obsidian:** duplicates strata's wiki; hooks call bare `python3`, which breaks on this Windows setup.
- **obsidian-second-brain:** pip dependencies, API keys in `.env`, an install script.
- **second-brain-starter:** no licence.
- **From the gist:** Orbital (GPL-3.0), firecrawl (AGPL), Agent-Reach (runs on your browser cookies), jev (needs an API
  key), orca, qmd, archify and i-have-adhd (already covered by War Room, strata, understand-anything or lps),
  TradingAgents, Game Studios, hyperframes, voicebox and opencut (out of scope).
- **From the videos:** DeepSeek Harness (claims unverified; revisit as an allies member if it proves real),
  DeepSeek-V4.1-Flash (only through OmniRoute, and DeepSeek is blocked on the campus network), Task Observer (only new
  item in its reel; idea only), plus everything under "Not to touch" above.
