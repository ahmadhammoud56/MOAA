# Security

## What installing MOAA does to your machine

Read this before you install, especially the `--full` profile.

- **Third-party code runs inside Claude Code.** Plugins can ship hooks, which run shell commands on events such as every prompt, every tool call or session start, as well as MCP servers and scripts.
  - The core profile installs 10 plugins: 5 of MOAA's own and 5 widely used skill collections. Hooks in core:
    - superpowers: `SessionStart`, which injects its skill guide.
    - understand-anything: `SessionStart` and `PostToolUse`.
    - MOAA's own UI mods (flightdeck, plot-deck, prismantis): interface hooks only. prismantis is installed disabled.
  - The `--full` profile installs 93 plugins. Many more of them (ruflo, ecc, caveman and others) register hooks on prompts and tool calls, and some start background processes.
  - All of this runs with your user account's permissions.
- **Third-party plugins are pinned, not audited.** Each one is installed at the exact commit the MOAA maintainer tested (see the plugin list in the README). Pinning protects you from surprise upstream changes; it is not a security review. Review any plugin you don't trust before installing it, or install only the core profile.
- **The installer changes your settings.** It merges into `~/.claude/settings.json` after writing a timestamped backup. It only adds, never overwrites:
  - It adds plugins, the env settings `ECC_GATEGUARD=off` and `CLAUDE_CODE_OVERLOADED_RETRY_MAX_DELAY_MS=60000` (a longer backoff when the API is overloaded, for long council, arena and War Room runs), a deny rule for one skill, and allow rules so `council.py` runs without a permission prompt.
  - The allow rules match only `python …specialist-council…council.py…`. `council.py` uses only the Python standard library and has no network access.
  - Every change is recorded in `~/.claude/.moaa-manifest.json`, and `--uninstall` reverses it.
- **MCP servers:**
  - `rea` runs via `npx rea-agents@6.3.0`, pinned.
  - `ansys` (`--full` only) is cloned from GitHub at a pinned commit, with a patch applied and pinned dependencies installed in its own venv.
- **No secrets are collected or sent anywhere.** The installer never reads or writes credentials or API keys. claude-mem (opt-in with `--with-claude-mem`) needs a model-provider key, which you set up through claude-mem's own setup.

To see exactly what would happen, run `./install.sh --dry-run` (add `--full` for the full profile). It prints every command without changing anything.

## Supported versions

| Version | Supported |
|---|---|
| 0.4.x | yes |
| < 0.4 | no, please upgrade |

## Reporting a vulnerability

Please don't open a public issue for security problems. Use GitHub's private reporting: **Security → Report a vulnerability** on this repository. You can expect an acknowledgement within 7 days.

If the problem is in a third-party plugin, it is usually best fixed upstream. Report it to that plugin's repository (linked in the README plugin list) and let us know, so the MOAA pin can be updated or the plugin removed.
