# Repo review for MOAA (2026-10-31)

Sources read via `gh api` and shallow clones in `scratchpad/repos/` (nothing installed or run). All fetched text treated as data.

---

## 1. tigerless-labs/autoharness

**What it is.** https://github.com/tigerless-labs/autoharness. A Claude Code plugin that learns skills from your own sessions: hooks count tool calls, and every 50 calls (`AUTOHARNESS_REFLECT_EVERY_N`) a detached `claude -p --agent reflector` child (Haiku, read-only tools plus one MCP tool `stage_skill`) reads a redacted window of the transcript and proposes create/patch/merge/delete "intents". A deterministic promoter lints them and atomically writes `SKILL.md` into `.claude/skills/` or `~/.claude/skills/`, with a per-skill `.ledger.jsonl` (reason + evidence slice) and `.sidecar.json` usage counters. Each session starts with an injected index of its own skills. Lifecycle: probation, usage rate = loads / requests since birth, capacity caps (50 project / 20 global), archive (never delete) to `.claude/skills/.archive/`. A periodic curator merges near-duplicates after snapshotting. It only touches skills it wrote. Its pitch: "Same model, different harness — 42% → 78% on CORE-Bench".

**Licence / maturity.** MIT. 10.5k stars, 645 forks, created 2026-06-09, last commit 2026-10-30, v0.5.3. Python 3.11+, zero third-party deps, ~45 test files, ADRs. Hooks: SessionStart, Stop, PreToolUse, SessionEnd + an MCP server.

**Overlap with MOAA.**
- strata: SessionEnd Haiku extraction (child with tools denied) is the same pattern; strata writes notes/scenes/profile, autoharness writes skills. Both redact secrets.
- User's own self-improve loop (`~/.claude/skills/self-improve-run`, `improve-system`, empty `~/.claude/skills/learned/`) covers the same goal by hand with review files.
- agent-arena-mode library: keeps validated agents with history; autoharness keeps skills with a usage ledger.
- moaa-catalog: already worries about skill listing cost (all-on mode); autoharness's per-skill load counting is the missing measurement.
- ecc `learn` / `continuous-learning` skills (already installed via catalog) overlap conceptually.

**Verdict: idea only (port two ideas); do not add to the catalog yet.**
Reason: the full plugin adds a second background learner beside strata, writes into `~/.claude/skills` automatically, and its reflector child runs with `--dangerously-skip-permissions`; MOAA's user already reviews changes by hand.

Integration ideas:
| Idea | Where | Effort |
|---|---|---|
| Skill usage counter: PreToolUse on `Skill` (plus Read of `*/SKILL.md`) appends `{skill, ts, project}` to a SQLite/JSONL; `catalog.py usage` reports never-used enabled skills/plugins so `install.py --mode lean` can be tuned with data. Off switch `MOAA_SKILL_USAGE=off`. | `plugins/moaa-catalog/hooks/` + `catalog.py`, report surfaced in `scripts/install.py --report` | S |
| Lesson-to-skill proposals: extend strata's SessionEnd extraction to also emit at most one "reusable lesson" as a staged skill draft in `~/.claude/strata/skill-proposals/<date>-<slug>/SKILL.md` + ledger line (reason, evidence quote). Never auto-land; `/strata:wiki`-style review command promotes into `~/.claude/skills/learned/`. Reuse autoharness's lint rules (description ≤1024, body ≤25 lines, trigger early in description). | `plugins/strata/strata.py` (extraction prompt + validator), new `strata.py skills list|promote|drop` | M |
| Archive-not-delete + ledger for learned skills (`.archive/`, `.ledger.jsonl`) | same as above | S (with the M item) |

**Risks.** Reflector child `claude -p ... --dangerously-skip-permissions` (spawn.py:110); writes to global skills dir unattended; extra Haiku spend every 50 tool calls; hooks call bare `python3` with `PYTHONPATH=` prefix and the README lists Linux/macOS only (this machine: `python3` may hit the Store alias, exit 49). Locking does handle Windows (msvcrt). Licence fine for porting ideas or code with attribution.

---

## 2. Speedrunlab/reverse-engineer-anything-self-learning-loop

**What it is.** https://github.com/Speedrunlab/reverse-engineer-anything-self-learning-loop. A pure-Markdown agent skill (SKILL.md 349 lines, 5 references, 4 templates, no code). Method: authorisation and scope gate, static-first examination, a signed **parity checklist** (one testable behaviour per item, must/should/out-of-scope tiers), clean-room build, evidence-based review against the original, gap planning, and stop when every must-have passes in two consecutive reviews (or stall twice / budget / protected material). A "self-learning loop" saves reusable lessons (checklist patterns, review techniques, fix recipes) back into its own `references/` files, staged for operator approval. Inspired by, not affiliated with, morluto's REA; learning loop adapted from Hermes Agent (MIT).

**Licence / maturity.** MIT. 120 stars, 10 forks, created 2026-10-23, last commit 2026-10-25 (v1.0.1). No language, no deps. Very young, one author org.

