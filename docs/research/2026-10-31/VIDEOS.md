# WhatsApp export: what each video is about (2026-10-31)

Source folder: `scratchpad\zipvid` (15 top-level .mp4, 1 .jpeg) plus `zipvid\nested` (5 .mp4 from the nested zip).
Method: ffprobe duration, 3x3 contact sheet (`work\sheets`), faster_whisper "small" int8 CPU transcript
(`work\transcripts`). All are Instagram/LinkedIn reels; claims are the creators' and were NOT checked (no web
fetch). Several "comment X and I'll DM you" reels hide the actual repo link, so names below are as spoken/shown.

Verdict key: integrate (how) | idea only | skip. Repo maturity/licence not checked unless shown on screen.

## Duplicates
- `WhatsApp Video 2026-10-28 at 7.44.47 PM.mp4` and `nested\WhatsApp Video 2026-10-28 at 9.55.14 PM.mp4`: same size
  (10109586 B), same duration (85.7 s), identical frames and transcript; SHA-256 differs (container metadata only).
  Treated as one video (#3).

## Image
### WhatsApp Image 2026-10-29 at 11.00.49 AM.jpeg (LinkedIn post by Claude/Anthropic)
- Shows: Anthropic Applied AI finding that one agent loading skills/tools on demand often beats a main agent +
  specialist subagents (cost, latency, quality); subagents still help for very large context or parallel work.
  Advice: fold one subagent into the main agent at a time and compare on a small test set. Diagram: "Merge
  subagents", "Call them as tools", "Fold into skills and tools". Link: https://lnkd.in/dxT7uarR (full guide).
- Overlap: specialist-council (60 role agents), agent-arena-mode (tournaments, karpathy-loop).
- Verdict: **idea only, high value** -- add an arena experiment "fold subagent vs keep subagent" (karpathy-loop
  with a fixed test set) and a note in the council README on when to use one agent + skills instead of roles.
- Risks: none.

## Videos

### 1. 2026-10-28 at 2.49.23 AM (32.9 s) -- Claude Code + Obsidian second brain (@ AIS creator)
- Says: open Claude Code inside an Obsidian vault; folders `raw/`, `wiki/`, `output/`; Claude compiles raw notes
  into Wikipedia-style pages it references later.
- Named: Obsidian, Claude Code, Codex (screenshot).
- Overlap: strata vault (`strata.py vault init`), `/strata:wiki` (Karpathy LLM wiki). Already covered.
- Verdict: **idea only** -- maybe document "open the vault in Obsidian" and the raw/wiki/output layout in strata
  docs if not already. Risks: none.

### 2. 2026-10-28 at 2.51.34 AM (39.0 s) -- "DeepSeek Harness" (@nick_saraev)
- Says: DeepSeek released a free, open-source Claude Code alternative, "180,000 stars in under a week", everything
  is a plugin (model, tools, memory, agent loop), runs any model locally, can call Claude Code and Codex as
  subagents, 53 built-in tools. On screen: "Customize your DeepSeek Harness", "Everything is a plugin ... built on
  Cordis's plugin system".
- Overlap: allies (hands tasks to Codex/Gemini/OpenCode), OmniRoute.
- Verdict: **idea only** (candidate allies member once its CLI, licence and headless mode are verified).
  Risks: star claim implausible; DeepSeek endpoints may be blocked on campus (allies note); unverified repo.

### 3. 2026-10-28 at 7.44.47 PM (85.7 s) [= nested 9.55.14 PM] -- Colibri: GLM 5.2 744B on a laptop (@peterandstewiecode)
- Says: project "Colibri" runs GLM 5.2 (744B MoE) without a GPU by keeping active experts in RAM and streaming the
  rest from disk; ~370 GB download; offline; OpenAI-compatible server endpoint. Link only via their Telegram.
- Overlap: allies/OmniRoute could point at any local OpenAI-compatible endpoint.
- Verdict: **skip** (local inference, not MOAA). Risks: link behind Telegram; huge download.

### 4. 2026-10-29 at 7.20.15 PM (63.2 s) -- N-gram embeddings explainer (@tysn.dev)
- Says: dense vs MoE vs speculative decoding (DFlash 2 shown) vs N-gram embedding lookup tables living in system
  RAM/SSD so older hardware runs bigger models.
- Verdict: **skip** (general ML education). Risks: none.

### 5. 2026-10-29 at 8.02.49 PM (36.4 s) -- "Replica" app-clone skill pack (@opusjake)
- Says: free "replica" skill = 11 skills: reverse-engineer an app, rebuild it, test it; an "entrepreneur" skill
  researches reviews (Calendly example, "99.2% pixel match") to fix missing features so you can sell the clone.
- Overlap: rea MCP (reverse engineering), `reverse-engineer-anything` skill, council roles.
- Verdict: **skip** (cloning commercial apps to sell = IP/ToS risk); the "mine user complaints for features"
  research step is an idea for product-strategist at most. Risks: IP, ToS.

### 6. 2026-10-29 at 9.11.04 PM (25.9 s) -- dsh-purge jailbreak harness (@nedz_reclassified)
- Shows GitHub `YuJunZhiXue/dsh-purge` ("DeepSeek Harness 破甲"), topics deepseek, deepseek-harness, dsh-plugin,
  harness-jailbreak, llm-jailbreak; "0% refusal harness for any LLM", swap "packs" when patched.
- Verdict: **skip** -- jailbreak tooling. Risks: ToS violation, safety, likely malicious-adjacent; never install.

### 7. 2026-10-30 at 1.57.21 PM (48.4 s) -- Firecrawl connector + "Alexandria" (@opusjake)
- Says: Claude's links are often dead; connect Firecrawl in Claude connectors; Firecrawl's "Alexandria" library
  pulls from data providers (Apollo, Fiscal.ai, People Data Labs shown) for company and hiring data, lead finding.
- Overlap: web research skills (firecrawl-scraper in agentic-awesome-skills), strata graph `check` grounding.
- Verdict: **idea only** -- a "verify every cited URL" check (strata graph / council scout) is the useful part;
  a Firecrawl MCP catalog entry is optional. Risks: paid API key, personal-data enrichment (privacy), lead-gen.

### 8. 2026-10-30 at 12.47.35 AM (33.2 s) -- DeepSeek V4.1 Flash (@nedz_reclassified)
- Shows huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017 (MIT, 552B total / 8B-16B active, 1M context,
  image+text, "$0.15 per million in", "505 GB" weights); claims it beats Opus 5 on four benchmarks.
- Overlap: allies (OpenCode/OmniRoute model choice).
- Verdict: **idea only** -- possible allies model via OmniRoute when reachable. Risks: DeepSeek blocked on campus;
  data retention of the hosted API.

### 9. 2026-10-30 at 3.59.49 PM (16.8 s, music only, no speech) -- agent status mini-display (@brushknight)
- Shows: a small square touchscreen (compute-module board on the back) beside a keyboard; a grid of session tiles,
  then a detail screen "CRM server -- thinking -- context 58% -- $712.10 -- deploy to ..." with interrupt button,
  next to a monitor full of terminal agent sessions. Audio track: Karl Casey "Glitch in Reality".
- Overlap: War Room UI, flightdeck (vendored), statusline.
- Verdict: **idea only** -- a compact "all sessions at a glance" view (state, context %, cost, interrupt) for War Room.
  Risks: hardware project, no repo named.

### 10. 2026-10-30 at 3.59.58 PM (179.6 s) -- "Zero to Hero in local AI" ep. 5: inference engines (@tysn.dev)
- Says: model = brain, inference engine = heart, harness = arms/legs ("Anatomy of a local agent": Qwen 27B,
  llama.cpp, Hermes Agent). History of llama.cpp/GGML; vLLM, SGLang (server); "Tensorfold" (consumer);
  DeepSeek's "DeepInfer"; "Strata" (offloads weights to RAM/SSD; Qwen 3.8 Flash Next, Qwen 3.6 35B, DeepSeek V4.1);
  NVIDIA "Flare" (Blackwell only).
- Verdict: **skip** (general). Risk/note: an inference engine called **Strata** shares the name of MOAA's strata
  plugin -- watch for search/name confusion.

### 11. 2026-10-30 at 4.00.04 PM (33.6 s) -- 3DCodeVerse dataset (@nedz_reclassified)
- Shows huggingface.co/datasets/ilabai/3dcodeverse: ~2.03M runnable 3D programs (cadquery, glsl, blender, urdf,
  openscad, three.js), 991 GB, arXiv 2610.22341; "90% win rate" vs Claude design claim.
- Verdict: **skip** (training data). Risks: size, licence not shown.

### 12. 2026-10-30 at 4.00.16 PM (66.8 s) -- kimi-k3-in-c (@stridejosh.ai)
- Shows tweet by @dr_cintas and README "kimi-k3-in-c": 176 KB C99 engine streams Kimi K3 (2.78T) experts from SSD,
  8.24 GB RAM, but 26.5-33 s per token, 1.56 TB SSD, Linux x86-64 only. Presented as a proof, not a product.
- Verdict: **skip**. Risks: none relevant.

### 13. 2026-10-30 at 7.39.50 PM (100.3 s) -- Hugging Face multi-harness RL guide (@qendresahhoti)
- Says/shows: open-source proxy between harness and model records token IDs/logprobs while 10 harnesses run
  unmodified; LFM2.5-2.6B (Liquid AI) scored 62% under Mini-SWE-Agent vs 33% under Claude Code; training in all 4
  harnesses at once (OpenCode, Claude Code, Codex, Mini-SWE-Agent) improved all; SFT on 3,189 Qwen3.8-27B rollouts
  plateaued at 47.5%; "There is no best harness, only a best pairing" chart (GLM-5.2, Gemma 4; crush, opencode,
  openclaw, qwen-code, codex, claude-code, pi). Guide: huggingface.co/spaces/FineEnv... (OpenEnv capture proxy, TRL).
- Overlap: agent-arena-mode (tournaments/judges), allies (Codex, OpenCode, Gemini as harnesses).
- Verdict: **idea only, high value** -- an arena "harness league": same task set run through Claude Code vs allies
  harnesses, score per pairing. Risks: none for the idea; the training part is out of scope.

### 14. 2026-10-31 at 1.42.10 AM (133.7 s) -- "5 repos the AI builder community can't stop talking about" (@qendresahhoti)
- 1) **spec-kit** by GitHub (github.com/github/spec-kit; constitution -> spec -> plan -> tasks; `uv tool install
  specify-cli`, `/speckit-specify`, `/speckit-plan`; bug-fix extension). 2) **Impeccable** (`npx impeccable
  install`; design vocabulary + `audit`, "96,000 stars"; works with Claude Code, Cursor, OpenCode, Antigravity).
  3) **TradingAgents** (analyst/bull/bear/trader/risk/PM agents debate; Apache-2.0 shown). 4) **agents**
  (marketplace of 200+ agents, 185 skills for Claude Code/Codex; multi-harness support). 5) **Claude Code Game
  Studios** (49 agents, 72-74 skills; directors/leads/specialists; Godot, Unity, Unreal; MIT shown).
