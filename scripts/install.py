#!/usr/bin/env python3
"""MOAA (Mother of All Agents) installer. Standard library only; safe to rerun.

  python scripts/install.py                 core profile: 10 plugins, council, arena, skills, rea MCP
  python scripts/install.py --full          everything: 93 plugins (95 with --with-claude-mem) + ansys MCP
  python scripts/install.py --with-claude-mem
  python scripts/install.py --skip-mcp      no rea/ansys MCP servers
  python scripts/install.py --skip-ansys    keep rea, skip the ansys MCP server
  python scripts/install.py --dry-run       print what would run, change nothing
  python scripts/install.py --uninstall     reverse what the kit recorded in its manifest
  python scripts/install.py --status        compare the install with this repo: versions, drift, edited copies
  python scripts/install.py --doctor        run every pre-commit check (all test suites, scans, validation)

The Claude config dir is $CLAUDE_CONFIG_DIR or ~/.claude. Existing settings are backed up and merged,
never overwritten: lists are unioned, and env keys and other defaults are only added when absent.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time

KIT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KIT / "scripts"))
from sync_catalog import ALIASES  # noqa: E402  reserved upstream names and their moaa catalog aliases
WINDOWS = platform.system() == "Windows"
MANIFEST = ".moaa-manifest.json"
LEGACY_MANIFEST = ".claude-kit-manifest.json"  # pre-rename name; read once, then replaced


def claude_home():
    return Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude").expanduser()


def log(msg):
    print(f"[moaa] {msg}", flush=True)


class Runner:
    def __init__(self, dry):
        self.dry = dry
        self.claude = shutil.which("claude")

    def run(self, args, check=False):
        if args[0] == "claude":
            args = [self.claude or "claude"] + args[1:]
        if self.dry:
            log("would run: " + " ".join(args))
            return subprocess.CompletedProcess(args, 0, "", "")
        result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")
        if check and result.returncode:
            raise RuntimeError(f"{' '.join(args)} failed: {(result.stderr or result.stdout).strip()[-500:]}")
        return result


def council_permissions(home):
    """Allow rules for the council plugin's council.py. Its cache path carries a version, hence the wildcards; no space
    after `council.py` because the quoted path ends in `council.py"`."""
    rules = [f"Bash({py} *specialist-council*council.py*)" for py in ("python", "python3", "py")]
    rules.append("PowerShell(python *specialist-council*council.py*)")
    return rules + war_room_permissions()


# War Room subcommands that only read, message, or stop. toggle, launch, integrate, finish, shutdown and approve are
# left out on purpose: they stay behind a permission prompt so arming and launching remain the user's own decision.
WAR_ROOM_SAFE = ("plan", "status", "post", "send", "wake", "app", "list", "measure", "tile", "merge",
                 "pause", "unpause", "stop", "resume", "demo")


def war_room_permissions():
    rules = []
    for sub in WAR_ROOM_SAFE:
        rules += [f"Bash({py} *war-room*warroom.py* {sub}*)" for py in ("python", "python3", "py")]
        rules.append(f"PowerShell(python *war-room*warroom.py* {sub}*)")
    return rules


def merge_settings(current, kit_settings, allow, plugins):
    """Return (merged, added) without mutating current. `added` lists exactly what uninstall must remove."""
    merged = copy.deepcopy(current)
    added = {"allow": [], "deny": [], "env": [], "defaults": [], "enabledPlugins": []}
    perms = merged.setdefault("permissions", {})
    for key, rules in (("allow", allow), ("deny", kit_settings.get("permissions_deny", []))):
        existing = perms.setdefault(key, [])
        for rule in rules:
            if rule not in existing:
                existing.append(rule)
                added[key].append(rule)
    env = merged.setdefault("env", {})
    for key, value in kit_settings.get("env", {}).items():
        if key not in env:
            env[key] = value
            added["env"].append(key)
    for key, value in kit_settings.get("defaults", {}).items():
        if key not in merged:
            merged[key] = copy.deepcopy(value)
            added["defaults"].append(key)
    enabled = merged.setdefault("enabledPlugins", {})
    for pid, on in plugins.items():
        if pid not in enabled:
            enabled[pid] = on
            added["enabledPlugins"].append(pid)
    return merged, added


def unmerge_settings(current, added):
    merged = copy.deepcopy(current)
    perms = merged.get("permissions", {})
    for key in ("allow", "deny"):
        perms[key] = [r for r in perms.get(key, []) if r not in added.get(key, [])]
    for key in added.get("env", []):
        merged.get("env", {}).pop(key, None)
    for key in added.get("defaults", []):
        merged.pop(key, None)
    for pid in added.get("enabledPlugins", []):
        merged.get("enabledPlugins", {}).pop(pid, None)
    return merged


def read_json(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path, data, dry):
    if dry:
        log(f"would write {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def preflight(args):
    problems = []
    if sys.version_info < (3, 10):
        problems.append("Python 3.10+ required")
    for tool in ("claude", "git"):
        if not shutil.which(tool):
            problems.append(f"`{tool}` not found on PATH")
    if not args.skip_mcp and not shutil.which("npx"):
        problems.append("`npx` (Node 20+) not found; install Node or pass --skip-mcp")
    if problems:
        raise SystemExit("[moaa] preflight failed:\n  - " + "\n  - ".join(problems))


def marketplace_names(r):
    out = r.run(["claude", "plugin", "marketplace", "list", "--json"])
    try:
        return {m["name"] for m in json.loads(out.stdout or "[]")}
    except ValueError:
        return set()


def installed_plugins(home):
    return set(read_json(home / "plugins" / "installed_plugins.json", {}).get("plugins", {}))


def install(args):
    preflight(args)
    home = claude_home()
    r = Runner(args.dry_run)
    kit = read_json(KIT / "config" / "kit.json", None)
    manifest = read_json(home / MANIFEST, None) or read_json(home / LEGACY_MANIFEST, {})
    record = {"kit_version": kit["version"], "kit_dir": str(KIT), "installed": time.time(),
              "marketplaces": manifest.get("marketplaces", []), "plugins": manifest.get("plugins", []),
              "skills": manifest.get("skills", []), "agents": manifest.get("agents", []),
              "mcp": manifest.get("mcp", []), "settings_added": manifest.get("settings_added", {})}
    plugins = [p for p in kit["plugins"]
               if (args.full or p.get("profile") == "core")
               and (not p.get("optional") or (args.with_claude_mem and p["optional"] == "claude-mem"))]
    log(f"profile: {'full' if args.full else 'core'} ({len(plugins)} plugins)")
    before = installed_plugins(home)

    def target(p):
        """Install id: the pinned moaa catalog entry by default; upstream marketplace with --upstream, or when the
        plugin is already installed from its upstream marketplace (keeps that install and its data untouched)."""
        name, market = p["id"].split("@")
        if market == kit["name"] or args.upstream or p["id"] in before:
            return p["id"]
        return f"{ALIASES.get(name, name)}@{kit['name']}"

    for p in plugins:
        p["target"] = target(p)
    needed = {p["target"].split("@")[1] for p in plugins}

    log(f"Claude home: {home}")
    have = marketplace_names(r)
    sources = dict(kit["marketplaces"], **{kit["name"]: str(KIT)})
    for name, source in sources.items():
        if name not in needed or name in have:
            continue
        log(f"adding marketplace {name}")
        r.run(["claude", "plugin", "marketplace", "add", source, "--scope", "user"], check=True)
        if name not in record["marketplaces"]:
            record["marketplaces"].append(name)
    if kit["name"] in have:  # pick up local edits to the vendored plugins
        r.run(["claude", "plugin", "marketplace", "update", kit["name"]])

    failed = []
    for p in plugins:
        pid = p["target"]
        if pid in before:
            if pid.endswith("@" + kit["name"]) and pid == p["id"]:  # vendored plugins: pick up new versions from this repo
                r.run(["claude", "plugin", "update", pid, "--scope", "user"])
            continue
        log(f"installing {pid}")
        result = r.run(["claude", "plugin", "install", pid, "--scope", "user"])
        if result.returncode:
            failed.append(pid)
            log(f"  FAILED: {(result.stderr or result.stdout).strip()[-300:]}")
            continue
        if pid not in record["plugins"]:
            record["plugins"].append(pid)
        if not p["enabled"]:
            r.run(["claude", "plugin", "disable", pid, "--scope", "user"])

    skills_dir = home / "skills"
    for name in kit["skills"]:
        target = skills_dir / name
        if target.exists() and name not in record["skills"]:
            if not shipped_by_moaa(name, target):
                log(f"skill {name} already present and not kit-managed; leaving it")
                continue
            log(f"skill {name}: an unmodified earlier MOAA copy; updating")
        log(f"skill {name}")
        if not args.dry_run:
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(KIT / "skills" / name, target, ignore=shutil.ignore_patterns("__pycache__"))
        if name not in record["skills"]:
            record["skills"].append(name)

    council = KIT / "plugins" / "specialist-council" / "council.py"
    log("specialist council: plugin specialist-council@moaa; moving any pre-plugin standalone install")
    if not args.dry_run:
        migrated = r.run([sys.executable, str(council), "migrate", "--home", str(home)], check=True)
        log("  " + " ".join(migrated.stdout.split()))
    if "specialist-council" in record["skills"]:  # now a plugin, no longer a kit-copied skill
        record["skills"].remove("specialist-council")
    for name in kit["agents"]:
        target = home / "agents" / name
        if target.exists() and name not in record["agents"]:
            continue
        if not args.dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(KIT / "agents" / name, target)
        if name not in record["agents"]:
            record["agents"].append(name)

    settings_path = home / "settings.json"
    current = read_json(settings_path, {})
    if settings_path.is_file() and not args.dry_run:
        shutil.copy2(settings_path, settings_path.with_name(f"settings.json.bak-{time.strftime('%Y%m%d-%H%M%S')}"))
    merged, added = merge_settings(current, kit["settings"], council_permissions(home),
                                   {p["target"]: p["enabled"] for p in plugins})
    for key, values in added.items():
        prior = record["settings_added"].setdefault(key, [])
        prior += [v for v in values if v not in prior]
    write_json(settings_path, merged, args.dry_run)
    log("settings merged (backup written next to settings.json)")

    if not args.skip_mcp:
        install_mcp(r, kit["mcp"], record, home, skip_ansys=args.skip_ansys or not args.full, dry=args.dry_run)

    write_json(home / MANIFEST, record, args.dry_run)
    if not args.dry_run:
        (home / LEGACY_MANIFEST).unlink(missing_ok=True)
    check = r.run([sys.executable, str(council), "check"])
    log("council check: " + ("ok" if check.returncode == 0 else check.stderr.strip()))
    if failed:
        log("plugins that failed to install (rerun to retry): " + ", ".join(failed))
    log("done. Restart Claude Code to load new plugins.")
    return 1 if failed or check.returncode else 0


def tree_text(files):
    """{relative posix path: content without CRs}, so a CRLF checkout and an LF copy compare equal."""
    return {k: v.replace(b"\r\n", b"\n") for k, v in files.items()}


def shipped_by_moaa(name, target):
    """True when an installed skill is byte-identical (line endings aside) to a version this repo shipped: an
    install made before the manifest tracked skills. A copy the user edited never matches, so it is left alone."""
    installed = tree_of(target)
    git =lambda *a: subprocess.run(["git", "-C", str(KIT), *a], capture_output=True)  # noqa: E731
    log_ = git("log", "--format=%H", "--", f"skills/{name}")
    for commit in (log_.stdout.decode().split() if log_.returncode == 0 else []):
        paths = git("ls-tree", "-r", "--name-only", commit, f"skills/{name}/").stdout.decode().split("\n")
        shipped = {p[len(f"skills/{name}/"):]: git("show", f"{commit}:{p}").stdout for p in paths if p}
        if tree_text(shipped) == installed:
            return True
    return False


def mcp_outdated(name, spec, record, home):
    """True when MOAA added this MCP server (it is in the manifest) and its configured command or args differ from the
    pinned spec. A server the user configured themselves is never touched."""
    current = (read_json(home.parent / ".claude.json", {}) or {}).get("mcpServers", {}).get(name)
    if not current or (current.get("command"), current.get("args")) == (spec.get("command"), spec.get("args")):
        return False
    if name in record.get("mcp", []):
        return True
    # Installed before the manifest tracked MCP servers: still ours when only the pinned version differs.
    unpin = lambda c: (c.get("command"), [re.sub(r"@\d+(\.\d+)*$", "@*", str(a)) for a in c.get("args") or []])  # noqa: E731
    return unpin(current) == unpin(spec)


def rea_spec(mcp):
    rea = mcp["rea"]
    command, args = (("cmd", ["/c", rea["command"]] + rea["args"]) if WINDOWS else (rea["command"], rea["args"]))
    return {"type": "stdio", "command": command, "args": args, "env": {}}


def install_mcp(r, mcp, record, home, skip_ansys, dry):
    def add(name, spec):
        if r.run(["claude", "mcp", "get", name]).returncode == 0 and not dry:
            if not mcp_outdated(name, spec, record, home):
                log(f"MCP {name} already configured; leaving it")
                return
            log(f"MCP {name}: MOAA installed it at an older pin; updating")  # e.g. rea-agents@6.3.0 -> 6.4.0
            r.run(["claude", "mcp", "remove", "--scope", "user", name])
        log(f"MCP {name}")
        r.run(["claude", "mcp", "add-json", "--scope", "user", name, json.dumps(spec)], check=True)
        if name not in record["mcp"]:
            record["mcp"].append(name)

    add("rea", rea_spec(mcp))
    if skip_ansys:
        return
    spec = mcp["ansys"]
    root = home / "kit-tools" / "ansys-mcp-server"
    log(f"ansys MCP server in {root} (needs a local Ansys install to do real work)")
    if not dry:
        if not (root / ".git").is_dir():
            root.parent.mkdir(parents=True, exist_ok=True)
            r.run(["git", "clone", spec["repo"], str(root)], check=True)
            r.run(["git", "-C", str(root), "checkout", "--quiet", spec["commit"]], check=True)
            r.run(["git", "-C", str(root), "apply", str(KIT / spec["patch"])], check=True)
        venv = root / ".venv"
        if not venv.is_dir():
            r.run([sys.executable, "-m", "venv", str(venv)], check=True)
        python = venv / ("Scripts/python.exe" if WINDOWS else "bin/python")
        pip = r.run([str(python), "-m", "pip", "install", "--quiet", "-r", str(KIT / spec["lock"])])  # tested versions
        if pip.returncode == 0:
            pip = r.run([str(python), "-m", "pip", "install", "--quiet", "--no-deps", "-e", str(root)])
        if pip.returncode:
            log("  ansys pip install failed; skipping ansys MCP: " + pip.stderr.strip()[-300:])
            return
    else:
        python = root / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")
    add("ansys", {"type": "stdio", "command": python.as_posix(), "args": ["-m", spec["module"]], "env": {}})


def tree_of(root):
    return tree_text({p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*")
                      if p.is_file() and "__pycache__" not in p.parts})


def copy_state(name, repo_path, target, recorded, is_skill):
    """State of an installed skill or agent against this repo's copy, and what the installer would do with it."""
    if not target.exists():
        return "missing", "rerun the installer"
    same = tree_of(target) == tree_of(repo_path) if is_skill else \
        target.read_bytes().replace(b"\r\n", b"\n") == repo_path.read_bytes().replace(b"\r\n", b"\n")
    if same:
        return "ok", ""
    if is_skill and shipped_by_moaa(name, target):
        return "outdated", "an unmodified older MOAA copy; rerun the installer"
    if recorded:
        return "modified", "edited; MOAA recorded it, so the installer will overwrite it"
    return "modified", "edited or your own; the installer leaves it alone"


