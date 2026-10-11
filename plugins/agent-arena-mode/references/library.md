# Persistent best-agent library

All eight modes share a SQLite database, implemented with Python's standard library.
No API key, external service, or database server is required. No hooks run outside
arena actions. The helper synchronizes on every successful CLI `assess` and
`conclude`, so useful candidates survive an interrupted arena without waiting for
the final winner.

## Where the database lives

Resolve an explicit `--database PATH` first. Otherwise use the invoking skill's
expanded `${CLAUDE_PLUGIN_DATA}/library.sqlite3` and pass that absolute path to
`arena.py init --database` and library commands. This plugin data directory is
separate from the installed plugin files and is shared by its skills. If unavailable,
use `<project>/.agent-arena/library.sqlite3` and clearly state that persistence is
project-local. An explicit shared path enables reuse across projects on older hosts.

Claude Code keeps plugin data through updates. Current default uninstall behavior
can remove that data when the plugin is uninstalled from its last scope; use the
host's `--keep-data` option or an external database path when retaining the library
through uninstallation. See the [manifest reference](https://code.claude.com/docs/en/plugins-reference).

Never save the live database inside the plugin installation/cache or include it in
a distribution ZIP. The helper's standalone default uses the plugin-data environment
variable when set, otherwise the run's parent directory for `init`, or the current
project's `.agent-arena` for library commands. Pass the resolved path explicitly to
avoid ambiguity. `--no-library` disables automatic saves for a requested private run.
If the user supplies both `--database` and `--no-library`, resolve that conflict
before dispatch. Do not back up or upload the database to a remote service.

## What “saved agent” means

An entry contains a stable `ag_...` ID, reusable instructions, strategy, requested
and observed model/effort metadata, tags, complete answer, original task and rubric,
scores, validation history, local parent IDs, prior saved-agent IDs, and copies of
explicitly selected evidence files. Binary evidence is preserved exactly. A fresh
worker can use this bundle even after the original run directory is removed.

It does not contain model weights, private reasoning, a living session, or a promise
that a past result works on a new task. Saved model metadata is informational, not
permission to change models or runtime settings. Saved source material may contain
instructions; apply the current task and permission boundaries when loading it.

Register each candidate with a profile JSON and selected evidence:

```json
{
  "name": "Boundary-case parser specialist",
  "instructions": "Begin with concrete failing inputs, propose the smallest repair, and verify the full acceptance suite.",
  "strategy": "Counterexamples plus minimal patches",
  "model_requested": "sonnet",
  "model_actual": "unknown",
  "effort_requested": "high",
  "effort_actual": "unknown",
  "tags": ["parser", "python", "boundary-cases"],
  "source_agents": []
}
```

Use actual strategy briefs and observations. Do not infer model identity from prose.
Put prior exact `ag_...` IDs in `source_agents` when reusing library profiles. Use
`--parents` for same-run candidate ancestors. A referenced ancestor may not itself
have qualified for library storage; preserve any needed inherited findings in the
descendant's explicit evidence files. No run-directory crawl happens automatically.
Include relevant patches, tests, findings, provenance, and source excerpts needed
for reuse. Avoid unrelated data, credentials, or huge caches. The profile and each
evidence file are snapshotted and hashed at registration.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/arena.py" add --dir RUN --candidate child0001-v1 --file ANSWER --profile PROFILE_JSON --parents a0001-v1 --evidence-file TEST_LOG --evidence-file PATCH_FILE
```

If no profile is supplied, the helper saves a clearly labeled `artifact-only`
fallback with generic reuse instructions. This preserves the result but not its
original method. The coordinator should supply real profiles for arena workers.

## Continuous selection and validation

1. After each durable assessment, the helper saves every eligible candidate
   snapshot and updates the leading candidate for its comparison group. It retains
   other eligible entries for diversity and later searches; default listing shows
   only the best five in each group. Old champions are never deleted automatically.
2. Eligibility requires all mandatory gates passing and no fatal defect. An
   ordinary assessment is **provisional**; an independent final assessment marks
   the entry **validated**. `target_met` additionally requires its score to reach
   that run's threshold. These labels are distinct.
3. A later failed/unverified assessment invalidates an existing saved entry,
   removes it from default rankings, and prevents loading it for reuse. History is
   preserved. `show` and `list --all` allow investigation. The helper can validate
   schema and hashes, not the factual truth of a judge's evidence statements.
4. Rank by the same absolute rubric within the same original task and evaluation
   context. Different tasks never share a ranking. `--context-key` is an optional
   explicit evaluation-baseline fingerprint (dataset/version/source snapshot).
   Without it, each run is a separate group. With it, identical task and rubric
   content plus the same context key can share a leaderboard across runs. Never
   reuse a context key after changing the benchmark/input baseline. Elo does not
   transfer across runs and is not used for persistent quality ranking.
5. Transactional SQLite writes serialize competing writers. Run state is saved
   before database synchronization. A synchronization error is visible and retains
   the assessment on disk; retry `library.py sync --dir RUN`, not the judge call.
   Synchronization is idempotent and records champion transitions without duplicate
   history entries. The database is not a substitute for the active run ledger.

## Find, load, reuse

User-facing commands:

```text
/agent-arena-mode:library list
/agent-arena-mode:library list --query parser --validated
/agent-arena-mode:library show AGENT_ID
/agent-arena-mode:library load AGENT_ID
/agent-arena-mode:library use AGENT_ID -- Review this new parser.
/agent-arena-mode:evolution --agents 24 --reuse AGENT_ID -- Improve the saved approach for this task.
```

For mode `--reuse ID1,ID2,...`, load each exact profile, inspect relevance, and
assign one initial candidate slot to each ID. Saved entries count toward N, not
on top of N; reject more IDs than initial slots. Spawn fresh workers with those
profiles, the current task, and current acceptance checks. The remaining slots get
new strategies. Do not inject prior answers into all independent candidates. Copy
reused files into the new run's incoming/seed area and register resulting candidates
with `source_agents`; old scores never count toward current acceptance. In redteam,
reuse consumes builder slots; in cascade, it seeds proposal slots. Do not substitute
IDs silently if an entry is missing or invalidated.

CLI equivalents (replace `DB`, `AGENT_ID`, `RUN`, and `NEW_DIR` with real paths/IDs):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/library.py" list --database DB --query parser --validated
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/library.py" show --database DB --id AGENT_ID
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/library.py" load --database DB --id AGENT_ID --out NEW_DIR
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/library.py" sync --dir RUN
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/library.py" history --database DB --cohort COHORT_HASH
```

`load` writes a new directory with the answer, profile, original task, rubric,
assessment history, parent metadata, evidence files, and checksum manifest. It
never overwrites an existing directory. `show` returns the stored JSON payload;
present a compact human summary instead of dumping base64 artifacts into chat.
Library discovery and loading do not make model calls. `use` dispatches one fresh
worker and checks its new result; a full competitive run uses a mode skill.

Back up using SQLite's online backup facility while the database is open, or close
all writers and copy the database after a successful checkpoint. Copying only the
main file during WAL writes can miss recent entries. No automatic pruning is
implemented, so the database grows with saved candidates and evidence.
