# Agent Arena Mode — Claude Code plugin

Eight multi-agent competition modes plus a persistent SQLite library of reusable
best agents. Each mode is its own skill; the skill you invoke selects the mode.
Inspired by [arena-skill](https://github.com/Jakeschincariol/arena-skill)
(MIT, reviewed at commit `df07b8e5`; see [REPO-REVIEW.md](REPO-REVIEW.md)).

Requirements: Claude Code (verified on 2.1.268), Python 3.9+ on `PATH` as
`python`, `python3`, or `py -3`. Standard library only; no API keys or services.

## Install for all projects (user scope)

The plugin ships in the [MOAA](https://github.com/ahmadhammoud56/MOAA) marketplace
(`plugins/agent-arena-mode/` in that repo). The MOAA installer adds it for you, or:

```bash
claude plugin marketplace add ahmadhammoud56/MOAA
```

```bash
claude plugin install agent-arena-mode@moaa --scope user
```

User scope makes the skills and judge agent available in every project. Check with
`claude plugin list`, then `/agents` inside a session. After editing plugin files in a
clone, run `claude plugin update agent-arena-mode@moaa` (or `/reload-plugins`).
To try it for one session without installing, from a MOAA clone:

```bash
claude --plugin-dir plugins/agent-arena-mode
```

The installed copy lives in Claude Code's plugin cache. Scripts are run through
`${CLAUDE_PLUGIN_ROOT}`, so nothing depends on where the source folder sits.

## Mode commands

```text
/agent-arena-mode:judge      --agents 100 -- Solve this task.
/agent-arena-mode:tournament --agents 16 -- Stress-test competing solutions.
/agent-arena-mode:swarm      --agents 12 --rounds 3 -- Investigate collaboratively.
/agent-arena-mode:league     --agents 16 --rounds 5 -- Compare frozen solutions with Elo.
/agent-arena-mode:evolution  --agents 24 --rounds 4 --threshold 90 -- Improve this algorithm against the supplied benchmarks.
/agent-arena-mode:synthesis  --agents 12 -- Combine the strongest compatible ideas.
/agent-arena-mode:redteam    --agents 12 -- Find failures in and repair this design.
/agent-arena-mode:cascade    --agents 100 -- Explore many proposals, develop the best.
```

| Option | Default |
|---|---|
| `--agents N` / `--quick` | 100 initial participants / 8 (conflict rejected) |
| `--concurrency N` | 8 simultaneous workers (never reduces total participants) |
| `--rounds N` | 3; league 5; tournament runs to one survivor |
| `--threshold S` | 85/100 plus every mandatory check passing |
| `--patience N` | stop after 2 complete rounds without a 1-point gain |
| `--max-calls N` / `--max-minutes N` | mode estimate + 10% / 60-minute dispatch window |
| `--difficulty LEVEL` | coordinator classifies `low/medium/high/critical`; drives automatic model and effort per slot and role |
| `--worker-model`, `--worker-effort`, `--judge-model`, `--judge-effort` | automatic by difficulty; explicit values win (requested vs actual recorded) |
| `--seed N`, `--communication TYPE` | 42, `auto` |
| `--resume RUN`, `--reuse IDS`, `--database PATH`, `--context-key KEY`, `--no-library` | see [orchestration](references/orchestration.md) |

“100 agents” means 100 initial participants, not 100 simultaneous workers or 100
calls. Judges, critics, revisions, descendants, and validators consume calls too;
the run announces its call allowance before dispatch. A tournament of N entrants
costs about N + 5(N−1) calls before final validation.

## Automatic model and effort assignment

Before dispatch, the coordinator classifies the task difficulty and `init` assigns every slot and role
a pinned model and effort. Mixed worker tiers add method diversity at bounded cost.

| Difficulty | Workers | Critic | Judge / validator | Synthesizer |
|---|---|---|---|---|
| low | 50% haiku-5.5/medium, 50% sonnet-5.5/low | sonnet/medium | opus-5.5/medium | opus/high |
| medium | 75% sonnet-5.5/medium, 25% haiku-5.5/medium | sonnet/high | opus-5.5/high | opus/high |
| high | 60% sonnet-5.5/high, 40% opus-5.5/high | opus/high | fable-5.1/high | fable/high |
| critical | 60% opus/high, 20% fable/high, 20% sonnet/high | opus/xhigh | fable-5.1/xhigh | fable/xhigh |

Cascade proposals run one difficulty step cheaper; finalists use the top worker tier. Reused agents keep
the model they were validated with. Model IDs: `claude-haiku-5-5`, `claude-sonnet-5-5`,
`claude-opus-5-5`, `claude-fable-5-1` (needs a Claude Code build that knows them; 2.1.295 does, 2.1.268 does not).

## Library: save and reuse the best agents

Every assessment automatically syncs qualifying candidates into the library.

```text
/agent-arena-mode:library list
/agent-arena-mode:library list --query parser --validated
/agent-arena-mode:library show AGENT_ID
/agent-arena-mode:library load AGENT_ID
/agent-arena-mode:library use AGENT_ID -- Solve this new task.
/agent-arena-mode:library history --cohort COHORT_ID
/agent-arena-mode:library sync --run RUN_PATH
/agent-arena-mode:library promote AGENT_ID
/agent-arena-mode:library council
/agent-arena-mode:evolution --agents 24 --reuse AGENT_ID -- Improve this saved approach.
```

States: `provisional`, `validated` (fresh independent validator), `target-met`,
`invalidated` (later failed validation; kept for history, hidden from
recommendations, refused for reuse). Rankings stay inside one task/rubric/context
group. Reused agents fill slots within N and are evaluated fresh.

### Forge council members from the arena

`promote` turns a proven saved agent into a Specialist Council member (`council-forged-<slug>`), with
its validated model and effort, a knowledge base (answer, evidence, profile, assessment history), a
council registry entry, and a `council_members` database row. Requirements: fresh-validated, validated in
at least 2 independent runs (itself plus `--reuse` descendants), every validated score at least 85, spread at most 10,
and no invalidation in its lineage. A later failed validation suspends the member automatically.
Typical path: win an arena, seed a second arena with `--reuse ID`, then `promote ID`.

### Where data lives, backup, uninstall

- Default: `~/.claude/plugins/data/agent-arena-mode-moaa/library.sqlite3`
  (the plugin data directory). Kept across plugin updates.
- **Uninstall deletes it by default.** Use
  `claude plugin uninstall agent-arena-mode@moaa --keep-data`, or
  pass `--database PATH` to keep the library elsewhere (also shares it explicitly).
- Back up by copying the `.sqlite3` file (plus `-wal`/`-shm` if present) while no
  arena is running, or `sqlite3 library.sqlite3 ".backup backup.sqlite3"`.
- Each run's ledger lives in the project under `.agent-arena/<run>/`.
- If library sync fails, the assessment is still saved; retry with
  `/agent-arena-mode:library sync --run RUN_PATH` (no new model call).

## What enforces what

`scripts/arena.py` (deterministic ledger): budgets, concurrency, deadline, frozen
task/rubric hashes, strict score/gate validation (rejects NaN, infinity, strings,
booleans, duplicate keys, missing gates, stale hashes), pairing/byes/Elo, culling,
plateau detection, swarm sharing barrier, fresh-validator identity, regressed
synthesis guard, per-run lock, checkpoint. `scripts/library.py`: SQLite storage,
checksums, export, history. Claude (the coordinator, following the skills) spawns
real agents, writes briefs, judges evidence, and decides mode transitions.

## Develop

```bash
python -m unittest discover -s tests -v
```

```bash
claude plugin validate .
```

```bash
python scripts/package.py ../agent-arena-mode.zip
```

See [VALIDATION.md](VALIDATION.md) for what was tested live versus synthetically.