def status_rows(home, kit):
    """[(kind, name, state, detail)] comparing the install in `home` with this repo. States: ok, outdated (a MOAA
    item older than the repo; rerun the installer), drift (a third-party plugin at another version than the tested
    one), modified (edited after install), missing, info."""
    rows = []
    record = read_json(home / MANIFEST, None) or read_json(home / LEGACY_MANIFEST, {})
    if record.get("kit_version") and record["kit_version"] != kit["version"]:
        rows.append(("moaa", "kit", "outdated", f"installed from {record['kit_version']}; repo is {kit['version']}"))
    elif record:
        rows.append(("moaa", "kit", "ok", kit["version"]))
    else:
        rows.append(("moaa", "kit", "missing", f"no {MANIFEST}; the installer has not run for this Claude home"))

    installed = read_json(home / "plugins" / "installed_plugins.json", {}).get("plugins", {})
    by_name = {}
    for p in kit["plugins"]:
        name, market = p["id"].split("@")
        for key in (p["id"], f"{ALIASES.get(name, name)}@{kit['name']}"):
            if key in installed:
                by_name[p["id"]] = (key, (installed[key] or [{}])[0])
                break
    # The profile is not recorded, so a full install is inferred from any full-profile plugin being present.
    full = any(p.get("profile") == "full" and p["id"] in by_name for p in kit["plugins"])
    for p in kit["plugins"]:
        if p["id"] not in by_name:
            if (p.get("profile") == "core" or full) and not p.get("optional"):
                rows.append(("plugin", p["id"], "missing", "rerun the installer"))
            continue
        key, entry = by_name[p["id"]]
        have = entry.get("version", "?")
        if p["id"].endswith("@" + kit["name"]):
            want = read_json(KIT / "plugins" / p["id"].split("@")[0] / ".claude-plugin" / "plugin.json", {}).get("version")
            rows.append(("plugin", key, "ok" if have == want else "outdated",
                         have if have == want else f"installed {have}; repo has {want}"))
            cache = home / "plugins" / "cache" / kit["name"] / p["id"].split("@")[0]
            stale = sorted(d.name for d in cache.iterdir() if d.is_dir() and d.name != have) if cache.is_dir() else []
            if stale:
                rows.append(("cache", key, "info", "old versions left for Claude Code to prune: " + ", ".join(stale)))
        elif have != p["tested_version"]:
            rows.append(("plugin", key, "drift", f"installed {have}; tested {p['tested_version']}"))
        else:
            rows.append(("plugin", key, "ok", have))

    for name in kit["skills"]:
        state, detail = copy_state(name, KIT / "skills" / name, home / "skills" / name, name in record.get("skills", []), True)
        rows.append(("skill", name, state, detail))
    for name in kit["agents"]:
        state, detail = copy_state(name, KIT / "agents" / name, home / "agents" / name, name in record.get("agents", []), False)
        rows.append(("agent", name, state, detail))

    servers = (read_json(home.parent / ".claude.json", {}) or {}).get("mcpServers", {})
    spec = rea_spec(kit["mcp"])
    current = servers.get("rea")
    if not current:
        rows.append(("mcp", "rea", "missing", "rerun the installer (or it was skipped with --skip-mcp)"))
    elif (current.get("command"), current.get("args")) == (spec["command"], spec["args"]):
        rows.append(("mcp", "rea", "ok", kit["mcp"]["rea"]["args"][1]))
    elif mcp_outdated("rea", spec, record, home):
        rows.append(("mcp", "rea", "outdated", f"MOAA's setup at another pin; repo pins {kit['mcp']['rea']['args'][1]}"))
    else:
        rows.append(("mcp", "rea", "modified", "your own setup; the installer leaves it alone"))
    if "ansys" in servers:
        ours = str(home / "kit-tools" / "ansys-mcp-server").replace("\\", "/") in servers["ansys"].get("command", "")
        rows.append(("mcp", "ansys", "ok" if ours else "modified",
                     "" if ours else "configured outside MOAA; the installer leaves it alone"))
    return rows


