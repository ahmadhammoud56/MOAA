# Live end-to-end evidence

Recorded 2026-10-26 with Claude Code 2.1.302 on Windows, with the user's full plugin set loaded plus
`--plugin-dir plugins/moaa-core`:

```bash
py tests/e2e/run_e2e.py            # both steps
py tests/e2e/run_e2e.py pipe       # piped hook call only
```

| File | What it shows |
|---|---|
| `pipe.txt` | A two-line `py -c` payload gets `hookSpecificOutput.additionalContext` with the note and no `permissionDecision`; a short one-liner gets empty stdout. Both exit 0. |
| `claude-p.jsonl` | Headless `claude -p` (haiku) from a throwaway temp folder: the Bash call ran a real two-line `py -c`, the moaa-core `PreToolUse:Bash` hook returned the note, the call was not blocked (tool result `2432902008176640000`). Only PreToolUse hook events, messages and the result are kept; home paths are redacted to `~`. |
| `claude-p.summary.json` | Exit 0; Claude's final reply quotes the guard note verbatim, so the note reached the model next to the tool result. |