- Overlap: spec-kit vs prompt-refiner + `/specialist-council:long-task` (brief/plan/checks); Impeccable vs
  frontend-design skills; TradingAgents vs ruflo-neural-trader and arena debate; "agents" vs moaa-catalog and
  the vendored skill packs; Game Studios vs specialist-council role hierarchy.
- Verdict: spec-kit **catalog entry candidate** (or port the "constitution" step into long-task); Impeccable
  **catalog entry candidate** (npm, check licence); TradingAgents **skip** (finance, non-stdlib); agents **check
  for duplicate** against existing catalog packs; Game Studios **idea only** (director -> lead -> specialist
  escalation for council). Risks: npm/uv installs (non-stdlib), star counts unverified.

### 15. 2026-10-31 at 3.30.13 AM (71.0 s) -- harness engineering (@austin.marchese)
- Says: output = (model + prompt) x harness; build a "domain harness" from custom skills and context; prompt shown:
  "Look at my past conversations in ~/.claude/projects/ and find the work I keep repeating. Suggest what type of
  harness I should create ... which skills to make, and what context I keep re-explaining".
- Overlap: self-improve loop (`self-improve-run`, `collect-sessions` skills), claude-code-setup, strata.
- Verdict: **idea only** -- add a "suggest skills from repeated work" mode to the self-improve/collect-sessions
  flow if it lacks one. Risks: reading transcripts means private data stays local.