def status(args):
    home = claude_home()
    kit = read_json(KIT / "config" / "kit.json", None)
    rows = status_rows(home, kit)
    counts = {}
    for kind, name, state, detail in rows:
        counts[state] = counts.get(state, 0) + 1
        if state != "ok" or kind != "plugin" or name.endswith("@" + kit["name"]) or args.verbose:
            print(f"  {state:<9} {kind:<7} {name:<45} {detail}".rstrip())
    print(f"[moaa] {home}: " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items())))
    if counts.get("drift"):
        print("[moaa] drift is informational: upstream-installed plugins move on their own; "
              "`python scripts/sync_catalog.py` re-pins the catalog to what is installed")
    return 1 if counts.get("missing") or counts.get("outdated") else 0


def doctor_checks():
    """(label, argv, cwd) for every check the release routine runs before a commit."""
    py = sys.executable
    plugins = KIT / "plugins"
    checks = [("installer tests", [py, "-m", "unittest", "discover", "-s", "tests"], KIT)]
    for name in ("specialist-council", "agent-arena-mode", "war-room"):
        checks.append((f"{name} tests", [py, "-m", "unittest", "discover", "-s", "tests"], plugins / name))
    checks += [
        ("war-room bus test", [py, "tests/test_bus.py"], plugins / "war-room"),
        ("MODELS.md matches the plugins", [py, "scripts/models_doc.py", "--check"], KIT),
        ("catalog matches installed plugins", [py, "scripts/sync_catalog.py", "--check"], KIT),
        ("public-release scan", [py, "scripts/scan.py", "--public"], KIT),
        ("validate marketplace", ["claude", "plugin", "validate", "."], KIT),
    ]
    checks += [(f"validate {d.name}", ["claude", "plugin", "validate", str(d)], KIT)
               for d in sorted(plugins.iterdir()) if (d / ".claude-plugin" / "plugin.json").is_file()]
    return checks


