---
name: local-build
description: "Walk the user through a local, offline build guide one step at a time: load a build file from this skill's builds/ folder, fill each step with the user's real project context, run it after confirmation, and blind-verify before moving on. Use when the user says 'run a build', 'local build', names a build (e.g. 'token-efficient-system'), or asks to list builds. Local replacement for /buildpartner:build; no network, no account."
---

# Local build runner

Builds are plain Markdown files in `builds/` next to this file. Nothing is fetched from the network. To add a build, drop a new `builds/<slug>.md` file in the same format.

## 1. Load the build

- No argument or "list": list `builds/*.md` with each file's `title` and `benefit` from its frontmatter, then ask which to run with **AskUserQuestion**.
- Argument given: match it to a slug. Read `builds/<slug>.md` once. A trailing `step N` resumes at step N: skip Orient's intro, confirm the workspace, and start there.

Build file format: YAML frontmatter (`title`, `benefit`, `summary`, `outcome` list) then one `## Step N: <title>` section per step. Each step has **Goal**, **Do**, optional **Ask** (inputs to gather), and **Verify**.

## 2. Orient (short)

Show the `benefit`, the `summary`, and the step count. Then ask the workspace with **AskUserQuestion** (header `Workspace`): "This project" (recommended) or "A different directory". Touch no files until they choose. Warn if the chosen folder is a temporary scratch workspace, because the output would be lost.

## 3. Walk the steps, one at a time

Hard gate: one step per turn. Never batch, skip ahead, or run a step the user has not confirmed.

For each step:

1. **Announce:** `Step N of M`, the title, and the Goal in one or two sentences tied to their setup.
2. **Check existing setup:** a few targeted searches for something that already does this step's job (CLAUDE.md, skills, hooks, settings, scripts). If found, show the evidence and ask "Use as-is" / "Improve it" / "Start fresh". If nothing is found, say nothing.
3. **Gather inputs:** for each **Ask**, inspect the project first and offer real candidates as **AskUserQuestion** options (best pick recommended, Other for free text). Use `multiSelect` when several answers can apply.
4. **Show and confirm:** show exactly what you will run or change, written for the user's actual OS and shell. If the step's lever does not exist in this setup, say so in one line and offer the nearest move that reaches the same goal, or "Skip this step". Ask "Run it" (recommended) / "Tweak first" / "Skip this step".
5. **Run:** do every part you can yourself and show the output or diff. Hand the user only what needs their own terminal (`/context`, `/cost`, `/usage`, interactive panels), one at a time, and ask for the reading as options plus "I'll paste it" and "Couldn't run it, skip". If the step changed hooks, agents, plugins, or MCP servers, a restart is needed before verifying. A restart ends this conversation, so first give the resume command `/local-build <slug> step N` and say it will re-run only the Verify for step N.
6. **Blind verify:** spawn a fresh sub-agent that has not seen your work, give it only the step's **Verify** text and the workspace path, and have it report pass or fail with evidence. Advance only on pass; on fail, fix and re-verify. After two failed fixes, stop and ask: "Try another fix" / "Skip this step" / "Stop here". A verifier only reads state, so a read-only agent type (such as Explore) at `effort: low` or `medium` is enough where the Agent tool takes `effort`. If sub-agents are unavailable, verify inline by inspecting real state, never from memory.
7. **Offer next:** ask "Done: <this step>. Next: <next step>?" with "Next step" (recommended), "Redo this step", "Stop here". On stop, give the resume command: `/local-build <slug>` and "start at step N+1".

## 4. Land the outcome

Check every `outcome` item against the real setup and report each as done, not done, or not available on this platform. Append a dated line to `~/.claude/build-log.md` with the build slug, steps completed, and any before/after numbers the user reported.

## Rules

- Every decision is an **AskUserQuestion** card, never a prose question.
- Steps, actions, and verify criteria come from the build file only. Options for questions come from the user's real setup.
- Never send project data anywhere. This skill makes no network calls.
- When a step adds a hook, run its command once by hand before saving it. Use `onFailure: "block"` only for safety gates: with it, a hook that cannot start, times out, or exits with an unexpected code blocks every matching action.
