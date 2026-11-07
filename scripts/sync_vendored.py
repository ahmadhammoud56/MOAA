#!/usr/bin/env python3
"""Keep MOAA's vendored plugins (copies of other people's plugins, listed under `vendored_plugins` in
config/kit.json) in step with upstream. Standard library only.

  python scripts/sync_vendored.py --check          which vendored plugins have a newer upstream release or commit
  python scripts/sync_vendored.py NAME [--ref TAG]  copy that release over plugins/NAME, re-apply its recorded patch,
                                                    validate and test it, and record the new version

The sync never deletes: files that upstream dropped are listed for you to remove. MOAA's own files in the folder
(MODIFICATIONS.md, PERMISSION.md, the patch) are kept. Nothing is committed or installed; run
`python scripts/install.py` after reviewing the diff.
"""
import argparse
import fnmatch
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

KIT = Path(__file__).resolve().parents[1]
OWN = ("MODIFICATIONS.md", "PERMISSION.md")  # MOAA's files inside a vendored folder


def api(path, timeout=10):
    req = urllib.request.Request("https://api.github.com/" + path,
                                 headers={"Accept": "application/vnd.github+json", "User-Agent": "moaa-sync"})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310  fixed GitHub API host
        return json.loads(r.read().decode("utf-8"))


def version_tuple(v):
    return tuple(int(x) for x in v.lstrip("v").split(".") if x.isdigit())


def latest(rec):
    """(version, commit) upstream has now: the latest release for repos that publish them, else the newest commit
    that touched the plugin's path."""
    if rec.get("version"):
        tag = api(f"repos/{rec['repo']}/releases/latest")["tag_name"]
        return tag.lstrip("v"), api(f"repos/{rec['repo']}/commits/{tag}")["sha"]
    path = f"&path={rec['path']}" if rec.get("path") else ""
    return "", api(f"repos/{rec['repo']}/commits?per_page=1{path}")[0]["sha"]


def newer(rec, version, commit):
    if rec.get("version"):
        return version_tuple(version) > version_tuple(rec["version"])
    return commit != rec["commit"]


def excluded(rel, patterns):
    return any(rel == p or rel.startswith(p + "/") or fnmatch.fnmatch(rel, p) for p in patterns)


def fetch(repo, ref, dest):
    """Unpack the repo at `ref` into dest; returns the top folder."""
    url = f"https://codeload.github.com/{repo}/tar.gz/{ref}"
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310  fixed GitHub host
        data = r.read()
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tar:
        tar.extractall(dest, filter="data")  # no links out of dest, no absolute paths
    return next(Path(dest).iterdir())


def copy_over(src, dst, rec):
    """Copy upstream files into dst, skipping excludes; returns (copied, gone) relative paths."""
    patterns = rec.get("exclude", [])
    copied = []
    for f in sorted(p for p in src.rglob("*") if p.is_file()):
        rel = f.relative_to(src).as_posix()
        if excluded(rel, patterns):
            continue
        (dst / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, dst / rel)
        copied.append(rel)
    keep = set(copied) | set(OWN) | {rec.get("patch") or ""}
    gone = [p.relative_to(dst).as_posix() for p in dst.rglob("*") if p.is_file()
            and p.relative_to(dst).as_posix() not in keep and not excluded(p.relative_to(dst).as_posix(), patterns)]
    return copied, sorted(gone)


def run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=sys.platform == "win32" and cmd[0] == "claude")
    return r.returncode, (r.stdout + r.stderr).strip()[-1500:]


def sync(name, ref=None, kit=KIT):
    cfg_path = kit / "config" / "kit.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    rec = cfg["vendored_plugins"][name]
    version, commit = (ref.lstrip("v"), api(f"repos/{rec['repo']}/commits/{ref}")["sha"]) if ref else latest(rec)
    dst = kit / "plugins" / name
    with tempfile.TemporaryDirectory() as tmp:
        top = fetch(rec["repo"], commit, tmp)
        copied, gone = copy_over(top / rec.get("path", ""), dst, rec)
    report = {"plugin": name, "from": rec.get("version") or rec["commit"][:7], "to": version or commit[:7],
              "files": len(copied), "dropped_upstream": gone}
    if rec.get("patch"):
        code, out = run(["git", "apply", "--whitespace=nowarn", rec["patch"]], dst)
        report["patch"] = "applied" if code == 0 else "FAILED, re-apply by hand (see MODIFICATIONS.md): " + out
    code, out = run(["claude", "plugin", "validate", "."], dst)
    report["validate"] = "passed" if code == 0 else "FAILED: " + out
    if (dst / "tests").is_dir():
        code, out = run(["claude", "plugin", "test", "."], dst)
        report["test"] = "passed" if code == 0 else "FAILED: " + out
    ok = all(not str(v).startswith("FAILED") for v in report.values())
    if ok:
        rec.update(version=version, commit=commit)
        for p in cfg["plugins"]:
            if p["id"] == f"{name}@moaa" and version:
                p["tested_version"] = version
        cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8", newline="\n")
    report["recorded"] = ok
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("name", nargs="?")
    p.add_argument("--check", action="store_true")
    p.add_argument("--ref", help="a tag or commit instead of the latest")
    a = p.parse_args(argv)
    cfg = json.loads((KIT / "config" / "kit.json").read_text(encoding="utf-8"))["vendored_plugins"]
    if a.check or not a.name:
        stale = 0
        for name, rec in cfg.items():
            try:
                version, commit = latest(rec)
            except OSError as e:
                print(f"{name}: upstream not reachable ({e})")
                continue
            if newer(rec, version, commit):
                stale += 1
                print(f"{name}: {rec.get('version') or rec['commit'][:7]} -> {version or commit[:7]} "
                      f"(python scripts/sync_vendored.py {name})")
            else:
                print(f"{name}: current")
        return 1 if stale and a.check else 0
    if a.name not in cfg:
        p.error(f"unknown vendored plugin; one of {', '.join(cfg)}")
    report = sync(a.name, a.ref)
    print(json.dumps(report, indent=2))
    return 0 if report["recorded"] else 1


if __name__ == "__main__":
    sys.exit(main())