def doctor(args):
    failed = []
    claude = shutil.which("claude")
    for label, argv, cwd in doctor_checks():
        if argv[0] == "claude":
            if not claude:
                print(f"  SKIP  {label} (claude not on PATH)")
                continue
            argv = [claude] + argv[1:]
        started = time.time()
        result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace")
        ok = result.returncode == 0
        print(f"  {'PASS' if ok else 'FAIL'}  {label} ({time.time() - started:.1f}s)", flush=True)
        if not ok:
            failed.append(label)
            tail = (result.stdout + result.stderr).strip().splitlines()[-15:]
            print("        " + "\n        ".join(tail))
    print(f"[moaa] doctor: {'all checks pass' if not failed else 'failed: ' + ', '.join(failed)}")
    return 1 if failed else 0


def uninstall(args):
    home = claude_home()
    r = Runner(args.dry_run)
    record = read_json(home / MANIFEST, None) or read_json(home / LEGACY_MANIFEST, None)
    if not record:
        raise SystemExit(f"[moaa] no manifest at {home / MANIFEST}; nothing recorded to undo")
    for name in record.get("mcp", []):
        r.run(["claude", "mcp", "remove", name, "--scope", "user"])
    for pid in record.get("plugins", []):
        log(f"uninstalling {pid}")
        r.run(["claude", "plugin", "uninstall", pid, "--scope", "user"])
    for name in record.get("marketplaces", []):
        r.run(["claude", "plugin", "marketplace", "remove", name])
    for name in record.get("skills", []):
        log(f"removing skill {name}")
        target = home / "skills" / name
        if args.dry_run or not target.is_dir():
            continue
        for child in target.iterdir():  # forged council members are user data from the arena; keep them
            if child.name == "forged":
                continue
            shutil.rmtree(child) if child.is_dir() else child.unlink()
        if not any(target.iterdir()):
            target.rmdir()
    for path in [Path(a) for a in record.get("agents", [])]:  # council agents leave with the plugin
        target = home / "agents" / path.name
        if target.is_file() and not args.dry_run:
            target.unlink()
    settings_path = home / "settings.json"
    write_json(settings_path, unmerge_settings(read_json(settings_path, {}), record.get("settings_added", {})), args.dry_run)
    if not args.dry_run:
        (home / MANIFEST).unlink(missing_ok=True)
        (home / LEGACY_MANIFEST).unlink(missing_ok=True)
    log("uninstalled. Arena library data and forged council members (if any) were left in place.")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--with-claude-mem", action="store_true")
    p.add_argument("--full", action="store_true",
                   help="install all 95 plugins and the ansys MCP server (default: the 10-plugin core profile)")
    p.add_argument("--upstream", action="store_true",
                   help="install third-party plugins from their own marketplaces (latest) instead of the pinned moaa catalog")
    p.add_argument("--skip-mcp", action="store_true")
    p.add_argument("--skip-ansys", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--uninstall", action="store_true")
    p.add_argument("--status", action="store_true",
                   help="compare what is installed with this repo (changes nothing; exit 1 if anything is missing or outdated)")
    p.add_argument("--verbose", action="store_true", help="with --status: also list third-party plugins that match")
    p.add_argument("--doctor", action="store_true", help="run every pre-commit check of the release routine")
    a = p.parse_args(argv)
    if a.status:
        return status(a)
    if a.doctor:
        return doctor(a)
    return uninstall(a) if a.uninstall else install(a)


if __name__ == "__main__":
    sys.exit(main())
