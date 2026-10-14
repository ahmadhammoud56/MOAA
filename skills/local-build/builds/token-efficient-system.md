---
title: Token-Efficient System
benefit: Get more done before hitting your usage limit by cutting what Claude Code loads and re-reads every session.
summary:
  - What: measure where tokens go, then trim always-loaded context, tool definitions, command output, and model choice.
  - Impact: smaller starting context in every session, cheaper sub-agents, fewer wasted turns.
  - Why now: every plugin, skill, MCP server, and CLAUDE.md line you add costs tokens in every session, whether used or not.
outcome:
  - A baseline measurement is recorded in ~/.claude/build-log.md.
  - Global and project CLAUDE.md files hold only rules needed in every session.
  - Plugins and MCP servers not used in the last month are disabled.
  - A rule or hook keeps long command output short.
  - Exploration-style sub-agents run on a smaller model.
  - At least one repeated multi-step chore is a script or skill.
  - A second measurement is recorded and compared with the baseline.
---

## Step 1: Measure the baseline

**Goal:** Know what each session costs before anything starts, so later steps can be checked against a number.

**Do:**
- Ask the user to run `/context` in a fresh session and report the total and the biggest categories (system tools, MCP tools, memory files, skills).
- Count what loads every session: line and byte size of `~/.claude/CLAUDE.md` and the project CLAUDE.md, number of enabled plugins (`claude plugin list`), number of MCP servers (`claude mcp list`), and SessionStart hooks that print text into context.
- Rank the top 5 sources by estimated size.

**Verify:** `~/.claude/build-log.md` contains a dated "baseline" entry with the `/context` total (or "not reported") and the top 5 sources.

## Step 2: Cut what loads every session

**Goal:** Every CLAUDE.md line, SessionStart hook message, and always-on output style is paid for in every session. Keep only what is needed every time.

**Ask:** Which CLAUDE.md files and SessionStart hooks to trim (offer the ones found in Step 1, largest first).

**Do:**
- Move reference material (long how-tos, examples, project history) out of CLAUDE.md into separate files that a skill or a one-line pointer loads only when needed.
- Remove duplicated rules and rules that repeat Claude Code defaults.
- For hooks that inject long text at SessionStart, propose shortening the text or disabling the plugin that adds it.
- Show the diff before saving. Back up each file first as `<name>.bak`.

**Verify:** Each trimmed CLAUDE.md is shorter than before, a `.bak` copy of the original exists next to it, and no rule was deleted without either being moved to a linked file or listed as removed in the step summary.

## Step 3: Disable unused plugins and MCP servers

**Goal:** Each enabled plugin adds skill descriptions, and each MCP server adds tool definitions, to every session.

**Ask:** Which plugins and MCP servers to disable (multi-select; offer those with no use in recent session history under `~/.claude/projects/`, largest skill or tool count first).

**Do:**
- Search recent session files for each plugin's skill names and each server's `mcp__<server>__` tool prefix to find what is actually used.
- Disable, do not uninstall: `claude plugin disable <plugin>@<marketplace>`; for MCP servers, move them from user scope to the projects that need them.
- Tell the user to restart Claude Code.

**Verify:** `claude plugin list` shows the chosen plugins as disabled, `claude mcp list` no longer shows the chosen servers at user scope, and the step summary lists how to re-enable each one.

## Step 4: Keep command output short

**Goal:** Long build, test, and install logs fill context fast. Claude rarely needs more than the failing part.

**Do:**
- Add a short rule to the global CLAUDE.md: prefer quiet flags (`-q`, `--silent`, `--reporter=dot`), pipe long output through `tail -n 50` or a filter for errors, and never dump full logs unless asked.
- If the project has a test or build command that is run often, add a project script that prints only the summary and failures, and point CLAUDE.md at it.

**Verify:** The global CLAUDE.md contains the output rule, and any project script added prints a summary line when run.

## Step 5: Run sub-agents on a smaller model

**Goal:** Search and exploration sub-agents do not need the largest model.

**Ask:** Which agent types to move to a smaller model (offer custom agents found in `~/.claude/agents/` and the project `.claude/agents/`, plus "all read-only explorers").

**Do:**
- For chosen custom agents, set `model: haiku` (or `sonnet`) in their frontmatter. For long-running ones, also set `autoCompactWindow` so they compact earlier than the main conversation.
- Optionally set `CLAUDE_CODE_SUBAGENT_MODEL` in the `env` block of `~/.claude/settings.json`. It is only the default: an agent's own `model:` and a per-call model still win. Do not use `CLAUDE_CODE_SUBAGENT_MODEL_FORCE`; it also overrides agents that need a larger model.
- If the user runs Workflow scripts, `CLAUDE_CODE_WORKFLOW_SUBAGENT_MODEL` puts every workflow agent on one model without touching other sub-agents.
- Add a CLAUDE.md line: lookup and search sub-agents get a low `effort` on the Agent call (the Agent tool takes `effort` since 2.1.292).
- Keep planning, review, and code-writing agents on the default model.

**Verify:** Each chosen agent file has a `model:` line with the smaller model, or `settings.json` has the chosen env entry. If the user ran a sub-agent since restarting, `/tasks` shows it ran on the smaller model.

## Step 6: Script one repeated chore

**Goal:** A task Claude re-derives every time (release steps, data refresh, environment setup) costs tokens each run. A script costs them once.

**Ask:** Which chore to script (offer repeated command sequences found in recent session history or shell history).

**Do:** Write the chore as a script in the project (or a small skill whose body just runs the script), test it once, and add a one-line pointer in CLAUDE.md.

**Verify:** The script exists, runs without error, and CLAUDE.md points to it.

## Step 7: Measure again

**Goal:** Confirm the savings with the same measurement as Step 1.

**Do:** Ask the user to run `/context` in a fresh session again, repeat the Step 1 counts, and compare with the baseline.

**Verify:** `~/.claude/build-log.md` has an "after" entry next to the baseline with both totals, or "not reported" for any reading the user could not get.