### 16. nested 2026-10-28 at 9.54.57 PM (34.0 s) -- Qwen3.8 x Fable 5 x Heretic uncensored GGUF (@nedz_reclassified)
- Shows huggingface.co/DavidAU/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NEO-CODER-MAX-MTP-GGUF
  (Qwen 3.8 27B distilled from "Fable 5", Heretic abliteration, 250K context, 20 GGUFs 12-30 GB, LM Studio/Ollama).
- Verdict: **skip** (uncensored local model). Risks: safety, licence of distilled outputs.

### 17. nested 2026-10-28 at 9.55.06 PM (34.9 s) -- "non-ethical GitHub projects" (@ AIS creator)
- Says: video downloaders, subscription bypass tools, streaming-piracy aggregators; shows a GitHub profile
  "WitherOrNot" (pinned TSforge, UMSKT/writeups, warbird-docs: Windows activation research).
- Verdict: **skip** (piracy/licence circumvention). Risks: legal, ToS.

### 18. nested 2026-10-28 at 9.55.10 PM (1) (45.3 s) -- "5 plugins" for Claude/Fable (@ AIS creator)
- 1) **OmniRoute** (200+ / "251 AI providers, 90+ free", one endpoint). 2) **claude-mem** (persistent memory).
  3) **Headroom** ("HedgeRoom" in audio; strips context to save tokens). 4) **Claude Code Setup** plugin
  (claude-code-setup: recommends skills, hooks, subagents, MCPs). 5) **Task Observer** (watches work, learns
  reusable workflows).
