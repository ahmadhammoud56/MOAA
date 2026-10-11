---
name: release
description: Cut a prismantis release - version bump, changelog, verify, tag and push. Use when asked to "release", "bump the version", "ship 0.x" or "publish".
---

# Release

1. **Pick the version.** Breaking option or token renames are minor while below 1.0 (and major after). New features are minor. Fixes are patch.
2. **Set it in both manifests**: `version` in `.claude-plugin/plugin.json` and `plugins[0].version` in `.claude-plugin/marketplace.json`.
3. **Changelog:** rename `## [Unreleased]` at the top of docs/CHANGELOG.md to a dated `## [x.y.z]`, keeping Added, Changed and Fixed, written for users. Merged PRs already put their entries there.
4. **Vendor:** if `scripts/package.json` changed, run `npm --prefix scripts run build:vendor`, and confirm the bundle has no `import` statements and no non-MIT code (`grep -c -i elk hooks/vendor/*.js` must print 0).
5. **Verify:** run every step in AGENTS.md Verify, plus `live-check`.
6. **Fresh install test** against a throwaway config:
   ```
   CLAUDE_CONFIG_DIR=<scratch>/fresh claude plugin marketplace add NahumLitvin/prismantis
   CLAUDE_CONFIG_DIR=<scratch>/fresh claude plugin install prismantis@prismantis
   CLAUDE_CONFIG_DIR=<scratch>/fresh claude plugin list
   ```
   Run it after pushing; the marketplace clones from GitHub.
7. **Commit, tag, push:** `git tag vX.Y.Z && git push --follow-tags`. The `release` workflow checks the tag against `plugin.json` and publishes the GitHub release from the CHANGELOG section.
8. **Confirm** CI and the release workflow are green.
