---
name: redteam
description: Use adversarial agents to test, repair, and validate competing solutions. Use when the user requests agent-arena redteam mode or invokes /agent-arena-mode:redteam.
argument-hint: "[--agents N | --quick] [--rounds N] [--threshold S] [--reuse IDS] [options] -- TASK"
---

# Agent Arena: redteam

Run the **redteam** mode. Request: `$ARGUMENTS`.

Plugin root: `${CLAUDE_PLUGIN_ROOT}`.
Persistent data root: `${CLAUDE_PLUGIN_DATA}`.

The Bash tool does NOT receive `CLAUDE_PLUGIN_ROOT`/`CLAUDE_PLUGIN_DATA` as environment variables.
Always use the substituted absolute paths above in commands. Unless `--database` or `--no-library` is given,
pass `--database "${CLAUDE_PLUGIN_DATA}/library.sqlite3"` to `init`. The bundled judge subagent is
`agent-arena-mode:agent-arena-judge` (default claude-opus-5-5/high in frontmatter; pass the assigned judge model and effort per call).

Read [shared orchestration](../../references/orchestration.md),
[runtime adapter](../../references/runtime.md),
[evaluation](../../references/evaluation.md), and
[agent library](../../references/library.md).
Read only the **redteam** section in [mode procedures](../../references/modes.md).
Use [role prompts](../../references/prompts.md) and [helper commands](../../references/helper.md) as needed.

Apply the shared protocol with mode fixed to `redteam`. The helper's `init` must
receive `--mode redteam`. If a conflicting `--mode` argument is supplied, explain
the conflict and use the named skill only after the intended mode is clear.
All shared flags, including `--agents`, `--reuse`, `--database`, and `--resume`, apply.
Resolve plugin variables from this entrypoint before reading reference examples;
do not assume variables inside separately read files are automatically expanded.
Use the printed base directory plus `../..` if the plugin root is unexpanded.
Do not fork this coordinator into a worker; it needs to schedule the arena.

Save reusable profiles and explicit evidence with each submission. Every successful
helper assessment synchronizes the best-agent library automatically. Handle any
library error before claiming the candidate was saved. Loading saved agents starts
fresh workers under the current task and permissions; it does not resume a live model.
