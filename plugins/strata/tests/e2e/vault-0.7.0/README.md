# strata 0.7.0 live checks (2026-10-31, Windows 11)

Run on the author's machine against the real memory database; home paths shortened to `~`.

## Vault created and refreshed from every project

```
$ strata.py vault init
vault ready at ~/code/brain (git init only; strata commits only on `vault snapshot`)
$ strata.py vault refresh
refreshed 17 project page(s) and Home.md in ~/code/brain
```

The first refresh, before throwaway folders were filtered, wrote 49 pages: e2e sandboxes (`refiner-e2e-*`,
`moaa-guard-e2e-*`), agent worktrees and test users. `real_project` now skips missing folders, temp folders, the home
folder and `worktrees` paths, leaving the 17 real projects. `projects/claude-kit.md` showed properties, five scenes,
the newest notes, recent commits and linked sessions; `Home.md` listed the 17 project pages.

## Extraction backlog drains again

Before: 67 pending. Grouped failures in `consolidate.log`: 22 runs where `claude -p`, started in the project folder,
exited non-zero next to a settings warning about a `Write(...)` permission rule; 12 runs with an expired OAuth login;
29 sessions that were too small to extract and were counted as pending forever.

After the fix (extraction runs in strata's data folder, a valid reply is accepted despite stderr warnings, small
sessions are not counted): 40 pending, then

```
$ strata.py consolidate --pending --limit 3
{"session": "285ef14b-...", "engine": "claude-haiku", "atoms": 11, "scenes": 1, "profile": 0, "superseded": 0}
{"session": "2129dcf0-...", "engine": "claude-haiku", "atoms": 12, "scenes": 2, "profile": 2, "superseded": 0}
{"session": "2dd438d5-...", "engine": "claude-haiku", "atoms": 12, "scenes": 2, "profile": 2, "superseded": 2}
```

37 pending; each SessionEnd now takes up to 4. The `local` fallback (no model) is covered by
`tests/test_strata.py::test_failed_engine_falls_back_to_local_extraction`, with the claude-mem error text.
