---
name: long-task
description: Run a long or multi-session task to completion with a written brief, acceptance checks, a progress file that survives context resets, an evidence review and a resume prompt. Use when the user asks to finish, carry through or resume a long task, or invokes /specialist-council:long-task.
argument-hint: "[task, or the slug of a task to resume]"
---

# Long task: finish it, survive resets

Request: `$ARGUMENTS`. Work in the user's project. Keep every file below in `.claude/long-task/<slug>/` of that
project (create it; add it to `.gitignore` only if the user wants it untracked), so a new session can pick it up.

## 1. Brief (once, before any work)

Write `brief.md` with these fields, filled from the request and the project. Ask only for what you cannot infer:

- **Task:** one paragraph.
- **Deliverables:** exact output paths.
- **Acceptance:** checkable conditions, each one something a command, a file or a reviewer can confirm
  (tests pass, file exists with sections X and Y, every claim in the claim table verified or marked unresolved).
- **Constraints:** what must not change, what needs the user's go-ahead (pushes, sends, deletes, spending).
- **Budget:** turn or time limit, if the user gave one.

## 2. Progress file (update after every step)

`progress.md` holds: task (one line), outputs so far with paths, checks done with their results, decisions and why,
open issues, and the **next action**. Write it before a long command and after each result, so a context reset or
usage limit loses at most one step. Never record secrets in it.

## 3. Goal

Give the user this line to run, filled from the brief, so Claude Code keeps working until the acceptance holds:

```
/goal All acceptance checks in .claude/long-task/<slug>/brief.md pass and progress.md lists their evidence. Stop after N turns.
```

`/goal` is a user command; you cannot run it yourself. The goal check is model-judged, so keep hard limits (money,
runtime) in the brief's constraints and stop on them yourself. `/goal clear` removes it.

## 4. Work

- Do one step at a time against the next action in `progress.md`. Batch independent reads into one turn.
- Commit or otherwise save durable work as you go; `/rewind` does not undo shell changes or subagent edits.
- **Before retrying anything that timed out or failed partway** (a push, an upload, a cluster sync, an API write, a
  commit by another agent), check whether the first attempt already took effect and record what you found.
- Use the Specialist Council for parts that benefit from independent specialists.

## 5. Evidence review (before calling it done)

Dispatch `specialist-council:council-peer-reviewer` (papers, reports, analyses) or
`specialist-council:council-validation-auditor` (models, data, numbers) with the deliverables and their sources, and
ask for the **claim table** in its evidence-review format. Fix every `incorrect` row, recheck the sentences around
each fix, and leave `unresolved` rows marked with the missing evidence. Save the table as `checks.md` next to the
brief.

## 6. Finish or hand over

- **Done:** every acceptance check passes with evidence in `progress.md`. Report the deliverable paths, the check
  results and any unresolved claims.
- **Not done:** write `resume.md`, a ready-to-paste prompt for a fresh session:
  `Resume the long task in .claude/long-task/<slug>/: read brief.md and progress.md, then continue from the next action.`
  Tell the user where it is.

## Resume

When `$ARGUMENTS` names an existing slug, or a `resume.md` exists: read `brief.md`, `progress.md` and `checks.md`,
verify the last recorded step really happened (files, commits, remote state), then continue from the next action.