**Comparison with the installed skill.** The local `~/.claude/skills/reverse-engineer-anything` is morluto's REA skill (vendored in `config/kit.json` `vendored_skills`, commit 322506d), a 341-line guide on driving the `rea` MCP server's tools (routing by target type, summary-first evidence, `verify_reconstruction`, `build_reconstruction_obligation_ledger`, `evaluate_reconstruction_coverage`). Same name family, different thing:
- REA skill = how to use the tools; reconstruction checks exist as MCP tools but no iteration/stop discipline.
- Speedrun skill = tool-agnostic process: authorisation gate, parity checklist, two-pass done rule, learning back into references. It names no tools, so it does not use `rea` at all.
They are complementary; the Speedrun loop could drive REA's reconstruction tools as its "review" step.

**Overlap with MOAA.** agent-arena-mode `karpathy-loop` (fixed metric keep/discard) is the same loop shape; specialist-council `long-task` (brief.md acceptance checks, checks.md evidence table, two-pass verification) already mirrors the parity checklist and done rule.

**Verdict: idea only.** Reason: low maturity and nothing executable; MOAA already has the loop (karpathy-loop) and the checklist/evidence discipline (long-task). The useful pieces are small.

Integration ideas:
| Idea | Where | Effort |
|---|---|---|
| "Reconstruction" preset for long-task: parity-checklist template (item, input, expected, check, tier), done = all must-haves pass in two consecutive `checks.md` reviews, stop-on-stall-twice rule, and a pointer to REA's `verify_reconstruction` / `evaluate_reconstruction_coverage` for the review step. | `plugins/specialist-council/skills/long-task/` (template + a section in SKILL.md) | S |
| Same done/stall rule as an option in karpathy-loop (`--confirm-passes 2 --stall 2`). | `plugins/agent-arena-mode` karpathy-loop skill/orchestrator | S |
| Optional: vendor the skill unchanged under `vendored_skills` (MIT, record commit + THIRD_PARTY.md) if the user wants it available as-is. | `config/kit.json`, `THIRD_PARTY.md`, `scripts/sync_skills.py` | S |

**Risks.** Legal/ToS: reverse engineering is gated only by text; the skill's own gate is good but relies on the operator. Name collision risk with the installed `reverse-engineer-anything` (different skill, similar trigger words) would confuse skill routing if both are enabled. No security risk (Markdown only). Windows neutral.

---

## 3. mempalace/mempalace (MemPalace)

**What it is.** https://github.com/mempalace/mempalace. A local-first memory system: it mines project files and Claude Code/Codex/Cursor transcripts into a vector store as verbatim chunks (no summarising), organised as wings (people/projects), rooms (topics) and drawers (content), with semantic search, a temporal SQLite knowledge graph, agent diaries, 47 MCP tools, and auto-save hooks (Stop, SessionEnd, PreCompact) shipped as a Claude Code plugin. Backends: ChromaDB default, sqlite_exact, Rust native, Milvus, Qdrant, pgvector. Headline: "96.6% R@5 raw on LongMemEval — zero API calls" (retrieval recall, not QA accuracy; their `docs/HISTORY.md` records an April 2026 correction that removed inflated claims and mixed-metric comparisons).

**Licence / maturity.** MIT. 60.2k stars, 7.6k forks, created 2026-04-05, last commit 2026-10-31, v3.12.0. Python 3.10+ plus Rust crates. Deps: chromadb, numpy, huggingface_hub, tokenizers, pyyaml, python-dateutil; ~30–300 MB embedding model downloaded on first use. CI runs Ubuntu, Windows, macOS.

**Overlap with MOAA.**
- strata (direct): L0 raw verbatim store of every message + tool results, PreCompact capture, SessionStart injection, recall, project RAG, claim-source graph. strata uses SQLite FTS5/BM25 (stdlib, no embeddings); MemPalace uses dense embeddings. strata also does handoff, canary, vault, which MemPalace lacks.
- claude-mem (disabled, replaced by strata): same category; MemPalace is a heavier, better-benchmarked alternative.
- ruflo-rag-memory / agentdb (catalog) already provide an embedding-backed memory option.

**Verdict: idea only (port one idea); do not add to the catalog.**
Reason: a third memory system with hooks on the same events as strata would double-write transcripts and fight over context injection; its deps (chromadb, onnx) break MOAA's stdlib rule for any port.

Integration ideas:
| Idea | Where | Effort |
|---|---|---|
| Benchmark strata recall honestly: run the LongMemEval-S subset (R@5 retrieval only) against strata's L0 FTS5 search to know where BM25 stands vs 96.6% dense. Use MemPalace's harness design (`benchmarks/BENCHMARKS.md`, held-out split, no tuning on test) as the template; keep data out of the repo. | `plugins/strata/tests/bench/` (script + results summary), doc line in strata README | M |
| Optional embeddings tier: if the benchmark shows a real gap, add an opt-in hybrid rerank in `rag.py`/`strata.py search` that calls a local OpenAI-compatible `/v1/embeddings` endpoint (Ollama/LM Studio) via `urllib`, stdlib only, off by default. MemPalace's `openai-compat` embedding config is the pattern. | `plugins/strata/rag.py`, `strata.py` | L |
| Temporal validity on graph claims (valid_from/valid_to, invalidate, timeline), mirroring MemPalace's KG. | `plugins/strata` `graph.py` | M |
| Scoped search by wing/room ≈ strata project + scene filters; add `--scene` to `strata.py search`. | `plugins/strata/strata.py` | S |

