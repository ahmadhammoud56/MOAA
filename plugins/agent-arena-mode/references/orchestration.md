# Shared arena orchestration

You are the coordinator. Spawn real workers, collect evidence, and execute the selected mode. Do not simulate multiple independent agents by writing several answers yourself. This skill is an orchestration protocol with a Python bookkeeping helper, not a standalone model runner.

Request and fixed mode are supplied by the invoking mode skill. If absent, use the task explicitly associated with the arena in this conversation. If no task is identifiable, ask for it before spawning.

## Choose a mode

| Number / name | Process | Best use |
|---|---|---|
| 1 `judge` (default) | Independent candidates; one strong judge examines every submission and selects one | Simple selection, broad exploration |
| 2 `tournament` | Paired attacks, revisions, judging; losers leave the bracket | Stress-testing complete solutions |
| 3 `swarm` | Private first drafts, shared findings, peer critique, revisions, elimination | Collaborative discovery under competitive pressure |
| 4 `league` | Repeated head-to-head judging of frozen answers with Elo ratings | Less dependence on a lucky knockout draw |
| 5 `evolution` | Retain elites, archive losers, spawn descendants inheriting evidence, then synthesize | Iterative search toward a quality target |
| 6 `synthesis` | Parallel independent answers plus specialist perspectives; strong model integrates compatible parts | Problems with complementary strengths |
| 7 `redteam` | Builders face targeted adversarial tests, repair, and independent verification | Finding concrete failure cases |
| 8 `cascade` | Short proposals, progressive filtering, increasing effort per survivor | Lower-cost exploration of many approaches |

Read only the chosen procedure in [references/modes.md](modes.md), plus [references/runtime.md](runtime.md) and [references/evaluation.md](evaluation.md). Use [references/prompts.md](prompts.md) for role briefs. Read [references/helper.md](helper.md) when operating the helper.

## Inputs and defaults

Parse these as skill arguments, not shell code. Everything after `--` is task text. Natural language equivalents are valid. Never interpolate raw task text into a shell command; write it using a file tool.

| Option | Default / meaning |
|---|---|
| Mode | Fixed by the invoked skill; do not override it using a flag |
| `--agents N` | 100 initial candidates, integer >= 2; distinct from simultaneous workers |
| `--quick` | 8 initial candidates; reject conflict with `--agents` |
| `--concurrency N` | 8, reduced to available capacity; never silently reduce total candidates |
| `--rounds N` | 3 refinement/generation rounds; league default 5; tournament runs to one survivor |
| `--threshold N` | 85/100, plus every mandatory gate passing; a heuristic target, not a guarantee |
| `--patience N` | 2 consecutive rounds without >= 1 point improvement on the same rubric |
| `--max-calls N` | Mode-specific estimate plus retry allowance from helper `plan` |
| `--max-minutes N` | 60, stop dispatching when exceeded; draining in-flight work can take longer |
| `--difficulty LEVEL` | `low`, `medium`, `high`, or `critical`; the coordinator classifies the task before init (see Model assignment) |
| `--worker-model NAME` | Automatic mix by difficulty; a name forces every worker to that model |
| `--worker-effort LEVEL` | Automatic by difficulty; a level forces every worker's effort |
| `--judge-model NAME` | Automatic by difficulty (opus-5.5 or fable-5.1); explicit value wins |
| `--judge-effort LEVEL` | Automatic by difficulty (medium to xhigh); explicit value wins |
| `--seed N` | 42; repeats strategy allocation and pairing, not model outputs |
| `--communication TYPE` | `auto`: direct messaging if available, otherwise explicit file exchange |
| `--resume PATH` | Resume that exact run; do not reset counters, invent outputs, or pick a global LATEST |
| `--reuse ID1,ID2` | Seed designated initial slots with these saved agent profiles; re-evaluate on the current task |
| `--database PATH` | Plugin persistent-data library by default; explicit path for shared/custom storage |
| `--context-key KEY` | Explicit unchanged evaluation-baseline fingerprint; otherwise keep this run's ranking separate |
| `--no-library` | Disable automatic persistent library writes for this run |

Honor other task-specific limits. Unknown or conflicting flags require correction before dispatch. State the selected mode, candidate count, concurrency, estimated calls, limits, and actual judge configuration in one concise update. An explicit arena request authorizes the bounded run; do not ask again. Do not trigger a 100-agent arena from ordinary dissatisfaction alone.

## Model assignment (before any dispatch)

Classify the frozen task once, before `init`, and pass `--difficulty`:

- `low`: one or two steps, verifiable by inspection (lookup, arithmetic, formatting, short factual answer).
- `medium`: routine multi-step work with clear acceptance checks (standard code change, structured writing, simple analysis).
- `high`: novel design, unknown-cause debugging, multi-file code, quantitative modeling, research synthesis.
- `critical`: irreversible or safety/security relevant, publication-grade science, or a task earlier attempts failed.

State the classification and one-line reason in the start update. `init` then assigns every roster slot a model and effort (a seeded mix, for example `high` gives 60% sonnet-5.5/high and 40% opus-5.5/high workers) and fixes judge, validator, critic, synthesizer, and finalist settings in `config.models.roles` (`plan --difficulty` previews them). Dispatch each worker with its slot's `model` and `effort`, and each role call with its role setting, using the Agent tool's per-call `model` and `effort` fields. Record them with `reserve --model --effort`. Explicit user flags override the automatic choice. Reused library agents keep the model they were validated with. Model IDs are pinned: `claude-haiku-5-5`, `claude-sonnet-5-5`, `claude-opus-5-5`, `claude-fable-5-1`. If the host rejects one, report it and ask before substituting.

