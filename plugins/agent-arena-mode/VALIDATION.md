# Validation record

Date: 2026-10-11. Plugin version 0.4.1. Host: Claude Code 2.1.268, Windows 11, Python 3.12.10.

## 1. Deterministic tests (synthetic, no model calls)

`python -m unittest discover -s tests` — **47 passed**. Fixtures are synthetic answers and
synthetic judge reports in temporary directories and databases.

| File | Covers |
|---|---|
| `test_arena.py` (18) | plans for all modes, seeded diversity, budgets/concurrency/deadline, idempotent finish, frozen task/rubric, NaN/inf/string/bool/out-of-range score rejection, duplicate JSON keys, gate evidence, stale hashes, eligibility ranking, odd pairing and bye rotation, Elo 1512/1488 and draws, duplicate-match protection, 7- and 100-entry knockouts (exactly N-1 matches), tie-break rule, fresh-validator identity, unverified gate cannot accept, atomic write, CLI round trip |
| `test_library.py` (14) | automatic sync on `assess`, champion replacement with history kept, load after run deletion with binary evidence, failed revalidation removes recommendation, provisional/validated/target-met/invalidated, validated outranks higher provisional, unrelated tasks separate, lineage and reuse IDs, rollback on integrity failure, tamper detection, parameterized search, parallel sync idempotent, sync failure + retry, `--no-library` |
| `test_modes.py` (14) | per-mode simulations: judge, tournament (revisions, bye, single survivor), swarm (private-draft barrier, bounded groups, halving min 2), league (Elo conservation, revisions start at 1500), evolution (elites unchanged, descendants with parents, immigrant, plateau stop, mandatory synthesis, regressed synthesis refused), synthesis, redteam (round limit), cascade (halving, proposals vs complete answers); `--quick`/patience/models, budget exhaustion, reuse seeding within N and rejection of unknown/invalidated IDs, 16 parallel CLI writers with no lost jobs, checkpoint |
| `test_package.py` (1) | ZIP has every required file and no databases, caches, locks, run data, or tool folders |

## 2. Runtime checks

- `claude plugin validate agent-arena-mode` — passed.
- `claude plugin validate .` (marketplace) — passed.
- `claude plugin marketplace add` + `claude plugin install agent-arena-mode@agent-arena-local --scope user` — installed, enabled.
- Discovery: all nine `agent-arena-mode:*` skills and agent `agent-arena-mode:agent-arena-judge` listed in a new session.

## 3. Live smoke tests (real Claude Code subagents, paid usage)