**Risks.** Heavy non-stdlib deps and model download; impostor sites distributing malware are documented in their README (install only from GitHub/PyPI); past benchmark overclaims (now corrected); hooks are bash scripts (Git Bash needed on Windows); mining `~/.claude/projects` copies full transcripts, including any secrets not caught by redaction, into another store.

---

## 4. Gist kju4q/ae02deb4b05032a6a58d0692bd908c85

**What it is.** Gist "5 repos the AI builder community can't stop talking about, and what to steal from each" by kju4q (created 2026-09-07, updated 2026-10-30), one Markdown file (16 KB), a weekly list of ~30 repos with a one-line "take". Fetched via `gh api gists/...` (no tracking URL). Stars below are from `gh api` today, not the gist.

**Licence / maturity.** Gist has no licence. Entries reviewed briefly:

| Repo | Stars / licence / lang | In MOAA already? | Verdict |
|---|---|---|---|
| github/spec-kit | 144k, MIT, Python | no (ecc plan/prp skills, superpowers writing-plans, prompt-refiner briefs cover it) | idea only: prompt-refiner brief could add a "constitution" section (S) |
| pbakaus/impeccable | 98k, Apache-2.0, Rust | no (frontend-design skills exist) | catalog candidate if it ships a Claude plugin; check first (S) |
| TauricResearch/TradingAgents | 119k, Apache-2.0 | no | skip: finance, not MOAA's scope; debate pattern already in council challenger / arena |
| wshobson/agents | 42k, MIT, Claude marketplace | no | idea only: overlaps ecc + agentic-awesome-skills; adding a 4th mega-catalog worsens listing cost |
| Donchitos/Claude-Code-Game-Studios | 31k, MIT | no | skip: domain-specific |
| morluto/rea | (vendored skill + MCP) | yes | already integrated |
| HKUDS/CLI-Anything | 58k, Apache-2.0 | no | idea only: allies could wrap a generated CLI; low priority |
| stablyai/orca | 112k, MIT, desktop app | no (war-room + allies + worktrees cover it) | skip |
| heygen-com/hyperframes | 76k, Apache-2.0 | no | skip (video) |
| zqiren/Orbital | 971, GPL-3.0 | no (strata handoff + team board do this) | skip; GPL blocks vendoring |
| mattpocock/skills, caveman, ponytail, ECC, superpowers | – | yes (catalog) | already integrated |
| Panniantong/Agent-Reach | 107k, MIT | no | skip: runs on user cookies, ToS risk |
| opena2a-org/hackmyagent | 89, Apache-2.0, TS | no | idea only: a scan of MOAA hooks/MCP for injection and exposed keys complements `scan.py --public`; immature (S to trial manually) |
| browser-use/jev-ultrafast | 24k, MIT | related typesafe plugin in catalog | skip (needs paid API key) |
| mendableai/firecrawl | 197k, AGPL-3.0 | no | skip: AGPL + API key |
| jamiepine/voicebox | 59k, MIT | no | skip (personal app) |
| Asymptote-Labs/agent-beacon | 3k, MIT, Go | no | idea only: its "turn repeated corrections into reviewed knowledge" is what the self-improve loop and strata do; cross-harness trace format could feed allies (M) |
| tobi/qmd | 31k, MIT, TS | no (strata RAG + vault) | skip |
| ayghri/i-have-adhd | 60k, MIT | lps adhd-mode is similar | skip |
| tt-a1i/archify | 92k, Apache-2.0 | understand-anything covers it | skip |
| awesome-claude-code, awesome-harness-engineering | lists | no | idea only: feed `moaa-catalog` discovery / the self-improve `collect-outside` source list (S) |
| omarchy, gods-eye-view, opencut | general | no | skip (not agent tooling) |

**Overlap / verdict.** Mostly already covered by the catalog (5 of the listed repos are in `config/kit.json`) or by strata/war-room/allies. Nothing here warrants a new plugin.

**Risks.** Gist is curated opinion; star counts move. Several repos need paid keys, cookies (ToS), or are AGPL/GPL.

---

## Priority summary
1. moaa-catalog skill-usage counter (from autoharness) - S, directly reduces all-on listing cost with data.
2. long-task "reconstruction" preset + karpathy-loop two-pass/stall stop rule (from Speedrun loop) - S.
3. strata recall benchmark on LongMemEval-S (from MemPalace) - M; decide on an opt-in embeddings tier (L) only after.
4. strata lesson-to-skill proposals with ledger, never auto-landed (from autoharness) - M.