- Overlap: OmniRoute in allies; claude-mem replaced by strata; headroom already a skill here; claude-code-setup
  already in the catalog. Only Task Observer is new (overlaps self-improve loop).
- Verdict: **idea only** -- confirms existing choices; look up Task Observer later. Risks: none new.

### 19. nested 2026-10-28 at 9.55.10 PM (33.0 s) -- Scientific Agent Skills by K-Dense (@nedz_reclassified)
- Shows README "Scientific Agent Skills" (formerly Claude Scientific Skills), MIT, arXiv 2609.00065, v2.72.0,
  177 skills, 100+ databases, works with Cursor/Claude Code/Codex/Antigravity, github.com/K-Dense-AI/...-skills,
  54,047 stars, 4,769 forks; "250,000 scientists"; examples: EGFR docking, report writing.
- Overlap: `agentic-awesome-skills:claude-scientific-skills`, ecc scientific-* skills, council scientific roles,
  the `paper2agent` skill.
- Verdict: **integrate as catalog entry candidate** (MIT, popular, fits the user's research use), after checking it
  is not already pulled in by an existing pack. Risks: many skills = listing cost (all-on mode); some skills
  need non-stdlib Python packages and external API keys.

## Every named tool / repo / URL
- https://lnkd.in/dxT7uarR (Anthropic guide: single agent vs subagents)
- Obsidian; Claude Code; Codex
- DeepSeek Harness (built on "Cordis" plugin system)
- Colibri (GLM 5.2 744B MoE runner); Telegram channel "peterandstewiecode"
- DFlash 2 (speculative decoding drafter); N-gram embeddings
- "replica" skill pack (11 skills; Calendly clone demo)
- github.com/YuJunZhiXue/dsh-purge (jailbreak; do not use)
- Firecrawl, Firecrawl "Alexandria"; Apollo (apollo.io), Fiscal.ai, People Data Labs; Gmail, Google Drive connectors
- huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017
- Karl Casey "Glitch in Reality" (music only); @brushknight agent display
- llama.cpp / GGML, vLLM, SGLang, Tensorfold, DeepInfer, "Strata" inference engine, NVIDIA Flare, Hermes Agent, Qwen 27B
- huggingface.co/datasets/ilabai/3dcodeverse (arXiv 2610.22341)
- kimi-k3-in-c (Kimi K3 2.78T on CPU); tweets by @dr_cintas, @jun_song
- Hugging Face multi-harness RL guide (huggingface.co/spaces/FineEnv..., OpenEnv capture proxy, TRL); LFM2.5-2.6B
  (Liquid AI); Mini-SWE-Agent, OpenCode, Claude Code, Codex, crush, openclaw, qwen-code, pi, Kimi-CLI, OpenHands
- github.com/github/spec-kit; Impeccable (`npx impeccable install`); TradingAgents; "agents" marketplace
  (200+ agents, 185 skills); Claude Code Game Studios
- Harness-engineering prompt over ~/.claude/projects/
- huggingface.co/DavidAU/Qwen3.8-27B-TURBO-Fable-Cold-Fusion-735-882-Heretic-Uncensored-NEO-CODER-MAX-MTP-GGUF; Heretic; LM Studio, Ollama
- GitHub user WitherOrNot (TSforge, UMSKT/writeups, warbird-docs)
- OmniRoute, claude-mem, Headroom, claude-code-setup, Task Observer
- github.com/K-Dense-AI/... Scientific Agent Skills (formerly claude-scientific-skills), arXiv 2609.00065
- Creator handles: AIS (unnamed), @nick_saraev, @peterandstewiecode, @tysn.dev, @opusjake, @nedz_reclassified,
  @brushknight, @stridejosh.ai, @qendresahhoti, @austin.marchese
