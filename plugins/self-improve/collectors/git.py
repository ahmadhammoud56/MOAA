#!/usr/bin/env python3
"""Compact facts from recent git history, for the self-improve loop.

Usage: python git.py [--days 7] [--repos <data folder>/repos.txt]

For each repo listed in repos.txt (one path per line, `~` allowed, `#` comments), runs only
read-only `git log` and prints Markdown: commit count, recent subjects, most-changed files
and folders, and fix/revert/retry commits (signs of rework). Home paths and e-mails are
redacted. Never writes, deletes, fetches or pushes. The data folder is $SELF_IMPROVE_HOME,
or ~/self-improve. Standard library only.
"""
import argparse
from collections import Counter
from datetime import datetime
import os
from pathlib import Path
import re
import subprocess
import sys

HOME = str(Path.home())
DATA = Path(os.environ.get("SELF_IMPROVE_HOME") or Path.home() / "self-improve").expanduser()
REWORK = re.compile(r"\b(fix(es|ed)?|revert|retry|again|oops|typo|hotfix|undo|broken)\b", re.I)


def redact(text):
    for h in sorted({HOME, HOME.replace("\\", "/")}, key=len, reverse=True):
        text = re.sub(re.escape(h), "~", text, flags=re.I)
    return re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", text)


def git(repo, *args):
    run = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                         encoding="utf-8", errors="replace")
    return run.stdout if run.returncode == 0 else ""


def summarize(repo, days):
    log = git(repo, "log", f"--since={days}.days", "--no-merges", "--numstat", "--format=@@%h\t%ad\t%s", "--date=short")
    commits, files = [], Counter()
    for line in log.splitlines():
        if line.startswith("@@"):
            commits.append(line[2:].split("\t", 2))
        elif line.strip():
            parts = line.split("\t")
            if len(parts) == 3:
                added, removed, name = parts
                files[name] += (int(added) if added.isdigit() else 0) + (int(removed) if removed.isdigit() else 0)
    folders = Counter()
    for name, n in files.items():
        folders[name.split("/")[0] if "/" in name else "(root)"] += n
    return commits, files, folders


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--repos", default=str(DATA / "repos.txt"))
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"# Git activity, last {args.days} days ({datetime.now():%Y-%m-%d})\n")
    repos = Path(args.repos)
    if not repos.is_file():
        print(f"- no repo list at {redact(str(repos))}: add one repo path per line there (selfimprove.py init makes it).")
        return 0
    for raw in repos.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        repo = Path(raw.replace("~", HOME, 1) if raw.startswith("~") else raw)
        name = redact(str(repo))
        if not (repo / ".git").exists():
            print(f"## {name}\n\n- not a git repo (skipped)\n")
            continue
        commits, files, folders = summarize(repo, args.days)
        rework = [c for c in commits if REWORK.search(c[2])]
        print(f"## {name}\n")
        print(f"{len(commits)} commits · {len(files)} files touched · {len(rework)} fix/revert/retry commits\n")
        if folders:
            print("- busiest folders: " + ", ".join(f"{d} ({n} lines)" for d, n in folders.most_common(5)))
        if files:
            print("- most-changed files: " + ", ".join(f"{redact(f)} ({n})" for f, n in files.most_common(5)))
        for h, day, subject in commits[:12]:
            print(f"- {day} {h} {redact(subject)[:110]}")
        if len(commits) > 12:
            print(f"- … {len(commits) - 12} more commits")
        if rework:
            print("- rework: " + "; ".join(redact(c[2])[:70] for c in rework[:6]))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
