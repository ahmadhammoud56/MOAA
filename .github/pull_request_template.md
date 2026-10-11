## What and why

## How I tested it
- [ ] `python -m unittest discover -s tests` (plus the council and arena suites if touched)
- [ ] `python scripts/scan.py --public`
- [ ] `python scripts/models_doc.py --check` (if presets changed)
- [ ] Installer dry run in an empty `CLAUDE_CONFIG_DIR` (if the installer changed)
- OS:

## Checklist
- [ ] Plugin `version` bumped if a MOAA plugin changed
- [ ] `CHANGELOG.md` updated
- [ ] No secrets or personal paths
