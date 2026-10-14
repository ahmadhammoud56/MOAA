# Contributing to MOAA

Thanks for helping. Issues and pull requests are welcome: bug reports, installer fixes, new council roles, arena improvements, docs.

## Ground rules

- **Never commit secrets or personal paths.** `python scripts/scan.py --public` must pass. CI runs it on every push.
- **Third-party code stays upstream.** To add a plugin from another project, reference it in the catalog (see below); don't copy it in. Vendoring is only for MOAA's own plugins, or for third-party code that has a licence or recorded permission (see `THIRD_PARTY.md`).
- **Model and effort presets live in the plugins.** Change a council role in `plugins/specialist-council/profile.json`, then run `python plugins/specialist-council/council.py apply` and `python scripts/models_doc.py`. Arena presets live in `plugins/agent-arena-mode/scripts/arena.py`.

## Development setup

```bash
git clone https://github.com/ahmadhammoud56/MOAA.git && cd MOAA
python -m unittest discover -s tests
(cd plugins/specialist-council && python -m unittest discover -s tests)
(cd plugins/agent-arena-mode && python -m unittest discover -s tests)
python scripts/scan.py --public
python scripts/models_doc.py --check
claude plugin validate .
```

`python scripts/install.py --doctor` runs all of these (plus the War Room suites, the catalog check and validation of every plugin) in one go.

Everything is Python standard library; no `pip install` is needed for development. To try the installer without touching your real setup, point it at an empty config dir:

```bash
CLAUDE_CONFIG_DIR=/tmp/moaa-test ./install.sh --dry-run
```

## Common changes

| Change | Where | Then run |
|---|---|---|
| Council role preset (model/effort) | `plugins/specialist-council/profile.json` | `council.py apply`, `scripts/models_doc.py`; `council.py diff` to review the shift |
| New council role | `profile.json`, `agents/council-<role>.md`, a role family file in `skills/specialist-council/references/` | `council.py apply`, council tests |
| Arena mode or library logic | `plugins/agent-arena-mode/` | arena tests |
| Add or bump a third-party plugin | install it locally, add it to `config/kit.json` | `scripts/sync_catalog.py` (re-pins and regenerates the README plugin list) |
| Installer behaviour | `scripts/install.py` | installer tests, then a dry run in an empty `CLAUDE_CONFIG_DIR` |
| Update a vendored skill | `config/kit.json` `vendored_skills` | `scripts/sync_skills.py [NAME]`, review the diff, fix version labels in THIRD_PARTY.md |

Bump the plugin `version` in `plugins/<name>/.claude-plugin/plugin.json` when you change a MOAA plugin, and add a line to `CHANGELOG.md`.

## Pull requests

- Keep each PR to one topic, and say how you tested it (which suites, which OS).
- CI must be green: tests, scans and plugin validation on Linux, macOS and Windows, plus a clean install on Linux and macOS.
- By contributing you agree that your contribution is licensed under the MIT licence of this repository.

## Reporting bugs and security issues

Use the issue templates for bugs and plugin requests. Report security problems privately; see [SECURITY.md](SECURITY.md).
