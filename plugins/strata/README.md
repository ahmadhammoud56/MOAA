# Strata

Long-term memory for Claude Code across sessions and projects. It follows the four-layer design of
[TencentDB Agent Memory](https://github.com/TencentCloud/TencentDB-Agent-Memory) (MIT). The design is used here,
not its code: no proxy, no services, no extra API key, and standard-library Python with SQLite full-text search.

| Layer | Holds | Written by |
|---|---|---|
| L0 raw | every user and assistant message of each session, plus tool calls and results (cut to 8,000 characters), with secrets redacted | SessionEnd, PreCompact and the next chat after a handoff |
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
a new chat in the same project. That new chat gets the handoff with its first prompt and carries on, so nothing has
to be compacted.

- **Measure:** the UserPromptSubmit and PostToolUse hooks read the last 256 KB of the transcript and take the newest
  assistant message's `usage` (input + cache read + cache write tokens). The window is 1M for a `[1m]` model and for
  the models that run with 1M natively (Fable, Sonnet 5+, Haiku 5.5+, Opus 4.7+), else 200k; an auto-compact window
  (`CLAUDE_CODE_AUTO_COMPACT_WINDOW` or `autoCompactWindow`) lowers it, and `CLAUDE_CODE_DISABLE_1M_CONTEXT` sets 200k.
- **Prompt once:** Claude is asked once at the threshold, and again only 5 points later or after the context fell
  below the threshold (a compaction). You see a one-line notice too.
- **Fallback:** if a conversation is compacted before Claude wrote a handoff, the PreCompact hook writes a script-only
  snapshot (last requests, plan or todo list, recent files, last reply), so the thread survives compaction.
- **Resume:** a new chat (startup or `/clear`) gets the newest unconsumed handoff of the project (`latest` names it)
  once, with its first prompt, marked as notes from the earlier chat, and Claude confirms in one line. SessionStart
  only notes the handoff; the first prompt takes it. That way a hidden machine session in the same folder cannot use
  it up: the Claude desktop app starts one (Haiku, prompt "Below is a conversation log from a Claude Code coding
  session ...") to summarize a chat, for example when it starts a side session. Such a prompt, a session that never
  sends a prompt, and processes strata starts itself (`MOAA_STRATA_CHILD`, which also switches off prompt-refiner and
  the catalog hints for them) leave the handoff for the next chat. After a compaction the same session gets its own
  handoff back at SessionStart. A handoff is consumed when injected and offered again only if its `HANDOFF.md`
  changes. `--resume` and forks get nothing; they already hold the conversation.
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

## Virtual context

No model has an unlimited context window, so strata makes what leaves the window recallable instead. Always on,
no command needed.

- **Nothing is dropped:** L0 keeps every user and assistant message plus each tool call and tool result (up to 8,000
  characters each; tool rows are never sent to the Haiku extraction). PreCompact stores the whole conversation
  before Claude Code compacts it, and remembers where the cut was.
- **Chains of chats:** `meta.json` of a handoff names the transcript that wrote it. The chat that takes the handoff
  stores that conversation and records its lineage (the sessions it continues, newest first, across any number of
  handoffs).
- **Recall on demand:** each prompt in a chat that continues a handoff, or that was compacted, is matched against
  the evicted turns of its lineage and its own turns from before the cut. The ones that match strongly (the same IDF
  test as the project RAG; identifier-like words such as `purge_dwell_s` count double) are added, up to five and
  about 4,000 characters (`config recall_chars N`), each with its role and time and an excerpt centred on the most
  specific word. Unrelated prompts get nothing.
- **Two ways to run a long job:** the default `handoff` mode asks for a handoff at 85% and you open a new chat;
  `handoff mode compact` never asks, lets Claude Code compact, and relies on recall, so one chat goes on.
- **Off:** `strata.py handoff recall off` (or `config recall off`), `STRATA_RECALL=off` for one shell.

Measured live (`tests/e2e/recall/`, Haiku with every tool denied, after Sonnet read a 119-setting `rig.cfg` and
wrote a handoff that did not mention `purge_dwell_s`): with recall off the next chat said it did not know; with recall
on it answered `purge_dwell_s = 37` from the recalled tool result. After `/compact` the evicted tool result was
recalled too (there the compaction summary also kept the value).

## Project RAG

Always on, no command needed. `rag.py` keeps a full-text index of each project's own files in
`~/.claude/strata/rag.sqlite3` (SQLite FTS5 with Porter stemming and BM25 ranking, standard library only, no
embeddings model and no API key).

- **What is indexed:** in a git repository, the tracked and untracked files git does not ignore; elsewhere a walk
  that skips build, cache, virtual-environment and hidden folders. Text, code, LaTeX, BibTeX, CSV, notebooks (cell
  sources only) and, when `pdftotext` (poppler) is on PATH, PDFs. Files over 1 MB, binaries, lock files and minified
  bundles are skipped; at most 5,000 files per project (`config rag_max_files N`).
- **Never read:** `.env*`, `*.pem`, `*.key`, `keys.env`, SSH keys, `*credential*` and `*secret*` files, and the
  `.ssh`, `.aws` and `.claude` folders. Secrets inside indexed text are redacted with the same patterns as memory.
- **Refresh:** SessionStart starts a background `rag.py index` when the project's index is older than ten minutes;
  it reads only new and changed files (by modification time and size) and drops deleted ones. Indexing this
  repository (540 files) takes about 5 s the first time and 0.2 s after. A home folder or a drive root that is not a
  git repository is never indexed by a hook.
- **Prompt hint:** each prompt of at least 15 characters with three or more key words is searched. Only the key
  words that occur somewhere in the project count, each weighted by its rarity there (IDF), so instructions around a
  question ("answer in one sentence, no tools") do not dilute it; words found in more than a quarter of a big
  project's passages count for nothing. A passage is added when it holds two informative words and at least 60% of
  the weight: up to four passages, about 3,000 characters (`config rag_hint_chars N`), each with
  `path:first-last line` and marked as file contents, not instructions. Chit-chat, approvals and requests about
  other topics get nothing. A search takes about 20 ms (`tests/e2e/rag/probe.txt`).
- **Off:** `rag.py off` (or `strata.py config rag off`), `STRATA_RAG=off` for one shell. `rag.py drop` deletes a
  project's index.

```
python rag.py search "QUERY" [--limit N]      passages with path:lines
python rag.py status                          files, passages, last refresh, pdftotext found or not
python rag.py index [--full]                  refresh now (--full re-reads every file)
python rag.py on|off                          python rag.py drop
```

## Commands

```
python strata.py search "QUERY" [--all]       python strata.py show
python strata.py remember "TEXT" [--kind preference] [--global]
python strata.py scene "TITLE" "BODY"         python strata.py profile KEY "TEXT"
python strata.py forget ID | --session ID | --scene ID | --profile KEY
python strata.py consolidate --pending [--dry-run]
python strata.py config auto off              (no background extraction)
python strata.py handoff on|off|status|threshold N|window N|mode handoff|compact|recall on|off
python strata.py stats
```

Data lives in `~/.claude/strata/memory.sqlite3` and `rag.sqlite3` (or `$MOAA_STRATA_DIR`). Nothing leaves your machine
except the Haiku extraction call to Anthropic, which is the same service your sessions already use.

## Safety

- Secrets matching common key, token and password patterns are redacted before storage.
- Extraction output is validated (kinds, sizes, ids) before it is stored, and it can only supersede live notes of
  the same project.
- Injected memory is marked as data, not instructions. The skill tells Claude never to follow commands found in it.

MIT licensed; see [LICENSE](LICENSE). Part of [MOAA](https://github.com/ahmadhammoud56/MOAA).
