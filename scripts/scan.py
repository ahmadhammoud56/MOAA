#!/usr/bin/env python3
"""Pre-push scan: secrets and machine-specific paths. Exit 1 on findings. Standard library only."""
import json
from pathlib import Path
import re
import sys

KIT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", "__pycache__", ".claude-flow", ".claude", "node_modules", ".venv", ".briefs"}  # .briefs: prompt-refiner, git-ignored
PATTERNS = {
    "anthropic key": r"sk-ant-[A-Za-z0-9_-]{20,}",
    "github token": r"gh[pousr]_[A-Za-z0-9]{30,}",
    "aws key": r"AKIA[0-9A-Z]{16}",
    "private key": r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    "generic secret": r"(?i)(api[_-]?key|secret|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{24,}['\"]",
    "user home path": r"(?i)[A-Z]:[\\/]+Users[\\/]+(?!<you>|you\b|USER|%)[^\\/\s\"']+|/c/Users/[^/\s\"']+|/home/(?!u/|user/)[a-z][^/\s\"']*",
}
# Known, reviewed hits that are not secrets (fixtures and placeholders).
ALLOW = [
    re.compile(r"ghp_abcdefgh"),                      # flightdeck test fixture
    re.compile(r"^/c/Users/(\.\.\.|\[\^)$"),            # comments and this file's own regex
    re.compile(r"^C:\\\\Users\\\\me$"),                # flightdeck test fixture
    re.compile(r"^/home/snp$"),                        # path quoted in the Paper2Agent paper
    re.compile(r"(?i)^(?:[a-z]:[\\/]+users[\\/]+|/home/)(?:me|demo|dev|mara(?:%20schwartz)?)$"),  # prismantis fixtures
]


def scan(root=KIT):
    findings = []
    for path in root.rglob("*"):
        if path.is_dir() or SKIP_DIRS & set(path.relative_to(root).parts) or path == Path(__file__).resolve():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            for label, pattern in PATTERNS.items():
                for match in re.finditer(pattern, line):
                    if not any(a.search(match.group(0)) for a in ALLOW):
                        findings.append(f"{path.relative_to(root).as_posix()}:{lineno}: {label}: {match.group(0)[:60]}")
    return findings


def licence_gaps(root=KIT):
    """Public-release check: every vendored plugin/skill/agent has a LICENSE or is declared own work."""
    kit = json.loads((root / "config" / "kit.json").read_text(encoding="utf-8"))
    own = set(kit.get("own_work", []))
    gaps = [f"{rel}: {why}" for rel, why in kit.get("public_blockers", {}).items() if (root / rel).exists()]
    units = [p for base in ("plugins", "skills") for p in sorted((root / base).iterdir()) if p.is_dir()]
    units += sorted((root / "agents").glob("*.md"))
    for unit in units:
        rel = unit.relative_to(root).as_posix()
        permitted = rel in kit.get("redistribution_permission", {}) and (unit / "PERMISSION.md").is_file()
        if rel in own or permitted or (unit.is_dir() and (unit / "LICENSE").is_file()):
            continue
        gaps.append(f"{rel}: no LICENSE and not declared own_work")
    return gaps


if __name__ == "__main__":
    hits = scan()
    if "--public" in sys.argv:
        hits += [f"licence: {g}" for g in licence_gaps()]
    print("\n".join(hits) if hits else "scan: clean")
    sys.exit(1 if hits else 0)
