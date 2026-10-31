# Skill-usage counter, live (2026-11-01, Windows)

A headless `claude -p` session (Haiku, refiner off) in a throwaway folder was asked to invoke the Skill tool with
`moaa-catalog:moaa-help`. The PostToolUse hook appended
`{"ts": 1793480597.33, "skill": "moaa-catalog:moaa-help"}` to `~/.claude/moaa-catalog/skill-usage.jsonl`, and
`catalog.py usage --days 1` then counted it. The interactive session that built 0.5.0 started before the hook was
installed, so it recorded nothing: hooks load at session start.