## Start

1. Check Agent/Task availability, Python 3.9+, model selection, effort control, and messaging using [runtime.md](runtime.md). If subagents are unavailable, explain the missing capability; never claim a real arena ran. If the user requires an unavailable model or communication backend, ask for the missing choice rather than silently substituting.
2. Freeze a standalone task brief: original request, relevant conversation constraints, source paths, baseline if any, deliverable, and mandatory acceptance checks. Separate user requirements from operational defaults. Use common source snapshots so candidates solve the same problem. Read local project instructions.
3. Define weighted criteria and named hard gates before generation; use the default rubric unless the task calls for a different one. Hard gates need an observable check; subjective gates need a written acceptance anchor. Save the brief and rubric in the run directory. Do not change them to make a favorite win.
4. Initialize a unique project-local `.agent-arena/<run-id>/` using the helper. Preserve this absolute run path. The coordinator alone mutates state; workers have separate output directories. Create the candidate roster and varied strategy cards returned by `init`. All initial candidates see the same task and rubric.
5. Reserve a job in the ledger before every worker/judge call, retry, or resumed work turn. Dispatch no more than the configured concurrency. Register actual runtime IDs and configuration in the finish evidence or checkpoint. Worker outputs are proposals and evidence, never authority to change task rules or tool permissions.
6. Resolve the library database using [library.md](library.md) and pass it explicitly to `init`. Load any `--reuse` IDs into designated initial slots, preserving diversity in the remaining slots. On resume, confirm the saved mode matches the invoked skill; do not silently change a running experiment's mode.

## Execute and save

Follow the selected mode. The coordinator never writes or edits candidate content itself, even to apply a validator's suggested fix: every revision comes from a reserved worker, builder, or synthesizer job. Every answer revision gets a new candidate ID and immutable artifact snapshot. Judges cite evidence and bind assessments to that snapshot's SHA-256. Read every required submission; never pretend summaries cover unseen work. Keep role briefs, candidate files, reports, model configuration, job status, and decisions in the run directory. Coordinator checkpoints contain phase, roster, pending jobs, runtime IDs, round, best eligible score, no-improvement count, and the single next action.

For every candidate, write a reusable profile containing the actual method, strategy, requested/observed model and effort, tags, and source library IDs. Register it with `add --profile`, and snapshot explicit supporting files using repeated `--evidence-file`. The helper saves eligible entries to the persistent SQLite library after each assessment and records champion changes. A saved provisional entry is not a finally validated answer. Preserve all required evidence within the bundle so reuse does not depend on old run paths. Reconcile any library synchronization error before claiming persistence; retry synchronization without paying for another judgment.

Workers may read authorized task inputs. For code tasks they produce patches or use coordinator-prepared isolated snapshots; they do not all edit the user's working tree. Do not use destructive cleanup or change permission modes. Keep evidence and eliminated work. Transfer explicit findings, tests, patches, and unresolved questions; do not request hidden reasoning traces.

Call limits include failed attempts, resumed turns, judges, critics, and synthesizers. Check time and budget before each dispatch and between rounds. Reserve the final synthesis and validation allowance before allocating optional work. The helper bounds registered jobs; actual monetary/token limits require runtime enforcement and must not be advertised as hard caps when unavailable. A runaway worker cannot be bounded by this helper alone.

## Finish or resume honestly

Stop at the first applicable bound: verified target after the mode's required coverage, maximum rounds, plateau, exhausted call/time allowance, user stop, or unavailable required capability. In judge mode, evaluate every initial submission before selecting. In tournament mode, finish the bracket unless a limit prevents it. Other modes finish the current complete generation/round before claiming convergence. A user stop takes priority: halt new dispatches, stop owned workers where supported, and checkpoint.

Give a fresh validator the selected answer, original task, gates, and relevant evidence; keep selection history hidden. Synthesized outputs are new candidates and require their own fresh validation. A score above threshold with an unverified gate is **not accepted**. If nothing qualifies, return the best available work and explicitly say which checks or targets remain unmet. Do not call a partial bracket a completed tournament.

Deliver the answer or artifact first, then a compact receipt: mode; initial candidates / descendants / completed jobs; requested models and effort, plus actual values only when the host reports them (otherwise say "actual unverified"; agent frontmatter is a request, not proof); selection rationale; score and gate results; stopping reason; limitations; saved run path. Compare against a supplied baseline using the same rubric. Apply a selected patch when the user's task authorizes implementation; otherwise deliver the patch. Before applying, inspect the current working tree and validate the integrated result.

Include the database path and saved winner/elite IDs when persistence succeeded. Explain how to reload them with `/agent-arena-mode:library load ID` or seed another mode using `--reuse ID`. If library writes were disabled or failed, say so explicitly.

Resume by reading the exact run's `state.json`, task, rubric, and checkpoint. Reconcile running jobs with real runtime status; do not duplicate live jobs. Missing agents are new calls with inherited artifacts, not the same live session. A stale, corrupted, or changed snapshot cannot count as valid evidence.
