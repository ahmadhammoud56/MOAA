# MOAA: Mother of All Agents

A complete Claude Code setup: 94 plugins from 14 marketplaces, the Specialist Council (60 role agents), the Agent Arena (which forges new council members from proven agents), 10 standalone skills, and the `rea` and `ansys` MCP servers. One command installs all of it.

Created by **[Ahmad Hammoud](https://github.com/ahmadhammoud56)**. The Specialist Council and the Agent Arena are original work; everything else is credited in [NOTICE](NOTICE) and [THIRD_PARTY.md](THIRD_PARTY.md).

## Requirements

- Claude Code 2.1.296 or newer, logged in (`claude --version`). The council pins `claude-*-5-5` and `claude-fable-5-1` model IDs, and older builds reject them.
- git, Python 3.10+, and Node 20+ (for `npx`).
- Optional: an Ansys install, so the ansys MCP server can do real work. Without one it installs but stays idle.
- Windows: if your Claude config dir has a long path, marketplace clones can fail with `Filename too long`. Run `git config --global core.longpaths true` once to fix it.

## Install

```bash
git clone https://github.com/ahmadhammoud56/MOAA.git
cd MOAA
./install.sh            # macOS / Linux / Git Bash
```

```powershell
.\install.ps1           # Windows PowerShell
```

Options (both wrappers pass them through to `scripts/install.py`):

| Flag | Effect |
|---|---|
| `--with-claude-mem` | Also install claude-mem and claude-mem-cowork. They need a model provider key, which you configure through claude-mem's own setup, and they run a background worker on port 37777. |
| `--skip-ansys` | Skip the ansys MCP server. |
| `--skip-mcp` | Skip both MCP servers. |
| `--dry-run` | Print every command without changing anything. |
| `--uninstall` | Reverse what the kit recorded in `~/.claude/.moaa-manifest.json`. |

Restart Claude Code afterwards.

The installer respects `CLAUDE_CONFIG_DIR`, so you can trial it in a throwaway config directory:

```bash
CLAUDE_CONFIG_DIR=/tmp/kit-test ./install.sh --skip-ansys
```

## What the installer does

1. Adds each needed marketplace: the upstream GitHub ones, plus this repo as the `moaa` marketplace for the vendored plugins.
2. Installs every plugin in `config/kit.json` at user scope. prismantis is installed disabled; enable it with `claude plugin enable prismantis@moaa`.
3. Copies the standalone skills to `~/.claude/skills`. A skill that already exists there and wasn't installed by the kit is left untouched.
4. Installs the Specialist Council with `specialist-council/council.py install`. This adds 60 `council-*` agents and the skill.
5. Merges settings into `~/.claude/settings.json`, after writing a timestamped backup. The merge never overwrites anything:
   - Permission lists are unioned.
   - `env` keys and the defaults (model, theme, and so on) are added only when they're absent.
   - `enabledPlugins` entries you already set are kept.
   - It adds allow rules so `council.py` runs without permission prompts, plus the env setting `ECC_GATEGUARD=off`.
6. Adds the MCP servers at user scope:
   - `rea` (`npx rea-agents@6.3.0`).
   - `ansys`: cloned at a pinned commit into `~/.claude/kit-tools/ansys-mcp-server`, with `vendor/ansys-mcp-server.patch` applied, inside its own venv.
7. Runs `council.py check` and writes the manifest.

Rerunning is safe: anything already present is skipped.

## Using it: council, arena, saving, forging

All four work at any time and on their own. Nothing needs to be started first.

| What | How | What happens |
|---|---|---|
| **Council** | Ask for a council or a specialist team, or run `/specialist-council`. | Picks 2 to 3 of the 60 role agents (plus any active forged members), resolves each one's model and effort with `council.py resolve`, runs them, then integrates and verifies the result. |
| **Arena** | `/agent-arena-mode:<mode> [--agents N] [--reuse IDS] -- TASK`, where mode is judge, tournament, swarm, league, evolution, synthesis, redteam or cascade. | Workers compete on a frozen task and rubric, and the `agent-arena-judge` scores them. |
| **Saving** | Automatic. Every judged arena result is written to the library. Add `--no-library` to opt out. | Stored in `~/.claude/plugins/data/agent-arena-mode-moaa/library.sqlite3`. Browse with `/agent-arena-mode:library list`; reuse with `library use ID -- TASK`, or `--reuse ID` in any mode. |
| **Forging** | `/agent-arena-mode:library promote ID`. It shows the evidence first (`promote --check`). | Writes `council-forged-<slug>` with its validated model and effort, a knowledge base, and a registry entry. The council can use it from the next session. |

Forging rules:
- **Eligibility:** the agent must be validated in 2 or more independent runs, with every validated score at least 85, a score spread of at most 10, and nothing in its lineage invalidated.
- **Earning a second run:** reuse a saved agent in a new arena run with `--reuse ID`.
- **Suspension:** a later failed validation suspends the member automatically and unregisters its agent card. `python ~/.claude/skills/specialist-council/council.py check` validates the 60 roles plus every forged member.
- **Command line:** you can run the library by hand without Claude Code: `python <plugin dir>/scripts/library.py list|show|promote|council`. It finds the installed library on its own, so `--database` is optional.
- **Not shipped:** no forged members come with this kit. Every machine forges its own.

## Tests

```bash
python -m unittest discover -s tests                         # installer
(cd specialist-council && python -m unittest discover -s tests)
(cd plugins/agent-arena-mode && python -m unittest discover -s tests)
```

`python scripts/scan.py` checks the tree for secrets and machine-specific paths. Run it before every push. `python scripts/scan.py --public` also fails on any vendored item without a clear licence.

## Updating the kit from a working machine

This repo is the canonical source: on the maintainer machine it lives at `~/code/claude-kit`, and the live install's `moaa` marketplace points at it. Edit here, bump the plugin version in `plugins/<name>/.claude-plugin/plugin.json`, then rerun the installer. It runs `claude plugin marketplace update moaa` before installing. Plugin versions that were tested together are recorded as `tested_version` in `config/kit.json`.

See [THIRD_PARTY.md](THIRD_PARTY.md) for the source and licence of everything vendored or referenced.

## Author and licence

MOAA is created and maintained by **Ahmad Hammoud** ([@ahmadhammoud56](https://github.com/ahmadhammoud56)). To cite it, use [CITATION.cff](CITATION.cff); GitHub shows a "Cite this repository" button.

MOAA's own code is released under the [MIT licence](LICENSE). Vendored third-party plugins and skills keep their own licences: MIT and Apache-2.0, listed in [NOTICE](NOTICE). Plugins installed from other marketplaces are fetched from their authors and are not redistributed here.
