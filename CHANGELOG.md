# Changelog

All notable changes to MOAA. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [SemVer](https://semver.org/).

## [Unreleased]

### Changed
- superpowers now comes from Anthropic's official marketplace listing (v6.4.1, `obra/superpowers` at `5bf4e78`) instead of the `superpowers-dev` marketplace (v6.3.0). The catalog generator handles marketplaces whose entries point at external repos.

## [0.4.2] - 2026-10-11

### Fixed
- Specialist Council 1.3.1: the runtime guide no longer tells the coordinator to pass full model IDs to the Agent tool. Its `model` field only takes the tier aliases `haiku`, `sonnet`, `opus` and `fable`, so a full ID failed validation and the first dispatch had to be retried. The frontmatter already pins the full ID.
- council-replay redacts user names that contain spaces, and the current user's home in every form, including the project-folder slug.

### Changed
- council-replay: IBM Plex is bundled under `tools/council-replay/fonts` (SIL OFL), so the GIF renders the same on every machine and offline.
- Checks now appear when the worker's result arrives, instead of on an invented schedule during the run.
- Three or more agents are laid out in a two-column grid, and three or more `resolve` calls use compact rows.
- `extract.py` skips Agent calls that were rejected, reads methods from the coordinator's summary table, and falls back to the resolved model and effort when the Agent call omits them.
- The demo GIF and test fixture come from a new real run with a cleaner prompt: "Is 221 prime? Factor it. Include the forged arithmetic checker."

## [0.4.1] - 2026-10-11

### Added
- `tools/council-replay`: replays a real Specialist Council transcript as an animation and records it as a GIF. `extract.py` turns a session into replay data and redacts paths and secrets, `replay.html` animates it on a canvas with a built-in GIF encoder, and `record.py` records it in headless Chrome, Edge or Chromium. It is optional and not installed. Standard library only, with no third-party JavaScript.
- `docs/demo/council-run.gif` near the top of the README, recorded from a scrubbed real run in `tests/fixtures/council-run`.

## [0.4.0] - 2026-10-11

### Added
- `--full` installer profile. The default is now a lighter **core** profile: 10 plugins (council, arena, the UI mods, superpowers, mattpocock-skills, karpathy-skills, document-skills, understand-anything), the standalone skills and the `rea` MCP server. `--full` installs all 93 plugins plus the `ansys` MCP server.
- `SECURITY.md`: what the installer changes, which plugins run hooks, and private vulnerability reporting.
- `CONTRIBUTING.md`, this changelog, issue and pull-request templates.
- README: a new top section (what it is, quick start, an example council run) and a security summary.

### Changed
- CI's clean-install job tests the core profile on macOS and the full profile on Linux.

## [0.3.0] - 2026-10-11

### Added
- `moaa` marketplace with all 95 plugins. The 90 third-party ones are pinned to tested commits (`scripts/sync_catalog.py`). Reserved upstream names are listed under aliases: `llm-api-reference`, `persistent-memory` and `persistent-memory-cowork`.
- Specialist Council 1.3.0 ships as a plugin (`specialist-council@moaa`). Forged members live in `~/.claude/specialist-council/forged/`, and `council.py migrate` converts older standalone installs.
- `council.py resolve --role forged-<slug>` for forged members.
- `MODELS.md`, generated from the plugins, listing every agent's model and effort.
- Generated plugin list in the README.
- CI on Linux, macOS and Windows, with clean-install tests on Linux and macOS.
- MIT licence, NOTICE, CITATION.cff and THIRD_PARTY.md.

### Fixed
- The `council.py` allow rule never matched: the quoted path ends in `council.py"`, so the rule can't have a space after `.py`.
- `install.sh` and the scripts were not executable on a fresh Linux or macOS clone.
- The ansys MCP server failed with `mcp` 2.x; its dependencies are now pinned.

## [0.2.0] - 2026-10-11

### Added
- Agent Arena 0.4.x: suspension unregisters a forged member's agent card; `council.py check` validates forged members; one shared model table; the arena library is found automatically when scripts run by hand.

## [0.1.0] - 2026-10-11

### Added
- First one-command installer: plugins, council, arena, skills, MCP servers and settings merge, with uninstall.

[0.4.0]: https://github.com/ahmadhammoud56/MOAA/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/ahmadhammoud56/MOAA/releases/tag/v0.3.0
