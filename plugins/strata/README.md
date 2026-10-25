# Strata

Long-term memory for Claude Code across sessions and projects. It follows the four-layer design of
[TencentDB Agent Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory) (MIT). The design is used here,
not its code: no proxy, no services, no extra API key, and standard-library Python with SQLite full-text search.

| Layer | Holds | Written by |
|---|---|---|
| L0 raw | every user and assistant message of each session, with secrets redacted | the SessionEnd hook |
| L1 notes | atomic facts, preferences, constraints and events; a newer note supersedes an older one | consolidation |
| L2 scenes | one block per ongoing topic of a project, rewritten as it moves on | consolidation |
| L3 profile | stable traits of the user and how they like to work, shared by all projects | consolidation |

## How it works

- **SessionStart:** injects the profile, this project's scenes and its newest notes (6,000 characters by default),
  labelled as data that may be out of date.
- **SessionEnd:** stores the session in L0. If at least 1,500 characters of new conversation came in, one
  background `claude -p --model haiku` call extracts notes, scenes and profile entries. That call has every tool
  denied and saves no session, so it cannot act or feed back into memory. Expect about 10-20k Haiku tokens per
  session.
- **Recall:** the `memory` skill searches upper layers first and falls back to raw conversations.

A project is its git repository root, so all worktrees of one repo share memory.

## Context handoff

Always on, no command needed. When a conversation fills about 85% of its context window, Claude stops at a safe
point, writes `HANDOFF.md` (goal, state, done, next actions, open questions, decisions, files, resume commands) and
`CONTEXT.md` (durable facts, constraints, paths, IDs) to `<project>/.claude/handoff/<stamp>/`, and tells you to open
a new chat in the same project. That new chat gets the handoff injected at its start and carries on, so nothing has
to be compacted.

- **Measure:** the UserPromptSubmit and PostToolUse hooks read the last 256 KB of the transcript and take the newest
  assistant message's `usage` (input + cache read + cache write tokens). The window is 1M for a `[1m]` model and for
  the models that run with 1M natively (Fable, Sonnet 5+, Haiku 5.5+, Opus 4.7+), else 200k; an auto-compact window
  (`CLAUDE_CODE_AUTO_COMPACT_WINDOW` or `autoCompactWindow`) lowers it, and `CLAUDE_CODE_DISABLE_1M_CONTEXT` sets 200k.
- **Prompt once:** Claude is asked once at the threshold, and again only 5 points later or after the context fell
  below the threshold (a compaction). You see a one-line notice too.
- **Fallback:** if a conversation is compacted before Claude wrote a handoff, the PreCompact hook writes a script-only
  snapshot (last requests, plan or todo list, recent files, last reply), so the thread survives compaction.
- **Resume:** SessionStart of a new chat (startup or `/clear`) injects the newest unconsumed handoff of the project
  (`latest` names it) once, marked as notes from the earlier chat, and Claude confirms in one line. A handoff is
  consumed when injected and offered again only if its `HANDOFF.md` changes. `--resume` and forks get nothing; they
  already hold the conversation.
- `.claude/handoff/` gets a `.gitignore` of `*`, so handoffs are never committed by accident.

```
python strata.py handoff status               python strata.py handoff off | on
python strata.py handoff threshold 90         (50-95)
python strata.py handoff window 400k          (0 = from the model)
STRATA_HANDOFF=off                            (env: off for one shell; STRATA_HANDOFF_THRESHOLD and
                                               STRATA_HANDOFF_WINDOW override too, the threshold down to 1 for tests)
```

Limits: the transcript records usage per assistant message, so the measure lags one model call and does not count
the prompt being submitted; a single tool result bigger than the remaining room can still overflow before the hook
sees it. Sub-agent calls are not counted (their context is separate) and do not trigger the prompt.

## Commands

```
python strata.py search "QUERY" [--all]       python strata.py show
python strata.py remember "TEXT" [--kind preference] [--global]
python strata.py scene "TITLE" "BODY"         python strata.py profile KEY "TEXT"
python strata.py forget ID | --session ID | --scene ID | --profile KEY
python strata.py consolidate --pending [--dry-run]
python strata.py config auto off              (no background extraction)
python strata.py handoff on|off|status|threshold N|window N
python strata.py stats
```

Data lives in `~/.claude/strata/memory.sqlite3` (or `$MOAA_STRATA_DIR`). Nothing leaves your machine
except the Haiku extraction call to Anthropic, which is the same service your sessions already use.

## Safety

- Secrets matching common key, token and password patterns are redacted before storage.
- Extraction output is validated (kinds, sizes, ids) before it is stored, and it can only supersede live notes of
  the same project.
- Injected memory is marked as data, not instructions. The skill tells Claude never to follow commands found in it.

MIT licensed; see [LICENSE](LICENSE). Part of [MOAA](https://github.com/ahmadhammoud56/MOAA).
