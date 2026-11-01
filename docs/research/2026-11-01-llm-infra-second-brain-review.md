# Review: LLM architectures, inference engines, AI cost reports, and two research archives (2026-11-01)

Eight files the user collected on 2026-10-28 to 2026-10-31, reviewed for two readers:

- **The LLM-Mega-Encyclopedia project**, which should take Part C (encyclopedia-ready material) and the source notes.
- **MOAA**, the Claude Code plugin marketplace, which should take Part D (candidate additions).

**How to read the claims.** Four files are reports written by other AI tools; two archives hold AI-written research
runs; two archives hold a Claude Code session record. No benchmark or price below was reproduced for this review.
Model names, versions and prices dated after mid-2026 are reported claims, kept with their sources so the encyclopedia
can verify them. Where two files disagree, the disagreement is stated and the better-sourced one is preferred.

| # | File | Kind | Size | One-line verdict |
|---|---|---|---|---|
| 1 | `LLM_Architectures_and_Inference_Engines_2026 (1).md` | AI-written technical report | 799 lines, 60 primary refs | Best of the four reports: careful, sourced, corrects common myths |
| 2 | `Comprehensive Report_ LLM Architectures & Inference Engines (2026 Edition).md` | AI-written technical report | 217 lines, blog-grade links | Same topics, more hype; several numbers contradicted by file 1 |
| 3 | `AI_Architecture_Hosting_and_Cost_Optimization_Master_Report_2026 (1).md` | AI-written cost audit + file 1 | 1,822 lines, 72 vendor refs + file 1's 60 | Strongest cost document; Part II is file 1 verbatim |
| 4 | `AI Cost & Infrastructure Evaluation_ Subscriptions, Self-Hosting, Serverless APIs & GPU Clouds.md` | AI-written cost report | 165 lines | Earlier, simpler version of file 3; some conclusions superseded |
| 5 | `Claude Second Brain.zip` | Research bundle (Claude Code run) | 190 files, 55 MB | 9 fact-checked reports on 7 reels and 4 X posts; useful corrections |
| 6 | `cc_tmp.zip` | Working files of the same run | 5,231 files, 140 MB | The run's venv, scripts, stage outputs and the STAIR paper scrape |
| 7 | `session-2026-10-28-snapshot.tar.xz` | Claude Code web session archive | 6.5 MB | LLM-Mega-Encyclopedia coordination work, mid-session |
| 8 | `session-2026-10-28-final.tar.xz` | Same session, final | 9.5 MB | Adds the git bundle, final audit (PASS) and Opus sign-off |

---

## Part A. What each file contains

### A1. LLM Architectures and Inference Engines in 2026 (file 1)

**Scope.** A technical report with an evidence cutoff of 29 October 2026. It treats model architecture, memory
mechanisms, decoding and serving as separate design axes. It cites papers, model configs, repositories and docs
directly (60 references), labels every number as author-, developer- or operator-reported, and reproduces nothing.

**Structure.**
1. Four axes of evolution: compute sparsity (MoE), conditional memory (n-gram lookup), token mixing and residual
   topology, heterogeneous and disaggregated serving.
2. Foundational families: encoder-only (BERT, ModernBERT, DeBERTa-v3), encoder-decoder (T5, BART, UL2), dense
   decoder-only with the Pre-RMSNorm, SwiGLU, RoPE and GQA recipe, plus the KV-cache formula
   `M_KV ≈ 2·B·N·L·H_KV·d_h·b` (worked: 32 layers, 8 KV heads, width 128, BF16 = 128 KiB per token, about 16 GiB at
   128K).
3. Production architectures: fine-grained MoE with shared experts, auxiliary-loss-free balancing, MLA, DeepSeek-V4
   CSA/HCA, Qwen sparse attention (QSA) with index reuse across MTP steps, and the complexity correction that an
   exhaustive indexer still adds `O(L²·d_i/r)` prefill work.
4. Emerging architectures: Engram conditional memory, Qwen3.8-Next's single n-gram layer, TN-gram, COUNT, mHC and
   four-branch gated residuals, Mamba-2, Gated DeltaNet, RWKV-7, xLSTM, hybrid recurrent/attention layouts, Titans,
   diffusion LLMs (LLaDA, Gemini Diffusion, Mercury 3), Byte Latent Transformer, COCONUT and Tiny Recursive Models.
5. A 16-row taxonomy matrix (compute scaling, state memory, active parameters, advantage, bottleneck, examples).
6. A schematic forward pass through a Qwen3.8-Flash-Next-style block, including what speculative rollback must undo.
7. Inference engines: Strata Local (consumer MoE engine), Strata/Contextra (SGLang context cache), KTransformers v0.7,
   Magnitude, llama.cpp/GGML, P/D disaggregation, vLLM (PagedAttention, TorchTPU), SGLang (RadixAttention, HiCache),
   NVIDIA Dynamo and NIXL, Mooncake.
