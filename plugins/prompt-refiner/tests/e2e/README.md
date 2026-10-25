# Live end-to-end evidence

Recorded 2026-10-25 with Claude Code 2.1.302 on Windows, with the user's full plugin set loaded plus
`--plugin-dir plugins/prompt-refiner`. Each case ran headless in a new throwaway folder outside the repo that held
one file, `greet.py`:

```bash
py tests/e2e/run_e2e.py <plugin dir> [ambiguous|clear|off-env]
py tests/e2e/summarize.py tests/e2e/ambiguous.jsonl
```

The runner calls `claude -p <prompt> --plugin-dir <plugin> --output-format stream-json --verbose
--include-hook-events --permission-mode acceptEdits --max-turns 12`. `<case>.jsonl` is the raw stream.
`<case>.files.txt` holds the prompt, the exit code, `greet.py` after the run, and every file in `.briefs/`.

| Case | Prompt | Hook output | Behaviour |
|---|---|---|---|
| `ambiguous` | `make the script better` | full brief instruction (`hook_response` with `prompt-refiner: before acting...`) | Wrote `.briefs/.gitignore` (`*`) and `.briefs/20261025-130225-make-the-script-better.md` with Goal, Deliverables, Inputs, Constraints and Acceptance checks. It noted "AskUserQuestion unavailable, took recommended options" and then edited the file. |
| `clear` | `In greet.py, change the greeting from Hello to Hi. Change nothing else.` | full brief instruction | Did not ask and made the one-line edit at once. It wrote no brief because the task was trivial. |
| `off-env` | `make the script better` with `PROMPT_REFINER=off` | empty (`"output": ""`) | No brief and no assumptions note. Claude edited the file directly and changed the output text unasked (`Hello, world!`), which the refiner run did not do. |
| `claude-dir-blocked` | `make the script better`, earlier build | full brief instruction, saving to `.claude/briefs/` | The brief write was refused as "a sensitive file". This happened under acceptEdits and also with a PreToolUse hook returning `permissionDecision: allow` (visible in the stream). Briefs therefore go to `.briefs/`. |

The `py greet.py` runs inside the sessions were refused ("This command requires approval"). That is expected
for headless acceptEdits mode and does not come from the refiner.

AskUserQuestion is not available in `claude -p`, so these runs check the headless fallback ("assume the
recommended option, do not wait"). They do not check the interactive question. That path depends only on
the injected text, which `tests/test_refiner.py` checks.

Paths under the user folder were redacted to `C:/Users/<you>` (`run_e2e.py ... redact`) because the repo is public.

`timing.txt` shows the hook process measured end to end (Python start included): a median of 74 ms over 10 runs.
`validate.txt` holds the output of `claude plugin validate`.