Each ran headless (`claude -p`) from a separate empty folder under `C:\aa_tmp\`, proving
the user-scope install works outside the plugin folder. All saved to the shared library at
`~/.claude/plugins/data/agent-arena-mode-agent-arena-local/library.sqlite3`.

| Test | Calls used / cap | Outcome |
|---|---|---|
| judge, 2 agents | 4 / 8 | 2 workers, bundled judge, fresh validator; accepted 97 |
| library list / show / load / history / sync (CLI and skill) | 0 | list grouped by cohort from another folder; load exported full bundle; history shows a0001→a0002 leader change; re-sync idempotent (2 entries, 3 assessments, 2 champion rows) |
| library use | 1 worker | **v1 failed**: coordinator answered itself, no export or worker. Skill fixed; **v2 passed**: export dir created, fresh worker runtime ID recorded, result verified |
| evolution, 4 agents, `--reuse` | 6 / 24 | reuse seeded slot 1; accepted 93, **but skipped mandatory synthesis after early target stop**. Fixed with helper guard + docs |
| evolution rerun, `--threshold 99` | 12 / 24 | gen0 (with reuse) → elite kept → 3 descendants (2 mutants with parents, 1 immigrant) → plateau/round-limit → synthesizer → fresh validation 94 vs elite 90.5 (no regression) → correctly **not accepted** (below 99) |
| tournament, 3 entrants | 14 / 16 | critiques, revisions as new immutable versions, bye, one survivor, fresh validation 93; **but** coordinator opened scored rounds before revisions froze, costing 2 procedural judge calls. Fixed with `pair --dry-run` |
| tournament rerun after fix | 14 / 16 | scored rounds opened only after revisions; 2 contested matches (N-1); exactly N + 5(N-1) + 1 = 14 calls; one survivor; fresh validation 86.5, accepted |
| swarm, 4 agents | 11 / 16 | private drafts, `exchange` file backend labeled "not live", revisions, cull to top 2, accepted 96 |
| league, 3 agents, 2 rounds | 8 / 14 | Elo verified by hand (1500 vs 1488 → +11.586), byes rotated, no rematch, accepted 97 |
| synthesis, 3 agents | 8 / 10 | 2 complete + 1 specialist → synthesis; validator found real bug; fixed and re-validated, accepted 92.5 |
| redteam, 2 builders + 2 critics | 6 / 14 | critics found zero defects (allowed), validator executed differential test, accepted 95 |
| cascade, 4 proposals | 9 / 16 | proposals scored with completion gates unverified, cut to 2, full answers built, accepted 91 |

Defects found by live tests and fixed in this version:

1. `library use` skipped export and worker → mandatory numbered steps in the skill.
2. Evolution skipped synthesis on early stop → `conclude --coverage-complete` now needs a finished `synthesizer` job (evolution/synthesis).
3. Synthesis coordinator patched an answer itself and left the specialist unassessed → orchestration forbids coordinator-authored revisions; specialists must be assessed.
4. Library champion preferred a higher provisional score over a validated entry → validated/target-met now rank first.
5. Swarm exchange path recorded as relative → now absolute.
6. A third-party hook created `.claude-flow/` inside the plugin → packager excludes hidden tool folders.
7. Tournament attack-phase pairing opened scored rounds early → `pair --dry-run` previews pairs without opening a round.

## 4. Not verified / limits

- Live runs used 2–4 agents. No 100-agent run was attempted (cost); scaling relies on the tested helper arithmetic (100-entry bracket, budgets).
- Actual model and effort used by subagents are not reported by the host; receipts record "requested, actual unverified". Per-call Agent `effort` needs Claude Code 2.1.292+; on 2.1.268 judge effort comes from the judge agent's frontmatter.
- Live direct messaging (SendMessage) was not exercised; swarm used the labeled file-exchange fallback. Agent teams are experimental and were not enabled.
- Fix 2 was verified live (evolution rerun ran after the guard was added). Fixes 3–4 were verified by deterministic tests and a re-sync of real data (the champion moved to the validated synthesis); synthesis mode was not re-run live.
- Some coordinator receipts said the model/effort was "actual" or "frontmatter-enforced"; the host does not report actual values, so treat these as requested-only.
- Live tests confirm the plugin runs end to end; they do not show that arenas beat a single strong model on quality.

## 5. Version 0.4.x: model assignment and council forge (2026-10-11)

Deterministic tests: **51 passed** (`python -m unittest discover -s tests`, five consecutive green runs; one earlier
unexplained single failure that did not reproduce, likely concurrent file edits during the run).

New coverage: exact and deterministic model mix for every difficulty (including N=100), cascade one step cheaper,
explicit overrides, per-job model/effort recording, reused agents keep their saved model, roster summary after reuse,
promotion refused for a single run, refused on inconsistent scores (spread > 10), successful forge (agent file,
knowledge base, registry, `council_members` row, idempotent), and automatic suspension after a later failed validation.

Live (Claude Code 2.1.295, the desktop runtime):

| Test | Result |
|---|---|
| Model ID check | `haiku`/`sonnet`/`opus` aliases resolve to `claude-*-5-5`; explicit 5.5 IDs and `claude-fable-5-1` work. The terminal CLI 2.1.268 rejects 5.5 IDs (`claude-code:unrecognized_model`) |
| Judge, 3 agents, `--reuse` | Coordinator classified difficulty `low`; roster sonnet-5.5/medium (reused), sonnet-5.5/low, haiku-5.5/medium; judge and validator opus-5.5/medium; host modelUsage shows sonnet-5.5, haiku-5.5, opus-5.5; reused agent won, fresh validation 95, accepted |
| Promotion on real data | `ag_8d5ad9a7...` eligible after that run (2 runs, scores 97 and 95); forged into an isolated project council home from a copy of the library |
| Forged member dispatch | `council-forged-independent-method-arithmetic-checker` loaded as a registered agent, ran on its validated model sonnet-5.5, read its knowledge base, answered correctly |

Not verified: effort values actually applied (the host reports models, not effort); fable workers at `critical` difficulty
were exercised in tests only; promotion into the user's global council was not performed (isolated home used).

## 0.4.2 (2026-10-11)

- Suspension now unregisters the forged agent card (moved to `forged/<slug>/agent.suspended.md`); promotion restores it.
- Promotion re-exports the knowledge base each time; lineage uses exact `profile.source_agents` match (`json_each`), not a payload substring scan.
- Model IDs come from the installed council `profile.json` when present (fallback `MODEL_IDS`).
- New end-to-end test: arena promotion into a fresh council install passes `council.py check`, and suspension leaves it passing with 0 active.
- Deterministic tests: **52 passed** on Claude Code 2.1.296, Windows 11, Python 3.12.10.
