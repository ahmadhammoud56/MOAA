#!/usr/bin/env python3
"""MOAA (Mother of All Agents) installer. Standard library only; safe to rerun.

  python scripts/install.py                 install everything (claude-mem off)
  python scripts/install.py --with-claude-mem
  python scripts/install.py --skip-mcp      no rea/ansys MCP servers
  python scripts/install.py --skip-ansys    keep rea, skip the ansys MCP server
  python scripts/install.py --dry-run       print what would run, change nothing
  python scripts/install.py --uninstall     reverse what the kit recorded in its manifest

The Claude config dir is $CLAUDE_CONFIG_DIR or ~/.claude. Existing settings are backed up and merged,
never overwritten: lists are unioned, and env keys and other defaults are only added when absent.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

KIT = Path(__file__).resolve().parents[1]
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
    """council.py allow rules in every spelling the shells produce, so council runs never prompt."""
    script = home / "skills" / "specialist-council" / "council.py"
    rules = [f"Bash({py} ~/.claude/skills/specialist-council/council.py *)" for py in ("python", "python3", "py")]
    rules.append("PowerShell(python ~/.claude/skills/specialist-council/council.py *)")
    posix = script.as_posix()
    rules.append(f'Bash(python "{posix}" *)')
    if WINDOWS:
        native = str(script)
        rules += [f'Bash(python "{native}" *)', f'PowerShell(python "{native}" *)']
        if len(posix) > 1 and posix[1] == ":":  # Git Bash spelling /c/Users/...
            rules.append(f'Bash(python "/{posix[0].lower()}{posix[2:]}" *)')
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
    plugins = [p for p in kit["plugins"] if not p.get("optional") or (args.with_claude_mem and p["optional"] == "claude-mem")]
    needed = {p["id"].split("@")[1] for p in plugins}

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

    before = installed_plugins(home)
    failed = []
    for p in plugins:
        if p["id"] in before:
            continue
        log(f"installing {p['id']}")
        result = r.run(["claude", "plugin", "install", p["id"], "--scope", "user"])
        if result.returncode:
            failed.append(p["id"])
            log(f"  FAILED: {(result.stderr or result.stdout).strip()[-300:]}")
            continue
        if p["id"] not in record["plugins"]:
            record["plugins"].append(p["id"])
        if not p["enabled"]:
            r.run(["claude", "plugin", "disable", p["id"], "--scope", "user"])

    skills_dir = home / "skills"
    for name in kit["skills"]:
        target = skills_dir / name
        if target.exists() and name not in record["skills"]:
            log(f"skill {name} already present and not kit-managed; leaving it")
            continue
        log(f"skill {name}")
        if not args.dry_run:
            shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(KIT / "skills" / name, target, ignore=shutil.ignore_patterns("__pycache__"))
        if name not in record["skills"]:
            record["skills"].append(name)

    log("specialist council (60 agents; forged members are created later by the arena)")
    r.run([sys.executable, str(KIT / "specialist-council" / "council.py"), "install", "--home", str(home)], check=True)
    if "specialist-council" not in record["skills"]:
        record["skills"].append("specialist-council")
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
                                   {p["id"]: p["enabled"] for p in plugins})
    for key, values in added.items():
        prior = record["settings_added"].setdefault(key, [])
        prior += [v for v in values if v not in prior]
    write_json(settings_path, merged, args.dry_run)
    log("settings merged (backup written next to settings.json)")

    if not args.skip_mcp:
        install_mcp(r, kit["mcp"], record, home, skip_ansys=args.skip_ansys, dry=args.dry_run)

    write_json(home / MANIFEST, record, args.dry_run)
    if not args.dry_run:
        (home / LEGACY_MANIFEST).unlink(missing_ok=True)
    check = r.run([sys.executable, str(home / "skills" / "specialist-council" / "council.py"), "check",
                   "--agents", str(home / "agents")])
    log("council check: " + ("ok" if check.returncode == 0 else check.stderr.strip()))
    if failed:
        log("plugins that failed to install (rerun to retry): " + ", ".join(failed))
    log("done. Restart Claude Code to load new plugins.")
    return 1 if failed or check.returncode else 0


def install_mcp(r, mcp, record, home, skip_ansys, dry):
    def add(name, spec):
        if r.run(["claude", "mcp", "get", name]).returncode == 0 and not dry:
            log(f"MCP {name} already configured; leaving it")
            return
        log(f"MCP {name}")
        r.run(["claude", "mcp", "add-json", "--scope", "user", name, json.dumps(spec)], check=True)
        if name not in record["mcp"]:
            record["mcp"].append(name)

    rea = mcp["rea"]
    command, args = (("cmd", ["/c", rea["command"]] + rea["args"]) if WINDOWS else (rea["command"], rea["args"]))
    add("rea", {"type": "stdio", "command": command, "args": args, "env": {}})
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
    council_agents = KIT / "specialist-council" / "agents"
    for path in list(council_agents.glob("council-*.md")) + [Path(a) for a in record.get("agents", [])]:
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
    p.add_argument("--skip-mcp", action="store_true")
    p.add_argument("--skip-ansys", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--uninstall", action="store_true")
    a = p.parse_args(argv)
    return uninstall(a) if a.uninstall else install(a)


if __name__ == "__main__":
    sys.exit(main())
