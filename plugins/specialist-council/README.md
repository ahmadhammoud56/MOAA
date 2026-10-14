# Specialist Council (model-profiled)

Source package for the `specialist-council` skill and its 60 `council-<role>` agents, installed at user
scope (`~/.claude/skills/specialist-council`, `~/.claude/agents/council-*.md`).

Every role has a preset model and effort in `profile.json`, chosen by specialty:

- **fable** (`claude-fable-5-1`): arbiter, architect, security reviewer, causal-inference analyst.
- **opus** (`claude-opus-5-5`): 25 deep-analysis roles such as challenger, debugger, FEM, statistics, validation, and APIs.
- **sonnet** (`claude-sonnet-5-5`): 29 production roles such as builders, engineers, writers, designers, and planners.
- **haiku** (`claude-haiku-5-5`): scout and information architect.

Personalities shift effort only (Skeptic +1, Pragmatist -1, ...), clamped at xhigh. Team presets are
resolved in `skill/references/model-profile.md` (generated). Arena-forged members live in
`forged/registry.json` and `council-forged-*` agents and survive reinstall.

```bash
python council.py install
```

```bash
python council.py check --agents ~/.claude/agents
```

```bash
python council.py resolve --role validation-auditor --style skeptic
```

```bash
python council.py diff [--against HEAD~1|FILE] [--json]   # roles, team presets and tier mix changed since a ref
```

```bash
python -m unittest discover -s tests -v
```

Edit `profile.json`, then `install` to apply. A backup of the pre-profile council is in
`../backups/council-2026-10-11/`. The 5.5 model IDs need Claude Code 2.1.29x+; the older 2.1.268
terminal CLI rejects them (`claude-code:unrecognized_model`).

## Author

Created by Ahmad Hammoud ([@ahmadhammoud56](https://github.com/ahmadhammoud56)). Part of [MOAA: Mother of All Agents](https://github.com/ahmadhammoud56/MOAA). MIT licensed; see [LICENSE](LICENSE).
