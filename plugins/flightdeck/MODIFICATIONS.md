# flightdeck: my modifications

Upstream: [scasella/claude-flightdeck](https://github.com/scasella/claude-flightdeck) (v0.6.0, synced 2026-11-07 from upstream commit 536cb33). No code changes, only settings. The upstream `.github/` folder is left out. Update with `python scripts/sync_vendored.py flightdeck`.

`my-settings.json` here is a fragment to merge into `~/.claude/settings.json`. The one change from the defaults is `panels`: the permission `gate` panel is removed, leaving `main,architect,agents,loops,receipt,log`.
