# Specialist Council

60 role agents for Claude Code, each with its own model and effort level. The `specialist-council` skill picks two or
three roles for a task, runs them in parallel (split, ensemble or hybrid), cross-checks what they return and delivers
one verified result.

## Install

```
/plugin marketplace add ahmadhammoud56/MOAA
/plugin install specialist-council@moaa
```

Or `/plugin install moaa-core@moaa` to get the council together with the Agent Arena, which forges proven agents into
new council members.

## Use

```
/specialist-council:specialist-council  Is 221 prime? Factor it.
```

Or ask for "a council" or "a specialist team" in plain words. The agents are named
`specialist-council:council-<role>`.

**Spawn rule.** Before spawning workers the council names which condition makes a subagent worth its cost: context
bloat, real parallelism, or tool and instruction conflicts (after Anthropic's guidance on when to fold subagents into
the main loop). If none applies, it does the work in the main loop with the role card as a brief. Workers return a
short Result / Evidence / Open questions block. `python council.py spawn-rule --set off` (or
`MOAA_COUNCIL_SPAWN_RULE=off`) turns the rule off; `spawn-rule` alone prints its state.

**Long tasks.** `/specialist-council:long-task` keeps a brief, progress and evidence files so work survives resets.
Its `reconstruction` preset, for rebuilding software from observed behaviour, starts with a recorded authorisation
step, keeps a behaviour checklist, verifies with REA's `verify_reconstruction` when available, and is done when every
must-have passes in two runs in a row.

## Roles and models

Every role has a preset model and effort in `profile.json`, chosen by specialty
([MODELS.md](https://github.com/ahmadhammoud56/MOAA/blob/main/MODELS.md) lists all 60):

- **fable** (`claude-fable-5-1`): arbiter, architect, security reviewer, causal-inference analyst.
- **opus** (`claude-opus-5-5`): 25 deep-analysis roles such as challenger, debugger, FEM, statistics, validation, and APIs.
- **sonnet** (`claude-sonnet-5-5`): 29 production roles such as builders, engineers, writers, designers, and planners.
- **haiku** (`claude-haiku-5-5`): scout and information architect.

Personalities shift effort only (Skeptic +1, Pragmatist −1, …), clamped at xhigh. Arena-forged members live in
`~/.claude/specialist-council/forged/` and `~/.claude/agents/council-forged-*.md`, outside the plugin, so updates never
touch them.

## What it costs

A `SubagentStop` hook records every finished worker's tokens in `~/.claude/specialist-council/ledger.jsonl`, and the
council ends each answer with one cost line. To see it yourself:

```bash
python council.py cost              # the latest session
python council.py cost --days 7     # every session of the last week
```

## Commands

```bash
python council.py check                          # the 60 agents match profile.json, plus every forged member
python council.py resolve --role validation-auditor --style skeptic
python council.py diff [--against REF|FILE]      # roles, team presets and tier mix changed since a ref
python -m unittest discover -s tests             # tests
claude plugin eval . --allow-tools Agent         # eval suite: with and without the council (needs an API key)
```

The 5.5 model IDs need Claude Code 2.1.296 or newer.

## Author

Created by Ahmad Hammoud ([@ahmadhammoud56](https://github.com/ahmadhammoud56)). Part of
[MOAA: Mother of All Agents](https://github.com/ahmadhammoud56/MOAA). MIT licensed; see [LICENSE](LICENSE).
