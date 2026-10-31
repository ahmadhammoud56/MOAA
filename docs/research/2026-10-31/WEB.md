# Web sources review (2026-10-31)

All fetched text was treated as data. Nothing was installed or run. X posts were read through api.fxtwitter.com;
repo facts come from `gh api` on 2026-10-31.

---

## 1. X: @HowToPrompt__ "RAG is officially cooked" (IBM STAIR)

https://x.com/HowToPrompt__/status/2114979460495872355 (2026-10-27, ~6.2K likes, ~429K views)

1. **What it is.** A hype thread claiming IBM built a retriever that "hallucinates 65x less than fine-tuned RAG". The
   attached image is the first page of **STAIR (STructure Aware Information Retriever)**, arXiv:2609.03874 (IBM,
   Vineet Kumar et al., Sept 2026). STAIR is a *generative* retriever: a fine-tuned Mistral-7B-Instruct v0.2 that,
   given a query, generates the leaf section header of the corpus' table of contents (ToC) that answers it, instead
   of doing vector search over fixed-length chunks. Reported: Recall@1 82.6% on their SearchTome benchmark (18 books,
   6 domains) vs 76.9% fine-tuned DSI, 68.7% DPR, 59.5% BM25; "hallucination" below 0.05% means the generated header
   almost never names a section that does not exist. The "65x" figure is not stated in the abstract and could not be
   found in any source; the tweet's claims ("zero hallucinations means zero liability") overstate a retrieval-ID
   result as an answer-quality result.
