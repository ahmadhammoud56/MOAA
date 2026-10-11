#!/usr/bin/env python3
"""Build a clean distributable ZIP of the plugin and verify its contents.

Usage: python scripts/package.py OUT.zip
Includes plugin source only; excludes databases, caches, run data, locks, archives, and credentials.
"""
import fnmatch
import hashlib
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
NAME = ROOT.name
REQUIRED = [".claude-plugin/plugin.json", "agents/arena-judge.md", "scripts/arena.py", "scripts/library.py",
            "README.md", "VALIDATION.md", "LICENSE"] + [
    f"skills/{s}/SKILL.md" for s in
    ("judge", "tournament", "swarm", "league", "evolution", "synthesis", "redteam", "cascade", "library")]
EXCLUDE = ["*.sqlite*", "*.db", "*.db-*", "*.pyc", "*.lock", "*.tmp", ".env*", "*.pem", "*.key", "*credential*", "*.zip"]
EXCLUDE_DIRS = {"__pycache__", ".agent-arena", ".git", ".pytest_cache", "loaded"}


def files():
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        hidden = any(part.startswith(".") and part != ".claude-plugin" for part in rel.parts[:-1])  # tool caches
        if path.is_file() and not hidden and not EXCLUDE_DIRS & set(rel.parts) and \
                not any(fnmatch.fnmatch(path.name.lower(), pattern) for pattern in EXCLUDE):
            yield rel.as_posix(), path


def build(out):
    out = Path(out).resolve()
    chosen = dict(files())
    missing = [r for r in REQUIRED if r not in chosen]
    if missing:
        raise SystemExit("missing required files: " + ", ".join(missing))
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for rel, path in chosen.items():
            archive.write(path, f"{NAME}/{rel}")
    with zipfile.ZipFile(out) as archive:  # verify byte-for-byte
        for rel, path in chosen.items():
            if hashlib.sha256(archive.read(f"{NAME}/{rel}")).digest() != hashlib.sha256(path.read_bytes()).digest():
                raise SystemExit(f"archive mismatch: {rel}")
    return out, sorted(chosen)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    target, names = build(sys.argv[1])
    print(f"{target}: {len(names)} files")
    for name in names:
        print("  " + name)
