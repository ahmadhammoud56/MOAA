---
name: project-docs
description: Audit a project for the agent doc set (AGENTS.md, CLAUDE.md, ARCHITECTURE, README, CODE_STYLE, TESTING, SECURITY, PRD, DESIGN_SYSTEM), report gaps, draft missing ones from the code.
---

# Project docs

Request: `$ARGUMENTS` (empty: audit the current project).

## 1. Audit

Look in the project root (and `docs/`) for each file, case-insensitive. Mark each **present**, **missing**, or
**stale** (names files, commands or folders that no longer exist, or its last commit is far behind the code it
describes: `git log -1 --format=%cr -- <file>` against `git log -1 --format=%cr -- <src dir>`).

| File | Purpose | Expect it when |
|---|---|---|
| `AGENTS.md` | Single source of agent rules: purpose, before you start, rules, code guidelines, security, useful commands | always |
| `CLAUDE.md` | One line, `@AGENTS.md`, plus Claude-only notes | always |
| `README.md` | What it is, install, quick start | always |
| `ARCHITECTURE.md` | Map of components, data flow, entry points | more than a handful of modules |
| `CODE_STYLE.md` | Conventions the linter does not enforce | team or multi-agent work |
| `TESTING.md` | How to run tests, where they live, what must pass | there are tests |
| `SECURITY.md` | Secrets handling, trust boundaries, reporting | network, auth, user data, or public repo |
| `PRD.md` | Goals, users, features, success metrics | app or product only |
| `DESIGN_SYSTEM.md` | Colours, type, spacing, components | UI project only |

Suggest `PRD.md` and `DESIGN_SYSTEM.md` only for app or UI projects (a frontend framework, `src/components`,
CSS/Tailwind, mobile app). Short sections of CODE_STYLE or TESTING can live inside AGENTS.md instead of their own file.

Report one table (file, status, one-line reason) and stop. Ask which missing or stale files to draft.

## 2. Draft (only the files the user picks)

- Write from the code itself: real commands from `package.json`, `pyproject.toml`, `Makefile`, CI files; real folder
  names; real test runners. Never invent features, metrics or policies; leave a `TODO:` where only the user knows.
- **AGENTS.md is the single cross-agent source.** Codex, Gemini CLI, OpenCode and Cursor read it. Keep `CLAUDE.md`
  to `@AGENTS.md` plus anything only Claude needs. If a long CLAUDE.md exists, offer to move its shared rules into
  AGENTS.md and leave the import line; do not duplicate text between the two.
- Keep each file short (AGENTS.md under about 150 lines); link to the others rather than repeating them.

Use an installed skill where one fits instead of writing from scratch:

| File | Skill |
|---|---|
| `AGENTS.md` | `agentic-awesome-skills:agents-md` |
| `PRD.md` | `ecc:plan-prd` |
| `DESIGN_SYSTEM.md` | `agentic-awesome-skills:design-md` |
| `ARCHITECTURE.md`, codemaps | `ecc:update-codemaps` |

If a skill is not installed, draft the file directly following the table in step 1. Show each draft as a diff or new
file and let the user approve before writing over anything that exists.
