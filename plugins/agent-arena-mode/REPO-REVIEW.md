# Review of arena-skill

Reviewed 2026-10-07 and re-checked 2026-10-11 at commit `df07b8e518e10cdecd8cd7712d9958b6f396250e` (still the upstream HEAD on 2026-10-11). License: MIT, Copyright (c) 2026 Jake Schincariol; attribution kept in this plugin's LICENSE. Scope: README, orchestration instructions, rubric, bracket implementation, strategy data structure, and test suite. All 27 upstream tests passed locally. This was a source/mechanics review; no paid 100-agent run was performed.

## How the competition works

The original creates N independent initial answers with different reasoning/workflow/strategy cards. Each knockout match then uses two attack calls, two revision/defense calls, and one judge call. Competitor identities persist through saved files; each stage can use a fresh subagent rather than a continuously living contestant. Thus 100 entries produce 100 + 5 x 99 = 595 calls, before an optional baseline comparison. They run in waves rather than necessarily all at once. [Source instructions](https://github.com/Jakeschincariol/arena-skill/blob/df07b8e518e10cdecd8cd7712d9958b6f396250e/skills/arena/SKILL.md)

The judge scores correctness (30%), completeness (25%), specificity (15%), robustness (20%), and clarity (10%). A verified fatal flaw should lose to a nonfatal solution. Scores and tie-breaks determine the survivor. This selects a relative winner; it does not establish an absolute quality target or guarantee correctness. [Rubric](https://github.com/Jakeschincariol/arena-skill/blob/df07b8e518e10cdecd8cd7712d9958b6f396250e/skills/arena/rubric.md)

The strongest reusable ideas are strategy diversity, concrete adversarial criticism, revision before judging, and a disk-backed state machine that survives context loss. The test suite covers bracket shapes, deterministic dealing, verdict handling, and a fake-agent pipeline. [Tests](https://github.com/Jakeschincariol/arena-skill/blob/df07b8e518e10cdecd8cd7712d9958b6f396250e/tests/test_bracket.py)

## Findings that affect reliability

1. **Incomplete scoring can bypass the fatal rule.** `decide()` returns the named winner when either score set is incomplete, before it compares fatal flags. Reproduced with candidate A marked fatal and missing score fields, candidate B complete and nonfatal, and the judge naming A: the function returned A. This is an explicit fallback, but it weakens the stated fatal-flaw guarantee. `agent-arena` requires complete reports.
2. **Nonfinite scores are not rejected.** `weighted_total()` converts values to float and clamps them. A local probe using NaN for all five scores returned 100.0. A malformed model output can therefore look perfect. The replacement rejects NaN, infinity, strings, booleans, and out-of-range values.
3. **Winning is not a stopping-quality certificate.** The bracket ends with one entry even if all candidates are poor. There is no general absolute acceptance gate, evolving population, inherited-finding cycle, Elo season, or specialist integration. These are extensions to the original design, not proof its basic tournament is broken.

The first two findings are in the reviewed [bracket implementation](https://github.com/Jakeschincariol/arena-skill/blob/df07b8e518e10cdecd8cd7712d9958b6f396250e/skills/arena/bracket.py#L443). They coexist with a passing test suite because those particular inputs are not covered there. Re-check 2026-10-11 (`python -I`, upstream not installed or executed beyond `bracket.py` import): `weighted_total` of all-NaN scores returned `100.0`; `decide` with candidate A fatal and incomplete, B complete and nonfatal, judge naming A, returned A with note "scores incomplete, used the judge's pick". Both findings remain. This plugin's tests cover the corresponding rejections (`test_invalid_scores_are_rejected_not_clamped`, `test_assessments_require_all_gates_evidence_and_current_hash`). This review does not modify the upstream repository.

## Design choices in agent-arena

- Separate initial population, concurrent capacity, total model work turns, and completed answers.
- Use strict assessments, explicit hard gates, candidate hashes, and independent final validation.
- Keep tournament and Elo league separate: knockout is cheaper in rounds but more sensitive to pairings; repeated league matches offer more comparisons at added cost.
- Freeze answers during an Elo season. Changing an answer while retaining its rating makes the rating ambiguous.
- Preserve independent first drafts in collaborative mode, then exchange evidence with bounded communication.
- Make elimination retire a run participant; preserve artifacts and useful failures for descendants.
- Treat inherited “database” as explicit saved findings, tests, artifacts, and lineage, not model-weight learning.
- Synthesize compatible strengths and revalidate the combined artifact; individually good pieces can conflict when assembled.
- Stop on a quality target, plateau, round limit, call/time bound, or user stop. Report which one actually happened.

The design can improve exploration and inspectability; its quality advantage over a single strong model remains an empirical question. A useful benchmark would compare the same tasks under equal token or monetary budgets, blinded evaluation, repeated seeds, and held-out acceptance cases. More agents alone is not evidence of better results.
