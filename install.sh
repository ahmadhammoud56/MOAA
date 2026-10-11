#!/usr/bin/env sh
# MOAA installer (macOS / Linux / Git Bash). Arguments pass through, e.g. --with-claude-mem, --uninstall.
set -e
cd "$(dirname "$0")"
PY=$(command -v python3 || command -v python) || { echo "Python 3.10+ is required" >&2; exit 1; }
exec "$PY" scripts/install.py "$@"