2. **Licence/maturity.** Paper only; code/data said to be on GitHub and Hugging Face, no repo found by search. Needs a
   fine-tuned 7B model per corpus (trained on the corpus' ToC), so not a drop-in.
3. **Overlap.** strata project RAG (`rag.py`, stdlib keyword/FTS search with `path:lines`); strata wiki (`index.md` is
   already a ToC-like map); strata graph.
4. **Verdict: idea only.** The transferable idea is cheap and stdlib-friendly: **structure-aware retrieval**. Port
   into strata `rag.py`: index Markdown/code by heading path (`file > H1 > H2`), return the section path with each hit,
   and add a "ToC first" mode that hands Claude the heading outline (or the wiki `index.md`) and lets it pick sections
   before passages are loaded. Effort **S-M**. Optionally a council/arena eval comparing chunk vs heading retrieval
   on the repo's own docs (S).
5. **Risks.** Misleading marketing numbers; the actual method needs a GPU fine-tune per corpus (not stdlib, not in
   scope). The idea port has no risk.

## 2. X article: @imryven "How to Build a Second Brain With Claude and Obsidian..."

https://x.com/imryven/status/2115046979659055476 (article https://x.com/i/article/2115042274614599680, ~196K views)

1. **What it is.** A 10-step tutorial for a Karpathy LLM-Wiki second brain: an Obsidian vault with `raw/` (read-only
   sources), `wiki/` (Claude-written linked pages + `index.md`), `output/`, and an interview-generated CLAUDE.md under
   200 lines; ingest/query/lint prompts; per-project subfolder CLAUDE.md; repeated workflows become skills; Google
   Calendar via `workspace-mcp`; a nightly Desktop **scheduled task** that ingests new `raw/` files and writes
   `output/daily-log.md`; a weekly read-only review (contradictions, orphans, unsourced claims). Key rules: ask
   "using only wiki/" so Claude does not fill gaps, and "permissions, not promises" (CLAUDE.md is context; block
   deletes with permissions or a PreToolUse hook). Author notes they did not run it end to end.
2. **Licence/maturity.** Article, no code.
3. **Overlap: high, with strata.** strata already has the vault (`~/code/brain`, local git), `capture`, daily lines,
   `/strata:wiki` (ingest, index, log, lint, distill), `graph.py lint/check` (grounding score), RAG over the vault,
   Obsidian-compatible `[[Page]]` resolution. Missing pieces vs the article: (a) a `raw/` read-only guard,
   (b) a scheduled nightly ingest, (c) a "wiki-only" answering mode, (d) the interview-to-profile bootstrap.
4. **Verdict: port ideas into strata.**
   - **raw/ guard hook** (S): PreToolUse on Edit/Write that refuses writes under `<vault>/raw/` (or `inbox/` once
     filed); block is the point, so allowed by the hook rule. Off switch `strata.py vault guard off`.
   - **wiki-only answers** (S): a `/strata:wiki ask` mode whose instructions require citing a page per claim and
     saying "not in the wiki" for gaps; reuse `graph.py check` to score grounding of the saved answer.
   - **nightly distill** (S-M): document/offer a Desktop scheduled task or `/schedule` recipe that runs
     `/strata:wiki distill` plus a read-only weekly lint report (`graph.py lint` output to `output/`-style log).
   - **profile interview** (S): a `vault init --interview` prompt that writes the vault CLAUDE.md (<200 lines).
5. **Risks.** Privacy of vault content sent to the model (already true for strata); scheduled runs need
   pre-approved permissions; the article's calendar step needs Google OAuth (skip).

## 3. X: @imryven "4 GitHub repos..."

https://x.com/imryven/status/2115158061752979536 (~25K views). Lists four repos; checked each:

| Repo | Stars | Licence | Last push | Lang/deps | What |
|---|---|---|---|---|---|
| [kepano/obsidian-skills](https://github.com/kepano/obsidian-skills) | 50.5K | MIT | 2026-09-15 | Markdown skills only | By Obsidian's CEO. Skills: `obsidian-markdown`, `obsidian-bases`, `json-canvas`, `obsidian-cli`, `defuddle`, `knap`. Teaches agents Obsidian formats and CLI. |
| [AgriciDaniel/claude-obsidian](https://github.com/AgriciDaniel/claude-obsidian) | 16.0K | MIT | 2026-10-25 | Python, Claude Code plugin v3.0.1 | Karpathy LLM-Wiki as a plugin: `wiki-ingest`, `wiki-query`, `wiki-lint`, `wiki-fold`, `wiki-retrieve`, `autoresearch`, `canvas`, `save`, `think`; SessionStart + Stop hooks; "recoverable operation transactions", provenance ledgers. |
| [eugeniughelbur/obsidian-second-brain](https://github.com/eugeniughelbur/obsidian-second-brain) | 5.1K | MIT | 2026-10-28 | Python; pip deps (openai, requests, python-dotenv, youtube-transcript-api, google-api-python-client, google-genai, feedparser, pyyaml), `install.sh` | 48 commands, works in Claude Code/Codex/Gemini/OpenCode; "Crew" shared logbook across agents; scheduled agents; research via Grok/Perplexity/Gemini. |
| [coleam00/second-brain-starter](https://github.com/coleam00/second-brain-starter) | 858 | none declared | 2026-06-09 | skill | Interviews you, then writes a PRD/build plan for your own second brain. |

1. **What it is.** A promo list pointing back to the article; adds the two rules "keep your sources read-only" and
   "using only wiki/".
2. See table.
3. **Overlap.** All four overlap strata (vault, wiki, graph). `obsidian-second-brain`'s "Crew" logbook overlaps the
   `team` plugin and allies hand-offs. `second-brain-starter` overlaps prompt-refiner/long-task brief writing.
4. **Verdicts.**
   - **kepano/obsidian-skills: integrate as a catalog entry** (S) in `config/kit.json` (it is a skills marketplace,
     MIT, no code to run except `obsidian-cli`/`defuddle` which shell out to user-installed tools). Complements strata:
     strata writes the pages, these skills make Claude write valid Obsidian Markdown, Bases and Canvas. Watch
     listing cost (all-on mode): 6 short skills.
   - **claude-obsidian: idea only** (do not add to catalog): duplicates strata's wiki with its own hooks; running both
     would double SessionStart/Stop work. Ideas worth porting into strata wiki: `wiki-fold` (merging weak/duplicate
     pages, M), provenance ledger per page (strata graph already has claim-source; S to surface it), "operation
     transactions" (snapshot before a bulk ingest so one undo restores the wiki: vault is already git, so a
     pre-ingest commit/stash is S).
   - **obsidian-second-brain: skip** (non-stdlib deps, third-party API keys, `install.sh`, `.env`); idea only for the
     cross-agent "Crew" logbook: allies could append a one-line entry per handed-off task to the vault daily note (S).
   - **second-brain-starter: skip** (no licence; prompt-refiner + `vault init --interview` cover it).
5. **Risks.** claude-obsidian hooks call `python3`, which on Windows is often the Store alias (exit 49) or missing:
   Windows support doubtful. obsidian-second-brain: API keys in `.env`, network research tools, pip installs; conflicts
   with MOAA's stdlib/secrets rules. No licence on second-brain-starter blocks vendoring.

## 4. X: @danikkk_wqs "a handful of people taught Claude to remember everything"

https://x.com/danikkk_wqs/status/2115177570824081911 (~22K views)

1. **What it is.** A short promo quoting the @imryven article: three folders (raw, wiki, output), Claude Desktop Code
   tab, interview-written CLAUDE.md, ingest one article, one scheduled task, and "using only wiki/".
2. N/A.
3. **Overlap.** Same as source 2 (strata vault + wiki).
4. **Verdict: skip** (duplicate of source 2; no new content).
5. None.

---

## 5. Article: "Building agents: When to fold subagents into your main agent loop"

https://claude.com/resources/articles/building-agents-when-to-fold-subagents-into-your-main-agent-loop
(Diane Sarkis, Claude Platform, 2026-10-22)

1. **What it is.** Anthropic guidance arguing many agents work better as **one loop** with progressively disclosed
   skills and tools than as an orchestrator with specialist subagents. Keep subagents only when (a) one loop measurably
   degrades from context bloat, (b) tasks must run in parallel in fresh, discardable contexts, or (c) tool selection
   or conflicting instructions break the single prompt. Named failure modes: context loss at handoffs ("telephone
   game"), subagent sprawl, the "Frankenprompt", localized evals, latency (one customer ~2x faster single-loop). Pattern:
   parallel tool calls in one loop; plan written and revised by the same model; procedures in skills, hard limits in
   tools; tool choice degrades past ~30-50 tool definitions (use deferred tool search). Migration: build evals first
   (~10 golden examples), merge tightly coupled specialists, convert subagents to tools as an intermediate, fold one at
   a time, **inspect flipped tasks** and run each task more than once. Subagents remain right for independent research
   paths, clean-interface components and black-box verification.
2. N/A (article).
3. **Overlap / how MOAA compares.**
   - **specialist-council**: 60 role agents is exactly the "org-chart" split the article warns about, but MOAA already
     defaults to 2-3 workers with the parent as lead evaluator and no recursion, and uses roles mainly for
     independent candidates and judging (which the article endorses: independent paths, black-box verification).
     The gap: no rule that says "do it in the main loop when the roles would share context or chain on each other",
     and no evidence that a council beats a single loop on a given task type.
   - **war-room**: parallel real Claude Code workers in worktrees with review gates: fits criterion (b) (independent
     parallel work with fresh contexts). Fine.
   - **agent-arena-mode**: tournaments, judge, karpathy-loop, effort-trial: already the eval machinery the article asks
     for; it can host the "single loop vs council" A/B.
   - The article's "converted to skills" direction matches MOAA's skills-first plugins; the 30-50 tool ceiling matches
     the council roles' explicit core `tools:` lists.
4. **Verdict: port ideas (no code to integrate).**
   - **specialist-council "fold check"** (S): add a dispatch rule to `SKILL.md`/`references/runtime.md`: before spawning,
     state which of the three criteria applies; if none, run the role as a skill/persona in the main loop. Merge roles
     that chain on each other's output into one worker.
   - **arena "fold-trial" mode** (M): reuse `effort-trial` plumbing to run the same frozen task as (A) single loop and
     (B) council/subagent, k>=2 runs each, report score, tokens, wall time and **flipped tasks**, and log to
     `library.sqlite3`. Gives data to drop or keep council recipes.
   - **golden-task set** (S-M): ~10 recorded tasks per council recipe under arena, replayable as evals.
   - **council handoff format** (S): require compact, structured returns (claims + evidence paths) to limit telephone-
     game loss; the claim-table in long-task `checks.md` already does this, reuse it.
5. **Risks.** None technical; the risk is over-applying it: arena/war-room parallelism is in the article's "keep" set.

---

## 6. YouTube: "This $100M AI App Just Changed Software Forever" (Nate Herk | AI Automation)

https://youtu.be/T6_Ges4j1qY (published 2026-03-23, 9:08, ~48K views)

**No transcript** (the caption track exists as auto-generated English, but the timedtext endpoint returned empty
without a browser token). Reviewed from title, description and chapters only.

1. **What it is.** A breakdown of Cal AI (food-photo calorie app reported sold for ~$100M) and how its founder built
   it, framed as "vibecoded"; chapters: scan-food idea, no coding needed, what made it successful, growth, retention.
   Description is mostly course and sponsor links.
2. N/A.
3. **Overlap.** None.
4. **Verdict: skip, review-only** (general startup/marketing story, not about Claude agents or MOAA).
5. N/A.

## 7. YouTube: "Can a Mac Mini Replace your $200 AI Subscription?" (Kai)

https://youtu.be/3R7yba577uA (published 2026-09-28, 19:41, ~371K views)

**No transcript** (same caption fetch failure). Reviewed from the detailed description, chapters and source list.

1. **What it is.** A cost analysis: a 32GB M6 Mac mini ($1,299) running Qwen3.8-27B (4-bit, ~16GB) scores 73 vs 89 for
   frontier models on Terminal Bench 2.1, writes ~10 tok/s, and needs minutes of prefill for agent-harness prompts
   (one case: a 50,111-token prompt read at 93 tok/s, about nine minutes to first token). A month flat out produces
   about $62 of hosted-equivalent tokens (~$15 for a working month), so the box competes with a cheap OpenRouter bill,
   not the $200 plan. Advice: downgrade the plan and try ~$20 of OpenRouter before buying hardware.
2. N/A.
3. **Overlap.** allies (OpenCode with free Zen models, OmniRoute gateway with no providers yet) is MOAA's route to
   cheap/local models; the harness-prefill point applies to any local engine MOAA would hand work to.
4. **Verdict: idea only (mostly review-only).** One useful point for allies: local or slow models choke on big
   harness prompts. If a local engine (e.g. an OpenAI-compatible llama.cpp/Ollama endpoint via OmniRoute) is ever
   added, allies should send a **slim brief** (task + file list, no full skill listing) and record prompt size and
   time-to-first-token per engine in its run log (S). Not worth a hardware recommendation in MOAA docs.
5. **Risks.** Figures are the creator's; hardware/model names are recent and unverified here.

---

## Shortlist (by value / effort)

| # | Idea | Plugin | Effort |
|---|---|---|---|
| 1 | `fold check` dispatch rule (spawn only if context bloat / parallel fresh contexts / tool-selection trouble) | specialist-council | S |
| 2 | Arena `fold-trial`: single loop vs council A/B, k runs, flipped tasks, tokens, time | agent-arena-mode | M |
| 3 | `raw/` read-only PreToolUse guard for the vault | strata | S |
| 4 | Wiki-only answering mode with per-claim page citations + `graph.py check` score | strata (wiki skill) | S |
| 5 | Heading-path (ToC) retrieval in project RAG | strata (`rag.py`) | S-M |
| 6 | Catalog entry for kepano/obsidian-skills | moaa-catalog (`config/kit.json`) | S |
| 7 | Nightly distill + weekly read-only lint recipe (scheduled task) | strata | S-M |
| 8 | Pre-ingest snapshot (git commit in vault) and `fold` (merge weak pages) | strata wiki | S / M |
| 9 | Slim brief + prompt-size/TTFT logging for local engines | allies | S |

Skipped: STAIR model itself, claude-obsidian (duplicate), obsidian-second-brain (deps/keys), second-brain-starter
(no licence), @danikkk_wqs (duplicate), Cal AI video (general).
