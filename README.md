# claude-kit

A complete Claude Code setup: 94 plugins from 14 marketplaces, the Specialist Council (60 role agents), the Agent Arena (which forges new council members from proven agents), 10 standalone skills, and the `rea` and `ansys` MCP servers. One command installs all of it.

This repository is private. Clone it with SSH.

## Requirements

- Claude Code 2.1.296 or newer, logged in (`claude --version`). The council pins `claude-*-5-5` and `claude-fable-5-1` model IDs, and older builds reject them.
- git, Python 3.10+, and Node 20+ (for `npx`).
- Optional: an Ansys install, so the ansys MCP server can do real work. Without one it installs but stays idle.
- Windows: if your Claude config dir has a long path, marketplace clones can fail with `Filename too long`. Run `git config --global core.longpaths true` once to fix it.

## Install

```bash
git clone git@github.com:ahmadhammoud56/claude-kit.git
cd claude-kit
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
| `--uninstall` | Reverse what the kit recorded in `~/.claude/.claude-kit-manifest.json`. |

Restart Claude Code afterwards.

The installer respects `CLAUDE_CONFIG_DIR`, so you can trial it in a throwaway config directory:

```bash
CLAUDE_CONFIG_DIR=/tmp/kit-test ./install.sh --skip-ansys
```

## What the installer does

1. Adds each needed marketplace: the upstream GitHub ones, plus this repo as the `claude-kit` marketplace for the vendored plugins.
2. Installs every plugin in `config/kit.json` at user scope. prismantis is installed disabled; enable it with `claude plugin enable prismantis@claude-kit`.
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

## Council and arena

- The **Specialist Council** (`specialist-council/`) picks 2 to 3 role agents per task. Each role's model and effort come from `profile.json`; `council.py resolve` prints them.
- The **Agent Arena** (`plugins/agent-arena-mode/`) runs tournaments and other modes. It scores entries with a judge and keeps a library of winners in SQLite.
- **Forging:** an arena agent becomes a council member after it is validated in 2 or more runs with every score at least 85 and a spread of at most 10. Run:

  ```bash
  python <arena plugin>/scripts/library.py promote --id <agent id>
  ```

  This writes `council-forged-<slug>` and a knowledge base under `~/.claude/skills/specialist-council/forged/`.
- **Suspension:** if a later validation fails, the member is suspended and its agent card is unregistered. `council.py check` checks forged members too.
- No forged members ship with this kit. Every machine forges its own.

## Tests

```bash
python -m unittest discover -s tests                         # installer
(cd specialist-council && python -m unittest discover -s tests)
(cd plugins/agent-arena-mode && python -m unittest discover -s tests)
```

`python scripts/scan.py` checks the tree for secrets and machine-specific paths. Run it before every push.

## Updating the kit from a working machine

Edit the vendored copies here, bump the plugin version in `plugins/<name>/.claude-plugin/plugin.json`, then rerun the installer. It runs `claude plugin marketplace update claude-kit` before installing. Plugin versions that were tested together are recorded as `tested_version` in `config/kit.json`.

See [THIRD_PARTY.md](THIRD_PARTY.md) for the source and licence of everything vendored or referenced.
