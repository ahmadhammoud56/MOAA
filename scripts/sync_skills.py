#!/usr/bin/env python3
"""Re-sync the vendored skills from their upstream repos. Standard library and git only.

Each vendored skill's upstream repo, path and commit live in config/kit.json under "vendored_skills"; THIRD_PARTY.md
names the same commits. Files MOAA adds itself (LICENSE, NOTICE) are never touched or compared.

  python scripts/sync_skills.py --check          exit 1 if any skill differs from its upstream's current HEAD
  python scripts/sync_skills.py --check --pinned exit 1 if any skill differs from the commit recorded in kit.json
  python scripts/sync_skills.py                  update every vendored skill to upstream HEAD
  python scripts/sync_skills.py networkx         update one skill (with the others from the same repo, which share a commit)
  python scripts/sync_skills.py --ref v1.5       update to a tag, branch or commit instead of HEAD

An update rewrites the skill folders, the commits in kit.json and the short commits in THIRD_PARTY.md. Review the
diff, fix any version label in THIRD_PARTY.md by hand, and add a CHANGELOG entry.
"""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

KIT = Path(__file__).resolve().parents[1]
KIT_JSON = KIT / "config" / "kit.json"
THIRD_PARTY = KIT / "THIRD_PARTY.md"
KEEP = {"LICENSE", "NOTICE"}  # MOAA's own files in a vendored skill's root


def tree(root):
    """{relative posix path: bytes with LF line endings} for every file under root, minus KEEP files at its top."""
    root = Path(root)
    return {p.relative_to(root).as_posix(): p.read_bytes().replace(b"\r\n", b"\n") for p in sorted(root.rglob("*"))
            if p.is_file() and "__pycache__" not in p.parts and not (p.parent == root and p.name in KEEP)}


def git(cwd, *args):
    out = subprocess.run(["git", "-c", "core.longpaths=true", *args], cwd=cwd, capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(f"git {' '.join(args)}: {(out.stderr or out.stdout).strip()[-400:]}")
    return out.stdout.strip()


def fetch(repo, ref, paths, work):
    """Shallow, sparse checkout of `paths` at `ref`; returns (full sha, {path: tree})."""
    git(work, "init", "-q")
    git(work, "config", "core.autocrlf", "false")
    git(work, "fetch", "-q", "--depth", "1", "--filter=blob:none", repo, ref)
    git(work, "sparse-checkout", "set", "--no-cone", *[f"/{p.strip('/')}/" for p in paths])
    git(work, "checkout", "-q", "FETCH_HEAD")
    trees = {p: tree(Path(work) / p) if (Path(work) / p).is_dir() else {} for p in paths}
    empty = [p for p, t in trees.items() if not t]
    if empty:  # a moved or deleted upstream folder must never read as "delete every file"
        raise RuntimeError(f"{repo} @ {ref}: no files at {', '.join(empty)}; update the path in config/kit.json")
    return git(work, "rev-parse", "FETCH_HEAD"), trees


def groups(skills):
    """{repo: [skill names]}: skills from one repo are fetched, and updated, together."""
    out = {}
    for name, spec in skills.items():
        out.setdefault(spec["repo"], []).append(name)
    return out


def compare(local, upstream):
    added = sorted(set(upstream) - set(local))
    removed = sorted(set(local) - set(upstream))
    changed = sorted(k for k in set(local) & set(upstream) if local[k] != upstream[k])
    return {"added": added, "removed": removed, "changed": changed}


def summary(d):
    return ", ".join(f"{len(d[k])} {k}" for k in ("added", "removed", "changed") if d[k]) or "identical"


def write_skill(dest, files):
    """Replace a skill folder's contents with `files`, keeping its KEEP files."""
    for p in sorted(dest.rglob("*"), reverse=True):
        if p.is_file() and not (p.parent == dest and p.name in KEEP):
            p.unlink()
        elif p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    for rel, data in files.items():
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("names", nargs="*", help="skills to update (default: all vendored skills)")
    p.add_argument("--check", action="store_true", help="compare only; exit 1 on any difference")
    p.add_argument("--pinned", action="store_true", help="with --check: compare with the recorded commit, not HEAD")
    p.add_argument("--ref", default="HEAD", help="upstream ref to update to (default HEAD)")
    a = p.parse_args(argv)
    kit = json.loads(KIT_JSON.read_text(encoding="utf-8"))
    skills = kit["vendored_skills"]
    unknown = [n for n in a.names if n not in skills]
    if unknown:
        p.error(f"not vendored skills: {', '.join(unknown)}; one of: {', '.join(skills)}")
    wanted = {r: ns for r, ns in groups(skills).items() if not a.names or set(ns) & set(a.names)}
    differs, third_party = False, THIRD_PARTY.read_text(encoding="utf-8")
    for repo, names in wanted.items():
        recorded = skills[names[0]]["commit"]
        ref = recorded if a.check and a.pinned else a.ref
        with tempfile.TemporaryDirectory(prefix="moaa-") as work:  # a short path: deep upstream trees hit MAX_PATH
            sha, trees = fetch(repo, ref, [skills[n]["path"] for n in names], work)
        group_differs = False
        for name in names:
            d = compare(tree(KIT / "skills" / name), trees[skills[name]["path"]])
            same = not any(d.values())
            group_differs |= not same
            where = f"{repo.removeprefix('https://github.com/')} @ {sha[:7]}"
            print(f"  {'ok' if same else 'DIFFERS':<8} {name:<28} {summary(d)} vs {where}"
                  + ("" if sha == recorded else f" (recorded {recorded[:7]})"))
            if a.check and not same:
                for k in ("added", "removed", "changed"):
                    for f in d[k][:8]:
                        print(f"           {k}: {f}")
            if not a.check and not same:
                write_skill(KIT / "skills" / name, trees[skills[name]["path"]])
        differs |= group_differs
        # The recorded commit moves only when content changed: an upstream commit that left these skills alone
        # would otherwise churn kit.json and THIRD_PARTY.md. Skills from one repo always share one commit.
        if not a.check and group_differs and sha != recorded:
            for name in names:
                skills[name]["commit"] = sha
            third_party = third_party.replace(f"`{recorded[:7]}`", f"`{sha[:7]}`")
    if a.check:
        print("[sync_skills] " + ("every vendored skill matches upstream" if not differs else
                                  "differences found: run scripts/sync_skills.py to update, then review the diff"))
        return 1 if differs else 0
    KIT_JSON.write_text(json.dumps(kit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    THIRD_PARTY.write_text(third_party, encoding="utf-8", newline="\n")
    print("[sync_skills] updated; review `git diff`, adjust version labels in THIRD_PARTY.md and add a CHANGELOG entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
