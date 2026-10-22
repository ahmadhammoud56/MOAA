# Specialist Council vs a single agent

Does a council of specialist subagents answer better than one model on its own? This benchmark checks that on tasks
with fixed answer keys, and records what each answer cost.

**Result (2026-10-22): no.** On all five tasks, Sonnet alone and Opus alone scored 100% in every run. The council
was never more accurate, cost 2.5 to 6 times as much and took 3.5 to 7 times as long. One council run lost its answer
to a formatting failure (see below). The council skill now answers small checkable tasks with a single worker
(Specialist Council 1.6.1).

## Method

- **Arms:**
  - `solo-sonnet`: Claude Sonnet 5.5 on its own.
  - `solo-opus`: Claude Opus 5.5 on its own. This is the control for "is it just the bigger model?".
  - `council`: Sonnet 5.5 as coordinator, told to dispatch at least two specialists from the Specialist Council
    (1.6.0) and cross-check them. Workers run on their role presets: Opus or Sonnet, see MODELS.md.
- **Isolation:**
  - Each run is a fresh headless `claude -p` session (Claude Code 2.1.302) in an empty folder, with only project
    settings, so no user plugins, hooks or output styles take part.
  - The council arm adds only the specialist-council plugin (`--plugin-dir`).
  - No arm may run shell commands, write files or use the web. Answers come from reasoning and review, not from
    running the code.
- **Scoring is deterministic:**
  - Every answer ends with a JSON block, and `bench.py` checks it against the key in `cases/`.
  - Review tasks score the share of planted bugs found. A bug counts when any line it spans is reported. Lines that
    are not bugs are counted as false positives.
  - Claims and answer tasks score the share answered correctly. Answers are compared by value, so `14.7` equals
    `147/10`.
  - An answer without a parsable JSON block scores 0.
- **Answer keys are verified by execution.** Every planted bug was reproduced and every decoy checked as correct by
  running the code, and every math answer was computed: `python verify_keys.py`.
- **Cost** is Claude Code's `total_cost_usd`: the API-equivalent price including subagents. These runs used a
  claude.ai subscription, so no money was spent per run. **Time** is wall-clock per run, because `duration_ms` leaves
  out subagent work.

## Tasks

| Round | Case | What it is |
|---|---|---|
| 1 | `review-utils` | 35-line module, 5 planted bugs, 1 neutral line |
| 1 | `review-hard` | 65-line module, 8 subtle bugs (shared class state, default evaluated once, late-binding closure, unanchored regex, binary search bound, mutating while iterating, float money, shallow copy) and 4 correct decoys |
| 1 | `claims` | 10 statistical claims, 5 wrong (relative vs absolute risk, overlapping confidence intervals, percent change, p-value meaning, standard error scaling) |
| 1 | `math-traps` | 10 questions with common traps, answered without tools |
| 2 | `review-large` | 109-line orders module, 12 subtle bugs and 5 correct decoys |

Round 1 saturated: every arm scored 100%. Round 2 was designed afterwards to test the council's strongest case, high
recall on a long review. It was fixed and verified before it ran, and both rounds are reported in full.

## Results

3 runs per case per arm, 45 runs in total.

| | Sonnet alone | Opus alone | Council |
|---|---|---|---|
| Round 1 score (4 cases, 12 runs per arm) | 100% | 100% | 100% |
| Round 2 score (`review-large`, 3 runs per arm) | 100% | 100% | 67% |
| False-positive bug reports (all review runs) | 0 | 0 | 0 |
| Mean cost per run, round 1 | $0.06 | $0.12 | $0.33 |
| Mean cost per run, round 2 | $0.07 | $0.14 | $0.35 |
| Mean wall time per run, round 1 | 11 s | 17 s | 79 s |
| Mean wall time per run, round 2 | 14 s | 22 s | 77 s |
| Total cost, 15 runs | $0.87 | $1.85 | $5.05 |

All 15 council runs used worker models beyond the coordinator, so the council really dispatched specialists.

**The council's one failure:** in `review-large` run 2, the coordinator gave its full answer, then a late worker
report arrived and its final message only said that "the final answer and JSON block above stand". Headless runs keep
only the last message, so the answer was lost and scored 0. The text of that run says both workers and the
coordinator agreed on all 12 bugs, but that can't be checked from the saved output, so the score stays 0.
Specialist Council 1.6.1 now waits for every worker and restates the full answer after a late report.

## What this does and doesn't show

- On short tasks with checkable answers, a single current model is already at the ceiling. A council adds cost and
  time and no accuracy. That is why the council now triages: small checkable tasks get one worker or none.
- It does **not** test what the council was built for: long, ambiguous or multi-part work where specialists bring
  different methods and can disagree. Those tasks have no fixed answer key and need graded or human evaluation. That
  is the next benchmark.
- Small sample: 3 runs per cell and 5 tasks. A 100% ceiling cannot show differences in either direction.

## Reproduce

```bash
python bench.py run --runs 3 --out results/my-run   # needs a logged-in Claude Code CLI (claude auth status)
python bench.py score --out results/my-run
python -m unittest test_bench
```

Raw results: `results/2026-10-22/` (round 1) and `results/2026-10-22-round2/` (round 2). Each run file holds the
prompt, the full answer, tokens per model, cost and timestamps. `scores.json` and `summary.md` hold the scores.
