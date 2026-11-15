# prismantis: MOAA's modifications

Upstream: [NahumLitvin/prismantis](https://github.com/NahumLitvin/prismantis), **v0.46.0** (`404b89a`), MIT, see
`LICENSE`. MOAA changes no upstream code.

## Layout

Since 0.46.0 upstream keeps the installable plugin in `plugin/` and its tests in `tests/` beside it. This folder is
upstream's `plugin/` with upstream's `tests/` added, the same layout upstream's own `npm --prefix scripts test`
builds in a temp folder before it runs `claude plugin test`. `config/kit.json` records this as `"path": "plugin"`
and `"also": ["tests"]`, so `scripts/sync_vendored.py` copies the same two folders on the next update.

## Left out of the copy

Everything outside `plugin/` and `tests/`: upstream's `.github/`, the Codex plugin (`codex/`, `.codex-plugin/`,
`.agents/`), the OpenCode port (`opencode/`), its developer scripts (`scripts/*.mjs`), `docs/` and the screenshots.
Claude Code does not use them, and every install copies the whole plugin folder.

## PNG button: now upstream's

MOAA used to carry a patch (`png-button.patch`) that added an opt-in `▣ png` button through Python and Pillow,
switched on with `PRISMANTIS_PNG_BUTTON`. Upstream has had its own `▣ png` button since 0.36.0 (upstream PR 276): on
tables, diagrams and figures, in the theme's colours, on Windows and macOS, with nothing to install. The MOAA patch
was dropped in the 0.46.0 update. `PRISMANTIS_PNG_BUTTON` no longer does anything; upstream's button shows whenever
the terminal's clipboard can take an image.

## Checked for this update (2026-11-15)

- `claude plugin validate .`: passed.
- `claude plugin test .`: 1175 passed, 0 failed (upstream's whole suite).
- Not yet checked: the button in a live session.

## Update to a newer upstream

Run `python scripts/sync_vendored.py prismantis`. It copies `plugin/` and `tests/`, validates, tests and records
the new version. It lists files that upstream dropped instead of deleting them; remove those by hand.