8. An engine matrix with each number qualified, a 12-dimension checklist for a meaningful benchmark, and five
   engineering conclusions.

**Corrections it makes that the encyclopedia should keep** (each is contradicted by file 2):
- Qwen3.8-Flash-Next is 125B main model + 6B active + a separate 51B n-gram table; the popular "3B active" is wrong.
- Two unrelated projects are called Strata: Niko1221/Strata (local engine) and the Strata/Contextra SGLang cache
  paper. (A third, MOAA's strata memory plugin, is unrelated to both.)
- A hybrid with a fixed fraction of full attention stays quadratic; sparse attention must count its indexer.
- Muon is a training optimizer, not an inference operator.
- Mooncake's trillion-tokens/day case describes SSD as a planned tier, not a deployed one.
- Engram's "75/25" is an empirical optimum (75-80% of the sparse budget to MoE, 20-25% to memory) in tested
  regimes, not a hardware rule.
- Strata Local's "swap 96 experts every 4 turns" was not found in the project's primary docs.
- vLLM's 2-4x figure is the original 2023 PagedAttention paper's, not a 2026 comparison.

**Reliability: high for a secondary source.** It is conservative, explicit about units and baselines, and separates
architecture claims from measured deployment evidence. Model facts dated 2026 still need checking against the cited
primary pages.

### A2. Comprehensive Report: LLM Architectures & Inference Engines, 2026 Edition (file 2)

**Scope.** The same outline as file 1 (four axes, foundational, mainstream, emerging, forward pass, engines, two
matrices), written in a promotional register and sourced largely from blogs, Medium and note.com posts.

**What it adds over file 1.** Clear plain-language explanations of each mechanism (useful for teaching), the Engram
canonicalisation pipeline spelled out (NFKC, NFD, accent strip, lowercase, whitespace), and the encoder MLM masking
range.

**Where it conflicts with file 1 (prefer file 1):**

| Claim in file 2 | File 1 / primary sources |
|---|---|
| Qwen3.8-Flash-Next "24,576 experts", hot cache of 3,556-4,500 experts, swaps 96 experts every 4 turns | Swap schedule not found in primary docs; it is configurable |
| Hybrids "retain 100% exact needle recall", "8.6x prefill at 1M" | Stated without baseline; hybrids with fixed attention fraction stay quadratic |
| Engram "<3% throughput penalty", "Layer 5 matches Layer 12", "+5.0 BBH, +3.4 MMLU, 97.0 vs 84.2 NIAH" | Reported by the Engram authors under their settings; not general |
| Titans "scales past 2M-10M tokens" | Paper's claims under its settings |
| Diffusion LLMs give "7x-15x" speed | No hardware-normalised comparison exists |
| Mooncake pools "local NVMe SSDs" as a persistent tier | Operator describes SSD as planned |
| Magnitude "up to 2x faster than llama.cpp" | Developer's comparison is against Ollama, whole-stack |
| llama.cpp/GGML "joined Hugging Face in Feb 2026" | Not checked here; verify |
| TRM "45% on ARC-AGI-1 with 7M parameters" | Paper studies puzzle tasks; not a general assistant |

One line contains a stray Indonesian word ("puluhan gigabytes"), a sign of unedited machine output.

**Reliability: medium-low.** Use it for explanations and outline, never for numbers without file 1's qualifier.

### A3. AI Architecture, Inference, Hosting, and Subscription Economics, master report (file 3)

**Scope.** A cost audit dated 30 October 2026, written for one user in Qatar who pays one $100 or $200 plan (Claude
Max or ChatGPT Pro), followed by **file 1 reproduced verbatim** (Part II, lines 1022-1822; a diff finds only a trailing
blank line). It has 72 economic references (E01-E72), all vendor or primary pages checked 30 October 2026; no papers,
no independent benchmarks.

**Method.** Every result comes from four equations with the variables stated:
- Blended rate with cache reads and writes kept disjoint: `b(h,w) = 0.8[(1-h-w)I + hR + wW] + 0.2O`.
- Subscription break-even `M_BE = S/b`, capped plans `S + max(0, M - M_cap)·b_over`, and plans with API credits
  `S + max(0, B_eligible - K) + B_ineligible`.
- Local hardware: decode `D = 0.75·B/W` (an assumed efficiency), time per 1M blended
  `10⁶(0.8/P + 0.2/D)`, monthly cost `(C0 - resale)/36 + energy + maintenance + labour`.
- Cloud idle trap: `b = p·10⁶/(3600·u)·(0.8/P + 0.2/D)`.

It also defines cost per successful task `C/p`, so a cheap model that fails often can cost more.

**Main findings (claims as of 30 Oct 2026).**
- Claude Max 5x/20x and ChatGPT Pro 100/200 advertise separately claimable monthly API credits equal to the plan
  price, with eligibility, expiry and exclusions (Claude's exclude interactive Claude Code). A credit is worth only
  the spend it displaces. Buying a plan for its credits never saves cash below $100 of eligible API work.
- Gateways: OpenRouter 5.5% credit fee (BYOK free up to $25k/month list), Requesty 5%, Eden 5.5%, Not Diamond
  $0.05/M routed, LiteLLM and RouteLLM self-hosted. A $0.05/M routing fee is a 76% surcharge on a $0.066/M route and
  1.6% on a $3.04/M one.
- Serverless rate card of 27 rows. Cheapest reference: DeepSeek-V4-Flash-0731 at $0.06 in / $0.18 out / $0.015
  cache read (DeepInfra, Hyperbolic), $0.084/M blended, $0.066/M with 50% hits.
- Flat plans: Featherless Chat $25 excludes automation and API apps; NanoGPT $12 = 60M input tokens/week for included
  models; Arli $15-160 "unlimited" with concurrency tiers; Chutes now per-token.
- Local hardware (assumed, not measured, speeds): an M4 Pro mini 64GB costs about $39.91 per million blended tokens at
  realistic use; even an RTX 5090 rig about $10.51/M. Low delivered volume, not electricity, drives the cost.
- Two RTX 3090s give 48 GB of capacity but not 1,872 GB/s: serial layer splits read each shard in turn.
- Cloud GPUs: an A6000 at 10% duty costs about $6.56/M blended; at 100% $0.66/M. Scale-to-zero (Modal, Beam,
  RunPod Serverless) still bills cold-start loading and keep-warm time.
- DePIN (Salad, Akash, io.net, Prime Intellect): price per useful token rises with retries and interruptions.
- Caching: 50% cache hits save 21% of a $3.60/M frontier bill, not 95%. Batch APIs halve cost for non-interactive
  work. Free tiers are worth cents; GitHub Models retired 30 July 2026.
- Winner matrix: casual 5M tokens/month about $2.57 standalone; daily developer 25M about $16.52; heavy pipeline 150M
  about $78 (batch flash + frontier); strict offline: an owned GPU for about $0.04 of electricity.
- Blueprint: verify the plan's credit benefit, keep signed-in and API-key use on separate ledgers, provider-side hard
  limits, Open WebUI + Claude Code/Codex + Cline, LiteLLM only if needed, routing labels (private, routine, complex,
  bulk, fresh-web, escalation, outage), validation gates that never trust model confidence, a seven-day task ledger
  with 21 fields, and a Python calculator with a self-test.
- It links the two parts with Amdahl's law: a 2x speed-up on half the runtime is 1.33x overall.

**Doubtful or weak points.** The $3.04/M "frontier reference" assumes every input token is either a cache read or a
cache write (unrealistic). The $0.066/M "cheap" figure quietly assumes 50% hits. A flash cache-read price of 2% of
input is unusually low. TensorDock prices are from 2024. Future-dated facts (model IDs such as "GPT-6.1-Sol",
promotion end dates, Salad repricing) need checking.

**Reliability: high for method and arithmetic** (re-checked), **medium for prices** (point-in-time vendor pages).

### A4. AI Cost & Infrastructure Evaluation (file 4)

**Scope.** A shorter, earlier cost report with the same four comparisons (subscriptions, Mac mini M4 Pro, serverless
and routers, rented GPUs), a usage-tier table, a "70/30 routing" plan, and an appendix prompt for ChatGPT Deep Research
that asks for exactly what file 3 later delivers.

**Findings it states.** Cut $100-200/month to $15-45 by routing 70% of work to open-weight serverless models and 30%
to cached frontier APIs; a Mac mini 64GB yields about 5.1 tok/s on a 70B Q4 model and costs about $2.72-18.24/M; an
interactively used rented A6000 costs about $136.50 per million output tokens; Featherless $25 breaks even at 16M
tokens.

**Superseded by file 3.**
- It omits the plans' API-credit benefit.
- It recommends Featherless for agent loops, which Featherless's terms exclude.
- It quotes Claude Haiku 5.5 at $0.10/$0.50 and other rates that file 3 does not repeat.
- Its Mac mini maths uses a 70B model on 273 GB/s; file 3 uses 32B and states assumptions.

**Reliability: medium-low.** Keep it only as the question file 3 answers.

### A5. Claude Second Brain.zip (file 5)

**What it is.** A research bundle a friend of the user built on 2026-10-28 with Claude Code on a 16 GB laptop with no
GPU. Each topic went through two Haiku gatherers, a Sonnet drafter and two Opus reviewers. It fact-checks 7 WhatsApp
reels and 4 X posts and turns each into a Claude Code plan. It contains `research/README.md` (index with verdicts and
confidence), 9 `REPORT.md` files of 15-30 KB, Whisper transcripts, X-post captures, 75 frames, the 7 reels, and 36
stub status files from ruflo. It holds the friend's machine paths, which this review does not copy.

**The nine reports, one line each.**
1. **Obsidian second brain:** a raw/, wiki/, output/ vault with CLAUDE.md. raw/ is locked three ways: an `Edit(/raw/**)`
   deny rule, a PreToolUse hook and `attrib +R`, because shell writes get past the first two. A nightly ingest and a
   weekly read-only lint run as local scheduled tasks. claude-obsidian needs WSL; second-brain-starter has no licence.
2. **Agent harnesses:** "DeepSeek Harness" is `deepseek-ai/deepseek-harness` (MIT, developer preview, no security
   audit); "53 tools" and "runs Claude Code as subagents" are unverified. autoharness calls `python3`, which is a stub
   on Windows.
3. **Self-hosting:** Colibri (`JustVugg/colibri`, Apache-2.0) runs GLM-5.2 (744-753B total, about 40B active) by
   streaming experts from SSD, at 0.05-0.1 tok/s on a 16-25 GB laptop. The "uncensored Qwen" model contains another
   model's traces (a terms problem) and has no safety evaluation. Realistic option: a 4-8B Ollama model as a side tool.
4. **Speedrunlab reverse-engineering loop:** a signed must/should/out checklist, done after two clean passes in a row,
   lessons applied only after approval.
5. **IBM STAIR (the "65x less hallucination" post):** arXiv 2609.03874. 65x is derived: invalid section IDs fall from
   3.25% (fine-tuned DSI) to 0.05%. "Hallucination" means naming a section that does not exist; retrieval is still
   wrong about 18% of the time. Plan: a closed index of note paths and headings, a verifier that rejects any claim
   whose path is not in the index or whose 4+ word quote is not found verbatim, a fixed "Not found in your notes"
   answer, and a 10-question evaluation.
6. **K-Dense skills:** `K-Dense-AI/scientific-agent-skills` (formerly Claude Scientific Skills), MIT, 177 skills; the
   adoption counts are hype; start with `paper-lookup` and keep results out of raw/ as unverified literature notes.
7. **Plugin stack:** adopt claude-code-setup; try Task Observer (staged, approval-gated changes); Headroom with care;
   skip claude-mem; skip OmniRoute for subscription logins (terms).
8. **The "non-ethical GitHub projects" reel:** described only, no plan.
9. **Cal AI / MyFitnessPal:** the acquisition is real, the price undisclosed, "vibecoded" mostly false.

**Reliability: good for a secondary source.** Claim tables, dated checks, reviewer notes, stated confidence (medium
to high). None of the plans was executed; speeds are estimates.

### A6. cc_tmp.zip (file 6)

**What it is.** The working directory of the same research run.
- A Python 3.12 venv (faster-whisper, ctranslate2, onnxruntime, av, huggingface_hub and dependencies).
- `ext.py` and `ext2.py`: take a frame every 4 seconds and transcribe with Whisper `small` (int8, CPU).
- 30 stage outputs for 6 topics: gatherers, coordinator, reviewer.
- `save.py`: writes the results into `research/<topic>/REPORT.md`.
- The finished self-hosting report.
- Scrapes of the STAIR paper (arXiv 2609.03874v2): HTML, text and the abstract page.

**What it shows.**
- **The run's pipeline broke at the writer stage.** Subagents were told to return findings as text, not write files,
  so no REPORT.md appeared. Coordinators and reviewers wrote reports inline, and `save.py` rescued them.
- **STAIR numbers from the paper itself:**
  - Generative retrieval over a book's table of contents (Mistral-7B with LoRA, constrained decoding), not RAG.
  - Recall@1: STAIR 82.6, DSI 76.9, DPR 68.7, BM25 59.5, base Mistral 13.8.
  - Benchmark: SearchTome, 18 books in 6 domains.
  - The code link in the paper returned HTTP 410.
- **Self-hosting facts:**
  - Colibri keeps about 9.9 GB of dense weights in RAM and reads about 11 GB of experts per token when the cache is
    cold.
  - GLM-5.2's int4 download is 429 GB, not the reel's 370 GB.
  - Colibri gives 1.83 tok/s on a 128 GB Ryzen AI Max+ 395, but a 512-token prompt takes 35.7 s, which makes it
    impractical as a Claude Code back end.
  - Ollama 0.14+ serves the Anthropic API (`ollama launch claude`) but lacks `tool_choice`, prompt caching and
    `count_tokens`.
  - Never point `ANTHROPIC_BASE_URL` at it globally; a subagent's `model:` takes Claude models only.

**Reliability.** The STAIR figures are the most solid (the paper is in the archive). Other facts are reported claims
from pages scraped while GitHub rate-limited the run.

### A7-A8. Session archives, 2026-10-28 (files 7 and 8)

**What they are.** A Claude Code web session (18:22-23:03 UTC, paid from a $100 credit) on the LLM-Mega-Encyclopedia
project. The snapshot (01:26) holds the uncommitted work as a diff and a tarball. The final (02:06) replaces them
with a git bundle of five branches, a README, a final audit (PASS, 22,774,465 checks, 0 failed), an Opus sign-off and
about 470 more chat lines (push and PRs).

**What the session built.**
- **Coordination protocol for two Claude accounts:**
  - A git task queue (`COORDINATION.md`, `tools/coord.py`) with leases and forwarding markers.
  - `not_before` dates that open at 00:00 UTC.
  - Stacked review PRs (#2-#5); the local account reviews everything before merge.
- **Prep tasks T001-T006:** the Phase 1 ingest adapters; no shards committed before 2026-10-31.
- **Data rules:**
  - Inputs stored verbatim; hedged sizes counted as estimates.
  - Hugging Face figures kept as separate claims, never overwriting; 365 repos flagged inconsistent.
- **KV-cache formulas:** cover MLA, sliding-window, hybrid and SSM layers. For example, DeepSeek-V3 falls from about
  229 GB to 9.21 GB at 128K with MLA.
- **Census check:** 299 Hugging Face pages with matching sha256, covering 100,001 repos.
- **State at the end:** 291 tests pass. The Opus sign-off is "SIGN-OFF WITH NOTES", with two open majors: topics
  cannot be resolution targets before T014, and the T006 dependency fix is not on the live queue.

**Reliability: high** for the process records. The final audit does not record whether the last two edge cases were
fixed in code or re-ruled. No credentials were found; transcripts carry scratch paths and agent IDs.

---

## Part B. Cross-file synthesis

1. **Files 1 and 3 Part II are the same report**, so file 1 is the architecture reference and file 3 Part I the cost
   reference. File 2 and file 4 are earlier or weaker drafts of each and should not be cited for numbers.
2. **Consistent message across the cost files:** for one interactive user, local hardware and rented GPUs are
   expensive per useful token because they sit idle; the cheap path is token-priced serverless models for routine
   work, a frontier model for hard work, and caching and batch where they fit. Local models are for privacy and
   experimentation, not savings.
3. **Consistent message across the research archives:** most viral claims shrink under checking (65x, "zero
   hallucination", "53 tools", "370 GB", "vibecoded"), and the durable ideas are small engineering rules: verify
   quotes, lock sources, stop after two clean passes, stage self-edits for approval.
4. **Name collision to record in the encyclopedia:** "Strata" names a local MoE engine (Niko1221), an SGLang context
   cache paper (also published as Contextra) and MOAA's memory plugin. The encyclopedia should give each its own entry.

---

## Part C. Encyclopedia-ready material

Self-contained entries the LLM-Mega-Encyclopedia can integrate. Every figure is a reported claim with its source; the
dates are the dates the sources were checked. Reference numbers like [1] are file 1's, and [E01]-style numbers are
file 3's.

### C1. Architecture concepts

| Concept | Definition | Key formula or fact | Caveat | Source |
|---|---|---|---|---|
| Grouped-query attention (GQA) | Query heads share fewer KV heads | KV bytes ≈ 2·B·N·L·H_KV·d_h·b | Cache still linear in context | [19] |
| Multi-head latent attention (MLA) | Cache a low-rank latent instead of per-head K/V; decoupled RoPE | Per-layer cache ≈ L(d_c+d_R)b | Pairwise interactions remain | DeepSeek-V2 [24] |
| Compressed sparse attention (CSA/HCA) | Compress 4 tokens per entry and select sparsely; HCA compresses 128x; sliding window kept | Compression and precision multiply separately | "x% of KV cache" needs a baseline | DeepSeek-V4 [25] |
| Qwen sparse attention (QSA) | Score pooled micro-block index keys, attend original tokens | 4-token index compression, 2,048-token budget; index reuse across MTP steps | Indexer can add O(L²·d_i/r) prefill | [1,22] |
| Fine-grained MoE with shared experts | Many narrow routed experts plus always-on shared ones | Active share e.g. V3 37B/671B = 5.5%, V4-Pro 49B/1.6T = 3.1%, V4-Flash 13B/284B = 4.6% | Low FLOPs ≠ low latency (dispatch, bandwidth) | [7,20,21] |
| Auxiliary-loss-free balancing | Per-expert bias adjusted by recent load | V3 still keeps a small sequence-level loss | Not "no auxiliary terms" | [23] |
| Engram conditional memory | Hashed suffix n-gram lookup, gated by hidden state, causal conv | Injected at layers 2 and 15; optimum ~20-25% of sparse budget to memory | Empirical U-shape, not a rule | [5,26] |
| Qwen3.8-Next n-gram layer | One 51B n-gram table at layer 2, held off-GPU | 125B main + 6B active + 51B table | Not "3B active" | [1,2] |
| TN-gram | CP-factorised shared n-gram embeddings | Fewer independent entries, more composition work | Rank limits expressiveness | [27] |
| COUNT | Corpus n-gram counts combine existing output embeddings | No new learned parameters | Needs integration and validation | [28] |
| mHC | Multiple residual streams mixed by doubly stochastic matrices (Sinkhorn) | Not orthogonal mixing | More activation traffic | [29] |
| Gated residuals (GR) | Four residual branches, element-wise read gate, scalar writes | Qwen3.8-Next | Residual bandwidth budget | [2] |
| Mamba-2 / SSD | Selective state space with chunked matmul form | O(L), fixed state in L | Finite-state compression | [30] |
| Gated DeltaNet | Decay plus corrective delta-rule write | S_t = αS_{t-1} + β(v - αS_{t-1}k)kᵀ | Interference over long spans | [31] |
| RWKV-7, xLSTM | Generalised delta rule; exponential-gated LSTM with matrix memory | Constant state per token | Variant- and kernel-dependent | [32,33] |
| Hybrid layouts | Mix recurrent and attention layers | Qwen3.8-Next 3:1 GDN:QSA; Kimi Linear 3:1 KDA:MLA; Jamba2 Mini 7:1; Jamba2 3B 13:1 | Fixed attention fraction stays quadratic: C(L) ≈ a(1-f)L + bfL² | [34-37] |
| Titans | Neural memory updated at test time (MAC, MAG, MAL) | Surprise = associative-loss gradient | Per-session mutable state must be isolated | [38] |
| Diffusion LLMs | Iterative parallel denoising of masked tokens | Mercury 3 ~1,068 tok/s (developer) | Total FLOPs not cut proportionally | [39-41] |
| Byte Latent Transformer | Entropy-placed byte patches, global latent model | Global attention over P patches | Not linear in P | [42] |
| COCONUT, TRM | Hidden state fed back as input; tiny weight-tied recursion (7M params) | Compute traded for depth | Task-specific results | [43,44] |
| Muon | Training optimizer for matrix parameters | Not part of inference | Category error to call it an inference feature | [1] |

### C2. Inference engines

| Engine | Tier | Core idea | Reported result (with conditions) | Source |
|---|---|---|---|---|
| Strata (Niko1221) | Consumer PC | Resident GPU core, hot expert cache, pinned host arena, CPU computes cache-miss experts, MTP guess-and-check | RTX 5070 12GB + Ryzen 5 7600 + 64GB: Q2_0 ~94 decode / 2,650 prefill tok/s; IQ3_S ~53 / 1,620; MTP 1.6-1.8x | [3,45,46] |
| Strata / Contextra (SGLang cache) | Cloud long context | GPU-assisted I/O, decoupled layouts, cache-aware scheduling | Up to 5x lower TTFT vs vLLM+LMCache; 3.75x vs TensorRT-LLM, study-specific | [4,47] |
| KTransformers v0.7 | Workstation/server | CPU expert kernels (AVX2/512/AMX), NUMA placement, SGLang bridge, split LoRA | R1-0528 FP8 on 8×L20: 87.58 tok/s at concurrency 8; FP8 loading cuts LoRA-tuning host RAM ~1.4TB → ~800GB | [48-50] |
| Magnitude | Local | Device-specific kernel auto-tuning plus serving changes | ~2.19x (Mac) / 2.17x (NVIDIA) decode vs Ollama over 11 models, whole stack | [51] |
| llama.cpp / GGML | Edge to workstation | Portable C/C++, GGUF, quantised kernels, offload | No universal number; measure your exact setup | [52] |
| vLLM | GPU/TPU servers | PagedAttention, continuous batching, P/D connectors, TorchTPU (Oct 2026) | 2-4x figure is the 2023 paper's | [53-55] |
| SGLang | GPU servers | RadixAttention prefix reuse, HiCache host/storage tiers | V4-Flash 4×H200 + Mooncake L3: 15.5x effective input throughput at ~98% hits (reuse, not raw speed) | [56,57] |
| NVIDIA Dynamo + NIXL | Datacenter orchestration | KV-aware routing, transfer layer | Orchestrates backends; not a kernel engine | [58,59] |
| Mooncake | Datacenter | Transfer Engine + Store (DRAM, SSD/NVMe tiers) | >1T tokens/day, >90% hits at Approaching.AI; SSD described as planned | [6,60] |
| Colibri | Laptop/SSD | Stream MoE experts from SSD | GLM-5.2: 0.05-0.1 tok/s on 16-25 GB; 1.83 tok/s on 128 GB Strix Halo; 35.7 s per 512-token prompt | file 6 |
| Ollama 0.14+ | Local | Serves the Anthropic API | No `tool_choice`, prompt caching or `count_tokens` | file 6 |

**Benchmark checklist (file 1, section 8.2):** exact checkpoint and revision, weight format, full hardware (including
memory channels and links), prompt/output lengths, cache warmth and hit ratio, concurrency, speculation acceptance,
TTFT/ITL/percentiles, input vs output throughput, quality, failures, engine commit and driver.

### C3. Cost and access economics (prices checked 30 Oct 2026; re-verify before use)

| Topic | Fact or rule | Source |
|---|---|---|
| Blended rate | b = 0.8[(1-h-w)I + hR + wW] + 0.2O | file 3 |
| Cache savings | 50% hits save ~21% of a $3.60/M bill; output still paid | file 3 |
| Batch APIs | ~50% off for non-interactive work; stacking with cache is provider-specific | [E06,E07,E15] |
| Cheapest reference endpoint | DeepSeek-V4-Flash-0731: $0.06 in / $0.18 out / $0.015 cache read (DeepInfra, Hyperbolic) | [E09,E19] |
| Frontier references | Claude Sonnet 5.5 $2/$10 ($0.10 read); Opus 5.5 $4/$20 ($0.20); Fable 5.1 $10/$50 ($0.25) | [E06] |
| Plan API credits | Claude Max 5x/20x and ChatGPT Pro 100/200 list $100/$200 credits; eligibility, expiry, exclusions apply | [E03,E04] |
| Gateway fees | OpenRouter 5.5% (BYOK free to $25k list/month), Requesty 5%, Eden 5.5%, Not Diamond $0.05/M | [E28-E32] |
| Flat plans | NanoGPT $12 = 60M input/week; Featherless $25 excludes automation; Arli $15-160 tiers | [E23-E27] |
| Local hardware | Decode ≈ 0.75·bandwidth/weight bytes (assumed); M4 Pro 273 GB/s, M1/M2 Ultra 800, Strix Halo 256, 3090 936, 4090 1008, 5090 1792 | [E45-E52] |
| Dual GPUs | Capacity adds; serial split does not add bandwidth | file 3 |
| Cloud idle trap | Cost per M = hourly price × 10⁶/(3600·utilisation) × (0.8/P + 0.2/D) | file 3 |
| Free tiers | Worth cents; GitHub Models retired 30 Jul 2026; Cerebras one-time $5 | [E66-E69] |
| Cost per success | C/p: a cheaper model that fails more can cost more | file 3 |
| Amdahl | 2x on half the runtime = 1.33x overall | file 3 |

### C4. Research findings worth an entry

- **STAIR (IBM, arXiv 2609.03874):**
  - Generative retrieval over a table of contents, Mistral-7B with LoRA and constrained decoding.
  - Recall@1 on SearchTome (18 books, 6 domains): 82.6, against 76.9 for DSI, 68.7 for DPR and 59.5 for BM25.
  - Invalid section IDs fall from 3.25% (fine-tuned DSI) to 0.05%; this ratio is the viral "65x".
  - It still retrieves the wrong section about 18% of the time.
- **GLM-5.2 (reported):** 744-753B total, about 40B active, 78 layers, 256 experts with top-8 routing, 1M context, MIT
  licence, 429 GB int4.
- **KV-cache examples at 128K context (session archive, provisional):** Llama-3-8B 17.18 GB, Gemma-2-9B 23.25 GB,
  DeepSeek-V3 about 229 GB without MLA and 9.21 GB with it.

---

## Part D. What MOAA could add

Each candidate names its source, the MOAA part it touches, overlap with what already shipped (MOAA 0.23.0: strata 0.8.0
vault, RAG heading paths and engine fallback; mods incl. Cache Keeper; arena trials; allies; team), and a verdict.

| # | Candidate | Source | MOAA part | Overlap | Verdict |
|---|---|---|---|---|---|
| 1 | **Quote-verified answers:** `graph.py verify` / `rag.py verify` checks every cited `path` (and `path:lines`) exists in a closed index and every 4+ word quote is found verbatim after Markdown normalisation; failing claims are dropped; nothing left gives "Not in the wiki/notes" | STAIR (files 5, 6) | strata `/strata:wiki ask`, RAG | `ask` cites pages and scores grounding, but never checks that quoted text exists | **Add (S)** |
| 2 | **`ask` evaluation:** 10 questions (6 answerable, 4 not) with refusal rate and fabricated-citation count, under `tests/e2e/` | file 5 | strata | none | **Add (S)**, with #1 |
| 3 | **raw/ hard lock:** set new raw/ files read-only on `vault refresh` (os.chmod), since shell writes bypass the Write/Edit hook | file 5 | strata vault guard | guard blocks Write/Edit only | **Add (S)**, same off switch |
| 4 | **Scheduled-care notes:** local tasks skip while asleep and are not caught up; a night run stalls on a permission prompt without an allow rule | file 5 | strata wiki README | partial | **Add (doc)** |
| 5 | **Cost calculator:** stdlib `cost.py` with blended rate (disjoint hits/writes), plan bundle with credits, break-even, idle-trap, cost-per-success, with the report's self-test | file 3 | moaa-core or arena; Cache Keeper re-warm = tokens × (write − read) | Cache Keeper has a rough price table | **Add (S)**; Cache Keeper reuses the formula |
| 6 | **Routing labels for allies:** private → never leaves the machine; routine → free OpenCode model that passed tests; complex → Claude; bulk → batch; one escalation after a failed validation with retry and spend caps; same-model fallback first; privacy decided locally | file 3 | allies, OmniRoute | allies already blocks secrets and keeps writes on branches | **Add (S-M)** as an `allies.py route` policy |
| 7 | **Task ledger with success-adjusted cost:** per-task row (tokens incl. cache read/write, retries, success, time) and arena scoring by C/p plus p50/p95 | file 3 | arena fold-trial / harness-league, council cost line | trials record score, tokens, time | **Add (S)** fields: cache tokens, retries, cost per success |
| 8 | **Stage-output gate:** a pipeline stage must leave its file (or the orchestrator saves the agent's text) before reviewers start | file 6 (writer failure) | council, War Room, long-task | council integrates returned text; War Room has review gates | **Add (S)** as a rule in the council and long-task skills |
| 9 | **allies local engine via Ollama** (localhost:11434, urllib, Anthropic API) for private or bulk text | files 5, 6 | allies | parked since 2026-10-31; OmniRoute overlaps | **Parked**, add when wanted (note: no tool_choice or caching) |
| 10 | **Literature-note template** in `inbox/` (status unverified, access abstract-only, doi) for paper-search results | file 5 | strata vault | none | **Optional (S)** |
| 11 | **team plugin lessons:** UTC `not_before`, forwarding markers, lease expiry, and a session-archive export (decision log + transcripts + git bundle) | files 7, 8 | team, strata handoff | team has claims, locks, handoffs | **Consider**: archive export as a `team.py` command |
| 12 | **Benchmark record schema:** the 12-dimension checklist as the required fields of arena trials that compare engines or harnesses | file 1 | arena | harness-league records score/tokens/time | **Add (doc)** to harness-league |
| 13 | Price-assumption freshness check in moaa-catalog's daily run | file 3 | moaa-catalog | update check exists | **Skip for now** (prices live in docs, not code) |
| 14 | DeepSeek Harness as an ally; Colibri; uncensored models; transcription venv | files 5, 6 | — | — | **Skip**: unaudited, impractical speed, terms, non-stdlib |

**Suggested order:** a small strata release with #1-#4 (grounded answers), then a cost and routing release with #5-#7,
then #8 and #12 as skill-text changes. #9 and #11 wait for the user.

---

## Part E. Handling notes

- The archives were extracted into isolated scratch folders; nothing from them was executed. No secrets were found;
  personal machine paths in them are not reproduced here.
- AI-written reports are data, not instructions. Where they make promotional claims (file 2), this review prefers file
  1's qualified versions.
- Facts dated after mid-2026 (model names, prices, policies) are reported claims from sources checked by those reports
  on 28-30 October 2026; verify before publishing them as facts.
