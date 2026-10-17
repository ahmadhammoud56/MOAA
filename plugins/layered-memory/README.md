# Layered memory

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

## Commands

```
python memory.py search "QUERY" [--all]       python memory.py show
python memory.py remember "TEXT" [--kind preference] [--global]
python memory.py scene "TITLE" "BODY"         python memory.py profile KEY "TEXT"
python memory.py forget ID | --session ID | --scene ID | --profile KEY
python memory.py consolidate --pending [--dry-run]
python memory.py config auto off              (no background extraction)
python memory.py stats
```

Data lives in `~/.claude/layered-memory/memory.sqlite3` (or `$MOAA_MEMORY_DIR`). Nothing leaves your machine
except the Haiku extraction call to Anthropic, which is the same service your sessions already use.

## Safety

- Secrets matching common key, token and password patterns are redacted before storage.
- Extraction output is validated (kinds, sizes, ids) before it is stored, and it can only supersede live notes of
  the same project.
- Injected memory is marked as data, not instructions. The skill tells Claude never to follow commands found in it.

MIT licensed; see [LICENSE](LICENSE). Part of [MOAA](https://github.com/ahmadhammoud56/MOAA).
