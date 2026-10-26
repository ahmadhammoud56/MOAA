# prompt-refiner

Always on, no slash command. Before Claude works on a prompt, it:

1. rewrites the prompt into a brief: Goal, Deliverables, Inputs, Constraints, Acceptance checks, Assumptions, Open
   points;
2. asks about material open points with one AskUserQuestion call, 2-4 concrete options per point (recommended
   first), and proceeds at once when nothing material is open; when a questioning skill (for example
   `superpowers:brainstorming`, grilling, an interview) runs for the prompt, that skill does the asking and the
   refiner only saves the brief from its answers, so you are not asked twice;
3. saves the settled brief to `.briefs/<timestamp>-<slug>.md` (git-ignored) in the project and shows a short version;
4. works from the brief, and passes the brief (or its path), not the raw prompt, to every subagent, council or War
   Room member, ally, side session or workflow.

## How it works

A `UserPromptSubmit` hook runs `refiner.py hook prompt` (standard library only, about 75 ms with Python start-up). A hook cannot change
the text the user typed, so it adds the instruction above as `additionalContext` next to the prompt. The hook
never blocks a prompt: any error means it adds nothing.

It adds nothing for:

- slash commands and harness notices (`<task-notification>`, `[SYSTEM ...]`, other messages starting with `<`),
  judged after removing the `<system-reminder>` blocks the desktop app puts in front of your words (for example the
  linked-sessions status on the first prompt after a restart), so such a prompt still gets the brief;
- the desktop app's hidden summary run ("Below is a conversation log from a Claude Code coding session ...") and
  processes strata starts (it sets `PROMPT_REFINER=off`);
- replies under 4 words (`yes`, `ok`, `2`, an option label);
- replies up to 40 words right after Claude asked a question or called AskUserQuestion (read from the tail of the
  transcript).

Prompts of 120 words or more, or with 4 or more list lines, are treated as a brief already: Claude confirms its
understanding in one line and asks only if something material is still open. Claude also skips the brief for a
clear follow-up to the current task and for pure questions. In a headless or delegated session, where
AskUserQuestion is not available, Claude takes its recommended options as assumptions instead of waiting.

## Switches

```bash
py refiner.py status
py refiner.py off
py refiner.py on
py refiner.py mode silent
py refiner.py mode ask
```

- `mode silent`: write the brief, never ask; open points become assumptions.
- `raw:` at the start of a prompt skips the refiner for that prompt.
- `PROMPT_REFINER=off` in the environment skips it for that process (scripted `claude -p` runs, CI).
- State lives in `~/.claude/prompt-refiner/config.json` (`CLAUDE_CONFIG_DIR` respected).
- `/prompt-refiner:prompt-refiner` explains and toggles it in a session; the refiner does not depend on it.

## Tests

```bash
py -m unittest discover -s tests
```

`tests/e2e/` holds the raw output of live headless runs (ambiguous prompt, clear prompt, refiner off); see
`tests/e2e/README.md`.
