---
name: prompt-refiner
description: Explain, turn on or off, or switch the mode of the always-on prompt refiner (rewrites each prompt into a brief, asks about ambiguous points, hands the brief to subagents). Use when the user asks about the refiner or wants it on, off, quieter, or silent.
---

# Prompt refiner

Request: `$ARGUMENTS`. Plugin root: `${CLAUDE_PLUGIN_ROOT}`. Use the substituted absolute path in commands
(the Bash tool does not receive `CLAUDE_PLUGIN_ROOT` as an environment variable).

The refiner works without this skill: a `UserPromptSubmit` hook adds an instruction to each prompt. Claude then
rewrites the prompt into a brief (Goal, Deliverables, Inputs, Constraints, Acceptance checks, Assumptions, Open
points), asks about material open points with AskUserQuestion (2-4 options each), saves the brief to
`.briefs/<timestamp>-<slug>.md` (git-ignored) in the project, and passes the brief to every subagent or side session.

It stays silent for slash commands, harness notices, replies under 4 words, and answers to a question Claude just
asked. Long or structured prompts get a one-line restatement instead of a full brief.

Map the request to one command, run it, and report the printed status line:

| Request | Command |
|---|---|
| status, "is it on?" | `py "${CLAUDE_PLUGIN_ROOT}/refiner.py" status` |
| turn on | `py "${CLAUDE_PLUGIN_ROOT}/refiner.py" on` |
| turn off | `py "${CLAUDE_PLUGIN_ROOT}/refiner.py" off` |
| ask about ambiguity (default) | `py "${CLAUDE_PLUGIN_ROOT}/refiner.py" mode ask` |
| write briefs but never ask | `py "${CLAUDE_PLUGIN_ROOT}/refiner.py" mode silent` |

Use `python3` or `python` where `py` does not exist. Changes apply from the next prompt.

Other switches, to mention when they fit:

- Skip it for one prompt: start the prompt with `raw:`.
- Skip it for a whole process (CI, scripted `claude -p` runs): set `PROMPT_REFINER=off`.
- Remove it entirely: `claude plugin disable prompt-refiner@moaa`.
